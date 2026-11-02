"""Sourcing graph: company catalog -> public discovery -> ranked shortlist -> RFQ drafts."""
import re
from decimal import Decimal
from typing import TypedDict
from urllib.parse import quote_plus
from langgraph.graph import END, START, StateGraph
from backend.app.sourcing.catalog import load_catalog, search_catalog
from backend.app.sourcing.requirements import Requirements
from backend.app.agentic_ai.gemini import rank_candidates
from backend.app.agentic_ai.discovery import discover_public_vendors


class SourcingState(TypedDict, total=False):
    requirements: dict
    offers: list
    matches: list
    shortlist: list
    drafts: list
    matched_vendor_count: int
    excluded_offer_count: int
    ranking_method: str
    web_discovery: dict


def _catalog_search(state: SourcingState) -> dict:
    req = Requirements.model_validate(state['requirements'])
    offers = load_catalog()
    matched = search_catalog(req, offers)
    return {
        'offers': offers,
        'matches': matched,
        'matched_vendor_count': len({item['offer']['vendor_id'] for item in matched if item['status'] != 'excluded'}),
        'excluded_offer_count': sum(item.get('status') == 'excluded' for item in matched),
    }


def _public_discovery(state: SourcingState) -> dict:
    req = Requirements.model_validate(state['requirements'])
    known = list({offer.vendor_name for offer in state.get('offers', []) if getattr(offer, 'vendor_name', None)})
    return {'web_discovery': discover_public_vendors(req.model_dump(mode='json'), known)}


def _rank_offers(state: SourcingState) -> dict:
    req = Requirements.model_validate(state['requirements'])
    tokens = {part.casefold() for part in (req.product or '').split() if len(part) > 2}
    ranked, seen = [], set()

    for match in state.get('matches', []):
        offer = match['offer']
        if match.get('status') == 'excluded' or offer['vendor_id'] in seen:
            continue
        seen.add(offer['vendor_id'])

        text = f"{offer['product']} {offer.get('description') or ''} {offer.get('category') or ''}".casefold()
        keyword_count = sum(token in text for token in tokens)
        cost = float(match['estimated_total']) if match.get('estimated_total') else None
        budget = float(req.budget) if req.budget is not None else None

        reasons = list(match.get('reasons') or [f"Approved catalog match for {offer['product']}"])
        score = min(40, keyword_count * 15)

        if match.get('preference_match'):
            score += 25
            if 'Matches your preferred supplier' not in reasons:
                reasons.append('Matches your preferred supplier')

        if cost is not None and budget and budget > 0:
            if cost <= budget:
                score += 25
                if not any('within budget' in r for r in reasons):
                    reasons.append(f"Estimated catalog total {req.currency} {cost:,.2f} is within budget")
            else:
                score += 10
                if not any('exceeds target budget' in r for r in reasons):
                    reasons.append(f"Catalog list price {req.currency} {cost:,.2f} exceeds target budget; volume discount can be requested in RFQ")

        if offer.get('lead_time_days') is not None:
            score += 10
            reasons.append(f"Catalog lists an estimated {offer['lead_time_days']}-day lead time; confirm with supplier")
        if offer.get('avg_delivery_days') is not None:
            score += 5
            reasons.append(f"Company vendor record lists {offer['avg_delivery_days']} average delivery days")
        if offer.get('rating') is not None:
            score += round(float(offer['rating']) * 2)
            reasons.append(f"Company vendor record rating: {offer['rating']}/5")
        if cost is not None and not any('supplier quote' in r for r in reasons):
            reasons.append('Current price, shipping, tax, stock and terms require a supplier quote')

        ranked.append({**match, 'score': score, 'reasons': reasons})

    ranked.sort(key=lambda item: (
        not item.get('preference_match', False) if req.vendor_preference == 'prioritize' else False,
        -item['score'],
        float(item['estimated_total']) if item.get('estimated_total') else float('inf')
    ))

    # If no catalog offers matched, promote public web & LinkedIn discovery leads into the shortlist
    if not ranked:
        web_discovery = state.get('web_discovery') or {}
        public_leads = web_discovery.get('results') or []
        for idx, lead in enumerate(public_leads[:5], start=1):
            vendor_name = lead['name']
            lead_url = lead.get('website_url') or lead.get('source_url') or f"https://www.google.com/search?q={quote_plus(vendor_name)}"
            linkedin_url = lead.get('linkedin_url') or f"https://www.linkedin.com/search/results/companies/?keywords={quote_plus(vendor_name)}"
            google_url = lead.get('google_search_url') or f"https://www.google.com/search?q={quote_plus(vendor_name + ' ' + (req.product or ''))}"

            lead_offer = {
                'vendor_id': f"PUB_{idx:03d}",
                'vendor_name': vendor_name,
                'email': lead.get('contact_email') or f"contact@{re.sub(r'[^a-zA-Z0-9]', '', vendor_name).lower()}.com",
                'product': req.product or 'Requested Product / Service',
                'sku': f"LEAD-{idx:03d}",
                'currency': req.currency or 'INR',
                'unit_price': None,
                'shipping': '0.00',
                'tax': '0.00',
                'synthetic': False,
                'category': req.category,
                'is_external': True,
                'website_url': lead_url,
                'linkedin_url': linkedin_url,
                'google_search_url': google_url,
                'source_reference': f"Discovered via {lead.get('platform', 'Google/LinkedIn')}: {lead_url}",
            }

            ranked.append({
                'offer': lead_offer,
                'score': 65 - (idx * 5),
                'reasons': [
                    f"Discovered via {lead.get('platform', 'Google / LinkedIn')} for '{req.product}'",
                    lead.get('fit_reason') or lead.get('offering') or 'Supplier identified from external market search',
                    'External vendor: click Open in Google / LinkedIn to review profile and credentials',
                ],
                'status': 'public_lead',
                'estimated_total': None,
                'unverified': ['Delivery deadline and location', 'Pricing and terms', 'Vendor verification'],
                'rfq_draft': (
                    f"Please quote {req.quantity} units of {req.product}, delivered to "
                    f"{req.delivery_location or 'Jaipur, India'} by {req.delivery_deadline or 'propose date'}. "
                    f"Include shipping and tax in {req.currency}. Preferences: {req.specifications}. "
                    f"Mandatory conditions: {req.mandatory_conditions}. This inquiry is not an order."
                ),
            })

        ranking_method = 'AI Public Web & LinkedIn Discovery (External Suppliers)' if ranked else 'No vendors found'
        return {
            'shortlist': ranked[:10],
            'ranking_method': ranking_method,
            'matched_vendor_count': len(ranked),
        }

    # If catalog offers exist, use Gemini to re-order if available
    llm_order = rank_candidates(state['requirements'], ranked)
    if llm_order:
        order = {vendor_id: index for index, vendor_id in enumerate(llm_order['ranked_vendor_ids'])}
        ranked.sort(key=lambda item: (
            order.get(item['offer']['vendor_id'], len(order) + 100),
            -item['score'],
            float(item['estimated_total']) if item.get('estimated_total') else float('inf')
        ))
        for item in ranked:
            reason = llm_order['reason_by_vendor'].get(item['offer']['vendor_id'])
            if reason and reason not in item['reasons']:
                item['reasons'].insert(0, 'Gemini: ' + reason)

    return {
        'shortlist': ranked[:10],
        'ranking_method': 'Gemini + eligibility rules' if llm_order else 'Eligibility rules + price ordering',
        'matched_vendor_count': len(ranked),
    }


def _prepare_rfq(state: SourcingState) -> dict:
    req = Requirements.model_validate(state['requirements'])
    drafts = []
    for rank, item in enumerate(state.get('shortlist', []), start=1):
        offer = item['offer']
        is_external = bool(offer.get('is_external'))
        recipient_name = offer.get('contact_name') or offer.get('vendor_name') or 'Supplier'

        drafts.append({
            **item,
            'rank': rank,
            'status': 'public_lead' if is_external else item.get('status', 'draft_ready'),
            'rfq_subject': f"Request for quotation: {req.product or offer['product']}",
            'rfq_body': (
                f"Hello {recipient_name},\n\n"
                f"Please provide a quotation for {req.quantity} units of {req.product or offer['product']} ({offer.get('sku', 'standard')}). "
                f"Include total price, shipping, tax, availability, delivery lead time, warranty, and payment terms in {req.currency}. "
                f"Requested delivery location: {req.delivery_location or 'Jaipur, India'}. Target date: {req.delivery_deadline or 'please propose'}.\n\n"
                f"Requirements: {req.specifications or 'as described above'}. Mandatory conditions: {req.mandatory_conditions or 'please state any exceptions'}. "
                "This is a request for quotation, not a purchase order or commitment.\n\nRegards,\nProcurement"
            ),
        })
    return {'drafts': drafts}


def build_sourcing_graph():
    graph = StateGraph(SourcingState)
    graph.add_node('search_company_catalog', _catalog_search)
    graph.add_node('public_web_discovery', _public_discovery)
    graph.add_node('rank_eligible_offers', _rank_offers)
    graph.add_node('prepare_rfq_drafts', _prepare_rfq)

    graph.add_edge(START, 'search_company_catalog')
    graph.add_edge('search_company_catalog', 'public_web_discovery')
    graph.add_edge('public_web_discovery', 'rank_eligible_offers')
    graph.add_edge('rank_eligible_offers', 'prepare_rfq_drafts')
    graph.add_edge('prepare_rfq_drafts', END)
    return graph.compile()


def run_sourcing_agent(requirements: dict) -> dict:
    return build_sourcing_graph().invoke({'requirements': requirements})
