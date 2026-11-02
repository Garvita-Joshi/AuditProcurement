"""Commercial quotation email reply parser.

Uses Gemini 2.5 Flash for accurate natural language extraction of commercial terms
(prices, delivery lead times, payment terms, and warranty coverage) from incoming vendor
quotation replies, with a deterministic regex fallback.
"""
import os
import re
import json


def _clean_number(val) -> float | None:
    if val is None:
        return None
    try:
        s = str(val).replace(',', '').replace(' ', '').strip()
        f = float(s)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def _parse_with_gemini(reply_text: str, quantity: int = 1, currency: str = 'INR') -> dict | None:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = (
            f"You are a commercial procurement auditor. Extract the quoted terms from this vendor email reply.\n"
            f"Target requested quantity is {quantity} and currency is {currency}.\n\n"
            f"Vendor Email Reply:\n\"\"\"\n{reply_text[:4000]}\n\"\"\"\n"
        )

        schema = {
            'type': 'OBJECT',
            'properties': {
                'total_price': {'type': 'NUMBER'},
                'unit_price': {'type': 'NUMBER'},
                'currency': {'type': 'STRING'},
                'lead_time_days': {'type': 'INTEGER'},
                'payment_terms': {'type': 'STRING'},
                'warranty': {'type': 'STRING'},
                'summary': {'type': 'STRING'},
            },
            'required': ['total_price', 'currency', 'lead_time_days', 'payment_terms', 'warranty', 'summary'],
        }

        resp = client.models.generate_content(
            model=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_json_schema': schema,
                'temperature': 0.1,
            },
        )

        if not resp.text:
            return None

        data = json.loads(resp.text)
        total_p = _clean_number(data.get('total_price'))
        unit_p = _clean_number(data.get('unit_price'))

        if total_p and not unit_p and quantity > 0:
            unit_p = round(total_p / quantity, 2)
        elif unit_p and not total_p and quantity > 0:
            total_p = round(unit_p * quantity, 2)

        lead_days = data.get('lead_time_days')
        if lead_days is not None:
            try:
                lead_days = int(lead_days)
            except (ValueError, TypeError):
                lead_days = None

        return {
            'total_price': total_p,
            'unit_price': unit_p,
            'currency': data.get('currency') or currency,
            'lead_time_days': lead_days,
            'payment_terms': data.get('payment_terms') or 'Net 30',
            'warranty': data.get('warranty') or 'Standard warranty',
            'summary': data.get('summary') or 'Vendor quotation received.',
        }
    except Exception:
        return None


def _parse_with_regex(reply_text: str, quantity: int = 1, currency: str = 'INR') -> dict:
    text = reply_text.replace('\r', '\n')

    # 1. Total Price search
    total_price = None
    # Pattern matching lines like: *Total Price...:* INR 109,150 or Total: INR 1,71,100
    tot_match = re.search(
        r'(?:total\s+price|grand\s+total|all[\s-]inclusive)[^\n\d]*?(?:INR|Rs\.?|₹|\$)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)',
        text, re.IGNORECASE
    )
    if tot_match:
        total_price = _clean_number(tot_match.group(1))

    # 2. Unit Price search
    unit_price = None
    unit_match = re.search(
        r'(?:unit\s+price|per\s+unit|each|rate\s+per\s+item)[^\n\d]*?(?:INR|Rs\.?|₹|\$)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)',
        text, re.IGNORECASE
    )
    if unit_match:
        unit_price = _clean_number(unit_match.group(1))

    # Derive missing price
    if total_price and not unit_price and quantity > 0:
        unit_price = round(total_price / quantity, 2)
    elif unit_price and not total_price and quantity > 0:
        total_price = round(unit_price * quantity, 2)

    # Fallback to largest figure in text if still none
    if not total_price:
        candidates = []
        for m in re.finditer(r'(?:INR|Rs\.?|₹|\$)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{2})?|[0-9]{4,}(?:\.[0-9]{2})?)', text, re.IGNORECASE):
            val = _clean_number(m.group(1))
            if val and val > 100:  # ignore tiny numbers like taxes or list numbers
                candidates.append(val)
        if candidates:
            total_price = max(candidates)
            if quantity > 0:
                unit_price = round(total_price / quantity, 2)

    # 3. Delivery Lead time in days
    lead_days = None
    # Match: *Delivery Lead Time:* 5 business days or delivery in 4 days
    lead_match = re.search(
        r'(?:lead\s*time|delivery(?:\s*lead\s*time)?|ships?\s*in|delivered?\s*in)[^\n\d]*?(\d+)\s*(?:business\s*days|working\s*days|days|weeks)',
        text, re.IGNORECASE
    )
    if lead_match:
        try:
            lead_days = int(lead_match.group(1))
            if 'week' in lead_match.group(0).lower():
                lead_days *= 7
        except ValueError:
            pass

    if lead_days is None:
        lead_match2 = re.search(r'(\d+)\s*(?:business\s*days|working\s*days)', text, re.IGNORECASE)
        if lead_match2:
            try:
                lead_days = int(lead_match2.group(1))
            except ValueError:
                pass

    # 4. Payment terms
    terms_match = re.search(r'(Net\s*\d+|PIA|Advance|Payment\s+in\s+advance|Immediate|50%\s*advance)', text, re.IGNORECASE)
    terms = terms_match.group(1) if terms_match else 'Net 30'

    # 5. Warranty
    warranty_match = re.search(
        r'(\d+[- ]*(?:year|yr|month|mo)[^\n\.,;]*?(?:warranty|support|onsite|coverage)[^\n\.,;]*)',
        text, re.IGNORECASE
    )
    warranty = warranty_match.group(1).strip() if warranty_match else 'Standard warranty included'

    summary_parts = []
    if total_price:
        summary_parts.append(f"Quoted {currency} {total_price:,.2f}")
        if unit_price:
            summary_parts.append(f"({currency} {unit_price:,.2f}/unit)")
    if lead_days:
        summary_parts.append(f"in {lead_days} days")
    if terms:
        summary_parts.append(f"with {terms}")
    if warranty:
        summary_parts.append(f"({warranty})")

    summary = ' '.join(summary_parts) if summary_parts else 'Vendor response received.'

    return {
        'total_price': total_price,
        'unit_price': unit_price,
        'currency': currency,
        'lead_time_days': lead_days,
        'payment_terms': terms,
        'warranty': warranty,
        'summary': summary,
    }


def parse_commercial_reply(reply_text: str, quantity: int = 1, currency: str = 'INR') -> dict:
    """Parse vendor quotation reply text with Gemini 2.5 Flash, falling back to deterministic regex."""
    if not reply_text:
        return {
            'total_price': None,
            'unit_price': None,
            'currency': currency,
            'lead_time_days': None,
            'payment_terms': None,
            'warranty': None,
            'summary': 'No reply text provided.',
        }

    gemini_result = _parse_with_gemini(reply_text, quantity=quantity, currency=currency)
    if gemini_result and gemini_result.get('total_price'):
        return gemini_result

    return _parse_with_regex(reply_text, quantity=quantity, currency=currency)
