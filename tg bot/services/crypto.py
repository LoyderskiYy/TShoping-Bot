import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, Dict, Any, List

import aiohttp

logger = logging.getLogger(__name__)

# Кеш курса BTC/RUB: (rate, timestamp)
_rate_cache: Optional[Tuple[Decimal, float]] = None
CACHE_TTL_SECONDS = 60


async def get_btc_to_rub_rate() -> Decimal:
    """Получает актуальный курс 1 BTC в рублях с кешированием на 60 сек."""
    global _rate_cache
    now = time.time()

    if _rate_cache is not None:
        cached_rate, timestamp = _rate_cache
        if now - timestamp < CACHE_TTL_SECONDS:
            return cached_rate

    rate: Optional[Decimal] = None

    # Попытка 1: Blockchain.info ticker (очень надежный и быстрый)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://blockchain.info/ticker",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "RUB" in data and "last" in data["RUB"]:
                        rate = Decimal(str(data["RUB"]["last"]))
    except Exception as e:
        logger.warning(f"Ошибка получения курса с blockchain.info: {e}")

    # Попытка 2: CoinGecko API (резервный)
    if rate is None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=rub",
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "bitcoin" in data and "rub" in data["bitcoin"]:
                            rate = Decimal(str(data["bitcoin"]["rub"]))
        except Exception as e:
            logger.warning(f"Ошибка получения курса с CoinGecko: {e}")

    # Попытка 3: Binance API USDT/RUB & BTC/USDT (резервный)
    if rate is None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        btc_usdt = Decimal(str(data["price"]))
                        # Примерный кросс-курс рубля ~95-100 при отказе всех провайдеров
                        rate = btc_usdt * Decimal("96.50")
        except Exception as e:
            logger.warning(f"Ошибка получения курса с Binance: {e}")

    if rate is None:
        # Если все внешние API недоступны, берем последнее кешированное или консервативное значение
        if _rate_cache is not None:
            return _rate_cache[0]
        # Резервный курс по умолчанию
        rate = Decimal("6500000.00")

    _rate_cache = (rate, now)
    return rate


def calculate_btc_amount(rub_amount: Decimal, btc_rate: Decimal) -> Decimal:
    """Вычисляет сумму в BTC с точностью до 8 знаков (в сатоши)."""
    if btc_rate <= 0:
        return Decimal("0.00000000")
    btc_val = rub_amount / btc_rate
    return btc_val.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def btc_to_satoshis(btc: Decimal) -> int:
    return int((btc * Decimal("100000000")).to_integral_value(rounding=ROUND_HALF_UP))


async def verify_transaction_by_hash(
    tx_hash: str,
    target_address: str,
    expected_btc: Decimal,
    check_since_timestamp: Optional[int] = None,
) -> Tuple[bool, str, Optional[int]]:
    """
    Проверяет конкретную транзакцию по её TxID через mempool.space и blockstream.info.
    Возвращает: (успех, сообщение, полученные сатоши).
    """
    expected_sats = btc_to_satoshis(expected_btc)
    tx_hash = tx_hash.strip().lower()

    endpoints = [
        f"https://mempool.space/api/tx/{tx_hash}",
        f"https://blockstream.info/api/tx/{tx_hash}",
    ]

    tx_data: Optional[Dict[str, Any]] = None

    for url in endpoints:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        tx_data = await resp.json()
                        break
        except Exception as e:
            logger.warning(f"Не удалось проверить tx {tx_hash} через {url}: {e}")

    if not tx_data:
        return False, "Транзакция не найдена в блокчейне. Проверьте правильность TxID или подождите несколько секунд.", None

    # Проверяем время транзакции, чтобы нельзя было использовать чужие старые транзакции
    status = tx_data.get("status", {})
    if status.get("confirmed") and check_since_timestamp:
        block_time = status.get("block_time")
        if block_time and block_time < check_since_timestamp:
            return False, "Эта транзакция была подтверждена в сети до создания вашей заявки на пополнение.", None

    # Проверяем выходы транзакции (vout)
    received_sats = 0
    vout_list = tx_data.get("vout", [])
    for vout in vout_list:
        scriptpubkey_address = vout.get("scriptpubkey_address")
        if scriptpubkey_address and scriptpubkey_address.lower() == target_address.lower():
            received_sats += vout.get("value", 0)

    if received_sats <= 0:
        return False, f"В транзакции нет перевода на кошелек магазина ({target_address}).", None

    # Допускаем погрешность в несколько сатоши из-за округлений (например, до 300 сатоши или 1%)
    tolerance_sats = max(300, int(expected_sats * 0.01))
    if received_sats < (expected_sats - tolerance_sats):
        received_btc = Decimal(received_sats) / Decimal("100000000")
        return False, f"Сумма в транзакции ({received_btc:.8f} BTC) меньше ожидаемой ({expected_btc:.8f} BTC).", received_sats

    return True, "Транзакция подтверждена!", received_sats


async def find_matching_address_tx(
    target_address: str,
    expected_btc: Decimal,
    check_since_timestamp: Optional[int] = None,
    is_hash_used_callback = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Ищет недавнюю транзакцию на адрес target_address с ожидаемой суммой BTC.
    Использует mempool.space и blockstream.info.
    """
    expected_sats = btc_to_satoshis(expected_btc)
    tolerance_sats = max(300, int(expected_sats * 0.01))

    endpoints = [
        f"https://mempool.space/api/address/{target_address}/txs",
        f"https://blockstream.info/api/address/{target_address}/txs",
    ]

    txs: Optional[List[Dict[str, Any]]] = None

    for url in endpoints:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        txs = await resp.json()
                        break
        except Exception as e:
            logger.warning(f"Ошибка получения списка транзакций с {url}: {e}")

    if txs is None:
        return False, "Сервис блокчейна временно недоступен. Вы можете ввести TxID вручную.", None

    for tx in txs:
        tx_hash = tx.get("txid")
        if not tx_hash:
            continue

        # Проверяем статус и время транзакции (отсекаем старые транзакции до создания счета)
        status = tx.get("status", {})
        if status.get("confirmed") and check_since_timestamp:
            block_time = status.get("block_time")
            if block_time and block_time < check_since_timestamp:
                continue

        # Проверяем, не использован ли уже этот хэш в БД
        if is_hash_used_callback and await is_hash_used_callback(tx_hash):
            continue

        # Проверяем выходы
        received_sats = 0
        for vout in tx.get("vout", []):
            if vout.get("scriptpubkey_address", "").lower() == target_address.lower():
                received_sats += vout.get("value", 0)

        # Сравниваем сумму: строго в пределах погрешности округления
        if abs(received_sats - expected_sats) <= tolerance_sats:
            return True, "Транзакция успешно найдена в сети Bitcoin!", tx_hash

    return False, "Транзакция на указанную сумму пока не обнаружена. Пожалуйста, подождите 1-3 минуты после отправки или укажите TxID вручную.", None
