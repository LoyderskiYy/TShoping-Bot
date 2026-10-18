import html
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Tuple, Any, Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS
from database.db import (
    get_user_by_tg_id,
    get_active_categories,
    get_products_by_category,
    get_product_by_id,
    get_product_variants,
    get_variant_by_id,
    get_product_type_options,
    get_all_cities,
    get_city_by_id,
    get_districts_by_city,
    get_district_by_id,
    get_product_stock_count,
    buy_product,
)
from keyboards.inline import (
    get_categories_keyboard,
    get_products_keyboard,
    get_product_card_keyboard,
    get_cities_selection_keyboard,
    get_districts_selection_keyboard,
    get_weights_selection_keyboard,
    get_types_selection_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()

# Память выбора пользователя: (user_id, product_id) -> {variant_id, city_id, district_id, type_id}
user_selection: Dict[Tuple[int, int], Dict[str, Any]] = {}


async def render_product_card(user_id: int, product_id: int) -> Tuple[str, Any]:
    """Формирует текст и клавиатуру карточки товара с учетом текущих выбранных параметров."""
    product = await get_product_by_id(product_id)
    if not product:
        return "Товар не найден", None

    variants = await get_product_variants(product_id)
    types = await get_product_type_options(product_id)
    cities = await get_all_cities()

    sel_key = (user_id, product_id)
    current_sel = user_selection.get(sel_key, {})

    # Инициализация дефолтных значений
    if "variant_id" not in current_sel and variants:
        current_sel["variant_id"] = variants[0].id
    if "city_id" not in current_sel and cities:
        current_sel["city_id"] = cities[0].id
        current_sel["district_id"] = 0
    if "type_id" not in current_sel and types:
        current_sel["type_id"] = types[0].id

    user_selection[sel_key] = current_sel

    # Получаем детали выбранных опций
    variant_obj = None
    price = product.price
    weight_name = "Стандарт"
    if current_sel.get("variant_id"):
        variant_obj = await get_variant_by_id(current_sel["variant_id"])
        if variant_obj:
            price = variant_obj.price
            weight_name = variant_obj.weight_name

    city_name = "Не выбран"
    if current_sel.get("city_id"):
        city_obj = await get_city_by_id(current_sel["city_id"])
        if city_obj:
            city_name = city_obj.name

    district_name = "Все районы"
    if current_sel.get("district_id") and current_sel["district_id"] != 0:
        dist_obj = await get_district_by_id(current_sel["district_id"])
        if dist_obj:
            district_name = dist_obj.name

    type_name = "Не указан"
    if current_sel.get("type_id"):
        for t in types:
            if t.id == current_sel["type_id"]:
                type_name = t.name
                break

    # Считаем остаток
    stock = await get_product_stock_count(
        product_id=product.id,
        variant_id=current_sel.get("variant_id"),
        city_id=current_sel.get("city_id"),
        district_id=current_sel.get("district_id") if current_sel.get("district_id") != 0 else None,
        type_name=type_name if type_name != "Не указан" else None,
    )
    stock_text = "Много" if product.product_type == "infinite_text" else f"{stock} шт."
    in_stock = (stock > 0)

    desc_text = f"\n📝 <i>{product.description}</i>\n" if product.description else ""

    text = (
        f"📦 <b>{product.name}</b>\n"
        f"{desc_text}\n"
        f"🏙 <b>Город:</b> {city_name}\n"
        f"📍 <b>Район:</b> {district_name}\n"
        f"⚖️ <b>Вес:</b> <b>{weight_name}</b>\n"
        f"🏷 <b>Тип:</b> {type_name}\n\n"
        f"💵 <b>Цена:</b> <b>{price:.2f} ₽</b>\n"
        f"📊 <b>В наличии:</b> <b>{stock_text}</b>"
    )

    kb = get_product_card_keyboard(
        product_id=product.id,
        price=float(price),
        category_id=product.category_id,
        in_stock=in_stock,
        has_cities=bool(cities),
        has_variants=bool(variants),
        has_types=bool(types),
    )
    return text, kb


@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: Message) -> None:
    """Отображение категорий каталога."""
    categories = await get_active_categories()
    uncategorized = await get_products_by_category(None)

    if not categories and not uncategorized:
        await message.answer(
            "🛍 <b>Каталог товаров</b>\n\n"
            "В данный момент каталог пуст. Администратор скоро добавит товары!",
            parse_mode="HTML",
        )
        return

    if not categories and uncategorized:
        await message.answer(
            "🛍 <b>Выберите товар:</b>",
            reply_markup=get_products_keyboard(uncategorized),
            parse_mode="HTML",
        )
        return

    await message.answer(
        "🛍 <b>Каталог товаров</b>\n\n"
        "Выберите интересующую вас категорию:",
        reply_markup=get_categories_keyboard(categories, has_uncategorized=bool(uncategorized)),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "back_categories")
async def back_to_categories_callback(callback: CallbackQuery) -> None:
    """Возврат к списку категорий."""
    categories = await get_active_categories()
    uncategorized = await get_products_by_category(None)

    await callback.message.edit_text(
        "🛍 <b>Каталог товаров</b>\n\n"
        "Выберите интересующую вас категорию:",
        reply_markup=get_categories_keyboard(categories, has_uncategorized=bool(uncategorized)),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cat:"))
async def show_category_products(callback: CallbackQuery) -> None:
    """Отображение товаров в выбранной категории."""
    cat_id_raw = callback.data.split(":")[1]
    cat_id = int(cat_id_raw) if cat_id_raw != "0" else None

    products = await get_products_by_category(cat_id)
    if not products:
        await callback.answer("В этой категории пока нет товаров.", show_alert=True)
        return

    await callback.message.edit_text(
        "📦 <b>Выберите товар для покупки:</b>",
        reply_markup=get_products_keyboard(products, category_id=cat_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("prod:"))
async def show_product_card(callback: CallbackQuery) -> None:
    """Карточка товара с кнопками выбора параметров."""
    product_id = int(callback.data.split(":")[1])
    text, kb = await render_product_card(callback.from_user.id, product_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ==================== ВЫБОР ГОРОДА И РАЙОНА ====================

@router.callback_query(F.data.startswith("pick_city:"))
async def pick_city_menu(callback: CallbackQuery) -> None:
    """Открытие списка городов для выбора."""
    product_id = int(callback.data.split(":")[1])
    cities = await get_all_cities()

    if not cities:
        await callback.answer("Список городов пока не настроен администратором.", show_alert=True)
        return

    await callback.message.edit_text(
        "🏙 <b>Выберите ваш город:</b>",
        reply_markup=get_cities_selection_keyboard(product_id, cities),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("sel_city:"))
async def select_city_action(callback: CallbackQuery) -> None:
    """Пользователь выбрал город -> предлагаем выбрать район."""
    parts = callback.data.split(":")
    product_id = int(parts[1])
    city_id = int(parts[2])

    sel_key = (callback.from_user.id, product_id)
    if sel_key not in user_selection:
        user_selection[sel_key] = {}
    user_selection[sel_key]["city_id"] = city_id
    user_selection[sel_key]["district_id"] = 0

    districts = await get_districts_by_city(city_id)
    if districts:
        await callback.message.edit_text(
            "📍 <b>Выберите район:</b>",
            reply_markup=get_districts_selection_keyboard(product_id, city_id, districts),
            parse_mode="HTML",
        )
    else:
        # Если районов нет, возвращаемся в карточку товара
        text, kb = await render_product_card(callback.from_user.id, product_id)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("sel_dist:"))
async def select_district_action(callback: CallbackQuery) -> None:
    """Пользователь выбрал район -> возвращаемся в карточку товара."""
    parts = callback.data.split(":")
    product_id = int(parts[1])
    district_id = int(parts[3])

    sel_key = (callback.from_user.id, product_id)
    if sel_key not in user_selection:
        user_selection[sel_key] = {}
    user_selection[sel_key]["district_id"] = district_id

    text, kb = await render_product_card(callback.from_user.id, product_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ==================== ВЫБОР ВЕСА / ФАСОВКИ ====================

@router.callback_query(F.data.startswith("pick_weight:"))
async def pick_weight_menu(callback: CallbackQuery) -> None:
    """Открытие списка весов с ценами."""
    product_id = int(callback.data.split(":")[1])
    variants = await get_product_variants(product_id)

    if not variants:
        await callback.answer("У этого товара нет других вариантов веса.", show_alert=True)
        return

    await callback.message.edit_text(
        "⚖️ <b>Выберите вес / фасовку товара:</b>\n"
        "<i>Цена будет автоматически пересчитана под выбранный вес.</i>",
        reply_markup=get_weights_selection_keyboard(product_id, variants),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("sel_weight:"))
async def select_weight_action(callback: CallbackQuery) -> None:
    """Пользователь выбрал вес -> пересчитываем цену и обновляем карточку."""
    parts = callback.data.split(":")
    product_id = int(parts[1])
    variant_id = int(parts[2])

    sel_key = (callback.from_user.id, product_id)
    if sel_key not in user_selection:
        user_selection[sel_key] = {}
    user_selection[sel_key]["variant_id"] = variant_id

    text, kb = await render_product_card(callback.from_user.id, product_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ==================== ВЫБОР ТИПА ТОВАРА ====================

@router.callback_query(F.data.startswith("pick_type:"))
async def pick_type_menu(callback: CallbackQuery) -> None:
    """Открытие списка типов (Магнит, Тайник, Доставка)."""
    product_id = int(callback.data.split(":")[1])
    types = await get_product_type_options(product_id)

    if not types:
        await callback.answer("У этого товара нет дополнительных типов.", show_alert=True)
        return

    await callback.message.edit_text(
        "🏷 <b>Выберите тип товара / упаковки:</b>",
        reply_markup=get_types_selection_keyboard(product_id, types),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("sel_type:"))
async def select_type_action(callback: CallbackQuery) -> None:
    """Пользователь выбрал тип -> обновляем карточку."""
    parts = callback.data.split(":")
    product_id = int(parts[1])
    type_id = int(parts[2])

    sel_key = (callback.from_user.id, product_id)
    if sel_key not in user_selection:
        user_selection[sel_key] = {}
    user_selection[sel_key]["type_id"] = type_id

    text, kb = await render_product_card(callback.from_user.id, product_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("nostock:"))
async def no_stock_alert(callback: CallbackQuery) -> None:
    await callback.answer("К сожалению, товар с выбранными параметрами закончился. Попробуйте выбрать другой вес или район.", show_alert=True)


# ==================== ПОКУПКА ====================

@router.callback_query(F.data.startswith("buy:"))
async def buy_product_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Оформление покупки с учетом выбранного веса, города, района и типа."""
    product_id = int(callback.data.split(":")[1])
    user = await get_user_by_tg_id(callback.from_user.id)

    if not user:
        await callback.answer("Пользователь не найден. Перезапустите бота.", show_alert=True)
        return

    sel_key = (callback.from_user.id, product_id)
    current_sel = user_selection.get(sel_key, {})

    variant_id = current_sel.get("variant_id")
    city_id = current_sel.get("city_id")
    district_id = current_sel.get("district_id") if current_sel.get("district_id") != 0 else None

    # Получаем название типа если выбран
    type_name = None
    if current_sel.get("type_id"):
        types = await get_product_type_options(product_id)
        for t in types:
            if t.id == current_sel["type_id"]:
                type_name = t.name
                break

    success, msg, order = await buy_product(
        user_id=user.id,
        product_id=product_id,
        variant_id=variant_id,
        city_id=city_id,
        district_id=district_id,
        type_name=type_name,
    )

    if not success or not order:
        await callback.answer(msg, show_alert=True)
        return

    await callback.answer("Покупка успешно оплачена!")
    user = await get_user_by_tg_id(callback.from_user.id)

    details_parts = [f"📦 <b>Товар:</b> {order.product_name}"]
    if order.city_name:
        dist_str = f" ({order.district_name})" if order.district_name else ""
        details_parts.append(f"🏙 <b>Город:</b> {order.city_name}{dist_str}")
    if order.variant_name:
        details_parts.append(f"⚖️ <b>Вес:</b> {order.variant_name}")
    if order.type_name:
        details_parts.append(f"🏷 <b>Тип:</b> {order.type_name}")

    details_text = "\n".join(details_parts)

    purchase_text = (
        f"🎉 <b>Покупка успешно оплачена!</b>\n\n"
        f"🧾 Заказ №<b>{order.id}</b>\n"
        f"{details_text}\n\n"
        f"💵 Списано: <b>{order.price:.2f} ₽</b>\n"
        f"💰 Остаток баланса: <b>{user.balance:.2f} ₽</b>\n\n"
        f"🎁 <b>Выданный товар / Данные заказа:</b>\n"
        f"<code>{order.delivered_content}</code>\n\n"
        f"<i>Информация о заказе сохранена в разделе «📦 Заказы».</i>"
    )

    await callback.message.edit_text(purchase_text, parse_mode="HTML")

    # Уведомление администраторам
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

    if callback.from_user.username:
        buyer_contact = f"@{callback.from_user.username} (ID: <code>{callback.from_user.id}</code>)"
        contact_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать покупателю", url=f"https://t.me/{callback.from_user.username}")]
            ]
        )
    else:
        buyer_name = html.escape(callback.from_user.full_name or "Покупатель")
        buyer_contact = f"<a href=\"tg://user?id={callback.from_user.id}\">{buyer_name}</a> (ID: <code>{callback.from_user.id}</code>)"
        contact_kb = None

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

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_notification,
                reply_markup=contact_kb,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")
