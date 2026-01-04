import sys
import os
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import get_settings
from src.core.security import hash_password
from src.models.user import User
from src.models.restaurant import Restaurant
from src.models.menu import MenuItem
from src.models.inventory import InventorySnapshot
from src.models.transaction import Transaction
from src.models.data_health import DataHealthScore

def seed():
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    print("Checking for demo user...")
    email = "demo@flux.com"
    user = db.query(User).filter(User.email == email).first()

    if not user:
        print("Creating demo user...")
        user = User(
            email=email,
            hashed_password=hash_password("password")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        print("Demo user already exists.")

    # Check for restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == user.id).first()
    if not restaurant:
        print("Creating demo restaurant...")
        restaurant = Restaurant(name="Flux Bistro", owner_id=user.id)
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

    # Create Menu Item
    item = db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant.id, MenuItem.name == "Signature Burger").first()
    if not item:
        item = MenuItem(
            restaurant_id=restaurant.id,
            name="Signature Burger",
            price=15.0,
            category_path="Mains",
            is_active=True
        )
        db.add(item)
        db.commit()
        db.refresh(item)

    # Create Inventory Snapshots (History)
    print("Seeding inventory history...")
    today = date.today()
    for i in range(30):
        day = today - timedelta(days=i)
        exists = db.query(InventorySnapshot).filter(
            InventorySnapshot.restaurant_id == restaurant.id,
            InventorySnapshot.menu_item_id == item.id,
            InventorySnapshot.date == day
        ).first()

        if not exists:
            # Simulate a few stockouts
            is_stockout = i in [3, 7, 12]
            snap = InventorySnapshot(
                restaurant_id=restaurant.id,
                menu_item_id=item.id,
                date=day,
                available_qty=0 if is_stockout else 20,
                stockout_flag='Y' if is_stockout else 'N',
                source='manual'
            )
            db.add(snap)

    # Create Transactions with Stockout flag logic if needed
    # Actually, transactions are needed for Completeness/Consistency scores (Data Health typically checks transactions or uploads)
    # The current DataHealthService checks 'Transaction' counts or 'DataUpload' logs.
    # Let's add some Transactions too so the completeness score isn't 0.

    print("Seeding transactions...")
    for i in range(30):
        # Create a transaction for each day
        day = today - timedelta(days=i)

        # Check if transaction exists (simple check)
        exists = db.query(Transaction).filter(
            Transaction.restaurant_id == restaurant.id,
            Transaction.transaction_date == day
        ).first()

        if not exists:
            tx = Transaction(
                id=uuid4(),
                restaurant_id=restaurant.id,
                transaction_date=day,
                total_amount=Decimal("45.00")
            )
            db.add(tx)

    db.commit()
    print("Seeding complete!")
    print(f"Login with: {email} / password")

if __name__ == "__main__":
    seed()
