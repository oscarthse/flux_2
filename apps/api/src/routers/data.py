"""
Data upload router for CSV ingestion.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.core.deps import get_current_user
from src.db.session import get_db
from src.models.data_upload import DataUpload
from src.models.restaurant import Restaurant
from src.models.user import User
from src.schemas.csv_preview import CSVPreviewResponse, PreviewError, PreviewRow
from src.schemas.data import (
    DataUploadList,
    DataUploadStatus,
    UploadResponse,
    UploadStatus,
)
from src.services.csv_parser import CSVParser
from src.services.ingestion import TransactionIngestionService

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/preview-csv", response_model=CSVPreviewResponse)
async def preview_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Preview CSV file with automatic POS vendor detection and parsing.

    Returns the first 10 parsed rows along with detected schema, encoding,
    and any parsing errors. Use this endpoint before full upload to validate
    the CSV format.

    Args:
        file: CSV file to preview

    Returns:
        CSVPreviewResponse with parsed preview data and errors
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    try:
        # Read file bytes
        content = await file.read()

        # Parse CSV with preview mode
        parser = CSVParser(max_preview_rows=10)
        result = parser.parse_csv(content, preview_mode=True)

        # Convert to response format
        preview_rows = [
            PreviewRow(
                row_number=row.row_number,
                date=row.date,
                item_name=row.item_name,
                raw_item_name=row.raw_item_name,
                quantity=row.quantity,
                unit_price=row.unit_price,
                total=row.total,
                warnings=row.warnings
            )
            for row in result.parsed_rows
        ]

        preview_errors = [
            PreviewError(
                row_number=error.row_number,
                field=error.field,
                message=error.message,
                raw_value=error.raw_value
            )
            for error in result.errors
        ]

        # Check if schema was detected (no header errors)
        schema_detected = not any(
            error.field == "headers" for error in result.errors
        )

        return CSVPreviewResponse(
            vendor=result.vendor.value,
            encoding=result.encoding,
            total_rows=result.total_rows,
            parsed_rows=preview_rows,
            errors=preview_errors,
            warnings=result.warnings,
            success_rate=result.success_rate,
            schema_detected=schema_detected
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview CSV: {str(e)}"
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CSV file with transaction data.

    Uses intelligent CSV parser to detect POS format and validate data.
    Includes file-level and row-level deduplication to prevent duplicate imports.

    Expected CSV formats:
    - Toast: Date, Menu Item, Qty, Price, Total
    - Square: Transaction Date, Item Name, Qty Sold, Item Price, Gross Sales
    - Lightspeed: Sale Date, Description, Quantity, Unit Price, Line Total
    - Clover: Order Date, Product Name, Quantity, Unit Price, Item Total
    - Generic: date, item, quantity, unit_price, total

    Returns:
        Upload status with statistics on rows processed, inserted, and skipped
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    # Get user's restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must have a restaurant to upload data"
        )

    # Create upload record
    upload = DataUpload(
        restaurant_id=restaurant.id,
        status=UploadStatus.PROCESSING.value,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    # Process CSV
    try:
        # Read file bytes
        content = await file.read()

        # Parse CSV using intelligent parser
        parser = CSVParser()
        parse_result = parser.parse_csv(content, preview_mode=False)

        # Check for critical parsing errors (missing columns, etc.)
        if parse_result.errors and any(e.field == "headers" for e in parse_result.errors):
            upload.status = UploadStatus.FAILED.value
            upload.errors = {
                "message": "Failed to detect CSV format or missing required columns",
                "errors": [{"field": e.field, "message": e.message} for e in parse_result.errors]
            }
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid CSV format: missing required columns"
            )

        # Ingest transactions with deduplication
        ingestion_service = TransactionIngestionService(db)
        ingestion_result = ingestion_service.ingest_transactions(
            restaurant_id=restaurant.id,
            upload_id=upload.id,
            parse_result=parse_result,
            file_bytes=content
        )

        # Check for file-level duplicate
        if ingestion_result.errors and any(e.get("type") == "duplicate_file" for e in ingestion_result.errors):
            upload.status = UploadStatus.FAILED.value
            upload.errors = ingestion_result.to_dict()
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This file has already been uploaded"
            )

        # Update upload status
        success_rate = (ingestion_result.rows_inserted / ingestion_result.rows_processed
                       if ingestion_result.rows_processed > 0 else 0)

        if success_rate == 1.0:
            upload.status = UploadStatus.COMPLETED.value
        elif success_rate > 0.5:
            upload.status = UploadStatus.COMPLETED.value  # Partial success still counts as completed
        else:
            upload.status = UploadStatus.FAILED.value

        upload.errors = ingestion_result.to_dict()
        db.commit()

        # Automatically run stockout detection after successful upload
        stockouts_detected = 0
        if upload.status == UploadStatus.COMPLETED.value and ingestion_result.rows_inserted > 0:
            try:
                from src.services.stockout_detection import StockoutDetectionService
                detection_service = StockoutDetectionService(db)

                # Analyze last 30 days for stockouts
                stockout_results = detection_service.detect_likely_stockouts(
                    restaurant_id=restaurant.id,
                    days_to_analyze=30
                )

                # Auto-save high-confidence stockouts (>= 0.8)
                from src.models.inventory import InventorySnapshot
                for result in stockout_results:
                    if result.confidence >= 0.8 and result.menu_item_id:
                        # Check if already exists
                        existing = db.query(InventorySnapshot).filter(
                            InventorySnapshot.restaurant_id == restaurant.id,
                            InventorySnapshot.menu_item_id == result.menu_item_id,
                            InventorySnapshot.date == result.detected_date
                        ).first()

                        if not existing:
                            new_snapshot = InventorySnapshot(
                                restaurant_id=restaurant.id,
                                menu_item_id=result.menu_item_id,
                                date=result.detected_date,
                                stockout_flag='Y',
                                source='auto_detected'
                            )
                            db.add(new_snapshot)
                            stockouts_detected += 1
                        elif existing.stockout_flag != 'Y':
                            existing.stockout_flag = 'Y'
                            existing.source = 'auto_detected'
                            stockouts_detected += 1

                if stockouts_detected > 0:
                    db.commit()
            except Exception as e:
                # Don't fail the upload if stockout detection fails
                # Just log the error
                import logging
                logging.warning(f"Stockout detection failed after upload {upload.id}: {str(e)}")

        # Build response message
        message_parts = []
        message_parts.append(f"Processed {ingestion_result.rows_processed} rows")
        message_parts.append(f"{ingestion_result.rows_inserted} inserted")
        if ingestion_result.rows_skipped_duplicate > 0:
            message_parts.append(f"{ingestion_result.rows_skipped_duplicate} duplicates skipped")
        if ingestion_result.rows_failed > 0:
            message_parts.append(f"{ingestion_result.rows_failed} failed")
        if stockouts_detected > 0:
            message_parts.append(f"{stockouts_detected} stockouts auto-detected")

        return UploadResponse(
            upload_id=upload.id,
            status=UploadStatus(upload.status),
            message=", ".join(message_parts)
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        upload.status = UploadStatus.FAILED.value
        upload.errors = {"error": str(e)}
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CSV: {str(e)}"
        )


@router.get("/uploads/{upload_id}", response_model=DataUploadStatus)
def get_upload_status(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the status of a specific upload."""
    # Get user's restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    upload = db.query(DataUpload).filter(
        DataUpload.id == upload_id,
        DataUpload.restaurant_id == restaurant.id
    ).first()

    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    errors_data = upload.errors or {}
    return DataUploadStatus(
        id=upload.id,
        status=UploadStatus(upload.status),
        rows_processed=errors_data.get("rows_processed"),
        rows_failed=errors_data.get("rows_failed"),
        errors=errors_data.get("errors"),
    )


@router.get("/uploads", response_model=DataUploadList)
def list_uploads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all uploads for the current user's restaurant."""
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        return DataUploadList(uploads=[])

    uploads = db.query(DataUpload).filter(
        DataUpload.restaurant_id == restaurant.id
    ).order_by(DataUpload.created_at.desc()).limit(20).all()

    result = []
    for upload in uploads:
        errors_data = upload.errors or {}
        result.append(DataUploadStatus(
            id=upload.id,
            status=UploadStatus(upload.status),
            rows_processed=errors_data.get("rows_processed"),
            rows_failed=errors_data.get("rows_failed"),
            errors=errors_data.get("errors"),
        ))

    return DataUploadList(uploads=result)

from src.services.data_health import DataHealthService
from src.schemas.data import DataHealthScoreResponse

@router.get("/health", response_model=DataHealthScoreResponse)
def get_data_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current data health score for the restaurant.

    Includes breakdown by component (completeness, consistency, timeliness, accuracy)
    and actionable recommendations to improve the score.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )

    service = DataHealthService(db)
    score = service.get_latest_score(restaurant.id)

    if not score:
        # Calculate initial score if none exists
        score = service.calculate_score(restaurant.id)

    return score
