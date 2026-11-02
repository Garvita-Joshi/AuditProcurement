"""
AuditAI — Dual-engine OCR: PaddleOCR (primary) with pytesseract fallback.

The engine automatically detects which OCR library is available and falls back
gracefully. A module-level singleton `ocr_engine` is provided for reuse.
"""
import logging
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)


class OcrEngine:
    """
    Dual-engine OCR that tries PaddleOCR first and falls back to pytesseract.

    Usage:
        from backend.app.ocr.engine import ocr_engine
        text, confidence, method = ocr_engine.extract_text(preprocessed_image)
    """

    def __init__(self):
        self._paddle_ocr = None
        self._paddle_available = False
        self._tesseract_available = False

        # Try to initialize PaddleOCR
        try:
            from paddleocr import PaddleOCR
            self._paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
            )
            self._paddle_available = True
            logger.info("PaddleOCR initialized successfully.")
        except Exception as e:
            logger.warning("PaddleOCR not available: %s. Will use pytesseract.", e)

        # Check if pytesseract is available
        try:
            import pytesseract  # noqa: F401
            self._tesseract_available = True
            logger.info("pytesseract available as fallback.")
        except ImportError:
            logger.warning("pytesseract not available either.")

    def extract_text(self, image: np.ndarray) -> Tuple[str, float, str]:
        """
        Extract text from a preprocessed image.

        Args:
            image: Preprocessed numpy array (grayscale or BGR).

        Returns:
            Tuple of (raw_text, confidence_0_to_1, method_used).
            method_used is one of 'paddleocr', 'tesseract', or 'failed'.
        """
        if image is None or image.size == 0:
            return ("", 0.0, "failed")

        # Try PaddleOCR first
        if self._paddle_available:
            try:
                text, confidence = self._extract_paddle(image)
                if text.strip():
                    return (text, confidence, "paddleocr")
                logger.info("PaddleOCR returned empty text, falling back.")
            except Exception as e:
                logger.warning("PaddleOCR extraction failed: %s", e)

        # Fallback to pytesseract
        if self._tesseract_available:
            try:
                text, confidence = self._extract_tesseract(image)
                return (text, confidence, "tesseract")
            except Exception as e:
                logger.warning("pytesseract extraction failed: %s", e)

        return ("", 0.0, "failed")

    def _extract_paddle(self, image: np.ndarray) -> Tuple[str, float]:
        """Run PaddleOCR and return (text, avg_confidence)."""
        result = self._paddle_ocr.ocr(image, cls=True)

        if not result or not result[0]:
            return ("", 0.0)

        lines = []
        confidences = []
        for line_info in result[0]:
            # Each line_info is [box_coords, (text, confidence)]
            if len(line_info) >= 2:
                text_conf = line_info[1]
                if isinstance(text_conf, (list, tuple)) and len(text_conf) >= 2:
                    lines.append(str(text_conf[0]))
                    confidences.append(float(text_conf[1]))

        raw_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return (raw_text, avg_confidence)

    def _extract_tesseract(self, image: np.ndarray) -> Tuple[str, float]:
        """Run pytesseract and return (text, avg_confidence)."""
        import pytesseract

        # Get plain text
        raw_text = pytesseract.image_to_string(image)

        # Get confidence from detailed data
        try:
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT
            )
            confidences = [
                int(c) for c in data.get("conf", [])
                if str(c).isdigit() and int(c) > 0
            ]
            avg_confidence = (
                sum(confidences) / len(confidences) / 100.0
                if confidences
                else 0.0
            )
        except Exception:
            avg_confidence = 0.5  # Default if data extraction fails

        return (raw_text, avg_confidence)


# Module-level singleton for reuse across the application
ocr_engine = OcrEngine()
