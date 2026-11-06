"""Life selection and protocol faults; platform/authority checks remain separate."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_policy import ROUTE, policy, ticket
from src.plugin_runtime.behavior_policy.context import provider_request
from src.plugin_runtime.behavior_policy.life import DEFAULT_PLUGIN, LifeProvider, validate_result
from src.plugin_runtime.behavior_policy.runtime import ADAPTER, BehaviorPolicy


def config(names, **extra):
    return {'enabled': True, 'targets': [{**ROUTE, 'providers': names}], **extra}


def test_old_and_generic_configs_have_identical_defaults_without_mutating_input():
    old = config(['hush', 'vita'])
    copy = deepcopy(old)
    legacy = BehaviorPolicy(old)
    modern = BehaviorPolicy(config(['life', 'hush']))
    assert old == copy
    assert legacy.targets == modern.targets
    assert legacy.life == modern.life == LifeProvider()
    assert legacy.life.plugin_id == DEFAULT_PLUGIN
    assert BehaviorPolicy(config(['hush'])).targets[0]['providers'] == ['hush']


@pytest.mark.parametrize('extra,names', [
    ({'life_provider': None}, ['life']),
    ({'life_provider': {'version': '2'}}, ['life']),
    ({'life_provider': {'version': 1}}, ['life']),
    ({'life_provider': {'plugin_id': ''}}, ['life']),
    ({'life_provider': {'fallback': True}}, ['life']),
    ({'life_provider': {'plugin_id': 'test.other'}}, ['vita']),
    ({}, ['life', 'vita']), ({}, ['weave']), ({}, []),
])
def test_invalid_or_ambiguous_configuration_fails(extra, names):
    with pytest.raises(ValueError): BehaviorPolicy(config(names, **extra))


def backend(result=None):
    result = result or {'version': 1, 'decision': 'allow', 'reason': 'available'}
    entry = SimpleNamespace(version='1', public=False, dynamic=False, handler_name='handler')
    registry = SimpleNamespace(get_apis=lambda **kw: [entry])
    invoke = AsyncMock(return_value=SimpleNamespace(error=None, payload={'success': True, 'result': result}))
    supervisor = SimpleNamespace(api_registry=registry, invoke_api=invoke)
    manager = SimpleNamespace(_get_supervisor_for_plugin=lambda plugin: supervisor)
    return manager, supervisor, entry


REQUEST = {'category': 'cognition', 'stream_id': 'real-session', 'route': ROUTE, 'origin': {'kind': 'host'}}


@pytest.mark.asyncio
async def test_custom_backend_uses_registered_handler_and_internal_context():
    manager, supervisor, _ = backend()
    calls = []
    async def invoke(plugin, handler, args, timeout_ms):
        calls.append((plugin, handler, args, timeout_ms, provider_request.get()))
        return SimpleNamespace(error=None, payload={'success': True, 'result': {
            'version': 1, 'decision': 'allow', 'reason': 'available'}})
    supervisor.invoke_api = invoke
    p = BehaviorPolicy(config(['life'], life_provider={'plugin_id': 'test.other', 'api': 'life_state'}))
    p.manager = manager
    assert (await p._provider('life', REQUEST))['decision'] == 'allow'
    assert calls == [('test.other', 'handler', {}, 150, REQUEST)]
    assert provider_request.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['missing', 'version', 'public', 'dynamic', 'disabled', 'exception',
                                  'timeout', 'cancelled', 'envelope', 'replacement'])
async def test_rpc_faults_never_fall_back_and_restore_context(fault):
    manager, supervisor, entry = backend()
    if fault == 'missing': manager._get_supervisor_for_plugin = lambda plugin: None
    if fault == 'version': entry.version = '2'
    if fault in ('public', 'dynamic'): setattr(entry, fault, True)
    if fault == 'disabled': supervisor.api_registry.get_apis = lambda **kw: []
    if fault == 'exception': supervisor.invoke_api.side_effect = RuntimeError('broken')
    if fault == 'cancelled': supervisor.invoke_api.side_effect = asyncio.CancelledError()
    if fault == 'timeout':
        async def wait(*args, **kwargs): await asyncio.sleep(1)
        supervisor.invoke_api.side_effect = wait
    if fault == 'envelope': supervisor.invoke_api.return_value.payload = None
    if fault == 'replacement':
        async def replace(*args, **kwargs):
            supervisor.api_registry.get_apis = lambda **kw: []
            return SimpleNamespace(error=None, payload={'success': True, 'result': {
                'version': 1, 'decision': 'allow', 'reason': 'available'}})
        supervisor.invoke_api.side_effect = replace
    with pytest.raises((RuntimeError, TimeoutError, asyncio.CancelledError)):
        await LifeProvider(plugin_id='test.other').evaluate(manager, REQUEST)
    assert provider_request.get() is None


@pytest.mark.parametrize('result', [None, {}, {'version': True, 'decision': 'allow', 'reason': 'available'},
    {'version': 2, 'decision': 'allow', 'reason': 'available'},
    {'version': 1, 'decision': 'unknown', 'reason': 'available'},
    {'version': 1, 'decision': 'allow', 'reason': 'state_unknown'},
    {'version': 1, 'decision': 'allow', 'reason': 'not_ready'},
    {'version': 1, 'decision': 'allow', 'reason': 'available', 'ready': False},
    {'version': 1, 'decision': 'abstain', 'reason': 'not_ready'},
    {'version': 1, 'decision': 'abstain', 'reason': 'not_managed', 'ready': False},
    {'version': 1, 'decision': 'allow'},
])
def test_invalid_state_is_not_permission(result):
    with pytest.raises(RuntimeError): validate_result(result)


@pytest.mark.parametrize('decision,reason', [('allow', 'available'), ('deny', 'sleeping'),
    ('deny', 'busy'), ('deny', 'not_ready'), ('deny', 'state_unknown'), ('abstain', 'not_managed')])
def test_vita_v1_states_remain_compatible(decision, reason):
    result = {'version': 1, 'decision': decision, 'reason': reason}
    assert validate_result(result) == result


@pytest.mark.asyncio
async def test_life_failure_stops_final_check_before_hush():
    p = policy()
    manager, supervisor, _ = backend({'version': 1, 'decision': 'allow', 'reason': 'state_unknown'})
    p.manager = manager
    t = await ticket(p)
    result = await p.final(ADAPTER, {**t, 'connection': 'one', 'digest': 'same'})
    assert not result['allowed'] and 'LIFE_PROVIDER_STATE_UNKNOWN' in result['reason']
    assert p.actions[t['reference']]['provider_calls'] == 1
