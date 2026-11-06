import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from CharTyr_MaiWork.maiwork.config import load_settings
from CharTyr_MaiWork.maiwork.together import Together, DeliveryError
from CharTyr_MaiWork.maiwork.herenow import HereNow, HereNowError
from test_outbox import _make, _rows, GID, NOON, FakeHereNow, _seed_task, _artifact_file, Delivery


def app_for(host, raw=None):
    settings,_=load_settings(raw or {'groups':{'serve':[{'group':'qq:'+GID}]}})
    app=SimpleNamespace(host=host,get_settings=lambda:settings)
    app.together=Together(app)
    host.together=app.together
    return app


def life(available=True):
    return {'api_version':1,'ok':True,'data':{'available':available,'sleep_phase':'awake' if available else 'sleeping',
        'snapshot_valid_until':(datetime.now(timezone.utc)+timedelta(seconds=5)).isoformat()}}


@pytest.mark.asyncio
async def test_weave_admission_without_vita_and_without_send_permission():
    now=datetime.now(timezone.utc)
    state={'version':1,'ready':True,'enabled':True,'schedule_enabled':False,
        'updated_at':now.isoformat(),'sleeping':False,'awake_until':None,'current':None}
    host=SimpleNamespace(_call=AsyncMock(return_value=state))
    app=app_for(host,{'groups':{'serve':[{'group':'qq:'+GID}]},'together':{'life_provider':'maiweave'}})
    assert await app.together.available(GID)
    assert await app.together.available()  # global background admission, not a fabricated group
    assert all(call.kwargs['api_name']=='ilworkcn.maiweave.get_life_status' for call in host._call.call_args_list)
    assert not await app.together.can_publish()
    host._call.reset_mock()
    assert not await app.together.available('outside')
    host._call.assert_not_called()
    for changes in ({'ready':False},{'enabled':False},{'version':2},
                    {'schedule_enabled':True},{'updated_at':(now-timedelta(minutes=10)).isoformat()}):
        host._call.return_value={**state,**changes}
        assert not await app.together.available(GID)
    host._call.return_value={**state,'current':{'id':'work','kind':'work','status':'active',
        'start':(now-timedelta(minutes=1)).isoformat(),'end':(now+timedelta(minutes=1)).isoformat()}}
    assert not await app.together.available(GID)
    app.together._active_tasks.add('approved')
    await app.together.model_guard(GID,'approved')
    with pytest.raises(Exception): await app.together.model_guard(GID,'new')
    host._call.side_effect=TimeoutError()
    assert not await app.together.available(GID)
    assert all(call.kwargs['api_name']=='ilworkcn.maiweave.get_life_status' for call in host._call.call_args_list)


def test_shared_life_rules_are_bundled_verbatim():
    import CharTyr_MaiWork.maiwork.life_status as shared
    original=Path(__file__).parents[3]/'host/src/plugin_runtime/behavior_policy/life_status.py'
    assert Path(shared.__file__).read_bytes()==original.read_bytes()


def test_recommended_config_is_valid():
    import tomllib
    raw=tomllib.loads((Path(__file__).parents[1]/'recommended.toml').read_text(encoding='utf-8'))
    settings,problems=load_settings(raw)
    assert not problems
    assert settings.together.enabled and not settings.together.public_publish
    assert not settings.approval.auto_review and not settings.extensions.mcp


@pytest.mark.asyncio
async def test_life_failure_and_running_task_exception():
    host=SimpleNamespace(_call=AsyncMock(return_value=life(False)))
    app=app_for(host)
    assert not await app.together.available(GID)
    with pytest.raises(Exception): await app.together.model_guard(GID,'')
    app.together._active_tasks.add('T-1')
    await app.together.model_guard(GID,'T-1')
    host._call.side_effect=TimeoutError()
    assert not await app.together.available(GID)
    assert not await app.together.can_publish()


@pytest.mark.asyncio
@pytest.mark.parametrize('state,status',[('unknown','uncertain'),('partial','uncertain'),('deferred','pending'),('failed','failed')])
async def test_receipt_no_retry_or_public_fallback(tmp_path,state,status):
    store,settings,host,push,mentions,outbox=_make(tmp_path,herenow=FakeHereNow())
    try:
        host.text_errors.append(DeliveryError(state))
        outbox.enqueue('case',GID,'text',{'text':'test','push_kind':'command'})
        await outbox.flush(NOON)
        assert _rows(store)[0]['status']==status
        if status!='pending':
            await outbox.flush(NOON+3600)
            assert len(host.texts)==1
        _seed_task(store)
        path=_artifact_file(tmp_path,name='x.txt',text='fixture')
        host.upload_errors.append(DeliveryError(state))
        await Delivery(store,outbox).deliver_task('T-1',kind='file',path=path,name='x.txt',note='fixture')
        await outbox.flush(NOON)
        assert all(r['kind']!='herenow' for r in _rows(store))
    finally:store.close()


@pytest.mark.asyncio
async def test_public_default_denies_before_network(tmp_path):
    (tmp_path/'index.html').write_text('fixture')
    with pytest.raises(HereNowError): await HereNow().publish(tmp_path)
    with pytest.raises(HereNowError): await HereNow(allow_publish=AsyncMock(return_value=False)).publish(tmp_path)


@pytest.mark.asyncio
async def test_outbox_sleep_recheck_and_latest_progress(tmp_path):
    store,settings,host,push,mentions,outbox=_make(tmp_path)
    try:
        app=app_for(host)
        host._call=AsyncMock(return_value=life(False))
        outbox.enqueue('first',GID,'text',{'text':'first','push_kind':'status'},task_id='T-1')
        outbox.enqueue('last',GID,'text',{'text':'last','push_kind':'status'},task_id='T-1')
        await outbox.flush(NOON)
        assert not host.texts
        assert [r['status'] for r in _rows(store)]==['dropped','pending']
        host._call.return_value=life()
        await outbox.flush(NOON+61)
        assert len(host.texts)==1 and host.texts[0]['text']=='last'
    finally:store.close()


@pytest.mark.asyncio
async def test_transport_failure_is_unknown():
    host=SimpleNamespace(_call=AsyncMock(side_effect=TimeoutError()))
    app=app_for(host)
    with pytest.raises(DeliveryError) as e: await app.together.delivery('message',{})
    assert e.value.state=='unknown'


@pytest.mark.asyncio
async def test_identity_requires_exact_message():
    message={'session_id':'s','platform':'qq','account_id':'bot','scope':None,'processed_plain_text':'/mw 批准 R-1',
        'message_info':{'user_info':{'user_id':'123'},'group_info':{'group_id':GID}}}
    host=SimpleNamespace(session_for_group=AsyncMock(return_value='s'),message_by_id=AsyncMock(return_value=message),
                         _call=AsyncMock(return_value={'is_admin':True}))
    guard=app_for(host).together
    assert await guard.command_admin(GID,'123','m','/mw 批准 R-1')
    assert not await guard.command_admin(GID,'999','m','/mw 批准 R-1')
    assert not await guard.command_admin('other','123','m','/mw 批准 R-1')
    assert not await guard.command_admin(GID,'123','m','/mw 批准 R-2')


@pytest.mark.asyncio
async def test_task_admission_and_running_task_can_finish():
    from CharTyr_MaiWork.maiwork.app import MaiWorkApp
    host=SimpleNamespace(_call=AsyncMock(return_value=life(False)))
    app=app_for(host)
    app._running_tasks={'T-1'}
    app._restart_if_requeued=Mock()
    app.coordinator=SimpleNamespace(run_task=AsyncMock())
    await MaiWorkApp._run_task_guarded(app,'T-1')
    app.coordinator.run_task.assert_not_awaited()
    app._restart_if_requeued.assert_not_called()
    assert not app._running_tasks
    host._call.return_value=life()
    app.store=SimpleNamespace(kv_get=lambda key:None)
    async def run(tid):
        host._call.return_value=life(False)
        await app.together.model_guard(GID,tid)
    app.coordinator.run_task=AsyncMock(side_effect=run)
    app._running_tasks.add('T-1')
    await MaiWorkApp._run_task_guarded(app,'T-1')
    app.coordinator.run_task.assert_awaited_once_with('T-1')
    assert not app.together._active_tasks and not app._running_tasks
    with pytest.raises(Exception):await app.together.model_guard(GID,'T-1')


@pytest.mark.asyncio
@pytest.mark.parametrize('allowed',[[],['read']])
async def test_mcp_requires_explicit_tool_list(tmp_path,allowed):
    import httpx
    from CharTyr_MaiWork.maiwork.extensions import Extensions
    from test_extensions import _McpServer, _tool_spec, _mcp_setting, _tools
    from CharTyr_MaiWork.maiwork.store import Store
    store=Store(tmp_path/'mcp.sqlite3');store.migrate()
    ext=Extensions(lambda:_mcp_setting(tools=allowed),transport=httpx.MockTransport(
        _McpServer([_tool_spec('read'),_tool_spec('write')])))
    tools=_tools(store)
    try:
        await ext.start(tools)
        assert [s['function']['name'] for s in tools.specs('worker')]==(['mcp_gh_read'] if allowed else [])
    finally:
        await ext.aclose();store.close()
