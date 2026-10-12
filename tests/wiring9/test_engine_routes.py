from copy import deepcopy
import importlib
import math
import pytest
from fastapi.testclient import TestClient
from app.main import app

BASE = 'app.modules.m20_general_cognitive_worker.'
CASES = [
    ('reliability_testing1543', 'prepare', {'specimen_count': 2, 'profiles': [{'id': 'hot', 'duration_hours': '3/2', 'cycles': 4}], 'measurements': ['voltage'], 'acceptance_criteria': ['no visible damage']}, 'planned_specimen_hours', '3'),
    ('accelerated_life_testing1544', 'run', {'model': 'arrhenius', 'failure_mechanism': 'oxide wear-out', 'activation_energy_ev': 0.7, 'use_temperature_k': 300, 'stress_levels': [{'id': 's1', 'temperature_k': 300, 'hours': 2, 'units_on_test': 3, 'failures': 0}]}, 'totals', {'device_hours': '6', 'failures': 0, 'units_on_test': 3}),
    ('environmental_testing1545', 'plan', {'profiles': [{'condition': 'temperature', 'setpoint': 85, 'unit': 'celsius', 'dwell_hours': 2.5}], 'specimen_count': 3, 'preconditioning': ['visual inspection'], 'measurements': ['resistance'], 'acceptance_criteria': ['no visible damage']}, 'total_dwell_hours', 2.5),
    ('vibration_modal1546', 'analyze_modal', {'request_id': 'modal-hand', 'mass_matrix': [[2]], 'stiffness_matrix': [[8]], 'units': {'mass': 'kg', 'stiffness': 'N/m'}, 'model': 'linear_undamped'}, 'frequency_hz', 1 / math.pi),
    ('shock_testing1547', 'plan', {'profiles': [{'pulse_shape': 'half_sine', 'peak_acceleration_g': 100, 'duration_ms': 11}], 'specimen_count': 3, 'axes': ['x'], 'acceptance_criteria': ['no visible damage']}, 'estimated_delta_velocity_m_per_s', 100 * 9.80665 * 11 / 1000 * (2 / math.pi)),
    ('thermal_cycling1548', 'plan', {'profile': {'low_temperature_c': -40, 'high_temperature_c': 85, 'ramp_rate_c_per_min': 10, 'dwell_low_min': 15, 'dwell_high_min': 15}, 'cycles': 100, 'specimen_count': 2, 'preconditioning': ['visual inspection'], 'measurements': ['resistance'], 'acceptance_criteria': ['no visible damage']}, 'estimated_cycle_time_min', 55.0),
    ('humidity_exposure1549', 'evaluate', {'rh_limit': 60.0, 'observations': [{'time': '2026-10-11T00:00:00+00:00', 'rh': 80.0}, {'time': '2026-10-11T00:00:10+00:00', 'rh': 50.0}]}, 'time_above_limit_seconds', 10.0),
]

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    return TestClient(app)

@pytest.mark.parametrize('engine,entry,payload,value_key,value', CASES)
def test_dedicated_engine_over_mounted_app(client, oidc_auth_headers, monkeypatch, engine, entry, payload, value_key, value):
    module = importlib.import_module(BASE + engine)
    expected = getattr(module, entry)(deepcopy(payload))
    if value_key == 'frequency_hz':
        assert expected['modes'][0][value_key] == pytest.approx(value)
    elif value_key == 'estimated_delta_velocity_m_per_s':
        assert expected['plan'][0][value_key] == value
    else:
        assert expected[value_key] == value
    routes = importlib.import_module(BASE + engine + '_routes')
    calls = []
    original = routes.engine_entry
    def observed(packet):
        calls.append(deepcopy(packet))
        return original(packet)
    monkeypatch.setattr(routes, 'engine_entry', observed)
    path = '/api/v1/api/modules/20/engineering/' + engine + '/run'
    headers = oidc_auth_headers('tenant-a', 'owner')
    response = client.post(path, json={'data': payload}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == set(expected) | {'tenant_id', 'actor_id'}
    assert body == dict(expected, tenant_id='tenant-a', actor_id='owner')
    assert calls == [payload]
    assert client.post(path, json={'data': payload}).status_code == 401
    assert client.post(path, json={'data': payload, 'tenant_id': 'tenant-b'}, headers=headers).status_code == 403
    assert client.post(path, json={'data': payload, 'actor_id': 'other'}, headers=headers).status_code == 403
    assert client.post(path, json={'data': payload, 'resource_refs': [{'tenant_id': 'tenant-b'}]}, headers=headers).status_code == 403
    assert client.post(path, json={'data': {}}, headers=headers).status_code == 422
    assert client.post(path, content=b'{"data":{"x":"\\ud800"}}', headers={**headers, 'content-type': 'application/json'}).status_code == 422

@pytest.mark.parametrize('engine,payload', [(case[0], case[2]) for case in CASES])
def test_resource_refs_count_boundary_over_mounted_app(client, oidc_auth_headers, engine, payload):
    path = '/api/v1/api/modules/20/engineering/' + engine + '/run'
    headers = oidc_auth_headers('tenant-a', 'owner')
    owned_ref = {'tenant_id': 'tenant-a'}
    at_cap = client.post(path, json={'data': payload, 'resource_refs': [owned_ref] * 64}, headers=headers)
    assert at_cap.status_code == 200, at_cap.text
    over_cap = client.post(path, json={'data': payload, 'resource_refs': [owned_ref] * 65}, headers=headers)
    assert over_cap.status_code == 422, over_cap.text
