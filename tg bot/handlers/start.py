from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_IDS
from database.db import get_or_create_user
from keyboards.default import get_main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start."""
    await state.clear()

    user = await get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    is_admin = message.from_user.id in ADMIN_IDS

    welcome_text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"Добро пожаловать в наш магазин!\n\n"
        f"🛍 <b>Каталог</b> - просмотр ассортимента товаров\n"
        f"📦 <b>Заказы</b> - ваши оплаченные покупки\n"
        f"👤 <b>Мой профиль</b> - баланс и пополнение через Bitcoin\n"
        f"💬 <b>Поддержка</b> - связь с администрацией по любым вопросам\n\n"
        f"Используйте кнопки меню ниже для навигации 👇"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(is_admin=is_admin),
        parse_mode="HTML",
    )


@router.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext) -> None:
    """Сброс текущего состояния и возврат в главное меню."""
    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS

    await message.answer(
        "Действие отменено. Вы вернулись в главное меню.",
        reply_markup=get_main_menu_keyboard(is_admin=is_admin),
    )
