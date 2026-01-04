"""
Pydantic schemas for CSV preview functionality.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class PreviewRow(BaseModel):
    """Preview of a single parsed row."""
    row_number: int
    date: datetime
    item_name: str
    raw_item_name: str
    quantity: int
    unit_price: Decimal
    total: Decimal
    warnings: List[str] = Field(default_factory=list)

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class PreviewError(BaseModel):
    """Error encountered during parsing."""
    row_number: int
    field: str
    message: str
    raw_value: Optional[str] = None


class CSVPreviewResponse(BaseModel):
    """Response for CSV preview endpoint."""
    vendor: str = Field(description="Detected POS vendor")
    encoding: str = Field(description="Detected file encoding")
    total_rows: int = Field(description="Total rows in file (or preview limit)")
    parsed_rows: List[PreviewRow] = Field(description="Successfully parsed rows")
    errors: List[PreviewError] = Field(description="Parse errors")
    warnings: List[str] = Field(default_factory=list, description="General warnings")
    success_rate: float = Field(description="Percentage of rows parsed successfully")
    schema_detected: bool = Field(description="Whether required columns were found")

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }
