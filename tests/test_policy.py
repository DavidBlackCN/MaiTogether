from pathlib import Path
from types import SimpleNamespace
import asyncio
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'maibot'))
from src.plugin_runtime.behavior_policy.context import Contexts, Invocation, current, runner_scope, runner_reference
from src.plugin_runtime.behavior_policy.runtime import ADAPTER, BehaviorPolicy

ROUTE = dict(platform='qq', account_id='123456789', scope=None, chat_type='group', target_id='987654321')


def policy():
    p = BehaviorPolicy({'enabled': True, 'targets': [{**ROUTE, 'providers': ['vita', 'hush'],
                                                     'autonomous_plugins': [ADAPTER]}]})
    async def route(args): pass
    async def resolve(args): return 'real-session'
    p._adapter_route = route
    p._resolve = resolve
    return p


async def ticket(p):
    return await p.prepare(ADAPTER, {'action': 'send_poke', 'route': ROUTE, 'connection': 'one', 'digest': 'same'})


@pytest.mark.asyncio
async def test_one_final_check_and_quota_under_concurrency():
    p = policy()
    calls = []
    async def provider(name, request):
        calls.append(name)
        await asyncio.sleep(.01)
        return {'version': 1, 'decision': 'allow'}
    p._provider = provider
    t = await ticket(p)
    args = {**t, 'connection': 'one', 'digest': 'same'}
    results = await asyncio.gather(*(p.final(ADAPTER, args) for _ in range(12)))
    assert sum(r['allowed'] for r in results) == 1
    assert calls == ['vita', 'hush']


@pytest.mark.asyncio
async def test_sleep_before_final_denies_without_consuming_hush():
    p = policy()
    calls = []
    async def provider(name, request):
        calls.append(name)
        return {'version': 1, 'decision': 'deny', 'reason': 'sleeping'}
    p._provider = provider
    t = await ticket(p)
    result = await p.final(ADAPTER, {**t, 'connection': 'one', 'digest': 'same'})
    assert not result['allowed'] and calls == ['vita']


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('connection', 'new'), ('digest', 'changed')])
async def test_connection_and_payload_binding(field, value):
    p = policy()
    t = await ticket(p)
    args = {**t, 'connection': 'one', 'digest': 'same', field: value}
    assert not (await p.final(ADAPTER, args))['allowed']


@pytest.mark.asyncio
async def test_provider_failure_read_access_and_unknown_action():
    p = policy()
    t = await ticket(p)
    assert not (await p.final(ADAPTER, {**t, 'connection': 'one', 'digest': 'same'}))['allowed']
    for action in ('get_msg', 'get_login_info'):
        assert (await p.prepare(ADAPTER, {'action': action}))['allowed']
    for action in ('get_credentials', 'get_rkey', 'send_packet', '.handle_quick_operation', 'invented'):
        assert not (await p.prepare(ADAPTER, {'action': action}))['allowed']


@pytest.mark.asyncio
async def test_tool_arguments_cannot_grant_cross_target_or_management():
    p = policy()
    token = current.set(Invocation('root', ADAPTER, {'kind': 'tool', 'stream_id': 'other', 'actor': '10001'}))
    try:
        assert not (await ticket(p))['allowed']
        assert not (await p.prepare(ADAPTER, {'action': 'set_group_ban', 'route': ROUTE}))['allowed']
    finally:
        current.reset(token)


def test_context_binding_nested_origin_expiry_and_forgery():
    registry = Contexts()
    with registry.issue('source', 'plugin.invoke_command', 'command', {'kind': 'command', 'actor': '10001'}) as ref:
        with pytest.raises(PermissionError):
            with registry.receive(ref, 'other'): pass
        with registry.receive(ref, 'source'):
            with registry.issue('adapter', 'plugin.invoke_api', 'poke') as child:
                with registry.receive(child, 'adapter') as nested:
                    assert nested.origin['actor'] == '10001' and nested.origin['plugin'] == 'source'
    with pytest.raises(PermissionError):
        with registry.receive(ref, 'source'): pass


@pytest.mark.asyncio
async def test_background_task_loses_completed_human_reference():
    event = asyncio.Event()
    async def background():
        await event.wait()
        return runner_reference()
    with runner_scope(SimpleNamespace(context_ref='human', behavior_control={})):
        assert runner_reference() == 'human'
        task = asyncio.create_task(background())
    event.set()
    assert await task == ''


def test_required_provider_configuration_is_explicit_and_ordered():
    with pytest.raises(ValueError): BehaviorPolicy({'enabled':True,'targets':[]})
    target={**ROUTE,'providers':['hush','vita']}
    p=BehaviorPolicy({'enabled':True,'targets':[target]})
    assert p.targets[0]['providers']==['vita','hush']
    with pytest.raises(ValueError): BehaviorPolicy({'enabled':True,'targets':[target,target]})


@pytest.mark.asyncio
async def test_unknown_or_expired_operation_cannot_be_submitted_again():
    p=policy()
    async def provider(name,request): return {'version':1,'decision':'allow'}
    p._provider=provider
    t=await ticket(p);args={**t,'connection':'one','digest':'same'}
    assert (await p.final(ADAPTER,args))['allowed']
    assert (await p.capability(ADAPTER,'behavior.check',{'phase':'result','reference':t['reference'],'state':'unknown'}))['state']=='unknown'
    assert not (await p.final(ADAPTER,args))['allowed']
    assert not (await policy().final(ADAPTER,args))['allowed']
    t=await ticket(p);p.actions[t['reference']]['expires']=0
    assert not (await p.final(ADAPTER,{**t,'connection':'one','digest':'same'}))['allowed']


def test_expired_context_does_not_survive_a_new_host_generation():
    registry=Contexts()
    with registry.issue('source','plugin.invoke_api','component') as ref:
        registry.entries[ref].deadline=0
        with pytest.raises(PermissionError):
            with registry.receive(ref,'source'): pass
        with pytest.raises(PermissionError):
            with Contexts().receive(ref,'source'): pass


def test_nested_background_rpc_loses_authority_when_original_command_returns():
    registry=Contexts()
    with registry.issue('source','plugin.invoke_command','command',{'kind':'command','actor':'10001'}) as root:
        with registry.receive(root,'source'):
            child_scope=registry.issue('adapter','plugin.invoke_api','action')
            child=child_scope.__enter__()
    try:
        with pytest.raises(PermissionError):
            with registry.receive(child,'adapter'): pass
    finally:child_scope.__exit__(None,None,None)
