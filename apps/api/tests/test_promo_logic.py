
import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, date

from src.models.transaction import Transaction
from src.services.ingestion import TransactionIngestionService
from src.services.csv_parser import ParseResult, ParsedRow
from src.models.data_upload import DataUpload

def test_promotion_detection_keyword(db, test_user_with_restaurant):
    """Verify that items with 'Discount' in name are flagged as promo."""
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

    # Create test data
    today = date.today()
    rows = [
        ParsedRow(
            row_number=1,
            date=datetime.combine(today, datetime.min.time()),
            item_name="Lunch Special Discount",
            raw_item_name="Lunch Special Discount",
            quantity=1,
            unit_price=Decimal("10.00"),
            total=Decimal("10.00")
        )
    ]

    result = ParseResult(
        parsed_rows=rows,
        errors=[],
        vendor="unknown",
        total_rows=1
    )

    # Execute
    ingestion_result = service.ingest_transactions(
        restaurant_id=test_restaurant.id,
        upload_id=upload.id,
        parse_result=result,
        file_bytes=b"fake_content"
    )

    # Verify
    assert ingestion_result.rows_inserted == 1

    tx = db.query(Transaction).filter(Transaction.restaurant_id == test_restaurant.id).first()
    assert tx is not None
    assert tx.is_promo is True, "Should be flagged as promo due to 'Discount' keyword"
    assert tx.discount_amount is None or tx.discount_amount == 0 # Price was positive, so no explicit discount amount extracted (unless logic changed)

def test_promotion_detection_negative_price(db, test_user_with_restaurant):
    """Verify that items with negative price are flagged as promo with amount."""
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

    # Create test data
    today = date.today()
    rows = [
        ParsedRow(
            row_number=1,
            date=datetime.combine(today, datetime.min.time()),
            item_name="Refund/Discount",
            raw_item_name="Refund/Discount",
            quantity=1,
            unit_price=Decimal("-5.00"),
            total=Decimal("-5.00")
        )
    ]

    result = ParseResult(
        parsed_rows=rows,
        errors=[],
        vendor="unknown",
        total_rows=1
    )

    # Execute
    ingestion_result = service.ingest_transactions(
        restaurant_id=test_restaurant.id,
        upload_id=upload.id,
        parse_result=result,
        file_bytes=b"fake_content_2"
    )

    # Verify
    tx = db.query(Transaction).filter(Transaction.upload_id == upload.id).first()
    assert tx.is_promo is True
    assert tx.discount_amount == Decimal("5.00"), "Should capture absolute value of negative total as discount"
