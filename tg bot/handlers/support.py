import logging
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS
from database.db import get_user_by_tg_id, create_ticket, get_ticket_by_id
from keyboards.default import get_cancel_keyboard, get_main_menu_keyboard
from keyboards.inline import get_ticket_admin_keyboard
from states.states import SupportStates, AdminStates

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "💬 Поддержка")
async def start_support_dialog(message: Message, state: FSMContext) -> None:
    """Вход в режим обращения в техподдержку."""
    await state.set_state(SupportStates.waiting_for_question)
    await message.answer(
        "💬 <b>Служба поддержки клиентов</b>\n\n"
        "Опишите ваш вопрос или возникшую проблему одним сообщением.\n"
        "Администратор свяжется с вами и пришлет ответ в этот чат!\n\n"
        "<i>Для отмены нажмите кнопку «❌ Отмена» ниже.</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(SupportStates.waiting_for_question)
async def process_support_question(message: Message, state: FSMContext, bot: Bot) -> None:
    """Прием вопроса пользователя и отправка администраторам."""
    question_text = message.text.strip()
    user = await get_user_by_tg_id(message.from_user.id)

    if not user:
        await message.answer("Ошибка: пользователь не найден. Введите /start.")
        await state.clear()
        return

    ticket = await create_ticket(
        user_id=user.id,
        user_tg_id=message.from_user.id,
        question=question_text,
    )

    await state.clear()

    await message.answer(
        f"✅ <b>Обращение №{ticket.id} успешно отправлено!</b>\n\n"
        f"Администрация уже получила ваш запрос и ответит вам прямо в этом боте в ближайшее время.",
        reply_markup=get_main_menu_keyboard(message.from_user.id in ADMIN_IDS),
        parse_mode="HTML",
    )

    # Уведомление администраторам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📩 <b>Новое обращение в поддержку!</b>\n\n"
                f"Тикет: <b>#{ticket.id}</b>\n"
                f"От: @{message.from_user.username or 'без_username'} (ID: <code>{message.from_user.id}</code>)\n"
                f"Имя: {message.from_user.full_name}\n\n"
                f"❓ <b>Вопрос:</b>\n{question_text}",
                reply_markup=get_ticket_admin_keyboard(ticket.id),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить тикет админу {admin_id}: {e}")
