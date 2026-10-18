from aiogram import Router, F
from aiogram.types import Message

from database.db import get_user_by_tg_id, get_user_orders

router = Router()


@router.message(F.text == "📦 Заказы")
async def show_orders(message: Message) -> None:
    """Отображение списка всех оплаченных заказов пользователя."""
    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден. Введите /start.")
        return

    orders = await get_user_orders(user.id)

    if not orders:
        await message.answer(
            "📦 <b>Ваши заказы</b>\n\n"
            "У вас пока нет оплаченных заказов.\n"
            "Перейдите в раздел 🛍 <b>Каталог</b>, чтобы совершить покупку!",
            parse_mode="HTML",
        )
        return

    text_parts = ["📦 <b>Ваши оплаченные заказы:</b>\n"]

    for order in orders[:15]:  # Показываем последние 15 заказов
        date_str = order.created_at.strftime("%d.%m.%Y %H:%M")
        meta = []
        if order.city_name:
            dist = f" ({order.district_name})" if order.district_name else ""
            meta.append(f"🏙 Город: {order.city_name}{dist}")
        if order.variant_name:
            meta.append(f"⚖️ Вес: {order.variant_name}")
        if order.type_name:
            meta.append(f"🏷 Тип: {order.type_name}")

        meta_str = ("\n" + "\n".join(meta)) if meta else ""

        text_parts.append(
            f"🧾 <b>Заказ №{order.id}</b> от {date_str}\n"
            f"🔹 Товар: <b>{order.product_name}</b>"
            f"{meta_str}\n"
            f"💵 Сумма: <b>{order.price:.2f} ₽</b>\n"
            f"🎁 <b>Полученный товар:</b>\n"
            f"<code>{order.delivered_content}</code>\n"
            f"────────────────────"
        )

    if len(orders) > 15:
        text_parts.append(f"<i>Показаны последние 15 заказов из {len(orders)}.</i>")

    await message.answer("\n\n".join(text_parts), parse_mode="HTML")

