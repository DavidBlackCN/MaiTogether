"""Latest pinned upstream MaiWeave + real Host/Runner, without Vita installed."""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from native_scenario import HUSH, IDENTITY, POKE, CATEYE, ADAPTER
VITA='davidblackcn.maibot-maivita-plugin'
COORD='davidblackcn.maibot-maicoordinate-plugin'

WEAVE='ilworkcn.maiweave'
WORK='chartyr.maiwork'


async def run_cases(values):
    c=SimpleNamespace(**values)
    from src.plugin_runtime.behavior_policy.runtime import get_policy
    from src.platform_io.manager import get_platform_io_manager
    from src.platform_io.types import RouteKey
    from src.plugin_runtime.hook_payloads import serialize_session_message
    policy=get_policy()
    assert VITA not in c.supervisor._registered_plugins and COORD not in c.supervisor._registered_plugins
    assert not (c.work/'plugins/maibot-maivita-plugin').exists()
    assert {WEAVE,HUSH,IDENTITY,POKE,CATEYE,ADAPTER} <= set(c.supervisor._registered_plugins)
    for plugin in (WEAVE,HUSH,IDENTITY):
        inspected=await c.supervisor.inspect_plugin_config(plugin)
        assert not inspected.config_error,(plugin,inspected.config_error)
    async def ready(): return bool(get_platform_io_manager().resolve_drivers(RouteKey('qq','123456789',None)))
    await c.wait(ready)
    c.cases.append('maiweave_actual_runner_without_vita_or_coordinate')
    request={'category':'cognition','stream_id':c.stream,'route':dict(policy.targets[0]),'origin':{'kind':'host'}}
    async def decision(category='cognition'):
        return await policy._provider('life',{**request,'category':category})
    async def seed(**kwargs): return await c.call(WEAVE,'acceptance_state',kwargs)
    async def work(mode='available',**kwargs):
        return await c.call(WORK,'acceptance_probe',dict(mode=mode,stream_id=c.stream,**kwargs))
    has_work=os.environ.get('MAIWORK_TEST')=='1'
    if policy.sleep_enabled:
        from src.plugin_runtime.behavior_policy import sleep_guard as guard
    assert (await decision())['decision']=='allow'
    if policy.behavior_enabled:
        assert await c.probe()
        assert (await c.probe('api'))['success']
        n=len(c.writes)
        await c.tool('emoji_like',{'stream_id':c.stream,'target_message_id':'-999','emoji':'128512'})
        assert len(c.writes)==n+1
        await c.tool('react_emoji',{'message_id':'-999','emoji_id':128512})
        assert len(c.writes)==n+2
    c.cases.append('public_status_maps_to_cognition_social_and_actual_tools')
    if has_work:
        assert (await work())['available']
        assert (await work('model'))['ok']
        assert not (await work('publish'))['allowed']
        assert (await work('send'))['state']=='confirmed'
        c.cases.append('maiwork_status_model_and_delivery_without_vita')

    for kind,reason in [('work','busy'),('study','busy'),('travel','busy'),('sleep','sleeping')]:
        await seed(kind=kind)
        assert (await decision('social'))['reason']==reason
        assert (await decision())['decision']==('deny' if kind=='sleep' else 'allow')
        if policy.behavior_enabled:
            n=len(c.writes)
            assert not (await c.probe('api'))['success']
            await c.tool('emoji_like',{'stream_id':c.stream,'target_message_id':'-999','emoji':'128512'})
            assert len(c.writes)==n
        if has_work: assert not (await work())['available']
    c.cases.append('work_study_travel_block_social_only_sleep_blocks_cognition_too')
    if has_work:
        await seed()
        c.faults.update(hold_model=True,model_started=asyncio.Event(),model_release=asyncio.Event())
        pending=asyncio.create_task(work('generate_send'))
        try:
            await asyncio.wait_for(c.faults['model_started'].wait(),3)
            await seed(kind='sleep')
        finally:
            c.faults['model_release'].set();c.faults['hold_model']=False
        assert (await pending)['state']=='deferred'
        count=len(c.model_calls)
        assert not (await work('model'))['ok'] and len(c.model_calls)==count
        row=await work('outbox',key='weave-sleep')
        assert row['status']=='pending' and row['attempts']==0
        c.cases.append('maiwork_generation_sleep_race_and_new_model_guard')

    if policy.sleep_enabled:
        from src.chat.heart_flow.heartflow_message_processor import HeartFCMessageReceiver
        from src.chat.heart_flow.heartflow_manager import heartflow_manager
        from src.services.memory_flow_service import memory_automation_service
        from src.common.database.database import get_db_session
        from src.common.database.database_model import Messages
        from src.common.data_models.mai_message_data_model import MaiMessage
        from sqlmodel import select
        registered=AsyncMock();memory=AsyncMock()
        message=c.raw('sleep raw only')
        with patch.object(heartflow_manager,'get_or_create_heartflow_chat',AsyncMock(return_value=SimpleNamespace(register_message=registered))), \
             patch.object(memory_automation_service,'on_incoming_message',memory):
            await HeartFCMessageReceiver().process_message(message)
        registered.assert_not_awaited();memory.assert_not_awaited()
        with get_db_session() as db:
            stored=MaiMessage.from_db_instance(db.exec(select(Messages).where(Messages.message_id==message.message_id)).one())
        assert guard.record_only(stored) and not await guard.memory_allowed(stored)
        from src.maisaka.chat_loop_service import MaisakaChatLoopService
        planner=MaisakaChatLoopService.__new__(MaisakaChatLoopService);planner._session_id=c.stream
        try: await planner.chat_loop_step([])
        except guard.CognitionPaused: pass
        else: raise AssertionError('sleeping planner advanced')
        from src.chat.replyer.maisaka_generator_base import BaseMaisakaReplyGenerator
        replyer=BaseMaisakaReplyGenerator.__new__(BaseMaisakaReplyGenerator)
        replyer.express_model=object();replyer._persist_reply_preview=lambda *a,**kw: None
        ok,result=await replyer.generate_reply_with_context(stream_id=c.stream,chat_history=[])
        assert not ok and 'sleeping' in result.error_message
        await seed()
        assert not await guard.memory_allowed(stored)
        c.cases.append('sleep_real_receiver_planner_replyer_and_memory_no_draft_replay')

    # Real reception hook can wake before the Host cognition gate, without a model.
    await seed(kind='sleep')
    await c.call(WEAVE,'acceptance_person',{'stream_id':c.stream,'user_id':'10001'})
    await c.manager.invoke_hook('chat.receive.after_process',message=serialize_session_message(c.raw('今天心情不好，陪陪我')))
    status=await c.call(WEAVE,'get_life_status')
    assert status['awake_until'],status
    assert (await decision())['decision']=='allow'
    c.cases.append('upstream_keyword_wake_before_cognition_without_planner')
    gap=await seed(kind=None,gap=True)
    assert gap['internal_sleeping'] and not gap['status']['sleeping']
    assert (await decision())['reason']=='sleep_state_ambiguous'
    if has_work: assert not (await work())['available']
    c.cases.append('upstream_expired_wake_gap_reproduced_and_denied')
    await seed(kind=None)
    assert (await decision())['reason']=='sleep_state_ambiguous'
    await seed(kind=None,all_day=True)
    assert (await decision())['decision']=='allow'
    c.cases.append('ambiguous_idle_denied_explicit_all_day_idle_allowed')
    await seed(age=181)
    assert (await decision())['reason']=='life_state_stale'
    if has_work: assert not (await work())['available']
    c.cases.append('stale_state_denies_host_and_work')
    await seed()
    if policy.behavior_enabled:
        assert (await c.command('/maihush mute 5m'))[0]
        n=len(c.writes)
        assert not await c.probe()
        if has_work: assert (await work('send'))['state']=='deferred'
        assert len(c.writes)==n
        assert (await c.command('/maihush unmute'))[0]
        c.cases.append('hush_and_identity_command_authorization_retained')
        # Original Smart Poke receives a real notice; no source adaptation.
        from src.plugin_runtime.hook_payloads import serialize_session_message
        io=get_platform_io_manager();io.set_inbound_dispatcher(c.manager._dispatch_platform_inbound)
        import time
        counter=0
        async def poke_notice():
            nonlocal counter
            counter+=1
            await c.peers[-1].send_json({'time':int(time.time())+counter,'self_id':123456789,'post_type':'notice',
                'notice_type':'notify','sub_type':'poke','group_id':987654321,'user_id':10003,
                'target_id':123456789,'operator_id':10003})
        n=len(c.writes)
        await poke_notice()
        async def wrote(): return len(c.writes)>n
        await c.wait(wrote)
        await seed(kind='sleep');n=len(c.writes);a=len(policy.audit)
        await poke_notice()
        async def checked(): return len(policy.audit)>a
        await c.wait(checked)
        assert len(c.writes)==n
        io.set_inbound_dispatcher(None)
        c.cases.append('original_smart_poke_real_notice_allowed_awake_denied_asleep')
    await seed()
    entry=c.supervisor.api_registry.get_apis(plugin_id=WEAVE,name='get_life_status',version='1')[0]
    for field,value in [('public',False),('version','2'),('enabled',False)]:
        old=getattr(entry,field);setattr(entry,field,value)
        try:
            try: await decision()
            except RuntimeError: pass
            else: raise AssertionError('bad public status contract allowed')
        finally: setattr(entry,field,old)
    c.cases.append('actual_public_registry_visibility_version_and_disabled_rejected')
    cfg=c.configs['maiweave']
    assert await c.supervisor.notify_plugin_config_updated(WEAVE,cfg,'0.9.0')
    assert (await decision())['decision']=='allow'
    assert (await c.supervisor.unload_plugins([WEAVE],reason='life-unload')).success
    try: await decision()
    except RuntimeError: pass
    else: raise AssertionError('unloaded life allowed')
    if has_work: assert not (await work())['available']
    assert await c.supervisor.reload_plugins([WEAVE],reason='life-reload')
    assert (await decision())['decision']=='allow'
    c.cases.append('configuration_reload_unload_and_restart_fail_closed')
