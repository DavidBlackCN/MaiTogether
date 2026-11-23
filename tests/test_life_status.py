"""The Host consumes a MaiWeave verdict for this action, without reading a schedule."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from test_life import backend, REQUEST
from src.plugin_runtime.behavior_policy.life import LifeProvider, weave_decision


def verdict(**changes):
    return {'version': 1, 'queried_at': datetime.now(timezone.utc).isoformat(),
            'decision': 'allow', 'reason': 'available', 'behavior': 'proactive', **changes}


@pytest.mark.parametrize('kind,action,message,expected', [
    ('host', 'platform.message', 'msg', 'conversation'),
    ('host', 'send_msg', 'msg', 'conversation'),
    ('host', 'send_group_msg', 'msg', 'conversation'),
    ('host', 'send_private_msg', 'msg', 'conversation'),
    ('host', 'send_group_msg', '', 'proactive'),
    ('background', 'send_group_msg', 'msg', 'proactive'),
    ('command', 'platform.message', 'msg', 'proactive'),
    ('tool', 'send_private_msg', 'msg', 'proactive'),
    ('host', 'send_poke', 'msg', 'proactive'),
    ('host', 'set_msg_emoji_like', 'msg', 'proactive'),
    ('host', 'send_qzone_msg', 'msg', 'proactive'),
])
@pytest.mark.asyncio
async def test_one_query_of_registered_api(kind, action, message, expected):
    manager, supervisor, entry = backend(verdict(behavior=expected))
    entry.public = True
    registry = Mock(return_value=[entry])
    supervisor.api_registry.get_apis = registry
    result = await LifeProvider().evaluate(manager, {
        **REQUEST, 'origin': {'kind': kind}, 'action': action, 'message_id': message})
    assert result == {'version': 1, 'decision': 'allow', 'reason': 'available'}
    assert all(call.kwargs['name'] == 'evaluate_behavior' for call in registry.call_args_list)
    supervisor.invoke_api.assert_awaited_once_with('ilworkcn.maiweave', 'handler', {'behavior': expected}, timeout_ms=150)


@pytest.mark.parametrize('decision,reason', [('defer','busy'), ('defer','farewell'), ('defer','sleeping'),
    ('defer','new_upstream_reason'), ('unknown','not_ready'), ('abstain','disabled')])
def test_only_explicit_permission_allows(decision, reason):
    assert weave_decision(verdict(decision=decision, reason=reason), 'proactive', 180) == {
        'version': 1, 'decision': 'deny', 'reason': reason}


@pytest.mark.parametrize('changes', [
    {'version': True}, {'version': 2}, {'behavior': 'conversation'}, {'decision': 'unexpected'},
    {'decision': 'allow', 'reason': 'not_ready'}, {'reason': ''}, {'queried_at': None},
    {'queried_at': 'unreadable'}, {'queried_at': '2026-11-23T12:00:00'},
])
def test_wrong_contract_never_allows(changes):
    with pytest.raises(RuntimeError):
        weave_decision(verdict(**changes), 'proactive', 180)


@pytest.mark.parametrize('seconds', [-181, 6])
def test_stale_or_future_verdict(seconds):
    at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    result = weave_decision(verdict(queried_at=at.isoformat()), 'proactive', 180)
    assert (result['decision'], result['reason']) == ('deny', 'life_state_stale')


@pytest.mark.asyncio
async def test_public_api_only_for_maiweave():
    manager, _, entry = backend(verdict())
    with pytest.raises(RuntimeError):
        await LifeProvider().evaluate(manager, REQUEST)
    entry.public = True
    with pytest.raises(RuntimeError):
        await LifeProvider(protocol='decision_v1').evaluate(manager, REQUEST)
    with pytest.raises(ValueError):
        LifeProvider.from_config({'life_provider': {'plugin_id': 'other'}})
