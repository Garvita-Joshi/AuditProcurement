import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.api import sourcing
from backend.app.core.security import require_authenticated_user
from backend.app.db import get_db
from backend.app.models.auth import User
from backend.app.sourcing.requirements import Requirements

@pytest.fixture
def api():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    User.__table__.create(engine)
    sourcing.SourcingRequest.__table__.create(engine)
    db=sessionmaker(bind=engine)()
    a,b=User(email='a@test.local',role='auditor'),User(email='b@test.local',role='finance')
    db.add_all([a,b]);db.commit()
    actor={'user':a}
    app=FastAPI();app.include_router(sourcing.router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_authenticated_user]=lambda:actor['user']
    with TestClient(app) as client: yield client,actor,b
    db.close();engine.dispose()


def test_intake_and_confirmation(api,monkeypatch):
    c,actor,other=api
    row=c.post('/api/v1/sourcing').json()
    req=Requirements(product='Headsets',quantity=20,budget='2000.00',currency='USD')
    monkeypatch.setattr(sourcing,'extract',lambda current,messages:req)
    monkeypatch.setattr(sourcing,'respond',lambda current,messages:('What delivery location and date do you need?',req))
    r=c.post(f"/api/v1/sourcing/{row['id']}/messages",json={'text':'20 headsets USD 2000','version':1})
    assert r.status_code==200
    data=r.json();assert data['requirements']['quantity']==20
    assert 'delivery' in data['messages'][-1]['text'].lower()
    url=f"/api/v1/sourcing/{row['id']}"
    assert c.put(url,json={'requirements':data['requirements'],'version':2,'confirm':True}).status_code==422
    complete={**data['requirements'],'delivery_deadline':'2027-01-01','delivery_location':'Mumbai, India','specifications':'Noise cancellation','mandatory_conditions':'One year warranty'}
    result=c.put(url,json={'requirements':complete,'version':2,'confirm':True})
    assert result.json()['status']=='ready_for_research'
    assert c.put(url,json={'requirements':complete,'version':2}).status_code==409
    assert c.get('/api/v1/sourcing').json()[0]['requirements']==complete
    assert c.put(url,json={'requirements':complete,'version':3}).json()['status']=='draft'
    actor['user']=other
    assert c.get('/api/v1/sourcing').json()==[]
    assert c.put(url,json={'requirements':complete,'version':4}).status_code==404
    assert c.post(url+'/messages',json={'text':'change','version':4}).status_code==404


def test_provider_failure_preserves_draft(api,monkeypatch):
    c,_,_=api;row=c.post('/api/v1/sourcing').json()
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    assert c.get('/api/v1/sourcing/config').json()['configured'] is False
    url=f"/api/v1/sourcing/{row['id']}/messages"
    assert c.post(url,json={'text':'headsets','version':1}).status_code==503
    assert c.get('/api/v1/sourcing').json()[0]==row
    assert c.post(url,json={'text':'   ','version':1}).status_code==422
    def invalid(*args): raise ValueError('secret provider response')
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(sourcing,'respond',invalid)
    r=c.post(url,json={'text':'headsets','version':1})
    assert r.status_code==502 and 'secret' not in r.text


def test_requires_authentication():
    app=FastAPI();app.include_router(sourcing.router)
    with TestClient(app) as c:
        assert c.get('/api/v1/sourcing/config').status_code==401


def test_purchase_preserves_sourcing_requirements():
    from backend.app.procurement.contracts import RequestDetails
    req = Requirements(product='Headsets', quantity=20, budget='2000.00', currency='USD',
        delivery_location='Mumbai, India', mandatory_conditions='One year warranty')
    details = RequestDetails(sourcing_requirements=req)
    restored = RequestDetails.model_validate(details.model_dump(mode='json'))
    assert restored.sourcing_requirements.mandatory_conditions == 'One year warranty'
    assert restored.sourcing_requirements.quantity == 20


def test_preferred_vendor_is_a_ranking_hint_and_line_items_are_saved(api):
    from backend.app.sourcing.catalog import CatalogOffer, search_catalog
    c,_,_=api
    row=c.post('/api/v1/sourcing').json()
    requirements={**row['requirements'], 'product':'headsets', 'quantity':2, 'budget':'500.00',
        'currency':'USD', 'delivery_deadline':'2027-01-01', 'delivery_location':'Mumbai, India',
        'specifications':'None', 'mandatory_conditions':'None', 'vendor_preference':'prioritize',
        'preferred_vendors':'Preferred Audio',
        'line_items':[{'description':'Noise-cancelling headset','quantity':2,'unit_price':'100.00','contract_start':None,'contract_end':None}]}
    saved=c.put(f"/api/v1/sourcing/{row['id']}",json={'requirements':requirements,'version':1,'confirm':True})
    assert saved.status_code==200
    assert saved.json()['requirements']['line_items'][0]['quantity']==2
    offers=[CatalogOffer(vendor_id=name,vendor_name=name,email=f"{name.lower().replace(' ','')}@vendor.test",approved=True,
        product='headsets',sku='sku-1',currency='USD',source_reference='approved internal catalog')
        for name in ['Other Audio','Preferred Audio']]
    req=Requirements.model_validate(saved.json()['requirements'])
    ranked=search_catalog(req,offers)
    assert ranked[0]['offer']['vendor_name']=='Preferred Audio'
    assert ranked[1]['offer']['vendor_name']=='Other Audio'


def test_fuzzy_and_synonym_catalog_search():
    from backend.app.sourcing.catalog import load_catalog, search_catalog
    offers = load_catalog()
    assert len(offers) > 0

    # Plural and synonym searches must find matches
    for prod in ['Laptops', 'Laptop', 'Computer', 'Dell Laptop', 'Ergonomic Chairs', 'A4 Papers', 'Website Design', 'Garvita']:
        req = Requirements(product=prod, quantity=1, budget='100000.00', currency='INR',
            delivery_deadline='2027-01-01', delivery_location='Jaipur, India',
            specifications='None', mandatory_conditions='None')
        results = search_catalog(req, offers)
        assert len(results) > 0, f"Query '{prod}' should match at least one catalog offer"


def test_over_budget_and_usd_currency_matching():
    from backend.app.sourcing.catalog import load_catalog, search_catalog
    offers = load_catalog()

    # Budget lower than list price must NOT be discarded
    req_low_budget = Requirements(product='Laptop 15 inch', quantity=1, budget='20000.00', currency='INR',
        delivery_deadline='2027-01-01', delivery_location='Jaipur, India',
        specifications='None', mandatory_conditions='None')
    res_low = search_catalog(req_low_budget, offers)
    assert len(res_low) > 0
    assert any(r.get('over_budget') for r in res_low)

    # USD currency must match INR catalog with conversion note
    req_usd = Requirements(product='Laptop 15 inch', quantity=1, budget='1000.00', currency='USD',
        delivery_deadline='2027-01-01', delivery_location='Jaipur, India',
        specifications='None', mandatory_conditions='None')
    res_usd = search_catalog(req_usd, offers)
    assert len(res_usd) > 0
    assert any('Catalog currency is INR' in r for r in res_usd[0]['reasons'])


def test_external_search_and_vendor_addition(api):
    c, _, _ = api
    row = c.post('/api/v1/sourcing').json()

    # Test external search tool endpoint
    search_res = c.post(f"/api/v1/sourcing/{row['id']}/agent/external-search", json={
        'query': 'Commercial Laptops',
        'location': 'Jaipur, India'
    })
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert 'search_tools' in search_data
    assert 'google_search_url' in search_data['search_tools']
    assert 'linkedin_search_url' in search_data['search_tools']

    # Confirm requirements and start agent
    complete = {
        'product': 'Forklift Heavy Machinery', 'quantity': 1, 'budget': '1000000.00',
        'currency': 'INR', 'delivery_deadline': '2027-01-01', 'delivery_location': 'Jaipur, India',
        'specifications': 'None', 'mandatory_conditions': 'None'
    }
    c.put(f"/api/v1/sourcing/{row['id']}", json={'requirements': complete, 'version': 1, 'confirm': True})
    agent_run = c.post(f"/api/v1/sourcing/{row['id']}/agent/runs").json()
    assert agent_run['summary']['shortlisted_count'] > 0

    # Test adding a custom vendor found on Google/LinkedIn
    add_res = c.post(f"/api/v1/sourcing/{row['id']}/agent/runs/{agent_run['id']}/vendors", json={
        'name': 'Apex Industrial Equipment',
        'email': 'sales@apexindustrial.example',
        'website': 'https://www.apexindustrial.example',
        'linkedin_url': 'https://www.linkedin.com/company/apex-industrial',
        'notes': 'Found via LinkedIn search'
    })
    assert add_res.status_code == 200
    updated_run = add_res.json()
    vendor_names = [v['name'] for v in updated_run['vendors']]
    assert 'Apex Industrial Equipment' in vendor_names

