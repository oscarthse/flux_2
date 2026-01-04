
import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, date, time

from src.models.transaction import Transaction
from src.services.ingestion import TransactionIngestionService
from src.services.csv_parser import ParseResult, ParsedRow
from src.models.data_upload import DataUpload

def test_operating_hours_capture(db, test_user_with_restaurant):
    """Verify that first and last order times are captured."""
    _, test_restaurant = test_user_with_restaurant

    # Setup
    service = TransactionIngestionService(db)
    upload = DataUpload(
        id=uuid4(),
        restaurant_id=test_restaurant.id,
        status="PROCESSING"
    )
    db.add(upload)
    db.commit()

    # Create test data for a single day
    today = date.today()
    # 09:00 AM, 12:30 PM, 05:00 PM
    rows = [
        ParsedRow(
            row_number=1,
            date=datetime.combine(today, time(9, 0)),
            item_name="Breakfast",
            raw_item_name="Breakfast",
            quantity=1,
            unit_price=Decimal("10.00"),
            total=Decimal("10.00")
        ),
        ParsedRow(
            row_number=2,
            date=datetime.combine(today, time(12, 30)),
            item_name="Lunch",
            raw_item_name="Lunch",
            quantity=1,
            unit_price=Decimal("15.00"),
            total=Decimal("15.00")
        ),
        ParsedRow(
            row_number=3,
            date=datetime.combine(today, time(17, 0)),
            item_name="Dinner early",
            raw_item_name="Dinner early",
            quantity=1,
            unit_price=Decimal("20.00"),
            total=Decimal("20.00")
        )
    ]

    result = ParseResult(
        parsed_rows=rows,
        errors=[],
        vendor="unknown",
        total_rows=3
    )

    # Execute
    service.ingest_transactions(
        restaurant_id=test_restaurant.id,
        upload_id=upload.id,
        parse_result=result,
        file_bytes=b"fake"
    )

    # Verify
    tx = db.query(Transaction).filter(Transaction.upload_id == upload.id).first()
    assert tx is not None
    assert tx.first_order_time == time(9, 0)
    assert tx.last_order_time == time(17, 0)
