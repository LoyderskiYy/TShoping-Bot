import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, List

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, DEFAULT_BTC_WALLET
from database.db import (
    get_all_categories,
    create_category,
    delete_category,
    get_products_by_category,
    get_product_by_id,
    get_product_stock_count,
    create_product,
    update_product,
    delete_product,
    add_product_items,
    get_product_variants,
    create_product_variant,
    delete_product_variant,
    get_product_type_options,
    create_product_type_option,
    delete_product_type_option,
    get_all_cities,
    create_city,
    delete_city,
    get_city_by_id,
    get_districts_by_city,
    create_district,
    delete_district,
    get_setting,
    set_setting,
    get_open_tickets,
    get_ticket_by_id,
    answer_ticket,
    get_user_by_tg_id,
    update_user_balance,
    get_shop_stats,
)
from keyboards.default import get_cancel_keyboard, get_main_menu_keyboard
from keyboards.inline import (
    get_admin_main_keyboard,
    get_admin_categories_keyboard,
    get_admin_cities_keyboard,
    get_admin_city_menu_keyboard,
    get_admin_products_keyboard,
    get_admin_prod_manage_keyboard,
)
from states.states import AdminStates

logger = logging.getLogger(__name__)
router = Router()


def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


# ==================== ГЛАВНОЕ МЕНЮ АДМИНА ====================

@router.message(Command("admin"))
@router.message(F.text == "👑 Админ-панель")
async def show_admin_panel(message: Message, state: FSMContext) -> None:
    """Точка входа в админ-панель."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав доступа к панели администратора.")
        return

    await state.clear()
    await message.answer(
        "👑 <b>Панель управления магазином</b>\n\n"
        "Выберите раздел для настройки и управления:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_back_main")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        "👑 <b>Панель управления магазином</b>\n\n"
        "Выберите раздел для настройки и управления:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML",
    )


# ==================== УПРАВЛЕНИЕ ГОРОДАМИ И РАЙОНАМИ ====================

@router.callback_query(F.data == "adm_cities")
async def admin_cities_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    cities = await get_all_cities()
    await callback.message.edit_text(
        "🏙 <b>Управление городами и районами</b>\n\n"
        "Нажмите ➕ чтобы добавить новый город, или нажмите на город для управления его районами:",
        reply_markup=get_admin_cities_keyboard(cities),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_add_city")
async def admin_add_city_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    await callback.answer()
    await state.set_state(AdminStates.waiting_for_city_name)
    await callback.message.answer(
        "🏙 Введите название нового города (например: <code>Москва</code>):\n\n"
        "<i>Для отмены нажмите кнопку «❌ Отмена» внизу.</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_city_name)
async def admin_add_city_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    city_name = message.text.strip()
    city = await create_city(city_name)
    await state.clear()

    await message.answer(
        f"✅ Город <b>«{city.name}»</b> успешно добавлен!",
        reply_markup=get_main_menu_keyboard(is_admin=True),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_city_menu:"))
async def admin_city_detail_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    city_id = int(callback.data.split(":")[1])
    city = await get_city_by_id(city_id)
    if not city:
        await callback.answer("Город не найден", show_alert=True)
        return

    districts = await get_districts_by_city(city_id)
    await callback.message.edit_text(
        f"🏙 <b>Город: {city.name}</b>\n\n"
        f"Районов в базе: <b>{len(districts)}</b>\n"
        f"Нажмите ➕ чтобы добавить район, или нажмите на район для удаления:",
        reply_markup=get_admin_city_menu_keyboard(city_id, districts),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_add_dist:"))
async def admin_add_district_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    city_id = int(callback.data.split(":")[1])
    await state.update_data(city_id=city_id)
    await state.set_state(AdminStates.waiting_for_district_name)

    await callback.message.answer(
        "📍 Введите название района для этого города (например: <code>Центральный</code>):\n\n"
        "<i>Для отмены нажмите кнопку «❌ Отмена» внизу.</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_district_name)
async def admin_add_district_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    dist_name = message.text.strip()
    data = await state.get_data()
    city_id = data.get("city_id")

    dist = await create_district(city_id, dist_name)
    await state.clear()

    await message.answer(
        f"✅ Район <b>«{dist.name}»</b> успешно добавлен!",
        reply_markup=get_main_menu_keyboard(is_admin=True),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_del_dist:"))
async def admin_del_dist_action(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    dist_id = int(parts[1])
    city_id = int(parts[2])

    await delete_district(dist_id)
    await callback.answer("Район удален")

    city = await get_city_by_id(city_id)
    districts = await get_districts_by_city(city_id)
    await callback.message.edit_text(
        f"🏙 <b>Город: {city.name}</b>\n\nРайон удален. Список обновлен:",
        reply_markup=get_admin_city_menu_keyboard(city_id, districts),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_del_city:"))
async def admin_del_city_action(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    city_id = int(callback.data.split(":")[1])
    await delete_city(city_id)
    await callback.answer("Город удален")

    cities = await get_all_cities()
    await callback.message.edit_text(
        "🏙 <b>Управление городами и районами</b>\n\nГород удален. Список обновлен:",
        reply_markup=get_admin_cities_keyboard(cities),
        parse_mode="HTML",
    )


# ==================== BTC КОШЕЛЕК ====================

@router.callback_query(F.data == "adm_btc")
async def admin_btc_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    current_wallet = await get_setting("btc_wallet", DEFAULT_BTC_WALLET)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить кошелек", callback_data="adm_change_btc")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm_back_main")],
        ]
    )

    await callback.message.edit_text(
        f"₿ <b>Настройка Bitcoin-кошелька магазина</b>\n\n"
        f"Текущий адрес для приема платежей:\n"
        f"<code>{current_wallet}</code>\n\n"
        f"На этот адрес пользователи переводят BTC при пополнении баланса.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_change_btc")
async def admin_change_btc_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    await callback.answer()
    await state.set_state(AdminStates.waiting_for_btc_wallet)
    await callback.message.answer(
        "₿ <b>Введите новый Bitcoin-адрес:</b>\n\n"
        "<i>Поддерживаются SegWit (bc1q...), Legacy (1...) и Script (3...).</i>\n"
        "Для отмены нажмите кнопку «❌ Отмена» внизу.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_btc_wallet)
async def admin_save_btc_wallet(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    new_wallet = message.text.strip()
    if len(new_wallet) < 25 or " " in new_wallet:
        await message.answer("Некорректный адрес Bitcoin. Попробуйте еще раз или нажмите «❌ Отмена».")
        return

    await set_setting("btc_wallet", new_wallet)
    await state.clear()

    await message.answer(
        f"✅ <b>BTC-кошелек успешно обновлен!</b>\n\n"
        f"Новый адрес: <code>{new_wallet}</code>",
        reply_markup=get_main_menu_keyboard(is_admin=True),
        parse_mode="HTML",
    )


# ==================== УПРАВЛЕНИЕ КАТЕГОРИЯМИ ====================

@router.callback_query(F.data == "adm_cats")
async def admin_categories_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    cats = await get_all_categories()
    await callback.message.edit_text(
        "📁 <b>Управление категориями</b>\n\n"
        "Нажмите ➕ чтобы создать категорию, или нажмите на категорию для ее удаления:",
        reply_markup=get_admin_categories_keyboard(cats),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_add_cat")
async def admin_add_cat_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    await callback.answer()
    await state.set_state(AdminStates.waiting_for_category_name)
    await callback.message.answer(
        "📁 Введите название новой категории:\n\n"
        "<i>Для отмены нажмите «❌ Отмена» ниже.</i>",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminStates.waiting_for_category_name)
async def admin_add_cat_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    cat_name = message.text.strip()
    cat = await create_category(cat_name)
    await state.clear()

    await message.answer(
        f"✅ Категория <b>«{cat.name}»</b> успешно создана!",
        reply_markup=get_main_menu_keyboard(is_admin=True),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_del_cat:"))
async def admin_del_cat_callback(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    cat_id = int(callback.data.split(":")[1])
    await delete_category(cat_id)
    await callback.answer("Категория удалена")

    cats = await get_all_categories()
    await callback.message.edit_text(
        "📁 <b>Управление категориями</b>\n\nКатегория удалена. Список обновлен:",
        reply_markup=get_admin_categories_keyboard(cats),
        parse_mode="HTML",
    )


# ==================== УПРАВЛЕНИЕ ТОВАРАМИ ====================

@router.callback_query(F.data == "adm_prods")
async def admin_products_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    products = await get_products_by_category(None, only_active=False)
    await callback.message.edit_text(
        "📦 <b>Управление товарами</b>\n\n"
        "Нажмите ➕ чтобы добавить новый товар, или выберите товар для настройки веса, цен, типов и наличия:",
        reply_markup=get_admin_products_keyboard(products),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_add_prod")
async def admin_add_prod_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    await callback.answer()
    cats = await get_all_categories()

    buttons = []
    for cat in cats:
        buttons.append([InlineKeyboardButton(text=cat.name, callback_data=f"adm_pick_cat:{cat.id}")])
    buttons.append([InlineKeyboardButton(text="Без категории", callback_data="adm_pick_cat:0")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="adm_prods")])

    await callback.message.edit_text(
        "📦 <b>Добавление товара: Шаг 1 из 4</b>\n\n"
        "Выберите категорию для нового товара:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_pick_cat:"))
async def admin_picked_cat(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    cat_id_raw = callback.data.split(":")[1]
    cat_id = int(cat_id_raw) if cat_id_raw != "0" else None

    await state.update_data(category_id=cat_id)
    await state.set_state(AdminStates.waiting_for_prod_name)

    await callback.message.answer(
        "📦 <b>Шаг 2 из 4:</b> Введите название товара:\n\n"
        "<i>Для отмены нажмите «❌ Отмена» внизу.</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_prod_name)
async def admin_add_prod_name(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(AdminStates.waiting_for_prod_desc)

    await message.answer(
        "📝 <b>Шаг 3 из 4:</b> Введите описание товара (или отправьте <code>-</code> если описание не требуется):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_prod_desc)
async def admin_add_prod_desc(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    desc = message.text.strip()
    if desc == "-":
        desc = ""

    await state.update_data(description=desc)
    await state.set_state(AdminStates.waiting_for_prod_weights)

    await message.answer(
        "⚖️ <b>Шаг 4 из 4:</b> Укажите варианты <b>веса и цены</b> за каждый вес!\n\n"
        "Введите варианты в одну строчку через запятую или каждый с новой строки, например:\n"
        "<code>200г: 1500, 500г: 3200, 1кг: 5800</code>\n\n"
        "<i>(Или отправьте просто одну цену, например: <code>1000</code>, если вес не разделяется)</i>",
        parse_mode="HTML",
    )


def parse_weights_input(text: str) -> List[tuple[str, Decimal]]:
    """Парсит строку с фасовками и ценами, например: '200г: 1500, 500г: 3200, 1кг: 5800'."""
    results = []
    # Заменяем переносы на запятые
    raw = text.replace("\n", ",")
    items = [x.strip() for x in raw.split(",") if x.strip()]

    for item in items:
        if ":" in item or "-" in item or "=" in item:
            sep = ":" if ":" in item else ("-" if "-" in item else "=")
            parts = item.split(sep, 1)
            w_name = parts[0].strip()
            price_clean = re.sub(r"[^\d.]", "", parts[1].replace(",", "."))
            if price_clean:
                results.append((w_name, Decimal(price_clean)))
        else:
            # Если просто число
            price_clean = re.sub(r"[^\d.]", "", item.replace(",", "."))
            if price_clean:
                results.append(("Стандарт", Decimal(price_clean)))
    return results


@router.message(AdminStates.waiting_for_prod_weights)
async def admin_add_prod_weights(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    parsed_weights = parse_weights_input(message.text)
    if not parsed_weights:
        await message.answer(
            "Не удалось распознать вес и цены.\n"
            "Пожалуйста, введите в формате: <code>200г: 1500, 500г: 3200, 1кг: 5800</code>"
        )
        return

    await state.update_data(weights=parsed_weights)
    await state.set_state(AdminStates.waiting_for_prod_types)

    await message.answer(
        "🏷 <b>Уточнения по типу товара</b> (например: <code>Магнит, Тайник, Доставка</code>)\n\n"
        "Введите доступные типы через запятую (или отправьте <code>-</code> если товар без разделения по типам):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_prod_types)
async def admin_add_prod_types(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    weights: List[tuple[str, Decimal]] = data["weights"]

    # Базовая цена = минимальная из фасовок
    min_price = min(w[1] for w in weights)

    product = await create_product(
        name=data["name"],
        price=min_price,
        category_id=data.get("category_id"),
        description=data.get("description"),
        product_type="stock",
    )

    # Создаем варианты веса
    for w_name, w_price in weights:
        await create_product_variant(product.id, w_name, w_price)

    # Создаем типы товара, если указаны
    types_raw = message.text.strip()
    if types_raw and types_raw != "-":
        for t_name in types_raw.split(","):
            if t_name.strip():
                await create_product_type_option(product.id, t_name.strip())

    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Загрузить наличие на склад", callback_data=f"adm_add_stock:{product.id}")],
            [InlineKeyboardButton(text="👌 В меню товаров", callback_data="adm_prods")],
        ]
    )

    await message.answer(
        f"✅ Товар <b>«{product.name}»</b> успешно создан!\n\n"
        f"⚖️ Добавлено вариантов веса: <b>{len(weights)}</b>\n"
        f"Теперь вы можете загрузить позиции наличия на склад.",
        reply_markup=kb,
        parse_mode="HTML",
    )


# ==================== УПРАВЛЕНИЕ КОНКРЕТНЫМ ТОВАРОМ ====================

@router.callback_query(F.data.startswith("adm_prod_menu:"))
async def admin_prod_detail_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    product = await get_product_by_id(prod_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    variants = await get_product_variants(prod_id)
    types = await get_product_type_options(prod_id)
    stock = await get_product_stock_count(prod_id)

    weights_str = ", ".join([f"{v.weight_name} ({v.price:.0f} ₽)" for v in variants]) if variants else "не заданы"
    types_str = ", ".join([t.name for t in types]) if types else "нет"

    await callback.message.edit_text(
        f"⚙️ <b>Управление товаром:</b> {product.name}\n\n"
        f"⚖️ <b>Вес и цены:</b> {weights_str}\n"
        f"🏷 <b>Типы:</b> {types_str}\n"
        f"📊 <b>Всего на складе:</b> <b>{stock} шт.</b>\n"
        f"📝 <b>Описание:</b> {product.description or 'нет'}",
        reply_markup=get_admin_prod_manage_keyboard(product.id),
        parse_mode="HTML",
    )


# --- Настройка весов ---
@router.callback_query(F.data.startswith("adm_manage_weights:"))
async def admin_manage_weights(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    variants = await get_product_variants(prod_id)

    buttons = [
        [InlineKeyboardButton(text="➕ Добавить вариант веса", callback_data=f"adm_add_w:{prod_id}")]
    ]
    for v in variants:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {v.weight_name} ({v.price:.0f} ₽)", callback_data=f"adm_del_w:{v.id}:{prod_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к товару", callback_data=f"adm_prod_menu:{prod_id}")])

    await callback.message.edit_text(
        "⚖️ <b>Управление весом и ценами товара</b>\n\n"
        "Нажмите ➕ чтобы добавить новый вес и цену, или нажмите на позицию для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_add_w:"))
async def admin_add_w_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=prod_id)
    await state.set_state(AdminStates.waiting_for_new_weight)

    await callback.message.answer(
        "⚖️ Введите новый вес и цену в формате:\n"
        "<code>500г: 3200</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_new_weight)
async def admin_add_w_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    parsed = parse_weights_input(message.text)
    if not parsed:
        await message.answer("Неверный формат. Пример: <code>500г: 3200</code>")
        return

    data = await state.get_data()
    prod_id = data.get("product_id")

    for w_name, price in parsed:
        await create_product_variant(prod_id, w_name, price)

    await state.clear()
    await message.answer("✅ Вариант веса успешно добавлен!", reply_markup=get_main_menu_keyboard(is_admin=True))


@router.callback_query(F.data.startswith("adm_del_w:"))
async def admin_del_w_action(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    w_id = int(parts[1])
    prod_id = int(parts[2])

    await delete_product_variant(w_id)
    await callback.answer("Удалено")

    variants = await get_product_variants(prod_id)
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить вариант веса", callback_data=f"adm_add_w:{prod_id}")]
    ]
    for v in variants:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {v.weight_name} ({v.price:.0f} ₽)", callback_data=f"adm_del_w:{v.id}:{prod_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к товару", callback_data=f"adm_prod_menu:{prod_id}")])

    await callback.message.edit_text(
        "⚖️ <b>Управление весом и ценами товара</b>\n\nПозиция удалена. Список обновлен:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


# --- Настройка типов ---
@router.callback_query(F.data.startswith("adm_manage_types:"))
async def admin_manage_types(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    types = await get_product_type_options(prod_id)

    buttons = [
        [InlineKeyboardButton(text="➕ Добавить тип", callback_data=f"adm_add_t:{prod_id}")]
    ]
    for t in types:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {t.name}", callback_data=f"adm_del_t:{t.id}:{prod_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к товару", callback_data=f"adm_prod_menu:{prod_id}")])

    await callback.message.edit_text(
        "🏷 <b>Управление типами товара (Магнит, Тайник, Доставка)</b>\n\n"
        "Нажмите ➕ чтобы добавить новый тип, или нажмите на тип для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_add_t:"))
async def admin_add_t_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=prod_id)
    await state.set_state(AdminStates.waiting_for_new_type)

    await callback.message.answer(
        "🏷 Введите название нового типа (например: <code>Магнит</code>):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_new_type)
async def admin_add_t_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    t_name = message.text.strip()
    data = await state.get_data()
    prod_id = data.get("product_id")

    await create_product_type_option(prod_id, t_name)
    await state.clear()

    await message.answer("✅ Новый тип товара добавлен!", reply_markup=get_main_menu_keyboard(is_admin=True))


@router.callback_query(F.data.startswith("adm_del_t:"))
async def admin_del_t_action(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    t_id = int(parts[1])
    prod_id = int(parts[2])

    await delete_product_type_option(t_id)
    await callback.answer("Тип удален")

    types = await get_product_type_options(prod_id)
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить тип", callback_data=f"adm_add_t:{prod_id}")]
    ]
    for t in types:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {t.name}", callback_data=f"adm_del_t:{t.id}:{prod_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к товару", callback_data=f"adm_prod_menu:{prod_id}")])

    await callback.message.edit_text(
        "🏷 <b>Управление типами товара</b>\n\nТип удален. Список обновлен:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


# --- Загрузка наличия ---
@router.callback_query(F.data.startswith("adm_add_stock:"))
async def admin_add_stock_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    variants = await get_product_variants(prod_id)

    # Если есть варианты веса, предлагаем выбрать к какому весу загрузить (или ко всем)
    if variants:
        buttons = []
        for v in variants:
            buttons.append([InlineKeyboardButton(text=f"Для веса: {v.weight_name}", callback_data=f"adm_stk_v:{prod_id}:{v.id}")])
        buttons.append([InlineKeyboardButton(text="Для любого веса (универсально)", callback_data=f"adm_stk_v:{prod_id}:0")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm_prod_menu:{prod_id}")])

        await callback.message.edit_text(
            "📥 <b>Выберите для какой фасовки загружаются позиции на склад:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )
        return

    await state.update_data(product_id=prod_id, variant_id=None)
    await state.set_state(AdminStates.waiting_for_add_stock)

    await callback.message.answer(
        "📦 <b>Укажите количество товара в наличии:</b>\n\n"
        "👉 Просто отправьте цифру в чат (например: <code>7</code>).\n\n"
        "<i>(Или отправьте строки с ключами/координатами, если используете штучную выдачу)</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_stk_v:"))
async def admin_stk_v_picked(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    prod_id = int(parts[1])
    var_id_raw = int(parts[2])
    variant_id = var_id_raw if var_id_raw != 0 else None

    await state.update_data(product_id=prod_id, variant_id=variant_id)
    await state.set_state(AdminStates.waiting_for_add_stock)

    await callback.message.answer(
        "📦 <b>Укажите количество для этой фасовки:</b>\n\n"
        "👉 Просто отправьте цифру в чат (например: <code>7</code>).\n\n"
        "<i>(Или отправьте строки с ключами/координатами)</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_add_stock)
async def admin_add_stock_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    text_val = message.text.strip()
    data = await state.get_data()
    prod_id = data.get("product_id")
    variant_id = data.get("variant_id")

    # Если администратор просто написал цифру (например: 7)
    if text_val.isdigit():
        qty = int(text_val)
        from database.db import set_variant_stock, set_product_stock
        if variant_id:
            await set_variant_stock(variant_id, qty)
        else:
            await set_product_stock(prod_id, qty)
        await state.clear()
        await message.answer(
            f"✅ Количество товара в наличии успешно установлено: <b>{qty} шт.</b>!",
            reply_markup=get_main_menu_keyboard(is_admin=True),
            parse_mode="HTML",
        )
        return

    # Если администратор загрузил построчные данные (ключи, координаты)
    lines = [line.strip() for line in message.text.split("\n") if line.strip()]
    if not lines:
        await message.answer("Пустой ввод. Пришлите число (например 7) или строки:")
        return

    added_count = await add_product_items(prod_id, lines, variant_id=variant_id)
    await state.clear()

    await message.answer(
        f"✅ Успешно загружено <b>{added_count}</b> позиций на склад!",
        reply_markup=get_main_menu_keyboard(is_admin=True),
        parse_mode="HTML",
    )



@router.callback_query(F.data.startswith("adm_edit_desc:"))
async def admin_edit_desc_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=prod_id)
    await state.set_state(AdminStates.waiting_for_edit_desc)

    await callback.message.answer(
        "📝 Введите новое описание товара:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminStates.waiting_for_edit_desc)
async def admin_edit_desc_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    prod_id = data.get("product_id")
    await update_product(prod_id, description=message.text.strip())
    await state.clear()

    await message.answer(
        "✅ Описание товара успешно обновлено!",
        reply_markup=get_main_menu_keyboard(is_admin=True),
    )


@router.callback_query(F.data.startswith("adm_del_prod:"))
async def admin_del_prod_callback(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split(":")[1])
    await delete_product(prod_id)
    await callback.answer("Товар удален!")

    products = await get_products_by_category(None, only_active=False)
    await callback.message.edit_text(
        "📦 <b>Управление товарами</b>\n\nТовар удален. Список обновлен:",
        reply_markup=get_admin_products_keyboard(products),
        parse_mode="HTML",
    )


# ==================== ТИКЕТЫ ПОДДЕРЖКИ ====================

@router.callback_query(F.data == "adm_tickets")
async def admin_open_tickets_list(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    tickets = await get_open_tickets()
    if not tickets:
        await callback.answer("Открытых тикетов нет! Все вопросы отвечены 🎉", show_alert=True)
        return

    buttons = []
    for t in tickets[:10]:
        buttons.append([
            InlineKeyboardButton(
                text=f"Тикет #{t.id} от {t.user_tg_id}",
                callback_data=f"reply_ticket:{t.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="adm_back_main")])

    await callback.message.edit_text(
        f"📩 <b>Открытые обращения ({len(tickets)}):</b>\n\n"
        f"Нажмите на тикет, чтобы ответить пользователю:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("reply_ticket:"))
async def admin_reply_ticket_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = await get_ticket_by_id(ticket_id)

    if not ticket:
        await callback.answer("Тикет не найден.", show_alert=True)
        return

    await state.update_data(ticket_id=ticket.id)
    await state.set_state(AdminStates.waiting_for_ticket_reply)

    await callback.message.answer(
        f"💬 <b>Ответ на тикет #{ticket.id}</b>\n"
        f"Пользователь: <code>{ticket.user_tg_id}</code>\n\n"
        f"❓ Вопрос:\n<i>{ticket.question}</i>\n\n"
        f"Введите текст вашего ответа пользователю:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_ticket_reply)
async def admin_reply_ticket_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return

    reply_text = message.text.strip()
    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    ticket = await answer_ticket(ticket_id, reply_text)
    await state.clear()

    if not ticket:
        await message.answer("Ошибка: тикет не найден.")
        return

    try:
        await bot.send_message(
            ticket.user_tg_id,
            f"👨‍💻 <b>Ответ службы поддержки на обращение #{ticket.id}:</b>\n\n"
            f"{reply_text}",
            parse_mode="HTML",
        )
        await message.answer(
            f"✅ Ответ успешно доставлен пользователю по тикету #{ticket.id}!",
            reply_markup=get_main_menu_keyboard(is_admin=True),
        )
    except Exception as e:
        await message.answer(
            f"⚠️ Ответ сохранен в базе, но не удалось доставить сообщение в Telegram: {e}",
            reply_markup=get_main_menu_keyboard(is_admin=True),
        )


# ==================== ВЫДАЧА БАЛАНСА ВРУЧНУЮ ====================

@router.callback_query(F.data == "adm_give_balance")
async def admin_manual_balance_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return

    await callback.answer()
    await state.set_state(AdminStates.waiting_for_manual_user_id)
    await callback.message.answer(
        "💰 <b>Ручное начисление баланса</b>\n\n"
        "Введите Telegram ID пользователя (цифры):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_manual_user_id)
async def admin_manual_balance_user(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    try:
        target_tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите корректный цифровой Telegram ID:")
        return

    user = await get_user_by_tg_id(target_tg_id)
    if not user:
        await message.answer(f"Пользователь с Telegram ID {target_tg_id} еще ни разу не запускал бота.")
        await state.clear()
        return

    await state.update_data(target_user_id=user.id, target_tg_id=target_tg_id)
    await state.set_state(AdminStates.waiting_for_manual_amount)

    await message.answer(
        f"Пользователь найден: <b>{user.full_name or 'Без имени'}</b> (баланс: {user.balance:.2f} ₽)\n\n"
        f"Введите сумму в рублях для начисления (например: <code>500</code>):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_manual_amount)
async def admin_manual_balance_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return

    try:
        amount = Decimal(message.text.replace(",", ".").strip())
        if amount <= 0:
            raise ValueError()
    except Exception:
        await message.answer("Введите положительное число для начисления:")
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")
    target_tg_id = data.get("target_tg_id")

    new_bal = await update_user_balance(user_id, amount)
    await state.clear()

    await message.answer(
        f"✅ Баланс успешно пополнен на <b>{amount:.2f} ₽</b>! Новый баланс пользователя: <b>{new_bal:.2f} ₽</b>.",
        reply_markup=get_main_menu_keyboard(is_admin=True),
        parse_mode="HTML",
    )

    try:
        await bot.send_message(
            target_tg_id,
            f"🎉 <b>Ваш баланс пополнен администратором на +{amount:.2f} ₽!</b>\n"
            f"Текущий баланс: <b>{new_bal:.2f} ₽</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить пользователя {target_tg_id}: {e}")


# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "adm_stats")
async def admin_stats_view(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return

    stats = await get_shop_stats()

    text = (
        f"📊 <b>Статистика магазина</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🏙 Городов в базе: <b>{stats.get('total_cities', 0)}</b>\n"
        f"📦 Всего товаров в базе: <b>{stats['total_products']}</b>\n"
        f"🛒 Оплаченных заказов: <b>{stats['total_orders']}</b>\n"
        f"💵 Сумма покупок: <b>{stats['total_revenue']:.2f} ₽</b>\n"
        f"₿ Всего пополнений через BTC: <b>{stats['total_deposits']:.2f} ₽</b>\n"
        f"📩 Открытых обращений в поддержку: <b>{stats['open_tickets']}</b>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="adm_back_main")]]
    )

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
