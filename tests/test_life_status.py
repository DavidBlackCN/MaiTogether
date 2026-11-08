"""MaiWeave state boundaries shared by Host and work admission."""
from datetime import datetime, timezone
from copy import deepcopy
import pytest
from test_life import backend, REQUEST
from src.plugin_runtime.behavior_policy.life import LifeProvider
from src.plugin_runtime.behavior_policy.life_status import evaluate_status

NOW = 1793966400
def iso(offset=0):
    return datetime.fromtimestamp(NOW+offset, timezone.utc).isoformat()

def status(kind='leisure', **values):
    return {'version': 1, 'ready': True, 'enabled': True, 'schedule_enabled': True,
        'updated_at': iso(), 'sleeping': kind == 'sleep', 'awake_until': None,
        'current': {'id': 'activity', 'kind': kind, 'status': 'scheduled',
                    'start': iso(-60), 'end': iso(60)} if kind else None, **values}

@pytest.mark.parametrize('kind,category,reason', [
    ('leisure','social','available'), ('sleep','social','sleeping'),
    ('work','social','busy'), ('study','work','busy'), ('travel','social','busy'),
    ('work','work','busy'), (None,'social','sleep_state_ambiguous'),
])
def test_activity_rules(kind, category, reason):
    value=status(kind); original=deepcopy(value)
    r=evaluate_status(value, category, now=NOW)
    assert r['reason'] == reason
    assert r['decision'] == ('allow' if reason == 'available' else 'deny')
    assert value==original

@pytest.mark.parametrize('value,reason', [
    (status(None, awake_until=iso(60)), 'available'),
    (status('sleep', awake_until=iso(60)), 'available'),
    (status(None, awake_until=iso(0)), 'life_boundary_changed'),
    (status(None, schedule_enabled=False), 'available'),
    (status('sleep', schedule_enabled=False), 'available'),
    (status(enabled=False), 'life_disabled'), (status(ready=False), 'not_ready'),
    (status(updated_at=iso(-181)), 'life_state_stale'),
    (status(updated_at=iso(6)), 'life_state_stale'),
    (status(version=True), 'life_contract_mismatch'),
    (status(version=2), 'life_contract_mismatch'),
    (status(ready='true'), 'state_unknown'), (status(sleeping=None), 'state_unknown'),
    (status('sleep', sleeping=False), 'state_unknown'),
    (status(updated_at='2026-11-06T12:00:00'), 'state_unknown'),
    (status(awake_until='bad'), 'state_unknown'),
])
def test_sleep_and_health_boundaries(value, reason):
    assert evaluate_status(value, 'social', now=NOW)['reason']==reason

@pytest.mark.parametrize('field', ['version','ready','enabled','schedule_enabled','updated_at','sleeping','awake_until','current'])
def test_missing_fields_never_allow(field):
    value=status(); del value[field]
    assert evaluate_status(value,'social',now=NOW)['decision']=='deny'

@pytest.mark.parametrize('field,value', [('kind','new_kind'),('status','completed'),('id',''),('end',iso()),('start',iso(1))])
def test_unknown_or_expired_activity(field,value):
    s=status();s['current'][field]=value
    assert evaluate_status(s,'work',now=NOW)['decision']=='deny'

@pytest.mark.asyncio
async def test_public_state_is_only_accepted_with_explicit_official_protocol():
    now=datetime.now(timezone.utc).isoformat()
    s=status(None, schedule_enabled=False, updated_at=now)
    manager, supervisor, entry=backend(s)
    entry.public=True
    configured=dict(plugin_id='ilworkcn.maiweave', api='get_life_status', protocol='maiweave_status_v1')
    p=LifeProvider.from_config({'life_provider':configured})
    assert (await p.evaluate(manager, REQUEST))['decision']=='allow'
    assert (await LifeProvider().evaluate(manager, REQUEST))['decision']=='allow'
    with pytest.raises(RuntimeError):
        await LifeProvider(plugin_id='test.other', api='life_state', protocol='decision_v1').evaluate(manager, REQUEST)
    entry.public=False
    with pytest.raises(RuntimeError): await p.evaluate(manager, REQUEST)
    with pytest.raises(ValueError): LifeProvider.from_config({'life_provider':{**configured,'plugin_id':'other'}})
    with pytest.raises(ValueError): LifeProvider.from_config({'life_provider':{**configured,'max_age_seconds':True}})
