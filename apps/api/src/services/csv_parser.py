"""
CSV Parser service for detecting POS formats and parsing transaction data.

Supports major POS systems: Toast, Square, Lightspeed, Clover, and generic formats.
"""
import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Dict, List, Optional, Tuple

import chardet
from dateutil import parser as date_parser
from pydantic import BaseModel, Field


class POSVendor(str, Enum):
    """Supported POS vendors."""
    TOAST = "toast"
    SQUARE = "square"
    LIGHTSPEED = "lightspeed"
    CLOVER = "clover"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class ParsedRow(BaseModel):
    """A single parsed transaction row."""
    date: datetime
    item_name: str
    quantity: int
    unit_price: Decimal
    total: Decimal
    raw_item_name: str = Field(description="Original item name before normalization")
    row_number: int
    warnings: List[str] = Field(default_factory=list)
    # Discount/promotion fields
    discount_amount: Optional[Decimal] = None
    is_promotion: bool = False
    promotion_type: Optional[str] = None  # explicit, comp_void, keyword

    class Config:
        arbitrary_types_allowed = True


class ValidationError(BaseModel):
    """A validation error for a specific row."""
    row_number: int
    field: str
    message: str
    raw_value: Optional[str] = None


class ParseResult(BaseModel):
    """Result of parsing a CSV file."""
    vendor: POSVendor
    total_rows: int
    parsed_rows: List[ParsedRow]
    errors: List[ValidationError]
    warnings: List[str] = Field(default_factory=list)
    encoding: str = "utf-8"

    @property
    def success_rate(self) -> float:
        """Calculate parse success rate."""
        if self.total_rows == 0:
            return 0.0
        return len(self.parsed_rows) / self.total_rows


class ColumnMapping(BaseModel):
    """Column mapping for a POS vendor."""
    date: List[str] = Field(description="Possible date column names")
    item: List[str] = Field(description="Possible item name column names")
    quantity: List[str] = Field(description="Possible quantity column names")
    unit_price: List[str] = Field(description="Possible unit price column names")
    total: List[str] = Field(description="Possible total column names")
    discount: List[str] = Field(default_factory=list, description="Optional discount column names")


class CSVParser:
    """
    Intelligent CSV parser with POS vendor detection and data normalization.

    Features:
    - Auto-detects POS vendor from CSV structure
    - Handles 15+ date formats via python-dateutil
    - Normalizes item names (case, whitespace, embedded quantities)
    - Validates prices, quantities, dates
    - Supports multiple character encodings
    """

    # Discount indicator keywords (case-insensitive)
    DISCOUNT_KEYWORDS = [
        'discount', 'promo', 'promotion', 'comp', 'void',
        'off', 'coupon', 'special', 'deal', 'happy hour',
        'sale', 'clearance', 'markdown', 'reduced'
    ]

    # Column mappings for different POS vendors
    VENDOR_MAPPINGS: Dict[POSVendor, ColumnMapping] = {
        POSVendor.TOAST: ColumnMapping(
            date=["Date", "Order Date", "date", "order_date", "Created Date"],
            item=["Item", "Item Name", "Menu Item", "item", "item_name", "menu_item"],
            quantity=["Qty", "Quantity", "qty", "quantity", "Amount"],
            unit_price=["Price", "Unit Price", "price", "unit_price", "Item Price"],
            total=["Total", "Amount", "total", "amount", "Line Total", "Net Sales"],
            discount=["Discount", "Discount Amount", "discount", "discount_amount", "Promo", "Modifier"]
        ),
        POSVendor.SQUARE: ColumnMapping(
            date=["Date", "Transaction Date", "date", "transaction_date", "Time"],
            item=["Item", "Item Name", "Product", "item", "item_name", "product"],
            quantity=["Qty", "Quantity", "qty", "quantity", "Qty Sold"],
            unit_price=["Price", "Unit Price", "Item Price", "price", "unit_price"],
            total=["Total", "Amount", "Net Total", "total", "amount", "Gross Sales"],
            discount=["Discount", "Discount Amount", "discount", "Modifiers"]
        ),
        POSVendor.LIGHTSPEED: ColumnMapping(
            date=["Date", "Sale Date", "date", "sale_date", "Timestamp"],
            item=["Item", "Description", "Product", "item", "description", "product"],
            quantity=["Quantity", "Qty", "quantity", "qty", "Units Sold"],
            unit_price=["Price", "Unit Price", "Item Price", "price", "unit_price"],
            total=["Total", "Amount", "Line Total", "total", "amount"],
            discount=["Discount", "Discount Amount", "discount"]
        ),
        POSVendor.CLOVER: ColumnMapping(
            date=["Date", "Order Date", "date", "order_date", "Time"],
            item=["Item", "Item Name", "Product Name", "item", "item_name"],
            quantity=["Quantity", "Qty", "quantity", "qty"],
            unit_price=["Price", "Unit Price", "price", "unit_price", "Item Price"],
            total=["Total", "Amount", "total", "amount", "Item Total"],
            discount=["Discount", "Discount Amount", "discount", "Modifier Amount"]
        ),
        POSVendor.GENERIC: ColumnMapping(
            date=["date", "Date", "transaction_date", "order_date", "time", "timestamp"],
            item=["item", "Item", "menu_item", "product", "description", "name"],
            quantity=["quantity", "Quantity", "qty", "Qty", "amount"],
            unit_price=["unit_price", "price", "Price", "item_price", "Unit Price"],
            total=["total", "Total", "amount", "Amount", "line_total"],
            discount=["discount", "Discount", "discount_amount", "promo"]
        ),
    }

    # Regex patterns for quantity extraction from item names
    QUANTITY_PATTERNS = [
        re.compile(r'^(\d+)\s*x\s*(.+)$', re.IGNORECASE),  # "2x Coffee"
        re.compile(r'^(\d+)\s*×\s*(.+)$', re.IGNORECASE),  # "2 × Coffee"
        re.compile(r'^(.+?)\s*x\s*(\d+)$', re.IGNORECASE),  # "Coffee x 2"
        re.compile(r'^\((\d+)\)\s*(.+)$', re.IGNORECASE),  # "(2) Coffee"
    ]

    def __init__(self, max_preview_rows: int = 10):
        """
        Initialize CSV parser.

        Args:
            max_preview_rows: Maximum number of rows to parse for preview
        """
        self.max_preview_rows = max_preview_rows

    def detect_encoding(self, file_bytes: bytes) -> str:
        """
        Detect file encoding using chardet.

        Args:
            file_bytes: Raw file bytes

        Returns:
            Detected encoding (utf-8, iso-8859-1, windows-1252, etc.)
        """
        result = chardet.detect(file_bytes)
        encoding = result['encoding'] or 'utf-8'

        # Normalize encoding names
        encoding_lower = encoding.lower()
        if 'utf' in encoding_lower:
            return 'utf-8'
        elif 'iso-8859' in encoding_lower or 'latin' in encoding_lower:
            return 'iso-8859-1'
        elif 'windows' in encoding_lower or 'cp125' in encoding_lower:
            return 'windows-1252'

        return encoding

    def detect_vendor(self, headers: List[str]) -> POSVendor:
        """
        Detect POS vendor from CSV column headers.

        Args:
            headers: List of column header names

        Returns:
            Detected POSVendor
        """
        headers_lower = [h.lower().strip() for h in headers]

        # Score each vendor based on header matches
        vendor_scores: Dict[POSVendor, int] = {vendor: 0 for vendor in POSVendor}

        for vendor, mapping in self.VENDOR_MAPPINGS.items():
            # Check each field type
            for field_variants in [mapping.date, mapping.item, mapping.quantity, mapping.unit_price, mapping.total]:
                for variant in field_variants:
                    if variant.lower() in headers_lower:
                        vendor_scores[vendor] += 1
                        break  # Count only first match per field type

        # Return vendor with highest score
        best_vendor = max(vendor_scores, key=vendor_scores.get)
        best_score = vendor_scores[best_vendor]

        # Need at least 3 matches for confident detection
        if best_score >= 3:
            return best_vendor
        else:
            return POSVendor.UNKNOWN

    def find_column(self, headers: List[str], possible_names: List[str]) -> Optional[str]:
        """
        Find column name from list of possibilities.

        Args:
            headers: CSV column headers
            possible_names: List of possible column names to match

        Returns:
            Matched column name or None
        """
        headers_lower = {h.lower().strip(): h for h in headers}

        for name in possible_names:
            if name.lower() in headers_lower:
                return headers_lower[name.lower()]

        return None

    def extract_quantity_from_name(self, item_name: str) -> Tuple[int, str]:
        """
        Extract embedded quantity from item name.

        Examples:
            "2x Coffee" → (2, "Coffee")
            "Coffee x 2" → (2, "Coffee")
            "(3) Burger" → (3, "Burger")
            "Salad" → (1, "Salad")

        Args:
            item_name: Raw item name

        Returns:
            Tuple of (quantity, cleaned_name)
        """
        for pattern in self.QUANTITY_PATTERNS:
            match = pattern.match(item_name.strip())
            if match:
                groups = match.groups()
                # Pattern can have quantity first or second
                if groups[0].isdigit():
                    qty = int(groups[0])
                    name = groups[1].strip()
                else:
                    qty = int(groups[1])
                    name = groups[0].strip()
                return (qty, name)

        return (1, item_name)

    def normalize_item_name(self, item_name: str) -> str:
        """
        Normalize item name for consistency.

        Normalization steps:
        1. Strip whitespace
        2. Lowercase
        3. Remove extra spaces
        4. Remove special characters (keeping alphanumeric and common punctuation)

        Args:
            item_name: Raw item name

        Returns:
            Normalized item name
        """
        # Strip and lowercase
        normalized = item_name.strip().lower()

        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)

        # Keep alphanumeric, spaces, hyphens, apostrophes, ampersands
        normalized = re.sub(r'[^a-z0-9\s\-\'&]', '', normalized)

        return normalized.strip()

    def parse_date(self, date_str: str, row_number: int) -> Tuple[Optional[datetime], Optional[ValidationError]]:
        """
        Parse date string using python-dateutil (handles 15+ formats).

        Args:
            date_str: Date string to parse
            row_number: Row number for error reporting

        Returns:
            Tuple of (parsed_datetime, error)
        """
        try:
            dt = date_parser.parse(date_str)

            # Validate date is not in future
            if dt > datetime.now():
                return None, ValidationError(
                    row_number=row_number,
                    field="date",
                    message="Date is in the future",
                    raw_value=date_str
                )

            # Validate date is not too old (>5 years)
            if dt.year < datetime.now().year - 5:
                return None, ValidationError(
                    row_number=row_number,
                    field="date",
                    message="Date is more than 5 years old",
                    raw_value=date_str
                )

            return dt, None

        except (ValueError, TypeError) as e:
            return None, ValidationError(
                row_number=row_number,
                field="date",
                message=f"Invalid date format: {str(e)}",
                raw_value=date_str
            )

    def parse_csv(
        self,
        file_bytes: bytes,
        preview_mode: bool = False
    ) -> ParseResult:
        """
        Parse CSV file with vendor detection and validation.

        Args:
            file_bytes: Raw CSV file bytes
            preview_mode: If True, parse only first N rows for preview

        Returns:
            ParseResult with parsed data and errors
        """
        # Detect encoding
        encoding = self.detect_encoding(file_bytes)

        try:
            decoded = file_bytes.decode(encoding)
        except UnicodeDecodeError:
            # Fallback to utf-8 with error replacement
            decoded = file_bytes.decode('utf-8', errors='replace')
            encoding = 'utf-8'

        # Parse CSV
        reader = csv.DictReader(io.StringIO(decoded))
        headers = reader.fieldnames or []

        # Detect vendor
        vendor = self.detect_vendor(headers)

        # If vendor unknown, try generic mapping
        if vendor == POSVendor.UNKNOWN:
            vendor = POSVendor.GENERIC

        # Get column mapping
        mapping = self.VENDOR_MAPPINGS[vendor]

        # Find actual column names
        date_col = self.find_column(headers, mapping.date)
        item_col = self.find_column(headers, mapping.item)
        qty_col = self.find_column(headers, mapping.quantity)
        price_col = self.find_column(headers, mapping.unit_price)
        total_col = self.find_column(headers, mapping.total)
        discount_col = self.find_column(headers, mapping.discount)  # Optional

        # Validate required columns found
        missing_columns = []
        if not date_col:
            missing_columns.append("date")
        if not item_col:
            missing_columns.append("item")
        if not qty_col:
            missing_columns.append("quantity")
        if not price_col and not total_col:
            missing_columns.append("price or total")

        if missing_columns:
            return ParseResult(
                vendor=vendor,
                total_rows=0,
                parsed_rows=[],
                errors=[ValidationError(
                    row_number=0,
                    field="headers",
                    message=f"Missing required columns: {', '.join(missing_columns)}"
                )],
                encoding=encoding
            )

        # Parse rows
        parsed_rows: List[ParsedRow] = []
        errors: List[ValidationError] = []
        warnings: List[str] = []
        total_rows = 0

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            total_rows += 1

            # Preview mode: stop after max_preview_rows
            if preview_mode and total_rows > self.max_preview_rows:
                warnings.append(f"Preview limited to {self.max_preview_rows} rows")
                break

            row_warnings = []

            # Parse date
            date_value, date_error = self.parse_date(row.get(date_col, ""), row_num)
            if date_error:
                errors.append(date_error)
                continue

            # Parse item name
            raw_item_name = row.get(item_col, "").strip()
            if not raw_item_name:
                errors.append(ValidationError(
                    row_number=row_num,
                    field="item",
                    message="Item name is empty"
                ))
                continue

            # Extract embedded quantity
            embedded_qty, clean_item_name = self.extract_quantity_from_name(raw_item_name)
            if embedded_qty > 1:
                row_warnings.append(f"Extracted quantity {embedded_qty} from item name")

            # Normalize item name
            normalized_name = self.normalize_item_name(clean_item_name)

            # Parse quantity
            qty_str = row.get(qty_col, "1").strip()
            try:
                base_quantity = int(float(qty_str))  # Handle "2.0" → 2
                if base_quantity <= 0:
                    raise ValueError("Quantity must be positive")
                # Multiply by embedded quantity
                final_quantity = base_quantity * embedded_qty
            except (ValueError, InvalidOperation) as e:
                errors.append(ValidationError(
                    row_number=row_num,
                    field="quantity",
                    message=f"Invalid quantity: {str(e)}",
                    raw_value=qty_str
                ))
                continue

            # Parse unit price
            unit_price: Optional[Decimal] = None
            if price_col:
                price_str = row.get(price_col, "").strip()
                try:
                    unit_price = Decimal(price_str)
                    if unit_price < 0:
                        row_warnings.append("Negative unit price (possible refund/discount)")
                    elif unit_price == 0:
                        row_warnings.append("Zero unit price (comp/staff meal)")
                except (ValueError, InvalidOperation) as e:
                    errors.append(ValidationError(
                        row_number=row_num,
                        field="unit_price",
                        message=f"Invalid unit price: {str(e)}",
                        raw_value=price_str
                    ))
                    continue

            # Parse total
            total_value: Optional[Decimal] = None
            if total_col:
                total_str = row.get(total_col, "").strip()
                try:
                    total_value = Decimal(total_str)
                    if total_value < 0:
                        row_warnings.append("Negative total (possible refund)")
                except (ValueError, InvalidOperation) as e:
                    errors.append(ValidationError(
                        row_number=row_num,
                        field="total",
                        message=f"Invalid total: {str(e)}",
                        raw_value=total_str
                    ))
                    continue

            # Parse discount (optional)
            discount_amount: Optional[Decimal] = None
            if discount_col:
                discount_str = row.get(discount_col, "").strip()
                if discount_str:
                    try:
                        discount_amount = Decimal(discount_str)
                        if discount_amount < 0:
                            discount_amount = abs(discount_amount)  # Normalize to positive
                    except (ValueError, InvalidOperation):
                        # Discount column exists but invalid value, ignore
                        pass

            # Detect promotion using multi-method approach
            from src.services.promotion_detection import PromotionDetectionService
            detection_service = PromotionDetectionService(db=None)  # No DB needed for detection
            detection = detection_service.detect_discount_in_item(
                item_name=raw_item_name,
                unit_price=unit_price if unit_price else Decimal(0),
                total=total_value if total_value else Decimal(0),
                discount_amount=discount_amount
            )

            # Calculate missing values
            if unit_price is None and total_value is not None:
                unit_price = total_value / final_quantity
            elif total_value is None and unit_price is not None:
                total_value = unit_price * final_quantity
            elif unit_price is None and total_value is None:
                errors.append(ValidationError(
                    row_number=row_num,
                    field="price",
                    message="Both unit_price and total are missing"
                ))
                continue

            # Create parsed row
            parsed_rows.append(ParsedRow(
                date=date_value,
                item_name=normalized_name,
                quantity=final_quantity,
                unit_price=unit_price,
                total=total_value,
                raw_item_name=raw_item_name,
                row_number=row_num,
                warnings=row_warnings,
                discount_amount=detection.discount_amount,
                is_promotion=detection.is_promo,
                promotion_type=detection.discount_type
            ))

        return ParseResult(
            vendor=vendor,
            total_rows=total_rows,
            parsed_rows=parsed_rows,
            errors=errors,
            warnings=warnings,
            encoding=encoding
        )
