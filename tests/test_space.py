from unittest.mock import AsyncMock
import pytest
from test_policy import policy, ROUTE
from test_preflight import gate, BehaviorDenied
from src.plugin_runtime.behavior_policy.runtime import ADAPTER, BehaviorPolicy


def space_policy():
    p = policy()
    p.targets.append({**ROUTE, 'chat_type': 'space', 'target_id': ROUTE['account_id'],
                      'providers': ['life'], 'autonomous_plugins': [ADAPTER]})
    p._resolve = AsyncMock(side_effect=AssertionError('space must not resolve a chat'))
    return p


@pytest.mark.asyncio
@pytest.mark.parametrize('decision', ['allow', 'deny', 'timeout'])
async def test_space_own_account_only_life_no_hush(decision):
    p = space_policy(); calls = []
    async def provider(name, request):
        calls.append(name)
        assert request['stream_id'] == '' and request['route']['chat_type'] == 'space'
        if decision == 'timeout': raise TimeoutError('unavailable')
        return {'decision': decision, 'reason': 'sleeping'}
    p._provider = provider
    g = gate(p); params = {'content': 'public life', 'ugc_right': 64}
    ticket = await g.prepare('send_qzone_msg', params, 'one')
    if decision == 'allow': await g.final(ticket, 'send_qzone_msg', params, 'one')
    else:
        with pytest.raises(BehaviorDenied): await g.final(ticket, 'send_qzone_msg', params, 'one')
    assert calls == ['life']
    p._resolve.assert_not_called()


@pytest.mark.asyncio
async def test_space_requires_explicit_target_and_rejects_spoofed_account():
    with pytest.raises(BehaviorDenied, match='SPACE_NOT_CONFIGURED'):
        await gate(policy()).prepare('send_qzone_msg', {'content': 'x'}, 'one')
    for key in ('user_id', 'account_id', 'group_id'):
        with pytest.raises(BehaviorDenied, match='ARGUMENTS'):
            await gate(space_policy()).prepare('send_qzone_msg', {'content': 'x', key: '99999'}, 'one')


@pytest.mark.parametrize('override', [{'providers': ['hush']}, {'target_id': '99999'}, {'platform': 'telegram'}])
def test_invalid_space_configuration(override):
    with pytest.raises(ValueError):
        BehaviorPolicy({'enabled': True, 'targets': [{**ROUTE, 'chat_type': 'space',
            'target_id': ROUTE['account_id'], 'providers': ['life'], **override}]})


@pytest.mark.parametrize('kind', ['background', 'hook', 'tool', 'command'])
def test_space_permission_cannot_be_bypassed_by_another_entry_kind(kind):
    p = space_policy()
    with pytest.raises(PermissionError, match='SPACE_CALLER_DENIED'):
        p.check_origin({'kind': kind, 'plugin': 'unlisted.plugin'}, '', p.targets[-1])
