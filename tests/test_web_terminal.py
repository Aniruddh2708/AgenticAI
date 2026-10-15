"""Smoke tests for the supplied terminal-style HTML frontend.

The full rendering and interactions were also exercised with headless Chromium
against recorded *actual API results*; these tests need no browser dependency.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from vibefinance.api import create_app


WEB = Path(__file__).resolve().parents[1] / 'vibefinance' / 'web'


def test_dashboard_is_primary_web_entry_and_assets_are_fully_local(tmp_path):
    with TestClient(create_app(tmp_path / 'terminal.sqlite3')) as client:
        for route in ('/', '/dashboard'):
            response = client.get(route)
            assert response.status_code == 200
            assert 'VIBEFINANCE' in response.text
            assert 'Active Financial Analyst Swarm' in response.text
            assert 'Run Audit' in response.text
            assert 'application/json' not in response.headers.get('content-type', '')
        for filename in ('styles.css', 'app.js', 'favicon.svg'):
            response = client.get('/assets/' + filename)
            assert response.status_code == 200
            assert len(response.content) > 100
        assert client.get('/_stcore/health').status_code == 200
        assert client.get('/health').json()['status'] in ('ok', 'degraded')
    assert 'cdn.tailwindcss.com' not in (WEB / 'index.html').read_text()
    assert 'fonts.googleapis.com' not in (WEB / 'index.html').read_text()
    assert 'NVDA' not in (WEB / 'index.html').read_text()
    assert '<script src="/assets/app.js" defer>' in (WEB / 'index.html').read_text()


def test_web_shell_is_public_but_account_data_stays_token_protected(monkeypatch, tmp_path):
    monkeypatch.setenv('VIBEFINANCE_API_TOKEN', 'isolated-hackathon-token')
    with TestClient(create_app(tmp_path / 'protected.sqlite3')) as client:
        assert client.get('/').status_code == 200
        assert client.get('/assets/app.js').status_code == 200
        assert client.get('/profiles').status_code == 401
        assert client.post('/analyze', json={}).status_code == 401
        headers = {'Authorization': 'Bearer isolated-hackathon-token'}
        assert len(client.get('/profiles', headers=headers).json()) == 3


def test_terminal_routes_use_existing_contracts_and_scenarios(tmp_path):
    with TestClient(create_app(tmp_path / 'state.sqlite3')) as client:
        reliance = client.post('/analyze', json={'ticker': 'RELIANCE.NS', 'user_id': 'arjun'})
        assert reliance.status_code == 200
        session = reliance.json()
        assert session['recommendation']['action'] == 'ACCUMULATE'
        assert len(session['recommendation']['agent_outputs']) == 5
        assert session['metrics']['total_latency_ms'] >= 0
        assert session['metrics']['claim_support_coverage'] is not None
        assert session['sources']
        source_ids = {src['chunk_id'] for src in session['sources']}
        assert all(cite['chunk_id'] in source_ids for cite in session['recommendation']['citations'])
        tcs = client.post('/analyze', json={'ticker': 'TCS.NS', 'user_id': 'arjun'}).json()
        assert tcs['recommendation']['conflicts']
        assert tcs['recommendation']['action'] == 'HOLD'
        missing = client.post('/analyze', json={'ticker': 'HDFCBANK.NS', 'user_id': 'arjun', 'missing_filing': True}).json()
        filings = next(agent for agent in missing['recommendation']['agent_outputs'] if agent['dimension'] == 'filings')
        assert filings['status'] != 'ok'
        assert not filings['citations']
        assert missing['recommendation']['action'] == 'WATCH'


def test_same_input_personalization_is_exposed_by_compare_endpoint(tmp_path):
    with TestClient(create_app(tmp_path / 'compare.sqlite3')) as client:
        response = client.post('/compare', json={'ticker': 'RELIANCE.NS', 'user_id': 'arjun'})
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 3
        assert {s['recommendation']['user_id']: s['recommendation']['action'] for s in sessions} == {
            'meera': 'REDUCE', 'arjun': 'ACCUMULATE', 'rohan': 'BUY'}
        assert len({s['market_fingerprint'] for s in sessions}) == 1
