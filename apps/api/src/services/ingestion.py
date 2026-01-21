"""
Transaction ingestion service with deduplication and batch processing.
"""
import hashlib
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.data_upload import DataUpload
from src.models.ingestion_log import IngestionLog
from src.models.transaction import Transaction, TransactionItem
from src.services.csv_parser import ParsedRow, ParseResult
from src.services.menu_extraction import MenuItemExtractionService
from src.core.business_day import get_business_date, BUSINESS_DAY_START_HOUR


class IngestionResult:
    """Result of ingestion operation."""
    def __init__(self):
        self.rows_processed = 0
        self.rows_inserted = 0
        self.rows_skipped_duplicate = 0
        self.rows_failed = 0
        self.items_created = 0
        self.items_found = 0
        self.price_changes_detected = 0
        self.errors: List[Dict] = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "rows_processed": self.rows_processed,
            "rows_inserted": self.rows_inserted,
            "rows_skipped_duplicate": self.rows_skipped_duplicate,
            "rows_failed": self.rows_failed,
            "items_created": self.items_created,
            "items_found": self.items_found,
            "price_changes_detected": self.price_changes_detected,
            "errors": self.errors[:10],  # Limit to first 10 errors
        }


class TransactionIngestionService:
    """
    Service for ingesting parsed CSV data into Transaction tables.

    Features:
    - File-level deduplication (hash entire file)
    - Row-level deduplication (hash individual rows)
    - Batch inserts for performance (1000 rows per batch)
    - Detailed error logging to IngestionLog table
    - Transaction atomicity (all-or-nothing per batch)
    """

    BATCH_SIZE = 1000

    def __init__(self, db: Session, enable_menu_extraction: bool = True):
        """
        Initialize ingestion service.

        Args:
            db: SQLAlchemy database session
            enable_menu_extraction: Whether to auto-create menu items (default True)
        """
        self.db = db
        self.enable_menu_extraction = enable_menu_extraction
        self.menu_extraction_service = MenuItemExtractionService(db) if enable_menu_extraction else None

    def compute_file_hash(self, file_bytes: bytes) -> str:
        """
        Compute SHA-256 hash of file content for deduplication.

        Args:
            file_bytes: Raw file bytes

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(file_bytes).hexdigest()

    def compute_row_hash(self, row: ParsedRow) -> str:
        """
        Compute hash of a single parsed row for deduplication.

        Hash is based on: date + item_name + quantity + unit_price + total

        Args:
            row: Parsed row data

        Returns:
            Hexadecimal hash string
        """
        hash_input = f"{row.date.isoformat()}|{row.item_name}|{row.quantity}|{row.unit_price}|{row.total}"
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

    def check_file_duplicate(
        self,
        restaurant_id: UUID,
        file_hash: str
    ) -> Optional[UUID]:
        """
        Check if file has already been uploaded.

        Args:
            restaurant_id: Restaurant UUID
            file_hash: SHA-256 hash of file content

        Returns:
            Upload ID if duplicate found, None otherwise
        """
        stmt = select(DataUpload.id).where(
            DataUpload.restaurant_id == restaurant_id,
            DataUpload.file_hash == file_hash,
            DataUpload.status == "COMPLETED"
        ).limit(1)

        result = self.db.execute(stmt).scalar_one_or_none()
        return result

    def get_existing_row_hashes(
        self,
        restaurant_id: UUID,
        row_hashes: List[str]
    ) -> set:
        """
        Get set of row hashes that already exist in database.

        Args:
            restaurant_id: Restaurant UUID
            row_hashes: List of row hashes to check

        Returns:
            Set of existing row hashes
        """
        # Query TransactionItem hashes by joining with Transaction to filter by restaurant
        stmt = (
            select(TransactionItem.source_hash)
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant_id,
                TransactionItem.source_hash.in_(row_hashes)
            )
        )

        results = self.db.execute(stmt).scalars().all()
        return set(r for r in results if r is not None)

    def log_error(
        self,
        upload_id: UUID,
        row_number: int,
        field: str,
        message: str,
        raw_value: Optional[str] = None,
        severity: str = "error"
    ):
        """
        Log ingestion error to database.

        Args:
            upload_id: Upload UUID
            row_number: Row number in CSV (1-indexed)
            field: Field name that caused error
            message: Error message
            raw_value: Raw value that caused error
            severity: Error severity (error, warning)
        """
        log_entry = IngestionLog(
            upload_id=upload_id,
            row_number=row_number,
            field=field,
            message=message,
            raw_value=raw_value,
            severity=severity
        )
        self.db.add(log_entry)

    def ingest_transactions(
        self,
        restaurant_id: UUID,
        upload_id: UUID,
        parse_result: ParseResult,
        file_bytes: bytes
    ) -> IngestionResult:
        """
        Ingest parsed CSV rows into Transaction and TransactionItem tables.

        Args:
            restaurant_id: Restaurant UUID
            upload_id: Upload UUID
            parse_result: Result from CSV parser
            file_bytes: Raw file bytes for file-level deduplication

        Returns:
            IngestionResult with statistics and errors
        """
        result = IngestionResult()

        # Check file-level duplicate
        file_hash = self.compute_file_hash(file_bytes)
        duplicate_upload_id = self.check_file_duplicate(restaurant_id, file_hash)

        if duplicate_upload_id:
            result.errors.append({
                "type": "duplicate_file",
                "message": f"File already uploaded (upload_id: {duplicate_upload_id})"
            })
            return result

        # Update upload with file hash
        upload = self.db.query(DataUpload).filter(DataUpload.id == upload_id).first()
        if upload:
            upload.file_hash = file_hash

        # Group rows by business date to create transactions
        transactions_by_date: Dict[str, List[ParsedRow]] = {}

        for row in parse_result.parsed_rows:
            # Use centralized business day logic (handles 4 AM cutoff consistently)
            # TODO: Add restaurant timezone support - for now assumes UTC
            business_date = get_business_date(row.date, restaurant_timezone=None)

            date_key = business_date.isoformat()
            if date_key not in transactions_by_date:
                transactions_by_date[date_key] = []
            transactions_by_date[date_key].append(row)

        # Compute row hashes for deduplication
        all_row_hashes = [self.compute_row_hash(row) for row in parse_result.parsed_rows]
        existing_hashes = self.get_existing_row_hashes(restaurant_id, all_row_hashes)

        # Extract and auto-create menu items if enabled
        if self.enable_menu_extraction and self.menu_extraction_service:
            items_data = [
                {
                    'name': row.item_name,
                    'price': row.unit_price,
                    'transaction_date': row.date
                }
                for row in parse_result.parsed_rows
            ]
            menu_items_map = self.menu_extraction_service.extract_items_from_transaction_data(
                restaurant_id=restaurant_id,
                items_data=items_data
            )
            result.items_created = sum(1 for item in menu_items_map.values() if item.auto_created)
            result.items_found = len(menu_items_map) - result.items_created
        else:
            menu_items_map = {}

        # Create transactions with batch processing
        for date_str, rows in transactions_by_date.items():
            # Calculate transaction total
            total_amount = sum(row.total for row in rows)

            # Calculate operating hours with offset logic
            row_times = [row.date.time() for row in rows]
            if row_times:
                # Normalize minutes relative to day start (4 AM)
                # 04:00 is 0, 05:00 is 60... 02:00 (next day) is 22*60
                def get_offset_minutes(t):
                    minutes = t.hour * 60 + t.minute
                    if t.hour < BUSINESS_DAY_START_HOUR:
                        minutes += 24 * 60
                    return minutes

                # Find min/max in "offset minute space"
                sorted_times = sorted(row_times, key=get_offset_minutes)
                first_order_time = sorted_times[0]
                last_order_time = sorted_times[-1]
            else:
                first_order_time = None
                last_order_time = None

            # Detect promotions using parsed discount information
            is_promo_day = False
            total_discount = Decimal("0.00")

            for row in rows:
                # Use promotion detection results from CSV parser
                if row.is_promotion:
                    is_promo_day = True
                    if row.discount_amount:
                        total_discount += row.discount_amount

            # Create transaction
            # Use date_str (adjusted for day start offset) as the transaction date
            from datetime import date as date_type
            adjusted_tx_date = date_type.fromisoformat(date_str)
            transaction = Transaction(
                restaurant_id=restaurant_id,
                transaction_date=adjusted_tx_date,
                total_amount=Decimal(str(total_amount)),
                upload_id=upload_id,
                is_promo=is_promo_day,
                discount_amount=total_discount if total_discount > 0 else None,
                first_order_time=first_order_time,
                last_order_time=last_order_time,
                source_hash=None  # Transactions don't have individual hashes, only items do
            )
            self.db.add(transaction)
            self.db.flush()  # Get transaction ID

            # Create transaction items
            for row in rows:
                result.rows_processed += 1

                # Compute row hash
                row_hash = self.compute_row_hash(row)

                # Check for duplicate
                if row_hash in existing_hashes:
                    result.rows_skipped_duplicate += 1
                    self.log_error(
                        upload_id=upload_id,
                        row_number=row.row_number,
                        field="row",
                        message="Duplicate row detected",
                        severity="warning"
                    )
                    continue

                # Create transaction item
                tx_item = TransactionItem(
                    transaction_id=transaction.id,
                    menu_item_name=row.item_name,
                    quantity=row.quantity,
                    unit_price=row.unit_price,
                    total=row.total,
                    source_hash=row_hash
                )
                self.db.add(tx_item)
                result.rows_inserted += 1

                # Mark hash as seen to avoid duplicates within same upload
                existing_hashes.add(row_hash)

        # Log any parsing errors from CSV parser
        for error in parse_result.errors:
            result.rows_failed += 1
            self.log_error(
                upload_id=upload_id,
                row_number=error.row_number,
                field=error.field,
                message=error.message,
                raw_value=error.raw_value,
                severity="error"
            )
            result.errors.append({
                "row": error.row_number,
                "field": error.field,
                "message": error.message
            })

        try:
            self.db.commit()

            # Recalculate data health score
            from src.services.data_health import DataHealthService
            health_service = DataHealthService(self.db)
            health_service.calculate_score(restaurant_id)

            # Run statistical promotion inference (non-blocking)
            try:
                from src.services.promotion_detection import PromotionDetectionService
                promo_service = PromotionDetectionService(self.db)
                promotions_inferred = promo_service.detect_and_save_promotions(
                    restaurant_id=restaurant_id,
                    confidence_threshold=0.6
                )
                if promotions_inferred > 0:
                    result.errors.append({
                        "type": "info",
                        "message": f"Detected {promotions_inferred} historical promotions from price patterns"
                    })
            except Exception as promo_error:
                # Don't fail ingestion if promotion detection fails
                result.errors.append({
                    "type": "warning",
                    "message": f"Promotion detection failed: {str(promo_error)}"
                })

        except Exception as e:
            self.db.rollback()
            result.errors.append({
                "type": "database_error",
                "message": f"Failed to commit transaction: {str(e)}"
            })
            raise

        return result
