"""
Tests for late-night/cross-midnight transaction ingestion.

Validates that the DAY_START_OFFSET correctly groups transactions
occurring after midnight (e.g., 1 AM) with the previous business day.
"""
import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.data_upload import DataUpload
from src.models.transaction import Transaction
from src.services.csv_parser import ParseResult, ParsedRow
from src.services.ingestion import TransactionIngestionService


class TestMidnightCrossing:
    """Test that late-night transactions group with previous business day."""

    def test_1am_transaction_groups_with_previous_day(self, db, test_user_with_restaurant):
        """
        A transaction at 1:00 AM on Dec 16 should be grouped with Dec 15's business day.
        This handles bars/clubs that operate past midnight.
        """
        _, test_restaurant = test_user_with_restaurant

        service = TransactionIngestionService(db, enable_menu_extraction=False)
        upload = DataUpload(
            id=uuid4(),
            restaurant_id=test_restaurant.id,
            status="PROCESSING"
        )
        db.add(upload)
        db.commit()

        # Create a transaction at 1:00 AM on Dec 16
        # This should be grouped with Dec 15's business day
        late_night = datetime(2024, 12, 16, 1, 0)  # 1:00 AM

        rows = [
            ParsedRow(
                row_number=1,
                date=late_night,
                item_name="Late Night Cocktail",
                raw_item_name="Late Night Cocktail",
                quantity=1,
                unit_price=Decimal("15.00"),
                total=Decimal("15.00")
            )
        ]

        result = ParseResult(
            parsed_rows=rows,
            errors=[],
            vendor="unknown",
            total_rows=1
        )

        service.ingest_transactions(
            restaurant_id=test_restaurant.id,
            upload_id=upload.id,
            parse_result=result,
            file_bytes=b"fake"
        )

        # Verify the transaction is stored with Dec 15 as the date
        tx = db.query(Transaction).filter(Transaction.upload_id == upload.id).first()
        assert tx is not None
        assert tx.transaction_date == date(2024, 12, 15), \
            f"Expected Dec 15, got {tx.transaction_date}"

    def test_3am_transaction_groups_with_previous_day(self, db, test_user_with_restaurant):
        """
        A transaction at 3:00 AM (before 4 AM cutoff) should group with previous day.
        """
        _, test_restaurant = test_user_with_restaurant

        service = TransactionIngestionService(db, enable_menu_extraction=False)
        upload = DataUpload(
            id=uuid4(),
            restaurant_id=test_restaurant.id,
            status="PROCESSING"
        )
        db.add(upload)
        db.commit()

        very_late = datetime(2024, 12, 16, 3, 30)  # 3:30 AM

        rows = [
            ParsedRow(
                row_number=1,
                date=very_late,
                item_name="After Hours Snack",
                raw_item_name="After Hours Snack",
                quantity=1,
                unit_price=Decimal("8.00"),
                total=Decimal("8.00")
            )
        ]

        result = ParseResult(
            parsed_rows=rows,
            errors=[],
            vendor="unknown",
            total_rows=1
        )

        service.ingest_transactions(
            restaurant_id=test_restaurant.id,
            upload_id=upload.id,
            parse_result=result,
            file_bytes=b"fake"
        )

        tx = db.query(Transaction).filter(Transaction.upload_id == upload.id).first()
        assert tx is not None
        assert tx.transaction_date == date(2024, 12, 15)

    def test_4am_transaction_belongs_to_current_day(self, db, test_user_with_restaurant):
        """
        A transaction at exactly 4:00 AM (the cutoff) should belong to the current day.
        """
        _, test_restaurant = test_user_with_restaurant

        service = TransactionIngestionService(db, enable_menu_extraction=False)
        upload = DataUpload(
            id=uuid4(),
            restaurant_id=test_restaurant.id,
            status="PROCESSING"
        )
        db.add(upload)
        db.commit()

        cutoff = datetime(2024, 12, 16, 4, 0)  # Exactly 4:00 AM

        rows = [
            ParsedRow(
                row_number=1,
                date=cutoff,
                item_name="Early Breakfast",
                raw_item_name="Early Breakfast",
                quantity=1,
                unit_price=Decimal("12.00"),
                total=Decimal("12.00")
            )
        ]

        result = ParseResult(
            parsed_rows=rows,
            errors=[],
            vendor="unknown",
            total_rows=1
        )

        service.ingest_transactions(
            restaurant_id=test_restaurant.id,
            upload_id=upload.id,
            parse_result=result,
            file_bytes=b"fake"
        )

        tx = db.query(Transaction).filter(Transaction.upload_id == upload.id).first()
        assert tx is not None
        assert tx.transaction_date == date(2024, 12, 16), \
            f"4 AM should be current day, got {tx.transaction_date}"

    def test_mixed_shift_groups_correctly(self, db, test_user_with_restaurant):
        """
        A shift spanning 8 PM - 2 AM should all group under the same business day.
        """
        _, test_restaurant = test_user_with_restaurant

        service = TransactionIngestionService(db, enable_menu_extraction=False)
        upload = DataUpload(
            id=uuid4(),
            restaurant_id=test_restaurant.id,
            status="PROCESSING"
        )
        db.add(upload)
        db.commit()

        # Shift: Dec 15 8 PM to Dec 16 2 AM
        rows = [
            ParsedRow(
                row_number=1,
                date=datetime(2024, 12, 15, 20, 0),  # 8 PM Dec 15
                item_name="Dinner",
                raw_item_name="Dinner",
                quantity=1,
                unit_price=Decimal("25.00"),
                total=Decimal("25.00")
            ),
            ParsedRow(
                row_number=2,
                date=datetime(2024, 12, 15, 23, 30),  # 11:30 PM Dec 15
                item_name="Drinks",
                raw_item_name="Drinks",
                quantity=2,
                unit_price=Decimal("10.00"),
                total=Decimal("20.00")
            ),
            ParsedRow(
                row_number=3,
                date=datetime(2024, 12, 16, 1, 30),  # 1:30 AM Dec 16
                item_name="Late Snack",
                raw_item_name="Late Snack",
                quantity=1,
                unit_price=Decimal("8.00"),
                total=Decimal("8.00")
            )
        ]

        result = ParseResult(
            parsed_rows=rows,
            errors=[],
            vendor="unknown",
            total_rows=3
        )

        service.ingest_transactions(
            restaurant_id=test_restaurant.id,
            upload_id=upload.id,
            parse_result=result,
            file_bytes=b"fake"
        )

        # All 3 items should be in ONE transaction for Dec 15
        transactions = db.query(Transaction).filter(
            Transaction.upload_id == upload.id
        ).all()

        assert len(transactions) == 1, f"Expected 1 transaction, got {len(transactions)}"
        assert transactions[0].transaction_date == date(2024, 12, 15)
        assert transactions[0].total_amount == Decimal("53.00")  # 25 + 20 + 8
