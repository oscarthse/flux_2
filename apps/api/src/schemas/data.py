"""
Data-related Pydantic schemas for CSV upload and validation.
"""
from pydantic import BaseModel, field_validator
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, List, Dict
from enum import Enum


class UploadStatus(str, Enum):
    """Status of a data upload."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TransactionRow(BaseModel):
    """Schema for validating a CSV row."""
    date: date
    menu_item: str
    quantity: int
    unit_price: Decimal
    total: Decimal

    @field_validator('quantity')
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError('quantity must be positive')
        return v

    @field_validator('unit_price', 'total')
    @classmethod
    def price_positive(cls, v):
        if v < 0:
            raise ValueError('prices cannot be negative')
        return v


class UploadResponse(BaseModel):
    """Response after initiating an upload."""
    upload_id: UUID
    status: UploadStatus
    message: str


class DataUploadStatus(BaseModel):
    """Status of a data upload."""
    id: UUID
    status: UploadStatus
    rows_processed: Optional[int] = None
    rows_failed: Optional[int] = None
    errors: Optional[list] = None

    class Config:
        from_attributes = True


class DataUploadList(BaseModel):
    """List of uploads for a user."""
    uploads: list[DataUploadStatus]


class DataHealthScoreResponse(BaseModel):
    """Data health score response."""
    overall_score: float
    completeness_score: float
    consistency_score: float
    timeliness_score: float
    accuracy_score: float
    component_breakdown: Dict
    recommendations: List[Dict]
    calculated_at: datetime

    class Config:
        from_attributes = True
