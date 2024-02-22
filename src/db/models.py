from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship
from sqlalchemy import Integer, BigInteger
from sqlalchemy import String
from sqlalchemy import ForeignKey
from sqlalchemy import DateTime
from sqlalchemy.sql import func

import datetime


class ShopifyBase(DeclarativeBase):
    pass


class ShopifyProduct(ShopifyBase):
    __tablename__ = "product"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    handle: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    product_type: Mapped[str] = mapped_column(String(50), nullable=True)

    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ShopifyVariant(ShopifyBase):
    __tablename__ = "variant"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(ShopifyProduct.id), nullable=False
    )
    product = relationship(ShopifyProduct, foreign_keys=[product_id])


class ShopifyInventory(ShopifyBase):
    __tablename__ = "inventory"
    id: Mapped[int] = mapped_column(
        Integer, autoincrement=True, primary_key=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(ShopifyVariant.id), nullable=False
    )
    variant = relationship(ShopifyVariant, foreign_keys=[variant_id])

    inventory_quantity: Mapped[int] = mapped_column(
        Integer, nullable=True, default=0
    )


class ShopifyMeta(ShopifyBase):
    __tablename__ = "meta"
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), primary_key=True
    )
    site_name: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)


class ShopifyCounter(ShopifyBase):
    __tablename__ = "total"
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        primary_key=True
    )
