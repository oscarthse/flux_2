
import pytest
from datetime import date, time, timedelta, datetime
from uuid import uuid4
from decimal import Decimal

from src.models.transaction import Transaction
from src.services.ingestion import TransactionIngestionService
from src.services.operating_hours import OperatingHoursService
from src.services.csv_parser import ParseResult, ParsedRow
from src.models.data_upload import DataUpload

def test_business_day_aggregation(db, test_user_with_restaurant):
    """Verify that transactions before 4AM are grouped with previous day."""
    _, test_restaurant = test_user_with_restaurant

    # Setup Ingestion
    service = TransactionIngestionService(db)
    upload = DataUpload(
        id=uuid4(),
        restaurant_id=test_restaurant.id,
        status="PROCESSING"
    )
    db.add(upload)
    db.commit()

    # Define Date: 2 days ago (safe from 90 day lookback)
    base_date = date.today() - timedelta(days=2)

    # Row 1: 23:00 on Day 1
    # Row 2: 02:00 on Day 2 (Should belong to Day 1 business day)

    rows = [
        ParsedRow(
            row_number=1,
            date=datetime.combine(base_date, time(23, 0)),
            item_name="Drink 1",
            raw_item_name="Drink 1",
            quantity=1,
            unit_price=Decimal("10.00"),
            total=Decimal("10.00")
        ),
        ParsedRow(
            row_number=2,
            date=datetime.combine(base_date + timedelta(days=1), time(2, 0)),
            item_name="Drink 2",
            raw_item_name="Drink 2",
            quantity=1,
            unit_price=Decimal("10.00"),
            total=Decimal("10.00")
        )
    ]

    result = ParseResult(
        parsed_rows=rows,
        errors=[],
        vendor="unknown",
        total_rows=2
    )

    # Execute Ingestion
    ingestion_result = service.ingest_transactions(
        restaurant_id=test_restaurant.id,
        upload_id=upload.id,
        parse_result=result,
        file_bytes=b"fake"
    )

    # Verify: Should be 1 Transaction row (for base_date)
    txs = db.query(Transaction).filter(Transaction.upload_id == upload.id).all()
    assert len(txs) == 1

    tx = txs[0]
    assert tx.transaction_date == base_date
    assert tx.total_amount == Decimal("20.00")

    # Verify Times
    # First order should be 23:00
    # Last order should be 02:00
    assert tx.first_order_time == time(23, 0)
    assert tx.last_order_time == time(2, 0)

def test_operating_hours_midnight_median(db, test_user_with_restaurant):
    """Verify median calculation across midnight."""
    _, test_restaurant = test_user_with_restaurant

    # Use recent dates (Sundays)
    # Today is Tuesday (in sim) -> -2 days is Sunday.
    # Find nearest Sunday in past
    base_date = date.today()
    while base_date.weekday() != 6: # Find Sunday
        base_date -= timedelta(days=1)

    sunday1 = base_date
    sunday2 = base_date - timedelta(days=7)

    tx1 = Transaction(
        restaurant_id=test_restaurant.id,
        transaction_date=sunday1,
        total_amount=Decimal("100"),
        first_order_time=time(18, 0),
        last_order_time=time(23, 50),
        is_promo=False
    )
    tx2 = Transaction(
        restaurant_id=test_restaurant.id,
        transaction_date=sunday2,
        total_amount=Decimal("100"),
        first_order_time=time(18, 0),
        last_order_time=time(0, 10),
        is_promo=False
    )
    db.add(tx1)
    db.add(tx2)
    db.commit()

    service = OperatingHoursService(db)
    hours = service.calculate_standard_hours(test_restaurant.id)

    sunday = hours["Sunday"]
    assert sunday is not None
    assert sunday["close"] == "00:00"
