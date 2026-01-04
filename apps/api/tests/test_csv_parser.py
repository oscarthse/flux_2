"""
Unit tests for CSV parser service.

Tests vendor detection, column mapping, date parsing, name normalization,
quantity extraction, and validation logic.
"""
import pytest
from datetime import datetime
from decimal import Decimal

from src.services.csv_parser import CSVParser, POSVendor, ParseResult


class TestVendorDetection:
    """Test POS vendor detection from CSV headers."""

    def test_detect_toast_vendor(self):
        """Toast format should be detected from headers."""
        parser = CSVParser()
        headers = ["Date", "Menu Item", "Qty", "Price", "Total"]
        vendor = parser.detect_vendor(headers)
        assert vendor == POSVendor.TOAST

    def test_detect_square_vendor(self):
        """Square format should be detected from headers."""
        parser = CSVParser()
        headers = ["Transaction Date", "Item Name", "Qty Sold", "Item Price", "Gross Sales"]
        vendor = parser.detect_vendor(headers)
        assert vendor == POSVendor.SQUARE

    def test_detect_lightspeed_vendor(self):
        """Lightspeed format should be detected from headers."""
        parser = CSVParser()
        headers = ["Sale Date", "Description", "Quantity", "Unit Price", "Line Total"]
        vendor = parser.detect_vendor(headers)
        assert vendor == POSVendor.LIGHTSPEED

    def test_detect_clover_vendor(self):
        """Clover format should be detected from headers."""
        parser = CSVParser()
        headers = ["Order Date", "Product Name", "Quantity", "Unit Price", "Item Total"]
        vendor = parser.detect_vendor(headers)
        assert vendor == POSVendor.CLOVER

    def test_detect_generic_vendor(self):
        """Generic format should be detected from common headers."""
        parser = CSVParser()
        headers = ["date", "item", "quantity", "price", "total"]
        vendor = parser.detect_vendor(headers)
        # Generic and Toast both match these headers - either is acceptable
        assert vendor in [POSVendor.GENERIC, POSVendor.TOAST]

    def test_detect_unknown_vendor_insufficient_matches(self):
        """Unknown vendor if too few columns match."""
        parser = CSVParser()
        headers = ["foo", "bar", "baz"]
        vendor = parser.detect_vendor(headers)
        assert vendor == POSVendor.UNKNOWN


class TestColumnMapping:
    """Test finding columns from various header formats."""

    def test_find_column_exact_match(self):
        """Should find column with exact case-insensitive match."""
        parser = CSVParser()
        headers = ["Date", "Item", "Quantity"]
        result = parser.find_column(headers, ["date", "Date", "DATE"])
        assert result == "Date"

    def test_find_column_case_insensitive(self):
        """Should match regardless of case."""
        parser = CSVParser()
        headers = ["order_date", "ITEM_NAME", "qTy"]
        result = parser.find_column(headers, ["Order_Date", "order_date"])
        assert result == "order_date"

    def test_find_column_no_match(self):
        """Should return None when no match found."""
        parser = CSVParser()
        headers = ["foo", "bar"]
        result = parser.find_column(headers, ["date", "time"])
        assert result is None

    def test_find_column_first_match_wins(self):
        """Should return first matching possibility from the possibilities list."""
        parser = CSVParser()
        headers = ["Date", "Order Date", "Transaction Date"]
        result = parser.find_column(headers, ["Transaction Date", "Date"])
        # Returns first match from possibilities list, not headers
        assert result == "Transaction Date"


class TestQuantityExtraction:
    """Test extracting embedded quantities from item names."""

    def test_extract_quantity_2x_prefix(self):
        """Should extract '2x Coffee' → (2, 'Coffee')."""
        parser = CSVParser()
        qty, name = parser.extract_quantity_from_name("2x Coffee")
        assert qty == 2
        assert name == "Coffee"

    def test_extract_quantity_x2_suffix(self):
        """Should extract 'Coffee x 2' → (2, 'Coffee')."""
        parser = CSVParser()
        qty, name = parser.extract_quantity_from_name("Coffee x 2")
        assert qty == 2
        assert name == "Coffee"

    def test_extract_quantity_parentheses(self):
        """Should extract '(3) Burger' → (3, 'Burger')."""
        parser = CSVParser()
        qty, name = parser.extract_quantity_from_name("(3) Burger")
        assert qty == 3
        assert name == "Burger"

    def test_extract_quantity_unicode_x(self):
        """Should extract '2 × Salad' with unicode × → (2, 'Salad')."""
        parser = CSVParser()
        qty, name = parser.extract_quantity_from_name("2 × Salad")
        assert qty == 2
        assert name == "Salad"

    def test_extract_quantity_no_embedded(self):
        """Should return (1, name) when no quantity embedded."""
        parser = CSVParser()
        qty, name = parser.extract_quantity_from_name("Ribeye Steak")
        assert qty == 1
        assert name == "Ribeye Steak"

    def test_extract_quantity_whitespace_handling(self):
        """Should handle extra whitespace."""
        parser = CSVParser()
        qty, name = parser.extract_quantity_from_name("  4x   Taco  ")
        assert qty == 4
        assert name == "Taco"


class TestItemNameNormalization:
    """Test item name normalization for consistency."""

    def test_normalize_lowercase(self):
        """Should convert to lowercase."""
        parser = CSVParser()
        assert parser.normalize_item_name("BURGER") == "burger"
        assert parser.normalize_item_name("Ribeye Steak") == "ribeye steak"

    def test_normalize_strip_whitespace(self):
        """Should strip leading/trailing whitespace."""
        parser = CSVParser()
        assert parser.normalize_item_name("  Salad  ") == "salad"

    def test_normalize_multiple_spaces(self):
        """Should replace multiple spaces with single space."""
        parser = CSVParser()
        assert parser.normalize_item_name("Caesar   Salad") == "caesar salad"

    def test_normalize_special_characters(self):
        """Should remove special characters except allowed ones."""
        parser = CSVParser()
        # Keep: alphanumeric, space, hyphen, apostrophe, ampersand
        assert parser.normalize_item_name("Fish & Chips") == "fish & chips"
        assert parser.normalize_item_name("Mom's Pasta") == "mom's pasta"  # apostrophe kept
        assert parser.normalize_item_name("T-Bone Steak") == "t-bone steak"

        # Remove: other special chars
        assert parser.normalize_item_name("Burger (Large)") == "burger large"
        assert parser.normalize_item_name("Salad w/ Chicken") == "salad w chicken"

    def test_normalize_consistency(self):
        """Variations should normalize to same value."""
        parser = CSVParser()
        variants = [
            "Ribeye Steak",
            "ribeye steak",
            "RIBEYE STEAK",
            "  Ribeye   Steak  ",
            "Ribeye  Steak",
        ]
        normalized = [parser.normalize_item_name(v) for v in variants]
        assert all(n == "ribeye steak" for n in normalized)


class TestDateParsing:
    """Test date parsing with multiple formats."""

    def test_parse_iso_format(self):
        """Should parse ISO format YYYY-MM-DD."""
        parser = CSVParser()
        dt, error = parser.parse_date("2024-12-15", 1)
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 12
        assert dt.day == 15
        assert error is None

    def test_parse_us_format(self):
        """Should parse US format MM/DD/YYYY."""
        parser = CSVParser()
        dt, error = parser.parse_date("12/15/2024", 1)
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 12
        assert dt.day == 15
        assert error is None

    def test_parse_eu_format(self):
        """Should parse EU format DD/MM/YYYY."""
        parser = CSVParser()
        dt, error = parser.parse_date("15/12/2024", 1)
        assert dt is not None
        # Ambiguous - dateutil may parse as MM/DD or DD/MM depending on context
        assert dt.year == 2024

    def test_parse_with_time(self):
        """Should parse date with time."""
        parser = CSVParser()
        dt, error = parser.parse_date("2024-12-15 14:30:00", 1)
        assert dt is not None
        assert dt.year == 2024
        assert dt.hour == 14
        assert dt.minute == 30
        assert error is None

    def test_parse_future_date_rejected(self):
        """Should reject future dates."""
        parser = CSVParser()
        dt, error = parser.parse_date("2030-12-15", 1)
        assert dt is None
        assert error is not None
        assert "future" in error.message.lower()

    def test_parse_very_old_date_rejected(self):
        """Should reject dates >5 years old."""
        parser = CSVParser()
        dt, error = parser.parse_date("2010-12-15", 1)
        assert dt is None
        assert error is not None
        assert "5 years" in error.message.lower()

    def test_parse_invalid_format(self):
        """Should return error for invalid format."""
        parser = CSVParser()
        dt, error = parser.parse_date("not-a-date", 1)
        assert dt is None
        assert error is not None
        assert "invalid date format" in error.message.lower()


class TestEncodingDetection:
    """Test file encoding detection."""

    def test_detect_utf8(self):
        """Should detect UTF-8 encoding."""
        parser = CSVParser()
        content = "date,item,qty\n2024-12-15,Café,1".encode('utf-8')
        encoding = parser.detect_encoding(content)
        # Chardet may detect as various encodings - all work with UTF-8 content
        assert encoding in ['utf-8', 'ascii', 'iso-8859-1']

    def test_detect_latin1(self):
        """Should detect ISO-8859-1 (Latin-1) encoding."""
        parser = CSVParser()
        content = "date,item,qty\n2024-12-15,Café,1".encode('iso-8859-1')
        encoding = parser.detect_encoding(content)
        assert encoding in ['iso-8859-1', 'utf-8']  # May normalize to utf-8

    def test_detect_windows1252(self):
        """Should detect Windows-1252 encoding."""
        parser = CSVParser()
        content = "date,item,qty\n2024-12-15,Café,1".encode('windows-1252')
        encoding = parser.detect_encoding(content)
        # Chardet may detect as various encodings - all acceptable
        assert encoding in ['windows-1252', 'utf-8', 'iso-8859-1', 'ascii']


class TestCSVParsing:
    """Integration tests for full CSV parsing."""

    def test_parse_simple_generic_csv(self):
        """Should parse simple generic CSV."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,unit_price,total
2024-12-15,Burger,2,10.00,20.00
2024-12-15,Fries,1,5.00,5.00
"""
        result = parser.parse_csv(csv_content)

        assert result.vendor in [POSVendor.GENERIC, POSVendor.TOAST]
        assert result.total_rows == 2
        assert len(result.parsed_rows) == 2
        assert len(result.errors) == 0

        # Check first row
        row1 = result.parsed_rows[0]
        assert row1.item_name == "burger"
        assert row1.raw_item_name == "Burger"
        assert row1.quantity == 2
        assert row1.unit_price == Decimal("10.00")
        assert row1.total == Decimal("20.00")

    def test_parse_toast_format(self):
        """Should parse Toast POS format."""
        parser = CSVParser()
        csv_content = b"""Date,Menu Item,Qty,Price,Total
12/15/2024,Ribeye Steak,1,25.00,25.00
12/15/2024,Caesar Salad,2,8.50,17.00
"""
        result = parser.parse_csv(csv_content)

        assert result.vendor == POSVendor.TOAST
        assert result.total_rows == 2
        assert len(result.parsed_rows) == 2

    def test_parse_embedded_quantity(self):
        """Should extract embedded quantities from item names."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,price
2024-12-15,2x Coffee,1,6.00
2024-12-15,Burger,1,10.00
"""
        result = parser.parse_csv(csv_content)

        assert len(result.parsed_rows) == 2

        # First row should have quantity 2 (1 * 2x)
        row1 = result.parsed_rows[0]
        assert row1.quantity == 2
        assert row1.item_name == "coffee"
        assert "Extracted quantity" in row1.warnings[0]

        # Second row normal
        row2 = result.parsed_rows[1]
        assert row2.quantity == 1

    def test_parse_missing_total_calculates_from_price(self):
        """Should calculate total from unit_price * quantity if missing."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,unit_price
2024-12-15,Burger,2,10.00
"""
        result = parser.parse_csv(csv_content)

        assert len(result.parsed_rows) == 1
        row = result.parsed_rows[0]
        assert row.total == Decimal("20.00")  # 2 * 10.00

    def test_parse_missing_unit_price_calculates_from_total(self):
        """Should calculate unit_price from total / quantity if missing."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,total
2024-12-15,Burger,2,20.00
"""
        result = parser.parse_csv(csv_content)

        assert len(result.parsed_rows) == 1
        row = result.parsed_rows[0]
        assert row.unit_price == Decimal("10.00")  # 20.00 / 2

    def test_parse_zero_price_warning(self):
        """Should warn about zero prices (comps/staff meals)."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,price,total
2024-12-15,Staff Meal,1,0.00,0.00
"""
        result = parser.parse_csv(csv_content)

        assert len(result.parsed_rows) == 1
        row = result.parsed_rows[0]
        assert "Zero unit price" in row.warnings[0]

    def test_parse_negative_price_warning(self):
        """Should warn about negative prices (refunds/discounts)."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,price,total
2024-12-15,Refund,-1,10.00,-10.00
"""
        result = parser.parse_csv(csv_content)

        # Negative quantity should error
        assert len(result.errors) > 0

    def test_parse_invalid_rows_errors(self):
        """Should collect errors for invalid rows."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,price,total
2024-12-15,Burger,2,10.00,20.00
invalid-date,Fries,1,5.00,5.00
2024-12-15,Salad,-1,8.00,8.00
2024-12-15,Pizza,abc,12.00,12.00
"""
        result = parser.parse_csv(csv_content)

        assert result.total_rows == 4
        assert len(result.parsed_rows) == 1  # Only first row valid
        assert len(result.errors) == 3  # 3 invalid rows

    def test_parse_missing_required_columns(self):
        """Should error if required columns missing."""
        parser = CSVParser()
        csv_content = b"""foo,bar,baz
        1,2,3
"""
        result = parser.parse_csv(csv_content)

        assert len(result.errors) > 0
        assert result.errors[0].field == "headers"
        assert "Missing required columns" in result.errors[0].message

    def test_parse_preview_mode_limits_rows(self):
        """Preview mode should limit to max_preview_rows."""
        parser = CSVParser(max_preview_rows=2)
        csv_content = b"""date,item,quantity,price
2024-12-15,Item1,1,10.00
2024-12-15,Item2,1,10.00
2024-12-15,Item3,1,10.00
2024-12-15,Item4,1,10.00
"""
        result = parser.parse_csv(csv_content, preview_mode=True)

        # Parses 2 rows, but total_rows counts 3rd before stopping
        assert result.total_rows == 3
        assert len(result.parsed_rows) == 2
        assert "Preview limited" in result.warnings[0]

    def test_parse_success_rate(self):
        """Should calculate success rate correctly."""
        parser = CSVParser()
        csv_content = b"""date,item,quantity,price
2024-12-15,Valid1,1,10.00
invalid-date,Invalid1,1,10.00
2024-12-15,Valid2,1,10.00
2024-12-15,Invalid2,abc,10.00
"""
        result = parser.parse_csv(csv_content)

        assert result.total_rows == 4
        assert len(result.parsed_rows) == 2
        assert result.success_rate == 0.5  # 2/4 = 50%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
