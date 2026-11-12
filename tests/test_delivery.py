from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest
from test_policy import policy
from src.plugin_runtime.behavior_policy import delivery
from src.plugin_runtime.behavior_policy.context import contexts,current


@pytest.mark.parametrize('states,sent,expected', [
    (['confirmed'], True, 'confirmed'), (['unknown'], False, 'unknown'),
    (['confirmed', 'failed'], False, 'partial'), ([], False, 'not_submitted')])
def test_standard_send_receipts_are_added_without_changing_host_send_helpers(states, sent, expected):
    with contexts.receive('', 'fixture'):
        for index, state in enumerate(states):
            current.get().results.append({'action_id': str(index), 'state': state})
        result = {'success': sent, 'sent': sent, 'message_id': 'id' if sent else None}
        annotated = delivery.annotate_send_result('send.text', {'return_details': True}, result)
        assert annotated == {**result, 'behavior_state': expected}
        assert 'behavior_state' not in result
        assert delivery.annotate_send_result('send.text', {}, result) is result
        assert delivery.annotate_send_result('api.call', {'return_details': True}, result) is result


def setup(monkeypatch, impl, allowed=True):
    registry={}
    auth=SimpleNamespace(check_capability=lambda p,c:(allowed,'denied'))
    supervisor=SimpleNamespace(capability_service=SimpleNamespace(
        _authorization=auth,register_capability=lambda n,f:registry.update({n:f})))
    manager=SimpleNamespace(_cap_send_hybrid=impl,_cap_api_call=impl)
    monkeypatch.setattr(delivery,'get_policy',lambda:policy())
    delivery.register(manager,supervisor)
    return registry['behavior.send_v1']


@pytest.mark.asyncio
@pytest.mark.parametrize('states,ok,expected',[
    (['confirmed'],True,'confirmed'),(['submitted','unknown'],False,'unknown'),
    (['confirmed','failed'],True,'partial'),(['denied'],False,'deferred'),
    (['failed'],False,'failed'),([],True,'unknown')])
async def test_delivery_state_and_native_sdk_preservation(monkeypatch,states,ok,expected):
    async def impl(plugin,cap,args):
        for i,state in enumerate(states):current.get().results.append({'action_id':str(i),'state':state,'reason':'fixture' if state=='denied' else ''})
        return {'success':ok,'sent':ok,'message_id':'1'}
    fn=setup(monkeypatch,impl)
    with contexts.receive('', 'fixture'):
        result=await fn('fixture','behavior.send_v1',{'version':1,'operation':'message','args':{'stream_id':'s'}})
    from maibot_sdk.context import PluginContext
    assert PluginContext._normalize_capability_result('behavior.send_v1',result)==result
    assert result['state']==expected


@pytest.mark.asyncio
async def test_original_capability_permission_still_required(monkeypatch):
    impl=AsyncMock()
    fn=setup(monkeypatch,impl,False)
    with contexts.receive('', 'fixture'):
        with pytest.raises(PermissionError): await fn('fixture','behavior.send_v1',{'version':1,'operation':'message','args':{}})
    impl.assert_not_awaited()


@pytest.mark.asyncio
async def test_space_uses_adapter_api_not_private_delivery(monkeypatch):
    impl = AsyncMock()
    fn = setup(monkeypatch, impl)
    with contexts.receive('', 'fixture'):
        with pytest.raises(ValueError, match='DELIVERY_OPERATION_INVALID'):
            await fn('fixture', 'behavior.send_v1', {'version': 1, 'operation': 'space', 'args': {}})
    impl.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_deliveries_do_not_share_receipts(monkeypatch):
    async def impl(plugin,cap,args):
        current.get().results.append({'action_id':'id','state':args['state']})
        await asyncio.sleep(.01)
        return {'sent':args['state']=='confirmed'}
    fn=setup(monkeypatch,impl)
    with contexts.receive('', 'fixture') as parent:
        results=await asyncio.gather(*[fn('fixture','behavior.send_v1',{'version':1,'operation':'message','args':{'state':s}}) for s in ('confirmed','unknown')])
        assert parent.results==[]
    assert [r['state'] for r in results]==['confirmed','unknown']
