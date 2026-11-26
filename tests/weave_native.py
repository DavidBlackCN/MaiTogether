"""Latest pinned upstream MaiWeave + real Host/Runner, without Vita installed."""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from native_scenario import HUSH, IDENTITY, POKE, CATEYE, ADAPTER
VITA='davidblackcn.maibot-maivita-plugin'
COORD='davidblackcn.maibot-maicoordinate-plugin'

WEAVE='ilworkcn.maiweave'


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
    assert (await decision())['decision']=='allow'
    if policy.behavior_enabled:
        assert await c.probe()
        assert (await c.probe('api'))['success']
        n=len(c.writes)
        await c.tool('emoji_like',{'stream_id':c.stream,'target_message_id':'-999','emoji':'128512'})
        assert len(c.writes)==n+1
        await c.tool('react_emoji',{'message_id':'-999','emoji_id':128512})
        assert len(c.writes)==n+2
    c.cases.append('public_behavior_api_controls_actual_tools')
    assert (await c.call(WEAVE, 'acceptance_delivery', {'mode': 'message', 'stream_id': c.stream}))['sent'] is True
    async def check_image(allowed):
        before = len(c.writes)
        result = await c.call(WEAVE, 'acceptance_delivery', {'mode': 'image', 'stream_id': c.stream})
        assert bool(result.get('sent')) == allowed, result
        assert len(c.writes) == before + int(allowed), c.writes[before:]
        if allowed:
            assert any(part['type'] == 'image' for part in c.writes[-1]['params']['message'])
    await check_image(True)
    result = await publish('normal')
    assert result['status'] == '已发布', result
    c.faults['client'] = 'NapCat'
    try:
        writes = len(c.writes)
        result = await publish('napcat')
        assert result['status'] == '发布失败' and '登录信息' in result['error'], result
        assert 'get_cookies' not in c.all_calls and len(c.writes) == writes
    finally:
        del c.faults['client']
    c.cases.append('napcat_diary_cannot_read_account_cookies')
    await seed(kind='sleep'); n = len(c.writes)
    await check_image(False)
    if os.environ.get('MAIWORK_TEST') == '1':
        from maiwork_native import check_paused_reply
        await check_paused_reply(c, '-803')
        c.cases.append('original_maiwork_processes_command_asleep_without_qq_output')
    result = await publish('sleep')
    assert result['status'] == '发布失败' and 'life:sleeping' in result['error'], result
    assert len(c.writes) == n
    await seed()
    assert (await c.command('/maihush mute 5m'))[0]
    await check_image(False)
    c.cases.append('maiweave_sdk_image_delivered_awake_and_blocked_asleep_or_muted')
    if os.environ.get('MAIWORK_TEST') == '1':
        await check_paused_reply(c, '-804')
        c.cases.append('original_maiwork_reply_blocked_in_muted_group')
    assert (await publish('group-muted'))['status'] == '已发布'
    assert (await c.command('/maihush unmute'))[0]
    c.faults['drop'] = 'send_qzone_msg'
    result = await publish('unknown')
    c.faults['drop'] = ''
    assert result['status'] == '待核对', result
    n = len(c.writes)
    assert (await publish('unknown'))['status'] == '待核对'
    assert len(c.writes) == n
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
    assert rows[-1]['outcome'] == '发送失败', rows
    assert len(c.writes) == n
    await seed()
    c.cases.append('upstream_share_generation_sleep_race_blocked_before_submission')
    async def check_outbound(kind, chat_allowed, active_allowed, **settings):
        await seed(kind=kind, **settings)
        for behavior, expected in [('conversation', chat_allowed), ('proactive', active_allowed)]:
            verdict = await c.call(WEAVE, 'evaluate_behavior', {'behavior': behavior})
            assert (verdict['decision'] == 'allow') == expected, (kind, behavior, verdict)
        before = len(c.writes)
        batch = await get_platform_io_manager().send_message(c.raw('ordinary host reply'), RouteKey('qq', '123456789', None))
        assert len(c.writes) == before + int(chat_allowed), (kind, batch)
        before = len(c.writes)
        assert bool(await c.probe()) == active_allowed, kind
        assert bool((await c.probe('api'))['success']) == active_allowed, kind
        await c.tool('emoji_like', {'stream_id': c.stream, 'target_message_id': '-999', 'emoji': '128512'})
        assert len(c.writes) == before + 3 * int(active_allowed), kind

    for kind in ('work', 'study'):
        await check_outbound(kind, True, False)
    await check_outbound('travel', True, True)
    c.cases.append('work_study_and_travel_follow_upstream_for_chat_and_plugin_sends')
    await check_outbound('sleep', False, False)
    await check_outbound('sleep', True, False, nap_quiet=False)
    c.cases.append('nap_setting_allows_only_ordinary_reply_and_quiet_sleep_blocks_both')
    # Native reception hook can wake without a model.
    await seed(kind='sleep')
    await c.call(WEAVE,'acceptance_person',{'stream_id':c.stream,'user_id':'10001'})
    await c.manager.invoke_hook('chat.receive.after_process',message=serialize_session_message(c.raw('今天心情不好，陪陪我')))
    status=await c.call(WEAVE,'get_life_status')
    assert status['awake_until'],status
    assert (await decision())['decision']=='allow'
    c.cases.append('upstream_keyword_wake_without_planner')
    replies = await c.call(WEAVE, 'acceptance_farewell', {'stream_id': c.stream})
    assert [item['action'] for item in replies] == ['continue', 'abort']
    assert (await decision())['reason'] == 'farewell'
    reply = await policy._provider('life', {**request, 'action': 'platform.message', 'message_id': 'reply'})
    assert reply['decision'] == 'allow'
    before = len(c.writes)
    assert not (await c.probe('api'))['success']
    assert (await publish('farewell'))['status'] == '发布失败'
    assert len(c.writes) == before
    c.cases.append('farewell_scopes_reply_and_defers_third_party_actions')
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
    c.cases.append('expired_real_wake_reports_effective_sleep_and_blocks_actions')
    await seed(kind=None)
    assert (await decision())['decision']=='allow'
    assert (await c.probe('api'))['success']
    await seed(kind=None,all_day=True)
    assert (await decision())['decision']=='allow'
    c.cases.append('scheduled_idle_and_all_day_idle_allowed')
    await seed(age=86400)
    assert (await decision())['decision']=='allow'
    c.cases.append('fresh_query_remains_valid_when_stored_body_state_is_old')
    await seed()
    if policy.behavior_enabled:
        assert (await c.command('/maihush mute 5m'))[0]
        n=len(c.writes)
        assert not await c.probe()
        await get_platform_io_manager().send_message(c.raw('ordinary reply in muted group'), RouteKey('qq', '123456789', None))
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
    entry=c.supervisor.api_registry.get_apis(plugin_id=WEAVE,name='evaluate_behavior',version='1')[0]
    for field,value in [('public',False),('version','2'),('enabled',False)]:
        old=getattr(entry,field);setattr(entry,field,value)
        try:
            try: await decision()
            except RuntimeError: pass
            else: raise AssertionError('bad public behavior contract allowed')
        finally: setattr(entry,field,old)
    c.cases.append('actual_public_registry_visibility_version_and_disabled_rejected')
    cfg=c.configs['maiweave']
    assert await c.supervisor.notify_plugin_config_updated(WEAVE,cfg,cfg['plugin']['config_version'])
    assert (await decision())['decision']=='allow'
    assert (await c.supervisor.unload_plugins([WEAVE],reason='life-unload')).success
    try: await decision()
    except RuntimeError: pass
    else: raise AssertionError('unloaded life allowed')
    assert await c.supervisor.reload_plugins([WEAVE],reason='life-reload')
    assert (await decision())['decision']=='allow'
    c.cases.append('configuration_reload_unload_and_restart_fail_closed')
