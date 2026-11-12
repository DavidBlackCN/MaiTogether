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
    if os.environ.get('POST_PROCESSING_TEST') == '1':
        for plugin in ('github.cateye.better-post-processing', 'saberlights.smart-segmentation-plugin'):
            assert plugin in c.supervisor._registered_plugins
            inspected = await c.supervisor.inspect_plugin_config(plugin)
            assert not inspected.config_error, (plugin, inspected.config_error)
        c.cases.append('cateye_and_smart_segmentation_actual_runner_coexist')
    assert VITA not in c.supervisor._registered_plugins and COORD not in c.supervisor._registered_plugins
    assert not (c.work/'plugins/maibot-maivita-plugin').exists()
    assert {WEAVE,HUSH,IDENTITY,POKE,CATEYE,ADAPTER} <= set(c.supervisor._registered_plugins)
    for plugin in (WEAVE,HUSH,IDENTITY):
        inspected=await c.supervisor.inspect_plugin_config(plugin)
        assert not inspected.config_error,(plugin,inspected.config_error)
    async def ready(): return bool(get_platform_io_manager().resolve_drivers(RouteKey('qq','123456789',None)))
    await c.wait(ready)
    if os.environ.get('POST_PROCESSING_TEST') == '1':
        from src.plugin_runtime.integration import get_plugin_runtime_manager
        import json
        segments = ['今天读了几页书，', '准备休息一下再继续。']
        response = ''.join(segments)
        model_calls = []
        async def segmentation_model(plugin_id, capability, args):
            assert plugin_id == 'saberlights.smart-segmentation-plugin'
            model_calls.append(plugin_id)
            return {'success': True, 'response': json.dumps(segments), 'model_name': 'local-fake'}
        c.supervisor.capability_service.register_capability('llm.generate', segmentation_model)
        try:
            manager = get_plugin_runtime_manager()
            await manager.invoke_hook('maisaka.replyer.after_response', response=response, session_id=c.stream)
            result = await manager.invoke_hook('maisaka.reply.before_post_process', response=response,
                session_id=c.stream, reply_message_id='-999', reply_tool_args={},
                skip_post_process=False, enable_splitter=True, enable_chinese_typo=True)
            assert model_calls == ['saberlights.smart-segmentation-plugin'], model_calls
            assert result.kwargs['skip_post_process'] is True, result
            assert result.kwargs['response'] == response, result
        finally:
            c.supervisor.capability_service.register_capability('llm.generate', c.model)
        c.cases.append('smart_segmentation_claims_reply_and_cateye_preserves_text')
    c.cases.append('maiweave_actual_runner_without_vita_or_coordinate')
    request={'category':'social','stream_id':c.stream,'route':dict(policy.targets[0]),'origin':{'kind':'host'}}
    async def decision(category='social'):
        return await policy._provider('life',{**request,'category':category})
    async def seed(**kwargs): return await c.call(WEAVE,'acceptance_state',kwargs)
    async def publish(suffix): return await c.call(WEAVE, 'acceptance_delivery', {'suffix': suffix})
    policy.targets.append({'platform': 'qq', 'account_id': '123456789', 'scope': None,
        'chat_type': 'space', 'target_id': '123456789', 'providers': ['life'],
        'autonomous_plugins': [WEAVE], 'cross_target_plugins': [WEAVE]})
    async def work(mode='available',**kwargs):
        return await c.call(WORK,'acceptance_probe',dict(mode=mode,stream_id=c.stream,**kwargs))
    has_work=os.environ.get('MAIWORK_TEST')=='1'
    assert (await decision())['decision']=='allow'
    if policy.behavior_enabled:
        assert await c.probe()
        assert (await c.probe('api'))['success']
        n=len(c.writes)
        await c.tool('emoji_like',{'stream_id':c.stream,'target_message_id':'-999','emoji':'128512'})
        assert len(c.writes)==n+1
        await c.tool('react_emoji',{'message_id':'-999','emoji_id':128512})
        assert len(c.writes)==n+2
    c.cases.append('public_status_maps_to_policy_queries_and_actual_tools')
    assert (await c.call(WEAVE, 'acceptance_delivery', {'mode': 'message', 'stream_id': c.stream}))['state'] == 'confirmed'
    result = await publish('normal')
    assert result['status'] == '已发布', result
    await seed(kind='sleep'); n = len(c.writes)
    result = await publish('sleep')
    assert result['state'] == 'deferred' and result['status'] == '草稿', result
    assert len(c.writes) == n
    await seed()
    assert (await c.command('/maihush mute 5m'))[0]
    assert (await publish('group-muted'))['status'] == '已发布'
    assert (await c.command('/maihush unmute'))[0]
    c.faults['drop'] = 'send_qzone_msg'
    result = await publish('unknown')
    c.faults['drop'] = ''
    assert result['state'] == 'unknown' and result['status'] == '待核对', result
    c.cases.append('maiweave_real_sdk_delivery_space_sleep_hush_unknown')
    entered, release = asyncio.Event(), asyncio.Event()
    async def reply_fixture(plugin_id, capability, args):
        entered.set()
        await release.wait()
        return {'success': True, 'text': 'isolated generated life sharing'}
    c.supervisor.capability_service.register_capability('maisaka.reply.generate', reply_fixture)
    task = asyncio.create_task(c.call(WEAVE, 'acceptance_share', {'stream_id': c.stream}))
    await asyncio.wait_for(entered.wait(), 4)
    await seed(kind='sleep'); n = len(c.writes)
    release.set()
    rows = await task
    assert rows[-1]['delivery_state'] == 'deferred', rows
    assert len(c.writes) == n
    await seed()
    c.cases.append('maiweave_generation_sleep_race_defers_before_submission')
    if has_work:
        assert (await work())['available']
        assert (await work('model'))['ok']
        assert not (await work('publish'))['allowed']
        assert (await work('send'))['state']=='confirmed'
        assert (await work('file'))['file_id'] == 'fixture-file'
        c.faults['drop'] = 'send_msg'; n = len(c.writes)
        assert (await work('outbox', key='work-unknown'))['status'] == 'uncertain'
        c.faults['drop'] = None
        await work('flush')
        assert len(c.writes) == n + 1
        from src.common.utils.utils_message import MessageUtils
        message = c.raw('/mw 批准 R-fixture')
        await MessageUtils.store_message_to_db_async(message)
        args = {'mid': message.message_id, 'raw': message.processed_plain_text}
        assert (await work('admin', user_id='10001', **args))['allowed']
        assert not (await work('admin', user_id='10003', **args))['allowed']
        allowed = await work('approval', user_id='10001', **args)
        denied = await work('approval', user_id='10003', **args)
        assert '没找到请求' in allowed['reply'] and '只有配置的任务管理员' in denied['reply'], (allowed, denied)
        c.cases.append('maiwork_status_model_and_delivery_without_vita')
        c.cases.append('maiwork_file_unknown_receipt_and_real_identity_approval')

    for kind,reason in [('work','busy'),('study','busy'),('travel','busy'),('sleep','sleeping')]:
        await seed(kind=kind)
        assert (await decision('social'))['reason']==reason
        if policy.behavior_enabled:
            n=len(c.writes)
            assert not (await c.probe('api'))['success']
            await c.tool('emoji_like',{'stream_id':c.stream,'target_message_id':'-999','emoji':'128512'})
            assert len(c.writes)==n
        if has_work: assert not (await work())['available']
    c.cases.append('work_study_travel_and_sleep_block_social')
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

    # Native reception hook can wake without a model.
    await seed(kind='sleep')
    await c.call(WEAVE,'acceptance_person',{'stream_id':c.stream,'user_id':'10001'})
    await c.manager.invoke_hook('chat.receive.after_process',message=serialize_session_message(c.raw('今天心情不好，陪陪我')))
    status=await c.call(WEAVE,'get_life_status')
    assert status['awake_until'],status
    assert (await decision())['decision']=='allow'
    c.cases.append('upstream_keyword_wake_without_planner')
    gap=await c.call(WEAVE,'acceptance_expire_wake')
    assert gap['internal_sleeping'] and not gap['status']['sleeping']
    assert gap['status']['current'] is None and gap['status']['awake_until'] is None
    assert gap['status']['effective_sleeping'] and gap['status']['sleep_until']
    assert gap['behavior']['decision']=='defer' and gap['behavior']['reason']=='sleeping'
    assert gap['read_only']
    assert (await decision())['reason']=='sleeping'
    n=len(c.writes)
    assert not (await c.probe('api'))['success']
    await c.tool('react_emoji',{'message_id':'-999','emoji_id':128512})
    assert len(c.writes)==n
    if has_work: assert not (await work())['available']
    c.cases.append('expired_real_wake_reports_effective_sleep_and_blocks_actions')
    await seed(kind=None)
    assert (await decision())['decision']=='allow'
    assert (await c.probe('api'))['success']
    await seed(kind=None,all_day=True)
    assert (await decision())['decision']=='allow'
    c.cases.append('scheduled_idle_and_all_day_idle_allowed')
    await seed(age=86400)
    assert (await decision())['decision']=='allow'
    if has_work: assert (await work())['available']
    c.cases.append('fresh_query_remains_valid_when_stored_body_state_is_old')
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
    assert await c.supervisor.notify_plugin_config_updated(WEAVE,cfg,cfg['plugin']['config_version'])
    assert (await decision())['decision']=='allow'
    assert (await c.supervisor.unload_plugins([WEAVE],reason='life-unload')).success
    try: await decision()
    except RuntimeError: pass
    else: raise AssertionError('unloaded life allowed')
    if has_work: assert not (await work())['available']
    assert await c.supervisor.reload_plugins([WEAVE],reason='life-reload')
    assert (await decision())['decision']=='allow'
    c.cases.append('configuration_reload_unload_and_restart_fail_closed')
