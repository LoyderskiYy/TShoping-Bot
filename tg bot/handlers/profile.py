import logging
from datetime import timezone
from decimal import Decimal, InvalidOperation

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS, MIN_DEPOSIT_RUB, DEFAULT_BTC_WALLET
from database.db import (
    get_user_by_tg_id,
    create_deposit,
    get_deposit_by_id,
    complete_deposit,
    is_tx_hash_used,
    get_setting,
)
from keyboards.default import get_cancel_keyboard, get_main_menu_keyboard
from keyboards.inline import get_profile_keyboard, get_deposit_keyboard
from services.crypto import (
    get_btc_to_rub_rate,
    calculate_btc_amount,
    find_matching_address_tx,
    verify_transaction_by_hash,
)
from states.states import DepositStates

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message) -> None:
    """Отображение профиля пользователя."""
    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Профиль не найден. Пожалуйста, перезапустите бота с помощью /start.")
        return

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 Telegram ID: <code>{user.tg_id}</code>\n"
        f"👤 Имя: <b>{user.full_name or 'Не указано'}</b>\n"
        f"💰 Баланс: <b>{user.balance:.2f} ₽</b>\n\n"
        f"Вы можете пополнить баланс с помощью криптовалюты <b>Bitcoin (BTC)</b>."
    )

    await message.answer(text, reply_markup=get_profile_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "start_deposit")
async def start_deposit_process(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса пополнения."""
    await callback.answer()
    await state.set_state(DepositStates.waiting_for_amount)

    await callback.message.answer(
        f"💳 <b>Пополнение баланса через Bitcoin (BTC)</b>\n\n"
        f"Введите сумму пополнения в рублях (минимально: <b>{MIN_DEPOSIT_RUB:.0f} ₽</b>):\n\n"
        f"<i>Для отмены нажмите кнопку «❌ Отмена» внизу.</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(DepositStates.waiting_for_amount)
async def process_deposit_amount(message: Message, state: FSMContext) -> None:
    """Обработка ввода суммы в рублях и создание счета BTC."""
    text_val = message.text.replace(",", ".").strip()

    try:
        amount_rub = Decimal(text_val)
    except InvalidOperation:
        await message.answer("Пожалуйста, введите корректное число (например: 500 или 1500.50):")
        return

    if amount_rub < Decimal(str(MIN_DEPOSIT_RUB)):
        await message.answer(
            f"Сумма не может быть меньше минимальной ({MIN_DEPOSIT_RUB:.0f} ₽).\n"
            f"Пожалуйста, введите сумму заново:"
        )
        return

    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Ошибка: пользователь не найден. Введите /start.")
        await state.clear()
        return

    await message.answer("⏳ Получаем актуальный курс Bitcoin...", reply_markup=get_main_menu_keyboard(message.from_user.id in ADMIN_IDS))

    btc_rate = await get_btc_to_rub_rate()
    amount_btc = calculate_btc_amount(amount_rub, btc_rate)

    wallet_address = await get_setting("btc_wallet", DEFAULT_BTC_WALLET)
    if not wallet_address:
        wallet_address = DEFAULT_BTC_WALLET

    deposit = await create_deposit(
        user_id=user.id,
        amount_rub=amount_rub,
        amount_btc=amount_btc,
        target_address=wallet_address,
    )

    await state.clear()

    invoice_text = (
        f"🧾 <b>Счет на пополнение №{deposit.id}</b>\n\n"
        f"💵 Сумма к зачислению: <b>{amount_rub:.2f} ₽</b>\n"
        f"₿ Сумма к переводу: <code>{amount_btc:.8f}</code> BTC\n"
        f"📈 Актуальный курс: <b>1 BTC ≈ {btc_rate:,.2f} ₽</b>\n\n"
        f"📥 <b>Кошелек для перевода BTC:</b>\n"
        f"<code>{wallet_address}</code>\n\n"
        f"⚠️ <i>Переведите точно указанную сумму BTC на данный кошелек. "
        f"После отправки нажмите кнопку <b>«🔄 Проверить оплату»</b> ниже или введите TxID вручную.</i>"
    )

    await message.answer(
        invoice_text,
        reply_markup=get_deposit_keyboard(deposit.id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("check_dep:"))
async def check_deposit_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Автоматическая проверка оплаты на блокчейне."""
    deposit_id = int(callback.data.split(":")[1])
    deposit = await get_deposit_by_id(deposit_id)

    if not deposit:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if deposit.status == "completed":
        await callback.answer("Этот счет уже успешно оплачен и зачислен!", show_alert=True)
        return

    await callback.answer("⏳ Проверяем сеть Bitcoin, подождите...")

    # Временная метка создания заявки (с запасом 2 минуты)
    created_dt = deposit.created_at
    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=timezone.utc)
    check_since = int(created_dt.timestamp()) - 120

    # Ищем транзакцию на адресе кошелька
    found, msg, tx_hash = await find_matching_address_tx(
        target_address=deposit.target_address,
        expected_btc=deposit.amount_btc,
        check_since_timestamp=check_since,
        is_hash_used_callback=is_tx_hash_used,
    )

    if found and tx_hash:
        success, comp_msg, new_balance = await complete_deposit(deposit.id, tx_hash=tx_hash)
        if success:
            await callback.message.edit_text(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"Счет №{deposit.id} успешно закрыт.\n"
                f"Зачислено: <b>+{deposit.amount_rub:.2f} ₽</b>\n"
                f"Хэш транзакции: <code>{tx_hash}</code>\n"
                f"Ваш текущий баланс: <b>{new_balance:.2f} ₽</b>\n\n"
                f"Спасибо за пополнение!",
                parse_mode="HTML",
            )

            # Уведомление администраторам
            user = await get_user_by_tg_id(callback.from_user.id)
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"💰 <b>Новое пополнение Bitcoin!</b>\n"
                        f"Пользователь: @{callback.from_user.username or 'без_username'} (ID: {callback.from_user.id})\n"
                        f"Сумма: <b>{deposit.amount_rub:.2f} ₽</b> ({deposit.amount_btc:.8f} BTC)\n"
                        f"TxID: <code>{tx_hash}</code>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")
            return
        else:
            await callback.answer(comp_msg, show_alert=True)
            return

    # Если транзакция пока не найдена
    await callback.message.answer(
        f"🔍 {msg}\n\n"
        f"Если транзакция уже отправлена в сеть, она появится в мемпуле в течение 1-3 минут. "
        f"Вы также можете нажать кнопку «📝 Указать TxID вручную».",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("txid_dep:"))
async def ask_txid_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос ввода TxID вручную."""
    deposit_id = int(callback.data.split(":")[1])
    deposit = await get_deposit_by_id(deposit_id)

    if not deposit or deposit.status == "completed":
        await callback.answer("Заявка недействительна или уже оплачена.", show_alert=True)
        return

    await callback.answer()
    await state.set_state(DepositStates.waiting_for_tx_hash)
    await state.update_data(deposit_id=deposit.id)

    await callback.message.answer(
        f"📝 <b>Ввод хэша транзакции (TxID)</b> для счета №{deposit.id}\n\n"
        f"Пожалуйста, отправьте в чат TxID (хэш транзакции из 64 символов), "
        f"который выдал вам ваш кошелек или биржа после отправки Bitcoin:\n\n"
        f"<i>Для отмены нажмите «❌ Отмена» внизу.</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(DepositStates.waiting_for_tx_hash)
async def process_manual_txid(message: Message, state: FSMContext, bot: Bot) -> None:
    """Проверка введенного вручную TxID."""
    tx_hash = message.text.strip()

    if len(tx_hash) < 50 or " " in tx_hash:
        await message.answer(
            "Неверный формат TxID. Хэш транзакции Bitcoin состоит из 64 шестнадцатеричных символов.\n"
            "Пожалуйста, проверьте и пришлите корректный TxID или нажмите «❌ Отмена»."
        )
        return

    data = await state.get_data()
    deposit_id = data.get("deposit_id")
    deposit = await get_deposit_by_id(deposit_id)

    if not deposit:
        await message.answer("Счет на пополнение не найден.")
        await state.clear()
        return

    if await is_tx_hash_used(tx_hash):
        await message.answer(
            "❌ Этот хэш транзакции уже был использован ранее в системе!",
            reply_markup=get_main_menu_keyboard(message.from_user.id in ADMIN_IDS),
        )
        await state.clear()
        return

    await message.answer("⏳ Проверяем транзакцию в блокчейне Bitcoin...", reply_markup=get_main_menu_keyboard(message.from_user.id in ADMIN_IDS))

    created_dt = deposit.created_at
    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=timezone.utc)
    check_since = int(created_dt.timestamp()) - 120

    valid, v_msg, sats = await verify_transaction_by_hash(
        tx_hash=tx_hash,
        target_address=deposit.target_address,
        expected_btc=deposit.amount_btc,
        check_since_timestamp=check_since,
    )

    if not valid:
        await message.answer(
            f"❌ <b>Проверка не пройдена:</b>\n{v_msg}\n\n"
            f"Убедитесь, что средства отправлены именно на адрес:\n<code>{deposit.target_address}</code>\n"
            f"и в сумме не менее <code>{deposit.amount_btc:.8f}</code> BTC.",
            reply_markup=get_deposit_keyboard(deposit.id),
            parse_mode="HTML",
        )
        await state.clear()
        return

    success, comp_msg, new_balance = await complete_deposit(deposit.id, tx_hash=tx_hash)
    await state.clear()

    if success:
        await message.answer(
            f"🎉 <b>Оплата подтверждена!</b>\n\n"
            f"Счет №{deposit.id} успешно закрыт.\n"
            f"Зачислено: <b>+{deposit.amount_rub:.2f} ₽</b>\n"
            f"TxID: <code>{tx_hash}</code>\n"
            f"Ваш текущий баланс: <b>{new_balance:.2f} ₽</b>",
            reply_markup=get_main_menu_keyboard(message.from_user.id in ADMIN_IDS),
            parse_mode="HTML",
        )

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💰 <b>Пополнение Bitcoin через TxID!</b>\n"
                    f"Пользователь: @{message.from_user.username or 'без_username'} (ID: {message.from_user.id})\n"
                    f"Сумма: <b>{deposit.amount_rub:.2f} ₽</b> ({deposit.amount_btc:.8f} BTC)\n"
                    f"TxID: <code>{tx_hash}</code>",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")
    else:
        await message.answer(f"Ошибка зачисления: {comp_msg}")


@router.callback_query(F.data.startswith("cancel_dep:"))
async def cancel_deposit_callback(callback: CallbackQuery) -> None:
    """Отмена счета на пополнение."""
    deposit_id = int(callback.data.split(":")[1])
    await callback.answer("Счет отменен")
    await callback.message.edit_text(f"❌ Счет на пополнение №{deposit_id} был отменен.")
