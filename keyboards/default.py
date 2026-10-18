from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    keyboard = [
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="📦 Заказы")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="💬 Поддержка")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="👑 Админ-панель")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )
