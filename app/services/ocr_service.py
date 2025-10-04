"""Placeholder OCR integration."""
from __future__ import annotations

from typing import Dict


def extract_expense_data(file_path: str) -> Dict[str, str]:
    """Placeholder for OCR-based receipt parsing."""
    # TODO: Integrate Tesseract or EasyOCR in Phase 2.
    return {
        "file_processed": file_path,
        "status": "pending_ocr",
    }
