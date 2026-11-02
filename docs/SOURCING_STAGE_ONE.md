# Buying assistant: stage one

Open http://127.0.0.1:5180 after signing in. Click New request. The Buying assistant is beside the purchase form throughout all four steps. Create or select a saved brief and describe your purchase. Review and edit the summary, then confirm requirements. Saved briefs survive reload and are visible only to their owner.

## Configuration

Use a Gemini key obtained from your own Google account in the repository-root `.env`:

```
GEMINI_API_KEY=your_replacement_key
GEMINI_MODEL=gemini-2.5-flash
```

Restart the backend after changing configuration. Never put keys in React or commit `.env`. The key supplied in chat was not installed or transmitted because its issuer is unknown. An existing configured key is used only when Send is clicked. Configuration presence does not prove validity. Provider failures leave the saved brief unchanged; manual editing still works. No live provider request was made during implementation verification.

## Architecture and boundaries

React Sourcing.jsx -> authenticated /api/v1/sourcing -> Gemini structured extraction -> validated Requirements -> database optimistic version update -> deterministic follow-up questions -> explicit human confirmation.

This is LLM-assisted requirements intake, the first component of the future agent. It does not yet perform autonomous research, negotiation, outreach, purchasing or payment. The autoencoder pipeline remains on invoice verification and is not called for chat messages. No supplier or recipient is invented from the requirements brief. Confirmation marks ready_for_research; the next-stage executor is not yet implemented.

Eight fields: product, quantity, total budget inclusive of shipping/tax, ISO-style currency code, delivery date, delivery location, preferred specifications, mandatory conditions. Missing fields remain null; explicit no preferences/conditions may be entered as None. First three missing fields generate follow-up questions. AI extraction is fallible; users review all fields before confirming. More than 100 messages requires a new brief or direct summary editing. Concurrent updates return 409 rather than silently overwrite another tab.

## Files

- backend/app/sourcing/requirements.py: validation, questions, Gemini structured extraction.
- backend/app/api/sourcing.py: owner-scoped CRUD, conversation, confirmation, table.
- frontend/src/pages/Sourcing.jsx and Sourcing.css: chat and editable brief.
- frontend/src/api/client.js: authenticated API methods.
- frontend/src/App.jsx and components/Navbar.jsx: route and navigation.
- scripts/init_procurement.py: additive table initialization, run with `.venv/bin/python -m scripts.init_procurement`.
- tests/test_sourcing.py: isolation, stale writes, confirmation, failures and authentication.

## Verification

17 sourcing/procurement tests passed; production frontend build passed. Provider extraction is mocked in tests: real Gemini credential/model availability still requires a live test by the configured account. Existing unrelated build chunk-size and datetime deprecation warnings remain.

## Purchase form integration
Apply saved requirements explicitly transfers the title, budget and first item description/quantity into the purchase draft. USD is required for application; other currencies are not silently converted. Supplier, recipient, SKU and unit price must still be supplied. Delivery location/date, preferences and mandatory conditions are stored in details.sourcing_requirements and shown in request Overview. The standalone /sourcing route redirects to home and its sidebar link is removed. On narrow screens the assistant stacks below the form.
