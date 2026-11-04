"""Preflight must not allocate reservations, consume quotas or grant authority."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace

import pytest
from test_policy import ROUTE, policy
from src.plugin_runtime.behavior_policy.runtime import ADAPTER
from src.plugin_runtime.behavior_policy.context import Invocation, current

package = ModuleType('test_adapter_services')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'adapter/services')]
sys.modules[package.__name__] = package
from test_adapter_services.behavior_policy import BehaviorGate, BehaviorDenied


def gate(p):
    runtime = SimpleNamespace(runtime_state=SimpleNamespace(account_id='123456789', scope=None))
    result = BehaviorGate(SimpleNamespace(), runtime)
    async def rpc(phase, **args):
        return await p.capability(ADAPTER, 'behavior.check', {'phase': phase, **args})
    result.rpc = rpc
    return result


@pytest.mark.asyncio
async def test_large_batch_preflight_allocates_no_tickets_or_quota():
    p = policy()
    async def provider(*args):
        raise AssertionError('preflight consumed provider quota')
    p._provider = provider
    g = gate(p)
    await g.preflight_batch([('send_poke', {'group_id':987654321, 'user_id':10001})] * 9000, 'one')
    assert p.actions == {} and not p.audit
    actual = await g.prepare('send_poke', {'group_id':987654321, 'user_id':10001}, 'one')
    assert actual['reference'] and len(p.actions) == 1


@pytest.mark.asyncio
async def test_invalid_tail_preflight_leaves_no_reservations():
    p = policy()
    with pytest.raises(BehaviorDenied):
        await gate(p).preflight_batch([('send_poke', {'group_id':987654321, 'user_id':10001}),
                                       ('invented_action', {})], 'one')
    assert not p.actions


@pytest.mark.asyncio
@pytest.mark.parametrize('expire_in_provider', [False, True])
async def test_expired_human_authority_rechecked_after_queue(expire_in_provider):
    p = policy()
    p.management = [{'plugin':ADAPTER, 'component':'cmd', 'actions':['set_group_ban']}]
    origin = {'kind':'command', 'stream_id':'real-session', 'actor':'10001', 'plugin':ADAPTER, 'component':'cmd'}
    invocation = Invocation('root', ADAPTER, origin, deadline=time.monotonic()+60)
    async def provider(*args):
        invocation.active = False
        return {'decision': 'allow'}
    p._provider = provider
    token = current.set(invocation)
    try:
        t = await p.prepare(ADAPTER, {'action':'set_group_ban', 'route':ROUTE, 'connection':'one', 'digest':'data'})
        if not expire_in_provider:
            invocation.active = False
        result = await p.final(ADAPTER, {**t, 'connection':'one', 'digest':'data'})
        assert not result['allowed'] and result['reason'] == 'BEHAVIOR_AUTHORITY_EXPIRED'
        assert p.actions[t['reference']]['provider_calls'] == int(expire_in_provider)
    finally:
        current.reset(token)
