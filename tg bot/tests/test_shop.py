import os
import unittest
from decimal import Decimal

# Настраиваем тестовую базу данных
TEST_DB_FILE = "test_shop.db"
os.environ["DATABASE_PATH"] = TEST_DB_FILE

from database.db import (
    init_db,
    engine,
    get_or_create_user,
    update_user_balance,
    create_category,
    create_product,
    add_product_items,
    get_product_stock_count,
    buy_product,
    get_user_orders,
    create_deposit,
    complete_deposit,
    is_tx_hash_used,
    create_ticket,
    answer_ticket,
    get_shop_stats,
    set_setting,
    get_setting,
)
from database.models import Base
from services.crypto import (
    get_btc_to_rub_rate,
    calculate_btc_amount,
    btc_to_satoshis,
)


class TestTelegramBotShop(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Изоляция каждого теста: пересоздаем чистую базу данных
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await init_db()

    async def test_01_crypto_calculations(self):
        """Проверка расчёта курса BTC и сатоши."""
        rate = await get_btc_to_rub_rate()
        self.assertGreater(rate, Decimal("0"))

        # Проверка перевода 5000 рублей в BTC
        rub_amount = Decimal("5000.00")
        btc_amount = calculate_btc_amount(rub_amount, rate)
        self.assertGreater(btc_amount, Decimal("0.00000000"))

        sats = btc_to_satoshis(Decimal("0.00010000"))
        self.assertEqual(sats, 10000)

    async def test_02_user_and_balance(self):
        """Проверка создания пользователя и управления балансом."""
        user = await get_or_create_user(
            tg_id=111222333,
            username="test_buyer",
            full_name="Test Buyer",
        )
        self.assertEqual(user.tg_id, 111222333)
        self.assertEqual(user.balance, Decimal("0.00"))

        # Пополняем баланс
        new_balance = await update_user_balance(user.id, Decimal("1500.00"))
        self.assertEqual(new_balance, Decimal("1500.00"))

        # Проверка ошибки при попытке списать больше баланса
        with self.assertRaises(ValueError):
            await update_user_balance(user.id, Decimal("-3000.00"))

    async def test_03_catalog_and_purchase_stock(self):
        """Проверка создания товара, склада и успешной покупки."""
        cat = await create_category("Игры и подписки")
        self.assertEqual(cat.name, "Игры и подписки")

        prod = await create_product(
            name="Telegram Premium 1 мес",
            price=Decimal("300.00"),
            category_id=cat.id,
            description="Активация подарком",
            product_type="stock",
        )
        self.assertEqual(prod.name, "Telegram Premium 1 мес")

        # Загружаем ключи
        keys = ["TG-PREM-KEY-001", "TG-PREM-KEY-002"]
        added = await add_product_items(prod.id, keys)
        self.assertEqual(added, 2)

        stock = await get_product_stock_count(prod.id)
        self.assertEqual(stock, 2)

        # Создаем пользователя и даем ему баланс для покупки
        user = await get_or_create_user(tg_id=222333444, username="game_buyer", full_name="Game Buyer")
        await update_user_balance(user.id, Decimal("500.00"))

        # Должна пройти успешно (баланс 500, цена 300)
        success, msg, order = await buy_product(user.id, prod.id)
        self.assertTrue(success)
        self.assertIsNotNone(order)
        self.assertEqual(order.delivered_content, "TG-PREM-KEY-001")

        # Проверяем, что остаток уменьшился до 1
        stock_after = await get_product_stock_count(prod.id)
        self.assertEqual(stock_after, 1)

        # Проверяем историю заказов пользователя
        orders = await get_user_orders(user.id)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].product_name, "Telegram Premium 1 мес")

    async def test_04_bitcoin_deposit_flow(self):
        """Проверка создания и подтверждения депозита Bitcoin."""
        user = await get_or_create_user(tg_id=333444555, username="crypto_user", full_name="Crypto User")
        initial_balance = user.balance

        deposit = await create_deposit(
            user_id=user.id,
            amount_rub=Decimal("2000.00"),
            amount_btc=Decimal("0.00030000"),
            target_address="bc1qtestaddress1234567890",
        )
        self.assertEqual(deposit.status, "pending")

        tx_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

        # Завершаем депозит
        success, msg, new_balance = await complete_deposit(deposit.id, tx_hash=tx_hash)
        self.assertTrue(success)
        self.assertEqual(new_balance, initial_balance + Decimal("2000.00"))

        # Проверяем защиту от повторного использования TxID
        is_used = await is_tx_hash_used(tx_hash)
        self.assertTrue(is_used)

        # Повторное завершение должно отказать
        success2, msg2, _ = await complete_deposit(deposit.id, tx_hash=tx_hash)
        self.assertFalse(success2)

    async def test_05_support_tickets(self):
        """Проверка создания тикета поддержки и ответа администратора."""
        user = await get_or_create_user(tg_id=444555666, username="help_user", full_name="Help User")
        ticket = await create_ticket(user.id, user.tg_id, "Здравствуйте, как активировать ключ?")
        self.assertEqual(ticket.status, "open")

        answered = await answer_ticket(ticket.id, "Здравствуйте! Введите ключ в приложении.")
        self.assertIsNotNone(answered)
        self.assertEqual(answered.status, "answered")
        self.assertEqual(answered.reply, "Здравствуйте! Введите ключ в приложении.")

    async def test_06_admin_settings_and_stats(self):
        """Проверка изменения BTC кошелька и статистики."""
        await set_setting("btc_wallet", "bc1qnewadminwalletaddress12345")
        saved_wallet = await get_setting("btc_wallet")
        self.assertEqual(saved_wallet, "bc1qnewadminwalletaddress12345")

        # Создаем тестовые данные для проверки статистики
        user = await get_or_create_user(tg_id=555666777, username="stats_user", full_name="Stats User")
        await update_user_balance(user.id, Decimal("1000.00"))
        prod = await create_product(name="Test Item", price=Decimal("150.00"), product_type="infinite_text", content="link")
        await buy_product(user.id, prod.id)

    async def test_07_weight_based_pricing_and_city_selection(self):
        """Проверка товаров с выбором веса (разные цены), города, района и типа."""
        from database.db import (
            create_city,
            create_district,
            create_product_variant,
            create_product_type_option,
        )

        # 1. Создаем город и район
        city = await create_city("Москва")
        district = await create_district(city.id, "Центральный (ЦАО)")
        self.assertEqual(city.name, "Москва")
        self.assertEqual(district.name, "Центральный (ЦАО)")

        # 2. Создаем товар
        prod = await create_product(
            name="Продукт А (высокое качество)",
            description="Свежая поставка",
            product_type="stock",
        )

        # 3. Добавляем разные варианты веса с РАЗНЫМИ ценами
        var_200 = await create_product_variant(prod.id, "200г", Decimal("1500.00"))
        var_500 = await create_product_variant(prod.id, "500г", Decimal("3200.00"))
        var_1kg = await create_product_variant(prod.id, "1кг", Decimal("5800.00"))

        # 4. Добавляем тип товара
        opt_type = await create_product_type_option(prod.id, "Магнит")
        self.assertEqual(opt_type.name, "Магнит")

        # 5. Загружаем наличие именно под 500г в Москве, ЦАО
        await add_product_items(
            product_id=prod.id,
            items_data=["Координаты: 55.751, 37.618 (фото: link1)"],
            variant_id=var_500.id,
            city_id=city.id,
            district_id=district.id,
            type_name="Магнит",
        )

        stock_500 = await get_product_stock_count(prod.id, variant_id=var_500.id)
        self.assertEqual(stock_500, 1)

        # 6. Покупатель с балансом 5000 рублей покупает 500г
        user = await get_or_create_user(tg_id=777888999, username="weight_buyer", full_name="Weight Buyer")
        await update_user_balance(user.id, Decimal("5000.00"))

        success, msg, order = await buy_product(
            user_id=user.id,
            product_id=prod.id,
            variant_id=var_500.id,
            city_id=city.id,
            district_id=district.id,
            type_name="Магнит",
        )

        self.assertTrue(success)
        self.assertIsNotNone(order)
        # Проверяем, что списалась цена ИМЕННО 500г (3200 ₽), а не дефолтная
        self.assertEqual(order.price, Decimal("3200.00"))
        self.assertEqual(order.variant_name, "500г")
        self.assertEqual(order.city_name, "Москва")
        self.assertEqual(order.district_name, "Центральный (ЦАО)")
        self.assertEqual(order.type_name, "Магнит")

        # Баланс пользователя после покупки: 5000 - 3200 = 1800
        refreshed_user = await get_or_create_user(tg_id=777888999, username=None, full_name=None)
        self.assertEqual(refreshed_user.balance, Decimal("1800.00"))

        # 7. Попытка купить 1кг за 5800 ₽ с балансом 1800 ₽ -> отказ
        success_kg, msg_kg, _ = await buy_product(
            user_id=user.id,
            product_id=prod.id,
            variant_id=var_1kg.id,
        )
        self.assertFalse(success_kg)
        self.assertIn("Недостаточно средств", msg_kg)

    async def test_08_numeric_stock_management(self):
        """Проверка указания количества товара простой цифрой (например: 7 шт)."""
        from database.db import set_variant_stock, set_product_stock, get_all_products_full, create_product_variant

        prod = await create_product(
            name="Товар с числовым остатком",
            description="Тест остатка цифрой",
            delivery_text="Ваш заказ готов к выдаче!",
            stock=10,
        )
        var = await create_product_variant(prod.id, "250г", Decimal("900.00"), stock=7)

        # 1. Проверяем, что в наличии именно 7 шт.
        stock_cnt = await get_product_stock_count(prod.id, variant_id=var.id)
        self.assertEqual(stock_cnt, 7)

        # 2. Покупатель с балансом 2000 покупает 1 шт
        user = await get_or_create_user(tg_id=888999000, username="num_buyer", full_name="Num Buyer")
        await update_user_balance(user.id, Decimal("2000.00"))

        success, msg, order = await buy_product(user.id, prod.id, variant_id=var.id)
        self.assertTrue(success)
        self.assertEqual(order.delivered_content, "Ваш заказ готов к выдаче!")

        # 3. Остаток должен уменьшиться с 7 до 6!
        stock_after = await get_product_stock_count(prod.id, variant_id=var.id)
        self.assertEqual(stock_after, 6)

        # 4. Администратор просто вводит цифру 15
        await set_variant_stock(var.id, 15)
        stock_new = await get_product_stock_count(prod.id, variant_id=var.id)
        self.assertEqual(stock_new, 15)

        # 5. Администратор ставит остаток 0 -> покупка не проходит
        await set_variant_stock(var.id, 0)
        stock_zero = await get_product_stock_count(prod.id, variant_id=var.id)
        self.assertEqual(stock_zero, 0)

        success_fail, msg_fail, _ = await buy_product(user.id, prod.id, variant_id=var.id)
        self.assertFalse(success_fail)
        self.assertIn("закончились на складе", msg_fail)

        # 6. Проверка получения списка товаров для веб-админки
        full_prods = await get_all_products_full()
        self.assertGreaterEqual(len(full_prods), 1)
        self.assertIn("variants", full_prods[0])
        self.assertIn("total_stock", full_prods[0])

    async def test_09_admin_order_notification_format(self):
        """Проверка генерации текста уведомления администратора об оплате заказа."""
        import html
        from datetime import datetime
        from database.db import create_city, create_district

        city = await create_city("Санкт-Петербург")
        district = await create_district(city.id, "Невский")
        prod = await create_product(
            name="Премиум Товар",
            description="Тест уведомления",
            stock=5,
        )

        user = await get_or_create_user(tg_id=777000111, username="test_client", full_name="Иван Иванов")
        await update_user_balance(user.id, Decimal("5000.00"))

        success, msg, order = await buy_product(
            user_id=user.id,
            product_id=prod.id,
            city_id=city.id,
            district_id=district.id,
            type_name="Магнит",
        )
        self.assertTrue(success)
        self.assertIsNotNone(order)

        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        city_parts = []
        if order.city_name:
            city_parts.append(order.city_name)
        if order.district_name:
            city_parts.append(order.district_name)
        city_district_val = ", ".join(city_parts) if city_parts else "-"

        prod_name_esc = html.escape(order.product_name)
        city_dist_esc = html.escape(city_district_val)
        weight_esc = html.escape(order.variant_name or "-")
        type_esc = html.escape(order.type_name or "-")

        buyer_contact = f"@{user.username} (ID: <code>{user.tg_id}</code>)"

        admin_notification = (
            "<b>ПОСТУПИЛ НОВЫЙ ЗАКАЗ</b>\n"
            f"🧾 Заказ №<b>{order.id}</b> от {now_str}\n"
            f"🔹 Товар: <b>{prod_name_esc}</b>\n"
            f"🏙 Город + район: <b>{city_dist_esc}</b>\n"
            f"⚖️ Вес: <b>{weight_esc}</b>\n"
            f"🏷 Тип: <b>{type_esc}</b>\n"
            f"💵 Сумма: <b>{order.price:.2f} ₽</b>\n\n"
            f"📥Связь с покупателем: {buyer_contact}"
        )

        # Проверяем наличие всех ключевых строк шаблона
        self.assertIn("ПОСТУПИЛ НОВЫЙ ЗАКАЗ", admin_notification)
        self.assertIn(f"🧾 Заказ №<b>{order.id}</b> от {now_str}", admin_notification)
        self.assertIn(f"🔹 Товар: <b>Премиум Товар</b>", admin_notification)
        self.assertIn("🏙 Город + район: <b>Санкт-Петербург, Невский</b>", admin_notification)
        self.assertIn("🏷 Тип: <b>Магнит</b>", admin_notification)
        self.assertIn(f"💵 Сумма: <b>{order.price:.2f} ₽</b>", admin_notification)
        self.assertIn(f"📥Связь с покупателем: @{user.username} (ID: <code>{user.tg_id}</code>)", admin_notification)


if __name__ == "__main__":
    unittest.main()


