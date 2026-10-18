from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    deposits: Mapped[List["Deposit"]] = relationship("Deposit", back_populates="user", cascade="all, delete-orphan")
    tickets: Mapped[List["Ticket"]] = relationship("Ticket", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    products: Mapped[List["Product"]] = relationship("Product", back_populates="category", cascade="all, delete-orphan")


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    districts: Mapped[List["District"]] = relationship("District", back_populates="city", cascade="all, delete-orphan")


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    city: Mapped["City"] = relationship("City", back_populates="districts")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Числовое количество в наличии
    delivery_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Текст/инструкция/контакты при покупке
    product_type: Mapped[str] = mapped_column(String(32), default="stock", nullable=False)  # "stock" or "infinite_text"
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # if product_type == "infinite_text"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")
    variants: Mapped[List["ProductVariant"]] = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    type_options: Mapped[List["ProductTypeOption"]] = relationship("ProductTypeOption", back_populates="product", cascade="all, delete-orphan")
    items: Mapped[List["ProductItem"]] = relationship("ProductItem", back_populates="product", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="product")


class ProductVariant(Base):
    """Варианты веса / фасовки товара со своей отдельной ценой (200г, 500г, 1кг и т.д.)."""
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    weight_name: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "200г", "500г", "1кг"
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # Цена за этот вес
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Числовое количество для данного веса
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")



class ProductTypeOption(Base):
    """Типы товара / упаковки / доставки (например: Магнит, Тайник, Доставка)."""
    __tablename__ = "product_type_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="type_options")


class ProductItem(Base):
    """Единица товара на складе (ключ / аккаунт / координаты / адрес)."""
    __tablename__ = "product_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    city_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)
    district_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True)
    type_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    data: Mapped[str] = mapped_column(Text, nullable=False)
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="items")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(256), nullable=False)
    variant_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    city_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    district_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    type_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    delivered_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="orders")
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="orders")


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount_rub: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_btc: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    target_address: Mapped[str] = mapped_column(String(128), nullable=False)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, completed, expired
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="deposits")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)  # open, answered, closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="tickets")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
