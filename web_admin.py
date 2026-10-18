import asyncio
import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Response, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import APIKeyCookie
import uvicorn

from config import WEB_ADMIN_PASSWORD, DEFAULT_BTC_WALLET
from database.db import (
    get_shop_stats,
    get_all_categories,
    create_category,
    delete_category,
    get_all_cities,
    create_city,
    delete_city,
    get_districts_by_city,
    create_district,
    delete_district,
    get_all_products_full,
    create_product,
    create_product_variant,
    create_product_type_option,
    set_variant_stock,
    set_product_stock,
    delete_product,
    get_all_orders_full,
    get_all_deposits_full,
    complete_deposit,
    get_all_tickets_full,
    get_ticket_by_id,
    answer_ticket,
    get_setting,
    set_setting,
    get_user_by_tg_id,
)

logger = logging.getLogger("web_admin")
app = FastAPI(title="Shop Web Admin Panel", docs_url=None, redoc_url=None)

# Глобальная ссылка на бота aiogram (для отправки сообщений из веба)
bot_instance = None


def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot


def check_auth(request: Request) -> bool:
    cookie_auth = request.cookies.get("admin_session")
    return cookie_auth == "authenticated"


def require_auth(request: Request):
    if not check_auth(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )


def get_base_html(title: str, content: str, active_tab: str = "dashboard") -> str:
    """Генерация базового макета с навигацией Tailwind CSS."""
    tabs = [
        ("dashboard", "Главная", "fa-chart-pie", "/"),
        ("products", "Товары и наличие", "fa-boxes-stacked", "/products"),
        ("cities", "Города и районы", "fa-city", "/cities"),
        ("categories", "Категории", "fa-folder", "/categories"),
        ("orders", "Заказы", "fa-receipt", "/orders"),
        ("deposits", "BTC Депозиты", "fa-bitcoin-sign", "/deposits"),
        ("tickets", "Поддержка", "fa-headset", "/tickets"),
        ("settings", "Настройки", "fa-gear", "/settings"),
    ]

    nav_links = ""
    for tab_id, tab_label, icon, url in tabs:
        active_class = "bg-blue-600 text-white font-semibold" if active_tab == tab_id else "text-gray-300 hover:bg-gray-800 hover:text-white"
        nav_links += f"""
        <a href="{url}" class="flex items-center gap-3 px-4 py-3 rounded-xl transition duration-150 {active_class}">
            <i class="fa-solid {icon} text-lg w-6 text-center"></i>
            <span>{tab_label}</span>
        </a>
        """

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Панель управления магазином</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
    </style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen flex flex-col md:flex-row">
    <!-- Боковое меню -->
    <aside class="w-full md:w-64 bg-gray-900 border-r border-gray-800 flex flex-col p-4 shrink-0">
        <div class="flex items-center gap-3 px-3 py-4 mb-4 border-b border-gray-800">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white text-xl font-bold shadow-lg shadow-blue-500/30">
                <i class="fa-solid fa-shop"></i>
            </div>
            <div>
                <h1 class="font-bold text-lg leading-tight">Shop Admin</h1>
                <p class="text-xs text-gray-400">Панель управления</p>
            </div>
        </div>

        <nav class="space-y-1 flex-1">
            {nav_links}
        </nav>

        <div class="pt-4 border-t border-gray-800 mt-4">
            <a href="/logout" class="flex items-center gap-3 px-4 py-3 rounded-xl text-red-400 hover:bg-red-500/10 transition">
                <i class="fa-solid fa-arrow-right-from-bracket text-lg w-6 text-center"></i>
                <span>Выйти</span>
            </a>
        </div>
    </aside>

    <!-- Основной контент -->
    <main class="flex-1 p-4 md:p-8 overflow-y-auto">
        <div class="max-w-6xl mx-auto">
            {content}
        </div>
    </main>
</body>
</html>
"""


# ==================== АВТОРИЗАЦИЯ ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if check_auth(request):
        return RedirectResponse(url="/", status_code=303)

    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в админ-панель</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body class="bg-gray-950 text-gray-100 flex items-center justify-center min-h-screen p-4 font-sans">
    <div class="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl p-8 shadow-2xl">
        <div class="text-center mb-8">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white text-3xl font-bold mx-auto mb-4 shadow-xl shadow-blue-500/20">
                <i class="fa-solid fa-shield-halved"></i>
            </div>
            <h1 class="text-2xl font-bold">Вход в панель управления</h1>
            <p class="text-sm text-gray-400 mt-1">Введите пароль администратора</p>
        </div>

        <form method="POST" action="/login" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">Пароль</label>
                <div class="relative">
                    <input type="password" name="password" required autofocus
                        placeholder="••••••••"
                        class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition">
                </div>
            </div>

            <button type="submit"
                class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 px-4 rounded-xl transition duration-150 shadow-lg shadow-blue-600/30">
                Войти
            </button>
        </form>
    </div>
</body>
</html>"""


@app.post("/login")
async def login_submit(password: str = Form(...)):
    if password == WEB_ADMIN_PASSWORD:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="admin_session", value="authenticated", max_age=86400 * 30, httponly=True)
        return response

    return HTMLResponse(
        "<script>alert('Неверный пароль!'); window.location.href='/login';</script>",
        status_code=401
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="admin_session")
    return response


# ==================== ДАШБОРД ====================

@app.get("/", response_class=HTMLResponse)
async def dashboard_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    stats = await get_shop_stats()
    orders = await get_all_orders_full()
    deposits = await get_all_deposits_full()

    recent_orders_html = ""
    for o in orders[:5]:
        date_str = o.created_at.strftime("%d.%m %H:%M")
        meta = []
        if o.variant_name: meta.append(f"⚖️ {o.variant_name}")
        if o.city_name: meta.append(f"🏙 {o.city_name}")
        meta_str = " | ".join(meta)

        recent_orders_html += f"""
        <tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
            <td class="py-3 px-4 text-gray-400 font-mono text-sm">#{o.id}</td>
            <td class="py-3 px-4 font-medium">{o.product_name} <span class="text-xs text-gray-400 block">{meta_str}</span></td>
            <td class="py-3 px-4 font-semibold text-emerald-400">{o.price:.2f} ₽</td>
            <td class="py-3 px-4 text-xs text-gray-400">{date_str}</td>
        </tr>
        """

    if not recent_orders_html:
        recent_orders_html = "<tr><td colspan='4' class='py-4 text-center text-gray-500'>Заказов пока нет</td></tr>"

    content = f"""
    <div class="mb-8">
        <h2 class="text-2xl font-bold">Обзор магазина</h2>
        <p class="text-gray-400 text-sm">Сводка ключевых показателей и активности</p>
    </div>

    <!-- Карточки статистики -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div class="flex items-center justify-between text-gray-400 mb-2">
                <span class="text-xs font-semibold uppercase tracking-wider">Выручка</span>
                <i class="fa-solid fa-coins text-amber-400 text-lg"></i>
            </div>
            <div class="text-2xl font-bold text-white">{stats['total_revenue']:,.2f} ₽</div>
        </div>

        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div class="flex items-center justify-between text-gray-400 mb-2">
                <span class="text-xs font-semibold uppercase tracking-wider">Заказы</span>
                <i class="fa-solid fa-bag-shopping text-blue-400 text-lg"></i>
            </div>
            <div class="text-2xl font-bold text-white">{stats['total_orders']}</div>
        </div>

        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div class="flex items-center justify-between text-gray-400 mb-2">
                <span class="text-xs font-semibold uppercase tracking-wider">Пополнения BTC</span>
                <i class="fa-brands fa-bitcoin text-orange-400 text-lg"></i>
            </div>
            <div class="text-2xl font-bold text-white">{stats['total_deposits']:,.2f} ₽</div>
        </div>

        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div class="flex items-center justify-between text-gray-400 mb-2">
                <span class="text-xs font-semibold uppercase tracking-wider">Пользователи</span>
                <i class="fa-solid fa-users text-indigo-400 text-lg"></i>
            </div>
            <div class="text-2xl font-bold text-white">{stats['total_users']}</div>
        </div>
    </div>

    <!-- Таблица последних заказов -->
    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold">Последние оплаченные заказы</h3>
            <a href="/orders" class="text-sm text-blue-400 hover:text-blue-300 font-medium">Все заказы &rarr;</a>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-left">
                <thead>
                    <tr class="text-xs font-semibold uppercase text-gray-400 border-b border-gray-800">
                        <th class="py-3 px-4">№</th>
                        <th class="py-3 px-4">Товар</th>
                        <th class="py-3 px-4">Сумма</th>
                        <th class="py-3 px-4">Дата</th>
                    </tr>
                </thead>
                <tbody>
                    {recent_orders_html}
                </tbody>
            </table>
        </div>
    </div>
    """
    return get_base_html("Дашборд", content, active_tab="dashboard")


# ==================== ТОВАРЫ И НАЛИЧИЕ ====================

@app.get("/products", response_class=HTMLResponse)
async def products_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    products_data = await get_all_products_full()
    categories = await get_all_categories()

    cat_options = '<option value="0">Без категории</option>'
    for c in categories:
        cat_options += f'<option value="{c.id}">{c.name}</option>'

    products_html = ""
    for item in products_data:
        p = item["product"]
        variants = item["variants"]
        types = item["types"]

        # Рендер вариантов веса с инлайн-редактированием остатка!
        variants_html = ""
        if variants:
            for v in variants:
                variants_html += f"""
                <div class="flex items-center justify-between bg-gray-950 border border-gray-800/80 rounded-xl px-3 py-2 text-sm mb-2">
                    <div>
                        <span class="font-medium text-white">{v.weight_name}</span>
                        <span class="text-emerald-400 font-semibold ml-2">{v.price:.0f} ₽</span>
                    </div>
                    <form method="POST" action="/products/variant/{v.id}/stock" class="flex items-center gap-2">
                        <span class="text-xs text-gray-400">Наличие:</span>
                        <input type="number" name="stock" value="{v.stock}" min="0"
                            class="w-20 bg-gray-900 border border-gray-700 rounded-lg px-2 py-1 text-center font-bold text-white focus:outline-none focus:border-blue-500">
                        <button type="submit" class="bg-gray-800 hover:bg-gray-700 px-3 py-1 rounded-lg text-xs font-semibold transition" title="Сохранить остаток">
                            <i class="fa-solid fa-check"></i>
                        </button>
                    </form>
                </div>
                """
        else:
            variants_html = f"""
            <div class="flex items-center justify-between bg-gray-950 border border-gray-800/80 rounded-xl px-3 py-2 text-sm">
                <div>
                    <span class="font-semibold text-emerald-400">{p.price:.0f} ₽</span>
                </div>
                <form method="POST" action="/products/{p.id}/stock" class="flex items-center gap-2">
                    <span class="text-xs text-gray-400">Наличие:</span>
                    <input type="number" name="stock" value="{p.stock}" min="0"
                        class="w-20 bg-gray-900 border border-gray-700 rounded-lg px-2 py-1 text-center font-bold text-white focus:outline-none focus:border-blue-500">
                    <button type="submit" class="bg-gray-800 hover:bg-gray-700 px-3 py-1 rounded-lg text-xs font-semibold transition">
                        <i class="fa-solid fa-check"></i>
                    </button>
                </form>
            </div>
            """

        types_badges = ""
        if types:
            for t in types:
                types_badges += f'<span class="bg-gray-800 text-gray-300 text-xs px-2 py-1 rounded-md mr-1">{t.name}</span>'

        products_html += f"""
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex flex-col justify-between">
            <div>
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold uppercase text-blue-400 tracking-wider">{item['category_name']}</span>
                    <form method="POST" action="/products/{p.id}/delete" onsubmit="return confirm('Удалить этот товар?');">
                        <button type="submit" class="text-gray-500 hover:text-red-400 transition" title="Удалить товар">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </form>
                </div>
                <h3 class="text-xl font-bold text-white mb-1">{p.name}</h3>
                <p class="text-sm text-gray-400 mb-4">{p.description or 'Нет описания'}</p>

                <div class="mb-4">
                    <div class="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Фасовка и наличие (в штуках):</div>
                    {variants_html}
                </div>

                {f'<div class="mb-2"><span class="text-xs text-gray-400">Типы:</span> {types_badges}</div>' if types_badges else ''}
            </div>
        </div>
        """

    if not products_html:
        products_html = "<div class='col-span-full py-12 text-center text-gray-500 bg-gray-900 rounded-2xl border border-gray-800'>Товары еще не добавлены</div>"

    content = f"""
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
            <h2 class="text-2xl font-bold">Товары и наличие на складе</h2>
            <p class="text-gray-400 text-sm">Управляйте ассортиментом, фасовками и количеством в наличии просто цифрой</p>
        </div>
        <button onclick="document.getElementById('modalAddProd').classList.remove('hidden')"
            class="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-4 py-2.5 rounded-xl transition flex items-center gap-2 self-start shadow-lg shadow-blue-600/30">
            <i class="fa-solid fa-plus"></i>
            <span>Добавить товар</span>
        </button>
    </div>

    <!-- Сетка товаров -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        {products_html}
    </div>

    <!-- Модальное окно добавления товара -->
    <div id="modalAddProd" class="hidden fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div class="bg-gray-900 border border-gray-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div class="flex items-center justify-between mb-6 pb-3 border-b border-gray-800">
                <h3 class="text-xl font-bold">Добавление нового товара</h3>
                <button onclick="document.getElementById('modalAddProd').classList.add('hidden')" class="text-gray-400 hover:text-white">
                    <i class="fa-solid fa-xmark text-xl"></i>
                </button>
            </div>

            <form method="POST" action="/products/create" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Категория</label>
                    <select name="category_id" class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-white">
                        {cat_options}
                    </select>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Название товара *</label>
                    <input type="text" name="name" required placeholder="Например: Продукт A"
                        class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-white">
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Описание</label>
                    <textarea name="description" rows="2" placeholder="Краткое описание товара..."
                        class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-white"></textarea>
                </div>

                <!-- Блок фасовок (вес + цена + остаток) -->
                <div class="bg-gray-950 border border-gray-800 rounded-xl p-4">
                    <label class="block text-sm font-semibold text-gray-200 mb-2">Фасовки, цены и количество в наличии:</label>
                    <p class="text-xs text-gray-400 mb-3">Укажите вес, цену и количество (в штуках), например: 200г - 1500 ₽ (наличие: 7 шт.)</p>
                    
                    <div id="weightsContainer" class="space-y-3">
                        <div class="grid grid-cols-3 gap-2">
                            <input type="text" name="weight_name[]" placeholder="Вес (напр. 200г)" value="200г" required
                                class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                            <input type="number" name="weight_price[]" placeholder="Цена ₽" value="1500" required
                                class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                            <input type="number" name="weight_stock[]" placeholder="Кол-во (шт.)" value="7" required
                                class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                        <div class="grid grid-cols-3 gap-2">
                            <input type="text" name="weight_name[]" placeholder="Вес (напр. 500г)" value="500г"
                                class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                            <input type="number" name="weight_price[]" placeholder="Цена ₽" value="3200"
                                class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                            <input type="number" name="weight_stock[]" placeholder="Кол-во (шт.)" value="5"
                                class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                    </div>

                    <button type="button" onclick="addWeightRow()" class="mt-3 text-xs text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1">
                        <i class="fa-solid fa-plus"></i> Добавить еще фасовку
                    </button>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Типы товара (через запятую)</label>
                    <input type="text" name="types_raw" placeholder="Магнит, Тайник, Доставка"
                        class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-white">
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Текст выдачи / Инструкция после оплаты</label>
                    <textarea name="delivery_text" rows="2" placeholder="Данный текст будет выдан покупателю сразу после списания баланса..."
                        class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-white"></textarea>
                </div>

                <div class="pt-4 flex justify-end gap-3">
                    <button type="button" onclick="document.getElementById('modalAddProd').classList.add('hidden')"
                        class="px-4 py-2.5 rounded-xl border border-gray-700 text-gray-300 hover:bg-gray-800 transition">Отмена</button>
                    <button type="submit"
                        class="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-2.5 rounded-xl transition">Создать товар</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function addWeightRow() {{
            const container = document.getElementById('weightsContainer');
            const div = document.createElement('div');
            div.className = 'grid grid-cols-3 gap-2';
            div.innerHTML = `
                <input type="text" name="weight_name[]" placeholder="Вес (напр. 1кг)" required class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                <input type="number" name="weight_price[]" placeholder="Цена ₽" required class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                <input type="number" name="weight_stock[]" placeholder="Кол-во (шт.)" value="10" required class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
            `;
            container.appendChild(div);
        }}
    </script>
    """

    return get_base_html("Товары и наличие", content, active_tab="products")


@app.post("/products/create")
async def products_create_submit(
    request: Request,
    name: str = Form(...),
    category_id: int = Form(0),
    description: Optional[str] = Form(None),
    delivery_text: Optional[str] = Form(None),
    types_raw: Optional[str] = Form(None),
):
    require_auth(request)

    form_data = await request.form()
    weight_names = form_data.getlist("weight_name[]")
    weight_prices = form_data.getlist("weight_price[]")
    weight_stocks = form_data.getlist("weight_stock[]")

    cat_id = category_id if category_id != 0 else None
    product = await create_product(
        name=name,
        category_id=cat_id,
        description=description,
        delivery_text=delivery_text,
    )

    # Добавляем фасовки
    for idx, w_name in enumerate(weight_names):
        if w_name and str(w_name).strip():
            w_price = Decimal(str(weight_prices[idx] or 0))
            w_stock = int(weight_stocks[idx] or 0)
            await create_product_variant(product.id, str(w_name).strip(), w_price, stock=w_stock)

    # Добавляем типы
    if types_raw and types_raw.strip():
        for t in types_raw.split(","):
            if t.strip():
                await create_product_type_option(product.id, t.strip())

    return RedirectResponse(url="/products", status_code=303)


@app.post("/products/variant/{variant_id}/stock")
async def update_variant_stock_submit(variant_id: int, stock: int = Form(...), request: Request = None):
    require_auth(request)
    await set_variant_stock(variant_id, stock)
    return RedirectResponse(url="/products", status_code=303)


@app.post("/products/{product_id}/stock")
async def update_product_stock_submit(product_id: int, stock: int = Form(...), request: Request = None):
    require_auth(request)
    await set_product_stock(product_id, stock)
    return RedirectResponse(url="/products", status_code=303)


@app.post("/products/{product_id}/delete")
async def product_delete_submit(product_id: int, request: Request):
    require_auth(request)
    await delete_product(product_id)
    return RedirectResponse(url="/products", status_code=303)


# ==================== ГОРОДА И РАЙОНЫ ====================

@app.get("/cities", response_class=HTMLResponse)
async def cities_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    cities = await get_all_cities()

    cities_html = ""
    for c in cities:
        districts = await get_districts_by_city(c.id)
        districts_chips = ""
        for d in districts:
            districts_chips += f"""
            <span class="inline-flex items-center gap-1.5 bg-gray-950 border border-gray-700/80 rounded-lg px-2.5 py-1 text-xs">
                <span>{d.name}</span>
                <form method="POST" action="/districts/{d.id}/delete" class="inline">
                    <button type="submit" class="text-gray-500 hover:text-red-400">&times;</button>
                </form>
            </span>
            """

        cities_html += f"""
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 mb-4">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-location-dot text-blue-500"></i>
                    {c.name}
                </h3>
                <form method="POST" action="/cities/{c.id}/delete" onsubmit="return confirm('Удалить город и все его районы?');">
                    <button type="submit" class="text-gray-500 hover:text-red-400 text-sm">
                        <i class="fa-solid fa-trash-can mr-1"></i> Удалить город
                    </button>
                </form>
            </div>

            <div class="flex flex-wrap gap-2 mb-4">
                {districts_chips if districts_chips else '<span class="text-xs text-gray-500">Районы еще не добавлены</span>'}
            </div>

            <!-- Форма быстрого добавления района -->
            <form method="POST" action="/districts/create" class="flex items-center gap-2 max-w-sm">
                <input type="hidden" name="city_id" value="{c.id}">
                <input type="text" name="name" required placeholder="Название района..."
                    class="flex-1 bg-gray-950 border border-gray-700 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500">
                <button type="submit" class="bg-gray-800 hover:bg-gray-700 text-white px-3 py-1.5 rounded-xl text-xs font-semibold">
                    <i class="fa-solid fa-plus"></i> Район
                </button>
            </form>
        </div>
        """

    content = f"""
    <div class="flex items-center justify-between mb-8">
        <div>
            <h2 class="text-2xl font-bold">Города и районы</h2>
            <p class="text-gray-400 text-sm">Настройка локаций для выбора пользователем в боте</p>
        </div>
    </div>

    <!-- Форма добавления города -->
    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8">
        <h3 class="text-md font-bold mb-3">Добавить новый город</h3>
        <form method="POST" action="/cities/create" class="flex gap-3 max-w-md">
            <input type="text" name="name" required placeholder="Например: Москва"
                class="flex-1 bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500">
            <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-5 py-2.5 rounded-xl transition">
                Добавить город
            </button>
        </form>
    </div>

    <div>
        {cities_html if cities_html else '<p class="text-gray-500 text-center py-8">Городов пока нет</p>'}
    </div>
    """
    return get_base_html("Города и районы", content, active_tab="cities")


@app.post("/cities/create")
async def city_create_submit(name: str = Form(...), request: Request = None):
    require_auth(request)
    await create_city(name)
    return RedirectResponse(url="/cities", status_code=303)


@app.post("/cities/{city_id}/delete")
async def city_delete_submit(city_id: int, request: Request):
    require_auth(request)
    await delete_city(city_id)
    return RedirectResponse(url="/cities", status_code=303)


@app.post("/districts/create")
async def district_create_submit(city_id: int = Form(...), name: str = Form(...), request: Request = None):
    require_auth(request)
    await create_district(city_id, name)
    return RedirectResponse(url="/cities", status_code=303)


@app.post("/districts/{district_id}/delete")
async def district_delete_submit(district_id: int, request: Request):
    require_auth(request)
    await delete_district(district_id)
    return RedirectResponse(url="/cities", status_code=303)


# ==================== КАТЕГОРИИ ====================

@app.get("/categories", response_class=HTMLResponse)
async def categories_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    cats = await get_all_categories()
    cats_html = ""
    for c in cats:
        cats_html += f"""
        <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between mb-3">
            <span class="font-semibold text-white">📁 {c.name}</span>
            <form method="POST" action="/categories/{c.id}/delete" onsubmit="return confirm('Удалить категорию?');">
                <button type="submit" class="text-gray-500 hover:text-red-400">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </form>
        </div>
        """

    content = f"""
    <div class="mb-8">
        <h2 class="text-2xl font-bold">Категории каталога</h2>
        <p class="text-gray-400 text-sm">Управление разделами каталога товаров</p>
    </div>

    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8 max-w-md">
        <h3 class="text-md font-bold mb-3">Создать категорию</h3>
        <form method="POST" action="/categories/create" class="flex gap-3">
            <input type="text" name="name" required placeholder="Название..."
                class="flex-1 bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-white">
            <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-5 py-2.5 rounded-xl">Создать</button>
        </form>
    </div>

    <div class="max-w-md">
        {cats_html if cats_html else '<p class="text-gray-500">Категорий нет</p>'}
    </div>
    """
    return get_base_html("Категории", content, active_tab="categories")


@app.post("/categories/create")
async def category_create_submit(name: str = Form(...), request: Request = None):
    require_auth(request)
    await create_category(name)
    return RedirectResponse(url="/categories", status_code=303)


@app.post("/categories/{cat_id}/delete")
async def category_delete_submit(cat_id: int, request: Request):
    require_auth(request)
    await delete_category(cat_id)
    return RedirectResponse(url="/categories", status_code=303)


# ==================== ЗАКАЗЫ ====================

@app.get("/orders", response_class=HTMLResponse)
async def orders_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    orders = await get_all_orders_full()

    rows = ""
    for o in orders:
        date_str = o.created_at.strftime("%d.%m.%Y %H:%M")
        meta = []
        if o.variant_name: meta.append(f"⚖️ {o.variant_name}")
        if o.city_name: meta.append(f"🏙 {o.city_name}")
        if o.district_name: meta.append(f"📍 {o.district_name}")
        if o.type_name: meta.append(f"🏷 {o.type_name}")
        meta_str = " | ".join(meta)

        rows += f"""
        <tr class="border-b border-gray-800 hover:bg-gray-900/50 transition">
            <td class="py-3 px-4 font-mono text-sm text-gray-400">#{o.id}</td>
            <td class="py-3 px-4 text-xs text-gray-400">{date_str}</td>
            <td class="py-3 px-4 font-bold text-white">{o.product_name}</td>
            <td class="py-3 px-4 text-xs text-gray-300">{meta_str or '-'}</td>
            <td class="py-3 px-4 font-bold text-emerald-400">{o.price:.2f} ₽</td>
            <td class="py-3 px-4 text-xs font-mono text-gray-400 max-w-xs truncate" title="{o.delivered_content}">{o.delivered_content}</td>
        </tr>
        """

    content = f"""
    <div class="mb-8">
        <h2 class="text-2xl font-bold">Оплаченные заказы ({len(orders)})</h2>
        <p class="text-gray-400 text-sm">Полная история покупок клиентов магазина</p>
    </div>

    <div class="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm">
                <thead>
                    <tr class="text-xs uppercase text-gray-400 bg-gray-950 border-b border-gray-800">
                        <th class="py-3 px-4">№</th>
                        <th class="py-3 px-4">Дата</th>
                        <th class="py-3 px-4">Товар</th>
                        <th class="py-3 px-4">Параметры</th>
                        <th class="py-3 px-4">Сумма</th>
                        <th class="py-3 px-4">Выдано</th>
                    </tr>
                </thead>
                <tbody>
                    {rows if rows else '<tr><td colspan="6" class="py-8 text-center text-gray-500">Заказов пока нет</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    return get_base_html("Заказы", content, active_tab="orders")


# ==================== BITCOIN ДЕПОЗИТЫ ====================

@app.get("/deposits", response_class=HTMLResponse)
async def deposits_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    deposits = await get_all_deposits_full()

    rows = ""
    for d in deposits:
        date_str = d.created_at.strftime("%d.%m.%Y %H:%M")
        status_badge = (
            '<span class="bg-emerald-500/10 text-emerald-400 text-xs px-2.5 py-1 rounded-full font-semibold">Оплачено</span>'
            if d.status == "completed"
            else '<span class="bg-amber-500/10 text-amber-400 text-xs px-2.5 py-1 rounded-full font-semibold">Ожидание</span>'
        )

        approve_btn = ""
        if d.status != "completed":
            approve_btn = f"""
            <form method="POST" action="/deposits/{d.id}/approve" onsubmit="return confirm('Подтвердить и начислить {d.amount_rub:.2f} ₽ пользователю?');">
                <button type="submit" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3 py-1.5 rounded-lg font-semibold transition">
                    Зачислить
                </button>
            </form>
            """

        rows += f"""
        <tr class="border-b border-gray-800 hover:bg-gray-900/50 transition">
            <td class="py-3 px-4 font-mono text-sm text-gray-400">#{d.id}</td>
            <td class="py-3 px-4 text-xs text-gray-400">{date_str}</td>
            <td class="py-3 px-4 font-semibold text-white">{d.amount_rub:.2f} ₽</td>
            <td class="py-3 px-4 font-mono text-xs text-orange-400">{d.amount_btc:.8f} BTC</td>
            <td class="py-3 px-4">{status_badge}</td>
            <td class="py-3 px-4 font-mono text-xs text-gray-400 max-w-xs truncate">{d.tx_hash or '-'}</td>
            <td class="py-3 px-4">{approve_btn}</td>
        </tr>
        """

    content = f"""
    <div class="mb-8">
        <h2 class="text-2xl font-bold">Счета и депозиты Bitcoin</h2>
        <p class="text-gray-400 text-sm">История выставленных счетов и возможность ручного подтверждения</p>
    </div>

    <div class="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm">
                <thead>
                    <tr class="text-xs uppercase text-gray-400 bg-gray-950 border-b border-gray-800">
                        <th class="py-3 px-4">Счет</th>
                        <th class="py-3 px-4">Дата</th>
                        <th class="py-3 px-4">Сумма (₽)</th>
                        <th class="py-3 px-4">Сумма (BTC)</th>
                        <th class="py-3 px-4">Статус</th>
                        <th class="py-3 px-4">TxID</th>
                        <th class="py-3 px-4">Действие</th>
                    </tr>
                </thead>
                <tbody>
                    {rows if rows else '<tr><td colspan="7" class="py-8 text-center text-gray-500">Депозитов пока нет</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    return get_base_html("BTC Депозиты", content, active_tab="deposits")


@app.post("/deposits/{deposit_id}/approve")
async def deposit_manual_approve(deposit_id: int, request: Request):
    require_auth(request)
    await complete_deposit(deposit_id, tx_hash=f"manual_admin_approve_{deposit_id}")
    return RedirectResponse(url="/deposits", status_code=303)


# ==================== ПОДДЕРЖКА И ТИКЕТЫ ====================

@app.get("/tickets", response_class=HTMLResponse)
async def tickets_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    tickets = await get_all_tickets_full()

    tickets_html = ""
    for t in tickets:
        status_badge = (
            '<span class="bg-gray-800 text-gray-400 text-xs px-2.5 py-1 rounded-full font-semibold">Отвечен</span>'
            if t.status == "answered"
            else '<span class="bg-emerald-500/10 text-emerald-400 text-xs px-2.5 py-1 rounded-full font-semibold">Открыт</span>'
        )

        reply_block = ""
        if t.status != "answered":
            reply_block = f"""
            <form method="POST" action="/tickets/{t.id}/reply" class="mt-4 flex gap-2">
                <input type="text" name="reply" required placeholder="Введите ответ пользователю..."
                    class="flex-1 bg-gray-950 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl text-sm font-semibold transition">
                    Ответить в Telegram
                </button>
            </form>
            """
        else:
            reply_block = f"""
            <div class="mt-3 bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-300">
                <span class="text-xs text-blue-400 font-bold block mb-1">Ответ поддержки:</span>
                {t.reply}
            </div>
            """

        tickets_html += f"""
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-4">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-3">
                    <span class="font-mono text-sm text-gray-400">Тикет #{t.id}</span>
                    <span class="text-xs text-gray-500">Пользователь: <code>{t.user_tg_id}</code></span>
                </div>
                {status_badge}
            </div>

            <div class="text-white font-medium my-2">
                ❓ {t.question}
            </div>

            {reply_block}
        </div>
        """

    content = f"""
    <div class="mb-8">
        <h2 class="text-2xl font-bold">Тикеты поддержки клиентов</h2>
        <p class="text-gray-400 text-sm">Отвечайте на вопросы клиентов прямо из браузера</p>
    </div>

    <div>
        {tickets_html if tickets_html else '<p class="text-gray-500 text-center py-8">Обращений в поддержку нет</p>'}
    </div>
    """
    return get_base_html("Поддержка", content, active_tab="tickets")


@app.post("/tickets/{ticket_id}/reply")
async def ticket_reply_submit(ticket_id: int, reply: str = Form(...), request: Request = None):
    require_auth(request)
    ticket = await answer_ticket(ticket_id, reply.strip())

    # Если бот запущен, отправляем уведомление прямо в Telegram
    if bot_instance and ticket:
        try:
            await bot_instance.send_message(
                ticket.user_tg_id,
                f"👨‍💻 <b>Ответ службы поддержки на обращение #{ticket.id}:</b>\n\n{reply.strip()}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось доставить сообщение пользователю {ticket.user_tg_id}: {e}")

    return RedirectResponse(url="/tickets", status_code=303)


# ==================== НАСТРОЙКИ ====================

@app.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)

    current_wallet = await get_setting("btc_wallet", DEFAULT_BTC_WALLET)

    content = f"""
    <div class="mb-8">
        <h2 class="text-2xl font-bold">Настройки магазина</h2>
        <p class="text-gray-400 text-sm">Управление платежными реквизитами</p>
    </div>

    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-xl">
        <h3 class="text-lg font-bold mb-4">Кошелек Bitcoin для приема оплат</h3>
        <form method="POST" action="/settings/save" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Адрес BTC-кошелька</label>
                <input type="text" name="btc_wallet" value="{current_wallet}" required
                    class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-3 font-mono text-sm text-white focus:outline-none focus:border-blue-500">
                <p class="text-xs text-gray-400 mt-1">Все новые счета на пополнение баланса будут формироваться с этим адресом.</p>
            </div>

            <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-2.5 rounded-xl transition">
                Сохранить настройки
            </button>
        </form>
    </div>
    """
    return get_base_html("Настройки", content, active_tab="settings")


@app.post("/settings/save")
async def settings_save_submit(btc_wallet: str = Form(...), request: Request = None):
    require_auth(request)
    await set_setting("btc_wallet", btc_wallet.strip())
    return RedirectResponse(url="/settings", status_code=303)


def start_web_admin(host: str = "0.0.0.0", port: int = 8000):
    """Синхронный запуск веб-админки (для отдельного процесса)."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_web_admin()
