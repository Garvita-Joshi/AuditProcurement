"""
AuditAI — Gemini API integration for structured field extraction and audit reports.

Two use cases:
  1. Structured extraction: OCR text → parsed receipt fields (fallback for regex)
  2. Audit report generation: flagged claim + SHAP explanation + OCR evidence → professional audit note

Gracefully degrades to template-based output if GEMINI_API_KEY is not set.
"""
import json
import logging
from typing import Any, Dict, Optional

from backend.app.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Initialize and cache the Gemini client. Returns None if no API key."""
    global _client
    if _client is not None:
        return _client
    if not GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY not set — LLM features will use template fallbacks.")
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _client = genai.GenerativeModel(GEMINI_MODEL)
        logger.info("Gemini client initialized with model: %s", GEMINI_MODEL)
        return _client
    except Exception as e:
        logger.error("Failed to initialize Gemini client: %s", e)
        return None


def extract_receipt_fields(raw_ocr_text: str) -> Dict[str, Any]:
    """
    Use Gemini to extract structured fields from OCR text.

    Args:
        raw_ocr_text: Raw text from OCR engine.

    Returns:
        Dict with keys: vendor, amount, date, tax_id, line_items.
        Empty dict if API unavailable or extraction fails.
    """
    client = _get_client()
    if not client:
        return {}

    prompt = (
        "Extract the following fields from this receipt text and return as JSON:\n"
        "- vendor (string): the business name\n"
        "- amount (number): the total amount paid\n"
        "- date (string): in YYYY-MM-DD format\n"
        "- tax_id (string or null): GST/EIN/VAT number if present\n"
        "- line_items (array): list of {description: string, amount: number}\n\n"
        f"Receipt text:\n{raw_ocr_text}\n\n"
        "Respond with ONLY valid JSON, no markdown formatting."
    )

    try:
        response = client.generate_content(prompt)
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse Gemini JSON response: %s", e)
        return {}
    except Exception as e:
        logger.warning("Gemini extraction failed: %s", e)
        return {}


def generate_audit_report(
    claim_data: Dict[str, Any],
    shap_explanation: Optional[Dict[str, float]] = None,
    ocr_evidence: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate a professional audit note for a flagged expense claim.

    Args:
        claim_data: Dict with claim_id, employee_name, vendor_name, claimed_amount,
                    claimed_date, category, combined_fraud_score.
        shap_explanation: Dict of feature_name → SHAP value (top features).
        ocr_evidence: Dict with extracted_vendor, extracted_amount, extracted_date,
                      raw_ocr_text.

    Returns:
        A concise, professional audit note string.
    """
    shap_explanation = shap_explanation or {}
    ocr_evidence = ocr_evidence or {}

    # Sort features by absolute SHAP value
    top_features = sorted(
        shap_explanation.items(),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:5] if shap_explanation else []

    client = _get_client()

    if not client:
        return _generate_template_report(claim_data, top_features, ocr_evidence)

    prompt = (
        "Generate a concise, professional audit note (2-3 sentences) for this "
        "flagged employee expense claim. Be specific about any discrepancies found.\n\n"
        f"Claim details: {json.dumps(claim_data, default=str)}\n"
        f"Top fraud indicators (SHAP values): {json.dumps(dict(top_features))}\n"
        f"OCR evidence from receipt: {json.dumps(ocr_evidence, default=str)}\n\n"
        "Example format:\n"
        '"Claim #4521 flagged: extracted receipt amount ₹340 does not match '
        "claimed ₹520; vendor 'Amazn Inc' is a near-match to no known vendor. "
        'Top contributing factors: amount_mismatch_ratio (0.35), vendor_anomaly_score (0.82)."\n\n'
        "Write the audit note:"
    )

    try:
        response = client.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.warning("Gemini audit report generation failed: %s", e)
        return _generate_template_report(claim_data, top_features, ocr_evidence)


def _generate_template_report(
    claim_data: Dict[str, Any],
    top_features: list,
    ocr_evidence: Dict[str, Any],
) -> str:
    """
    Template-based fallback when Gemini API is unavailable.

    Produces a structured audit note from the available data.
    """
    claim_id = claim_data.get("claim_id", "N/A")
    vendor = claim_data.get("vendor_name", "Unknown")
    claimed_amt = claim_data.get("claimed_amount", 0)
    score = claim_data.get("combined_fraud_score", 0)

    parts = [f"Claim {claim_id} flagged with fraud score {score:.2f}."]

    # Check for amount mismatch
    ocr_amt = ocr_evidence.get("extracted_amount")
    if ocr_amt is not None:
        try:
            ocr_val = float(ocr_amt)
            claimed_val = float(claimed_amt)
            if claimed_val > 0 and abs(ocr_val - claimed_val) / claimed_val > 0.05:
                parts.append(
                    f"Receipt amount (₹{ocr_val:,.2f}) does not match "
                    f"claimed amount (₹{claimed_val:,.2f})."
                )
        except (ValueError, TypeError):
            pass

    # Check for vendor mismatch
    ocr_vendor = ocr_evidence.get("extracted_vendor")
    if ocr_vendor and ocr_vendor.lower() != vendor.lower():
        parts.append(
            f"Receipt vendor '{ocr_vendor}' differs from claimed vendor '{vendor}'."
        )

    # Add top contributing factors
    if top_features:
        factors = ", ".join(
            f"{name} ({value:+.3f})" for name, value in top_features[:3]
        )
        parts.append(f"Key contributing factors: {factors}.")

    return " ".join(parts)
