"""
AuditAI — Image preprocessing for OCR.

Applies deskew, denoise, and binarization to receipt images before OCR extraction.
Handles both image files (JPEG, PNG) and PDFs (first page converted to image).
"""
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def _load_image(image_path: str) -> Optional[np.ndarray]:
    """Load an image file or the first page of a PDF as a numpy array."""
    path = Path(image_path)
    if not path.exists():
        logger.error("Image file not found: %s", image_path)
        return None

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        # Convert first page of PDF to image via Pillow
        try:
            pil_img = Image.open(path)
            pil_img = pil_img.convert("RGB")
            return np.array(pil_img)
        except Exception as e:
            logger.warning("PDF conversion failed for %s: %s", image_path, e)
            return None
    else:
        # Standard image file
        img = cv2.imread(str(path))
        if img is None:
            logger.warning("cv2.imread returned None for %s", image_path)
            # Fallback: try Pillow
            try:
                pil_img = Image.open(path).convert("RGB")
                return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            except Exception:
                return None
        return img


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert BGR image to grayscale."""
    if len(image.shape) == 2:
        return image  # Already grayscale
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _denoise(gray: np.ndarray) -> np.ndarray:
    """Apply Gaussian blur for noise reduction."""
    return cv2.GaussianBlur(gray, (5, 5), 0)


def _binarize(gray: np.ndarray) -> np.ndarray:
    """Adaptive thresholding for binarization."""
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )


def _deskew(image: np.ndarray) -> np.ndarray:
    """
    Detect skew angle via minAreaRect on contours and rotate if > 0.5 degrees.

    Returns the deskewed image, or the original if skew is negligible or detection fails.
    """
    try:
        # Find contours on inverted binary image
        inverted = cv2.bitwise_not(image)
        coords = np.column_stack(np.where(inverted > 0))

        if len(coords) < 10:
            return image

        # Get the minimum area rectangle
        angle = cv2.minAreaRect(coords)[-1]

        # minAreaRect returns angles in [-90, 0). Normalize:
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5:
            return image  # Skew is negligible

        # Rotate the image to correct skew
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, rotation_matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated

    except Exception as e:
        logger.warning("Deskew failed: %s", e)
        return image


def preprocess_image(image_path: str) -> Optional[np.ndarray]:
    """
    Full preprocessing pipeline for a receipt image.

    Steps:
      1. Load image (supports JPEG, PNG, PDF)
      2. Convert to grayscale
      3. Gaussian blur denoising
      4. Adaptive thresholding (binarization)
      5. Deskew via contour-based angle detection

    Args:
        image_path: Absolute or relative path to the image/PDF file.

    Returns:
        Preprocessed grayscale numpy array, or None if loading fails.
    """
    image = _load_image(image_path)
    if image is None:
        return None

    try:
        gray = _to_grayscale(image)
        denoised = _denoise(gray)
        binary = _binarize(denoised)
        deskewed = _deskew(binary)
        return deskewed
    except Exception as e:
        logger.error("Preprocessing failed for %s: %s", image_path, e)
        # Return grayscale fallback so OCR can still attempt extraction
        try:
            return _to_grayscale(image)
        except Exception:
            return image
