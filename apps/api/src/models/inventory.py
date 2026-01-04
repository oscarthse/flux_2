"""
Inventory tracking models.
"""
import uuid
from sqlalchemy import Column, String, Text, Date, Numeric, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class Inventory(Base):
    """Current inventory levels for ingredients."""
    __tablename__ = "inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit = Column(String(50), nullable=False)
    batch_id = Column(String(100))
    expiry_date = Column(Date)
    received_date = Column(Date, server_default=func.current_date())
    unit_cost = Column(Numeric(10, 4))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")
    ingredient = relationship("Ingredient", back_populates="inventory_items")
    movements = relationship("InventoryMovement", back_populates="inventory")


class InventoryMovement(Base):
    """Audit trail for inventory changes."""
    __tablename__ = "inventory_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_id = Column(UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="SET NULL"))
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    movement_type = Column(String(50), nullable=False)  # received, used, wasted, adjusted, transferred
    quantity = Column(Numeric(10, 3), nullable=False)  # Positive for in, negative for out
    unit = Column(String(50), nullable=False)
    reference_id = Column(UUID(as_uuid=True))  # Transaction ID, order ID, etc.
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")
    inventory = relationship("Inventory", back_populates="movements")


class InventorySnapshot(Base):
    """
    Daily snapshot of menu item availability and stockout status.

    Used by ML models to account for censored demand - when an item
    sells out, observed sales underestimate true demand.

    Example: If Salmon sells out at 7pm, reported sales of 12 units
    understates true demand (could have been 20+). This bias accumulates
    and causes chronic underordering.
    """
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint('restaurant_id', 'menu_item_id', 'date', name='uq_inventory_snapshot_item_date'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)

    # Availability data
    available_qty = Column(Numeric(10, 0), nullable=True)  # How many were available at start of day
    stockout_flag = Column(String(1), default='N', nullable=False)  # 'Y' if item sold out, 'N' otherwise

    # Source of the data
    source = Column(String(50), nullable=False, default="manual")  # 'manual', 'inferred', 'pos_import'

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    restaurant = relationship("Restaurant")
    menu_item = relationship("MenuItem")
