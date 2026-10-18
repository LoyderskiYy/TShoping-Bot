from typing import List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Category, Product, ProductVariant, ProductTypeOption, City, District


# ==================== ПРОФИЛЬ И ПОПОЛНЕНИЕ ====================

def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура в профиле."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить баланс (Bitcoin)", callback_data="start_deposit")],
        ]
    )


def get_deposit_keyboard(deposit_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для счета на пополнение BTC."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_dep:{deposit_id}")],
            [InlineKeyboardButton(text="📝 Указать TxID вручную", callback_data=f"txid_dep:{deposit_id}")],
            [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_dep:{deposit_id}")],
        ]
    )


# ==================== КАТАЛОГ ====================

def get_categories_keyboard(categories: List[Category], has_uncategorized: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура со списком категорий."""
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=f"📁 {cat.name}", callback_data=f"cat:{cat.id}")])

    if has_uncategorized:
        buttons.append([InlineKeyboardButton(text="📦 Без категории", callback_data="cat:0")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_products_keyboard(products: List[Product], category_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Клавиатура со списком товаров в категории."""
    buttons = []
    for prod in products:
        price_display = f"от {prod.price:.0f} ₽" if prod.price > 0 else "выбрать фасовку"
        buttons.append([
            InlineKeyboardButton(
                text=f"{prod.name} ({price_display})",
                callback_data=f"prod:{prod.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Назад к категориям", callback_data="back_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_card_keyboard(
    product_id: int,
    price: float,
    category_id: Optional[int],
    in_stock: bool,
    has_cities: bool = True,
    has_variants: bool = True,
    has_types: bool = True,
) -> InlineKeyboardMarkup:
    """
    Клавиатура карточки товара.
    В точности соответствует кнопкам из запроса/скриншота пользователя:
    - Выбрать город
    - Выбрать вес
    - Выбрать тип
    """
    buttons = []

    # Кнопки выбора параметров товара
    if has_cities:
        buttons.append([InlineKeyboardButton(text="Выбрать город", callback_data=f"pick_city:{product_id}")])
    if has_variants:
        buttons.append([InlineKeyboardButton(text="Выбрать вес", callback_data=f"pick_weight:{product_id}")])
    if has_types:
        buttons.append([InlineKeyboardButton(text="Выбрать тип", callback_data=f"pick_type:{product_id}")])

    # Кнопка покупки
    if in_stock:
        buttons.append([
            InlineKeyboardButton(text=f"🛒 Купить за {price:.2f} ₽", callback_data=f"buy:{product_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="❌ Нет в наличии", callback_data=f"nostock:{product_id}")
        ])

    back_cb = f"cat:{category_id}" if category_id else "back_categories"
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад к товарам", callback_data=back_cb)
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cities_selection_keyboard(product_id: int, cities: List[City]) -> InlineKeyboardMarkup:
    """Клавиатура выбора города."""
    buttons = []
    for city in cities:
        buttons.append([InlineKeyboardButton(text=f"🏙 {city.name}", callback_data=f"sel_city:{product_id}:{city.id}")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад к товару", callback_data=f"prod:{product_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_districts_selection_keyboard(product_id: int, city_id: int, districts: List[District]) -> InlineKeyboardMarkup:
    """Клавиатура выбора района в городе."""
    buttons = [
        [InlineKeyboardButton(text="🌐 Все районы города", callback_data=f"sel_dist:{product_id}:{city_id}:0")]
    ]
    for dist in districts:
        buttons.append([
            InlineKeyboardButton(text=f"📍 {dist.name}", callback_data=f"sel_dist:{product_id}:{city_id}:{dist.id}")
        ])

    buttons.append([InlineKeyboardButton(text="🔙 К выбору города", callback_data=f"pick_city:{product_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_weights_selection_keyboard(product_id: int, variants: List[ProductVariant]) -> InlineKeyboardMarkup:
    """Клавиатура выбора веса / фасовки с индивидуальной ценой."""
    buttons = []
    for var in variants:
        buttons.append([
            InlineKeyboardButton(
                text=f"⚖️ {var.weight_name} - {var.price:.0f} ₽",
                callback_data=f"sel_weight:{product_id}:{var.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Назад к товару", callback_data=f"prod:{product_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_types_selection_keyboard(product_id: int, types: List[ProductTypeOption]) -> InlineKeyboardMarkup:
    """Клавиатура выбора типа товара (Магнит, Тайник, Доставка и т.д.)."""
    buttons = []
    for t in types:
        buttons.append([
            InlineKeyboardButton(
                text=f"🏷 {t.name}",
                callback_data=f"sel_type:{product_id}:{t.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Назад к товару", callback_data=f"prod:{product_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ЗАКАЗЫ ====================

def get_order_details_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Кнопка просмотра полученного товара."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Показать купленный товар", callback_data=f"show_order:{order_id}")]
        ]
    )


# ==================== ПОДДЕРЖКА ====================

def get_ticket_admin_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Кнопка для ответа администратора на тикет."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить пользователю", callback_data=f"reply_ticket:{ticket_id}")]
        ]
    )


# ==================== АДМИН-ПАНЕЛЬ ====================

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📁 Категории", callback_data="adm_cats"),
                InlineKeyboardButton(text="📦 Товары", callback_data="adm_prods"),
            ],
            [
                InlineKeyboardButton(text="🏙 Города и районы", callback_data="adm_cities"),
                InlineKeyboardButton(text="₿ BTC-кошелек", callback_data="adm_btc"),
            ],
            [
                InlineKeyboardButton(text="📩 Тикеты поддержки", callback_data="adm_tickets"),
                InlineKeyboardButton(text="💰 Выдать баланс", callback_data="adm_give_balance"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика магазина", callback_data="adm_stats"),
            ],
        ]
    )


def get_admin_categories_keyboard(categories: List[Category]) -> InlineKeyboardMarkup:
    """Управление категориями для админа."""
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="adm_add_cat")]
    ]
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {cat.name}", callback_data=f"adm_del_cat:{cat.id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню админки", callback_data="adm_back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_cities_keyboard(cities: List[City]) -> InlineKeyboardMarkup:
    """Управление городами для админа."""
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить город", callback_data="adm_add_city")]
    ]
    for c in cities:
        buttons.append([
            InlineKeyboardButton(text=f"🏙 {c.name}", callback_data=f"adm_city_menu:{c.id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню админки", callback_data="adm_back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_city_menu_keyboard(city_id: int, districts: List[District]) -> InlineKeyboardMarkup:
    """Управление конкретным городом и его районами."""
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить район", callback_data=f"adm_add_dist:{city_id}")],
    ]
    for d in districts:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 Район: {d.name}", callback_data=f"adm_del_dist:{d.id}:{city_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🗑 Удалить весь город", callback_data=f"adm_del_city:{city_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к городам", callback_data="adm_cities")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_products_keyboard(products: List[Product]) -> InlineKeyboardMarkup:
    """Управление товарами для админа."""
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="adm_add_prod")]
    ]
    for prod in products:
        buttons.append([
            InlineKeyboardButton(text=f"⚙️ {prod.name}", callback_data=f"adm_prod_menu:{prod.id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню админки", callback_data="adm_back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_prod_manage_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Карточка управления конкретным товаром для админа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Загрузить наличие на склад", callback_data=f"adm_add_stock:{product_id}")],
            [
                InlineKeyboardButton(text="⚖️ Вес и цены", callback_data=f"adm_manage_weights:{product_id}"),
                InlineKeyboardButton(text="🏷 Типы товара", callback_data=f"adm_manage_types:{product_id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ Изменить описание", callback_data=f"adm_edit_desc:{product_id}"),
                InlineKeyboardButton(text="🗑 Удалить товар", callback_data=f"adm_del_prod:{product_id}"),
            ],
            [InlineKeyboardButton(text="🔙 К списку товаров", callback_data="adm_prods")],
        ]
    )
