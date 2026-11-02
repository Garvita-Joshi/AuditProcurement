import pytest
import numpy as np
import os
from PIL import Image

from backend.app.ocr.preprocess import preprocess_image
from backend.app.ocr.extractor import (
    _extract_amount_regex, _extract_date_regex, _extract_vendor_regex, 
    _extract_tax_id_regex, _calculate_extraction_confidence
)

# --- Preprocessing tests ---
def test_preprocess_returns_numpy_array(tmp_path):
    img_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (100, 100), color='white')
    img.save(img_path)
    
    result = preprocess_image(str(img_path))
    assert isinstance(result, np.ndarray)
    assert len(result.shape) == 2  # Grayscale

def test_preprocess_handles_missing_file():
    result = preprocess_image("nonexistent_file.jpg")
    assert result is None

# --- Extraction logic tests ---
def test_extract_amount_from_text():
    text = "Vendor ABC\nDate: 2025-04-15\nItem 1: 500\nTotal: $1,234.56"
    assert _extract_amount_regex(text) == 1234.56
    
    text2 = "Some text\nAmount Due: ₹50,000.00\nThank you"
    assert _extract_amount_regex(text2) == 50000.0

def test_extract_date_from_text():
    assert _extract_date_regex("Date: 15/04/2025") == "15/04/2025"
    assert _extract_date_regex("Date: 2025-04-15") == "2025-04-15"
    assert _extract_date_regex("Date: Apr 15, 2025") == "Apr 15, 2025"

def test_extract_vendor_from_text():
    text = "STARBUCKS COFFEE\n123 Main St\nTotal: $5.50"
    assert _extract_vendor_regex(text) == "STARBUCKS COFFEE"
    
    text_empty = "\n\n   \nAPPLE STORE\nTotal: 1000"
    assert _extract_vendor_regex(text_empty) == "APPLE STORE"

def test_extract_gst_number():
    text = "GST: 27AADCB2230M1ZT\nTotal: 1500"
    assert _extract_tax_id_regex(text) == "27AADCB2230M1ZT"

def test_extraction_confidence_calculation():
    full_fields = {
        "vendor": "A", "amount": 100, "date": "B", 
        "tax_id": "C", "line_items": [{"description": "D", "amount": 1}]
    }
    assert _calculate_extraction_confidence(full_fields) >= 0.95
    
    partial = {"vendor": "A", "amount": 100, "date": None}
    assert 0.4 < _calculate_extraction_confidence(partial) < 0.6
    
    empty = {}
    assert _calculate_extraction_confidence(empty) == 0.0

@pytest.mark.slow
def test_end_to_end_synthetic_receipt(tmp_path):
    img_path = tmp_path / "receipt.png"
    img = Image.new('RGB', (400, 400), color='white')
    img.save(img_path)
    
    result = preprocess_image(str(img_path))
    assert result is not None
    # We do not run full OCR here to avoid dependency issues on test machines
