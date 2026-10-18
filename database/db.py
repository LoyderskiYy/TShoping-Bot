from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, update, func, desc, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DATABASE_URL, DEFAULT_BTC_WALLET
from database.models import (
    Base,
    Category,
    City,
    District,
    Deposit,
    Order,
    Product,
    ProductVariant,
    ProductTypeOption,
    ProductItem,
    Setting,
    Ticket,
    User,
)

engine = create_async_engine(DATABASE_URL, echo=False)
session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Автоматическая миграция новых колонок для существующих БД
        migrations = [
            ("product_items", "variant_id", "INTEGER"),
            ("product_items", "city_id", "INTEGER"),
            ("product_items", "district_id", "INTEGER"),
            ("product_items", "type_name", "VARCHAR(64)"),
            ("orders", "variant_name", "VARCHAR(64)"),
            ("orders", "city_name", "VARCHAR(128)"),
            ("orders", "district_name", "VARCHAR(128)"),
            ("orders", "type_name", "VARCHAR(64)"),
            ("products", "stock", "INTEGER DEFAULT 0"),
            ("products", "delivery_text", "TEXT"),
            ("product_variants", "stock", "INTEGER DEFAULT 0"),
        ]

        for table_name, col_name, col_type in migrations:
            try:
                res = await conn.execute(text(f"PRAGMA table_info({table_name});"))
                columns = [row[1] for row in res.fetchall()]
                if col_name not in columns:
                    await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass


    # Установка дефолтных настроек, если их еще нет
    async with session_maker() as session:
        wallet_setting = await session.scalar(select(Setting).where(Setting.key == "btc_wallet"))
        if not wallet_setting:
            session.add(Setting(key="btc_wallet", value=DEFAULT_BTC_WALLET))
            await session.commit()


async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session


# ==================== SETTINGS ====================

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with session_maker() as session:
        res = await session.scalar(select(Setting.value).where(Setting.key == key))
        return res if res is not None else default


async def set_setting(key: str, value: str) -> None:
    async with session_maker() as session:
        setting = await session.scalar(select(Setting).where(Setting.key == key))
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))
        await session.commit()


# ==================== USERS ====================

async def get_or_create_user(
    tg_id: int, username: Optional[str], full_name: Optional[str]
) -> User:
    async with session_maker() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            user = User(
                tg_id=tg_id,
                username=username,
                full_name=full_name,
                balance=Decimal("0.00"),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            changed = False
            if user.username != username:
                user.username = username
                changed = True
            if user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if changed:
                await session.commit()
                await session.refresh(user)
        return user


async def get_user_by_tg_id(tg_id: int) -> Optional[User]:
    async with session_maker() as session:
        return await session.scalar(select(User).where(User.tg_id == tg_id))


async def update_user_balance(user_id: int, delta: Decimal) -> Decimal:
    """Изменяет баланс пользователя (может быть положительным или отрицательным)."""
    async with session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        new_balance = user.balance + delta
        if new_balance < Decimal("0.00"):
            raise ValueError("Недостаточно средств на балансе")
        user.balance = new_balance
        await session.commit()
        return user.balance


# ==================== CITIES & DISTRICTS ====================

async def get_all_cities() -> List[City]:
    async with session_maker() as session:
        res = await session.scalars(select(City).where(City.is_active == True).order_by(City.name))
        return list(res.all())


async def get_city_by_id(city_id: int) -> Optional[City]:
    async with session_maker() as session:
        return await session.get(City, city_id)


async def create_city(name: str) -> City:
    async with session_maker() as session:
        city = City(name=name.strip(), is_active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        return city


async def delete_city(city_id: int) -> bool:
    async with session_maker() as session:
        city = await session.get(City, city_id)
        if city:
            await session.delete(city)
            await session.commit()
            return True
        return False


async def get_districts_by_city(city_id: int) -> List[District]:
    async with session_maker() as session:
        res = await session.scalars(
            select(District).where(District.city_id == city_id, District.is_active == True).order_by(District.name)
        )
        return list(res.all())


async def get_district_by_id(district_id: int) -> Optional[District]:
    async with session_maker() as session:
        return await session.get(District, district_id)


async def create_district(city_id: int, name: str) -> District:
    async with session_maker() as session:
        district = District(city_id=city_id, name=name.strip(), is_active=True)
        session.add(district)
        await session.commit()
        await session.refresh(district)
        return district


async def delete_district(district_id: int) -> bool:
    async with session_maker() as session:
        district = await session.get(District, district_id)
        if district:
            await session.delete(district)
            await session.commit()
            return True
        return False


# ==================== CATEGORIES & PRODUCTS ====================

async def get_active_categories() -> List[Category]:
    async with session_maker() as session:
        res = await session.scalars(
            select(Category).where(Category.is_active == True).order_by(Category.id)
        )
        return list(res.all())


async def get_all_categories() -> List[Category]:
    async with session_maker() as session:
        res = await session.scalars(select(Category).order_by(Category.id))
        return list(res.all())


async def create_category(name: str) -> Category:
    async with session_maker() as session:
        cat = Category(name=name.strip(), is_active=True)
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat


async def delete_category(category_id: int) -> bool:
    async with session_maker() as session:
        cat = await session.get(Category, category_id)
        if cat:
            await session.delete(cat)
            await session.commit()
            return True
        return False


async def get_products_by_category(category_id: Optional[int], only_active: bool = True) -> List[Product]:
    async with session_maker() as session:
        query = select(Product)
        if category_id is not None:
            query = query.where(Product.category_id == category_id)
        if only_active:
            query = query.where(Product.is_active == True)
        query = query.order_by(Product.id)
        res = await session.scalars(query)
        return list(res.all())


async def get_product_by_id(product_id: int) -> Optional[Product]:
    async with session_maker() as session:
        return await session.get(Product, product_id)


# ==================== PRODUCT VARIANTS (ВЕС И ЦЕНА) ====================

async def get_product_variants(product_id: int) -> List[ProductVariant]:
    async with session_maker() as session:
        res = await session.scalars(
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id, ProductVariant.is_active == True)
            .order_by(ProductVariant.price)
        )
        return list(res.all())


async def get_variant_by_id(variant_id: int) -> Optional[ProductVariant]:
    async with session_maker() as session:
        return await session.get(ProductVariant, variant_id)


async def create_product_variant(
    product_id: int, weight_name: str, price: Decimal, stock: int = 0
) -> ProductVariant:
    async with session_maker() as session:
        variant = ProductVariant(
            product_id=product_id,
            weight_name=weight_name.strip(),
            price=price,
            stock=max(0, stock),
            is_active=True,
        )
        session.add(variant)
        await session.commit()
        await session.refresh(variant)
        return variant


async def set_variant_stock(variant_id: int, stock: int) -> bool:
    async with session_maker() as session:
        var = await session.get(ProductVariant, variant_id)
        if var:
            var.stock = max(0, stock)
            await session.commit()
            return True
        return False


async def delete_product_variant(variant_id: int) -> bool:
    async with session_maker() as session:
        var = await session.get(ProductVariant, variant_id)
        if var:
            await session.delete(var)
            await session.commit()
            return True
        return False


# ==================== PRODUCT TYPES (ТИП ТОВАРА: МАГНИТ/ТАЙНИК) ====================

async def get_product_type_options(product_id: int) -> List[ProductTypeOption]:
    async with session_maker() as session:
        res = await session.scalars(
            select(ProductTypeOption).where(ProductTypeOption.product_id == product_id).order_by(ProductTypeOption.id)
        )
        return list(res.all())


async def create_product_type_option(product_id: int, name: str) -> ProductTypeOption:
    async with session_maker() as session:
        opt = ProductTypeOption(product_id=product_id, name=name.strip())
        session.add(opt)
        await session.commit()
        await session.refresh(opt)
        return opt


async def delete_product_type_option(option_id: int) -> bool:
    async with session_maker() as session:
        opt = await session.get(ProductTypeOption, option_id)
        if opt:
            await session.delete(opt)
            await session.commit()
            return True
        return False


# ==================== PRODUCT STOCK & CRUD ====================

async def get_product_stock_count(
    product_id: int,
    variant_id: Optional[int] = None,
    city_id: Optional[int] = None,
    district_id: Optional[int] = None,
    type_name: Optional[str] = None,
) -> int:
    async with session_maker() as session:
        product = await session.get(Product, product_id)
        if not product:
            return 0
        if product.product_type == "infinite_text":
            return 999999

        # 1. Если проверяем для конкретного варианта веса
        if variant_id is not None:
            var = await session.get(ProductVariant, variant_id)
            if var and var.stock > 0:
                return var.stock
            query = select(func.count(ProductItem.id)).where(
                ProductItem.product_id == product_id,
                ProductItem.is_sold == False,
                ProductItem.variant_id == variant_id,
            )
            if city_id is not None:
                query = query.where((ProductItem.city_id == city_id) | (ProductItem.city_id == None))
            if district_id is not None:
                query = query.where((ProductItem.district_id == district_id) | (ProductItem.district_id == None))
            if type_name is not None:
                query = query.where((ProductItem.type_name == type_name) | (ProductItem.type_name == None))
            count = await session.scalar(query)
            return count or 0

        # 2. Если товар без вариантов веса
        if product.stock > 0:
            return product.stock

        query = select(func.count(ProductItem.id)).where(
            ProductItem.product_id == product_id,
            ProductItem.is_sold == False,
        )
        if city_id is not None:
            query = query.where((ProductItem.city_id == city_id) | (ProductItem.city_id == None))
        if district_id is not None:
            query = query.where((ProductItem.district_id == district_id) | (ProductItem.district_id == None))
        if type_name is not None:
            query = query.where((ProductItem.type_name == type_name) | (ProductItem.type_name == None))

        count = await session.scalar(query)
        return count or 0



async def set_product_stock(product_id: int, stock: int) -> bool:
    async with session_maker() as session:
        prod = await session.get(Product, product_id)
        if prod:
            prod.stock = max(0, stock)
            await session.commit()
            return True
        return False


async def create_product(
    name: str,
    price: Decimal = Decimal("0.00"),
    stock: int = 0,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    delivery_text: Optional[str] = None,
    product_type: str = "stock",
    content: Optional[str] = None,
) -> Product:
    async with session_maker() as session:
        prod = Product(
            category_id=category_id,
            name=name.strip(),
            description=description.strip() if description else None,
            price=price,
            stock=max(0, stock),
            delivery_text=delivery_text.strip() if delivery_text else None,
            product_type=product_type,
            content=content,
            is_active=True,
        )
        session.add(prod)
        await session.commit()
        await session.refresh(prod)
        return prod


async def update_product(
    product_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    price: Optional[Decimal] = None,
    stock: Optional[int] = None,
    delivery_text: Optional[str] = None,
    is_active: Optional[bool] = None,
    category_id: Optional[int] = None,
    content: Optional[str] = None,
) -> Optional[Product]:
    async with session_maker() as session:
        prod = await session.get(Product, product_id)
        if not prod:
            return None
        if name is not None:
            prod.name = name.strip()
        if description is not None:
            prod.description = description.strip() if description else None
        if price is not None:
            prod.price = price
        if stock is not None:
            prod.stock = max(0, stock)
        if delivery_text is not None:
            prod.delivery_text = delivery_text.strip() if delivery_text else None
        if is_active is not None:
            prod.is_active = is_active
        if category_id is not None:
            prod.category_id = category_id if category_id != 0 else None
        if content is not None:
            prod.content = content
        await session.commit()
        await session.refresh(prod)
        return prod



async def delete_product(product_id: int) -> bool:
    async with session_maker() as session:
        prod = await session.get(Product, product_id)
        if prod:
            await session.delete(prod)
            await session.commit()
            return True
        return False


async def add_product_items(
    product_id: int,
    items_data: List[str],
    variant_id: Optional[int] = None,
    city_id: Optional[int] = None,
    district_id: Optional[int] = None,
    type_name: Optional[str] = None,
) -> int:
    """Пакетное добавление позиций товара с привязкой к весу, городу, району и типу."""
    async with session_maker() as session:
        items = [
            ProductItem(
                product_id=product_id,
                variant_id=variant_id,
                city_id=city_id,
                district_id=district_id,
                type_name=type_name,
                data=data.strip(),
            )
            for data in items_data
            if data.strip()
        ]
        if not items:
            return 0
        session.add_all(items)
        await session.commit()
        return len(items)


# ==================== ORDERS & PURCHASES ====================

async def buy_product(
    user_id: int,
    product_id: int,
    variant_id: Optional[int] = None,
    city_id: Optional[int] = None,
    district_id: Optional[int] = None,
    type_name: Optional[str] = None,
) -> Tuple[bool, str, Optional[Order]]:
    """Покупка товара со списанием баланса по выбранному весу и параметрам."""
    async with session_maker() as session:
        user = await session.get(User, user_id)
        product = await session.get(Product, product_id)

        if not user or not product:
            return False, "Пользователь или товар не найден", None

        if not product.is_active:
            return False, "Товар сейчас недоступен для покупки", None

        # Определяем итоговую цену: если выбран вариант веса - берем цену веса!
        price = product.price
        variant_name = None
        if variant_id:
            variant = await session.get(ProductVariant, variant_id)
            if variant:
                price = variant.price
                variant_name = variant.weight_name
        else:
            # Если вариант не передан, проверим, есть ли у товара варианты веса
            first_var = await session.scalar(
                select(ProductVariant).where(ProductVariant.product_id == product_id, ProductVariant.is_active == True).limit(1)
            )
            if first_var:
                price = first_var.price
                variant_name = first_var.weight_name
                variant_id = first_var.id

        if user.balance < price:
            return False, f"Недостаточно средств. Ваш баланс: {user.balance:.2f} ₽, цена товара: {price:.2f} ₽", None

        city_name = None
        if city_id:
            city = await session.get(City, city_id)
            if city:
                city_name = city.name

        district_name = None
        if district_id:
            dist = await session.get(District, district_id)
            if dist:
                district_name = dist.name

        delivered_content: str = ""
        item_obj: Optional[ProductItem] = None

        if product.product_type == "infinite_text":
            delivered_content = product.content or "Товар предоставлен"
        elif variant_id:
            # 1. Если выбран конкретный вариант веса
            variant_obj = await session.get(ProductVariant, variant_id)
            if variant_obj and variant_obj.stock > 0:
                variant_obj.stock -= 1
                delivered_content = product.delivery_text or product.content or "Заказ успешно оплачен! Ожидайте выдачи или свяжитесь с оператором."
            else:
                # Проверяем штучные записи ProductItem для данного варианта
                query = select(ProductItem).where(
                    ProductItem.product_id == product_id,
                    ProductItem.is_sold == False,
                    ProductItem.variant_id == variant_id,
                )
                if city_id:
                    query = query.where((ProductItem.city_id == city_id) | (ProductItem.city_id == None))
                if district_id:
                    query = query.where((ProductItem.district_id == district_id) | (ProductItem.district_id == None))
                if type_name:
                    query = query.where((ProductItem.type_name == type_name) | (ProductItem.type_name == None))

                item_obj = await session.scalar(query.limit(1))
                if not item_obj:
                    return False, "К сожалению, данный товар/фасовка закончились на складе", None
                delivered_content = item_obj.data
        else:
            # 2. Если товар без разделения по весу
            if product.stock > 0:
                product.stock -= 1
                delivered_content = product.delivery_text or product.content or "Заказ успешно оплачен! Ожидайте выдачи или свяжитесь с оператором."
            else:
                query = select(ProductItem).where(
                    ProductItem.product_id == product_id,
                    ProductItem.is_sold == False,
                )
                if city_id:
                    query = query.where((ProductItem.city_id == city_id) | (ProductItem.city_id == None))
                if district_id:
                    query = query.where((ProductItem.district_id == district_id) | (ProductItem.district_id == None))
                if type_name:
                    query = query.where((ProductItem.type_name == type_name) | (ProductItem.type_name == None))

                item_obj = await session.scalar(query.limit(1))
                if not item_obj:
                    return False, "К сожалению, данный товар закончился на складе", None
                delivered_content = item_obj.data

        # Списываем баланс
        user.balance -= price

        # Создаем заказ с деталями
        order = Order(
            user_id=user.id,
            product_id=product.id,
            product_name=product.name,
            variant_name=variant_name,
            city_name=city_name,
            district_name=district_name,
            type_name=type_name,
            price=price,
            delivered_content=delivered_content,
        )
        session.add(order)
        await session.flush()



        if item_obj:
            item_obj.is_sold = True
            item_obj.sold_at = datetime.now(timezone.utc)
            item_obj.order_id = order.id

        await session.commit()
        await session.refresh(order)
        return True, "Успешная покупка", order


async def get_user_orders(user_id: int) -> List[Order]:
    async with session_maker() as session:
        res = await session.scalars(
            select(Order).where(Order.user_id == user_id).order_by(desc(Order.created_at))
        )
        return list(res.all())


async def get_order_by_id(order_id: int) -> Optional[Order]:
    async with session_maker() as session:
        return await session.get(Order, order_id)


# ==================== DEPOSITS (BITCOIN) ====================

async def create_deposit(
    user_id: int,
    amount_rub: Decimal,
    amount_btc: Decimal,
    target_address: str,
) -> Deposit:
    async with session_maker() as session:
        deposit = Deposit(
            user_id=user_id,
            amount_rub=amount_rub,
            amount_btc=amount_btc,
            target_address=target_address,
            status="pending",
        )
        session.add(deposit)
        await session.commit()
        await session.refresh(deposit)
        return deposit


async def get_deposit_by_id(deposit_id: int) -> Optional[Deposit]:
    async with session_maker() as session:
        return await session.get(Deposit, deposit_id)


async def is_tx_hash_used(tx_hash: str) -> bool:
    async with session_maker() as session:
        res = await session.scalar(
            select(Deposit.id).where(
                Deposit.tx_hash == tx_hash,
                Deposit.status == "completed",
            )
        )
        return res is not None


async def complete_deposit(deposit_id: int, tx_hash: Optional[str] = None) -> Tuple[bool, str, Optional[Decimal]]:
    """Подтверждает пополнение и начисляет баланс пользователю."""
    async with session_maker() as session:
        deposit = await session.get(Deposit, deposit_id)
        if not deposit:
            return False, "Заявка на пополнение не найдена", None

        if deposit.status == "completed":
            return False, "Эта заявка уже была успешно оплачена", None

        if tx_hash:
            existing = await session.scalar(
                select(Deposit.id).where(Deposit.tx_hash == tx_hash, Deposit.id != deposit_id)
            )
            if existing:
                return False, "Данный хэш транзакции уже был использован ранее", None
            deposit.tx_hash = tx_hash

        user = await session.get(User, deposit.user_id)
        if not user:
            return False, "Пользователь не найден", None

        deposit.status = "completed"
        deposit.completed_at = datetime.now(timezone.utc)
        user.balance += deposit.amount_rub

        await session.commit()
        return True, f"Баланс успешно пополнен на {deposit.amount_rub:.2f} ₽!", user.balance


# ==================== SUPPORT TICKETS ====================

async def create_ticket(user_id: int, user_tg_id: int, question: str) -> Ticket:
    async with session_maker() as session:
        ticket = Ticket(
            user_id=user_id,
            user_tg_id=user_tg_id,
            question=question,
            status="open",
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket


async def get_ticket_by_id(ticket_id: int) -> Optional[Ticket]:
    async with session_maker() as session:
        return await session.get(Ticket, ticket_id)


async def answer_ticket(ticket_id: int, reply: str) -> Optional[Ticket]:
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket:
            ticket.reply = reply
            ticket.status = "answered"
            ticket.answered_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(ticket)
        return ticket


async def get_open_tickets() -> List[Ticket]:
    async with session_maker() as session:
        res = await session.scalars(
            select(Ticket).where(Ticket.status == "open").order_by(desc(Ticket.created_at))
        )
        return list(res.all())


# ==================== STATISTICS ====================

async def get_shop_stats() -> Dict[str, Any]:
    async with session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        total_orders = await session.scalar(select(func.count(Order.id))) or 0
        total_revenue = await session.scalar(select(func.sum(Order.price))) or Decimal("0.00")
        total_deposits = (
            await session.scalar(
                select(func.sum(Deposit.amount_rub)).where(Deposit.status == "completed")
            )
            or Decimal("0.00")
        )
        total_products = await session.scalar(select(func.count(Product.id))) or 0
        open_tickets = (
            await session.scalar(
                select(func.count(Ticket.id)).where(Ticket.status == "open")
            )
            or 0
        )
        total_cities = await session.scalar(select(func.count(City.id))) or 0
        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_deposits": total_deposits,
            "total_products": total_products,
            "open_tickets": open_tickets,
            "total_cities": total_cities,
        }


# ==================== WEB ADMIN HELPERS ====================

async def get_all_orders_full() -> List[Order]:
    async with session_maker() as session:
        res = await session.scalars(select(Order).order_by(desc(Order.created_at)))
        return list(res.all())


async def get_all_deposits_full() -> List[Deposit]:
    async with session_maker() as session:
        res = await session.scalars(select(Deposit).order_by(desc(Deposit.created_at)))
        return list(res.all())


async def get_all_users_full() -> List[User]:
    async with session_maker() as session:
        res = await session.scalars(select(User).order_by(desc(User.created_at)))
        return list(res.all())


async def get_all_tickets_full() -> List[Ticket]:
    async with session_maker() as session:
        res = await session.scalars(select(Ticket).order_by(desc(Ticket.created_at)))
        return list(res.all())


async def get_all_products_full() -> List[Dict[str, Any]]:
    """Возвращает все товары с категориями, вариантами веса и типами."""
    async with session_maker() as session:
        prods = await session.scalars(select(Product).order_by(Product.id))
        result = []
        for p in prods.all():
            cat = await session.get(Category, p.category_id) if p.category_id else None
            variants = await session.scalars(select(ProductVariant).where(ProductVariant.product_id == p.id))
            types = await session.scalars(select(ProductTypeOption).where(ProductTypeOption.product_id == p.id))
            var_list = list(variants.all())
            total_stock = sum(v.stock for v in var_list) if var_list else p.stock
            result.append({
                "product": p,
                "category_name": cat.name if cat else "Без категории",
                "variants": var_list,
                "types": list(types.all()),
                "total_stock": total_stock,
            })
        return result

