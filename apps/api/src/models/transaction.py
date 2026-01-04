"""
Transaction and TransactionItem models for storing sales data.
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Integer, Date, func, Index, Boolean, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class Transaction(Base):
    """A sales transaction (e.g., a customer order/receipt)."""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    transaction_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.id", ondelete="SET NULL"), nullable=True)
    source_hash = Column(String(64), nullable=True)
    stockout_occurred = Column(Boolean, nullable=True, default=None)
    is_promo = Column(Boolean, nullable=False, default=False)
    discount_amount = Column(Numeric(10, 2), nullable=True)
    first_order_time = Column(Time, nullable=True)
    last_order_time = Column(Time, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="transactions")
    upload = relationship("DataUpload")
    items = relationship("TransactionItem", back_populates="transaction", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_transactions_restaurant_date', 'restaurant_id', 'transaction_date'),
        Index('idx_transactions_source_hash', 'restaurant_id', 'source_hash'),
    )


class TransactionItem(Base):
    """A line item within a transaction."""
    __tablename__ = "transaction_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    menu_item_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    source_hash = Column(String(64), nullable=True)
    promotion_id = Column(UUID(as_uuid=True), ForeignKey("promotions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    transaction = relationship("Transaction", back_populates="items")
    promotion = relationship("Promotion", back_populates="transaction_items")
