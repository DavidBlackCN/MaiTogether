"""Native Host/Runner and unchanged community code; only model/OneBot are fakes."""
from datetime import datetime
from pathlib import Path
import asyncio
import json
import os
import time
import uuid

from aiohttp import web
import tomli_w

LIFE='test.life-provider'
HUSH='davidblackcn.maibot-maihush-plugin'
IDENTITY='davidblackcn.maibot-maiidentity-plugin'
ADAPTER='maibot-team.snowluma-adapter'
POKE='TAIY2020.smart_poke_plugin'
CATEYE='github.cateye.set-msg-emoji-like'
PROBE='test.behavior-probe'


async def run(work):
    weave = os.environ.get('MAIWEAVE_TEST') == '1'
    from src.config.config import config_manager
    config_manager.initialize()
    cfg=config_manager.get_global_config()
    cfg.bot.qq_account=''; cfg.bot.platform=''; cfg.telemetry.enable=False; cfg.maim_message.enabled=False
    from src.common.database.database import initialize_database
    initialize_database()
    from src.chat.message_receive.chat_manager import chat_manager
    session=await chat_manager.get_or_create_session('qq','10001','987654321',account_id='123456789',scope=None)
    stream=session.session_id
    writes=[]; all_calls=[]; peers=[]; faults={'drop':None, 'bad_receipt':False,'account':123456789}
    async def ws_handler(request):
        ws=web.WebSocketResponse(); await ws.prepare(request); peers.append(ws)
        async for frame in ws:
            if frame.type != web.WSMsgType.TEXT: continue
            body=json.loads(frame.data); action=body['action']; params=body.get('params',{})
            all_calls.append(action)
            if action=='get_msg' and faults.get('read_entered') is not None:
                entered=faults.pop('read_entered');release=faults.pop('read_release')
                entered.set();await release.wait()
            if action=='get_login_info': data={'user_id':faults['account'],'nickname':'test'}
            elif action=='get_version_info': data={'app_name':'SnowLuma','app_version':'2.4.0'}
            elif action=='get_msg': data={'message_id':params['message_id'],'message_type':'group',
                'group_id':987654321,'user_id':10001,'message_seq':0 if faults['bad_receipt'] else 1,
                'message':[{'type':'text','data':{'text':'test'}}]}
            elif action=='get_group_member_info': data={'user_id':params.get('user_id',10001),'nickname':'test','role':'member'}
            elif action=='get_group_member_list': data=[]
            elif action=='get_group_list': data=[{'group_id':987654321,'group_name':'test'}]
            elif action=='get_group_info': data={'group_id':987654321,'group_name':'test','member_count':2}
            elif action.startswith('get_') or action.startswith('can_'): data={}
            else:
                writes.append({'action':action,'params':params})
                data={'message_id':-100-len(writes), 'file_id':'fixture-file'}
                if faults['drop']==action: continue
            await ws.send_json({'status':'ok','retcode':0,'data':data,'echo':body['echo']})
        return ws
    model_calls=[]
    async def work_model(request):
        model_calls.append(await request.json())
        if faults.get('hold_model'):
            faults['model_started'].set()
            await faults['model_release'].wait()
        return web.json_response({'id':'fixture','model':'fixture','choices':[{'index':0,
            'message':{'role':'assistant','content':'fixture result'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':3,'completion_tokens':2,'total_tokens':5}})
    app=web.Application(); app.router.add_get('/',ws_handler)
    if os.environ.get('MAIWORK_TEST')=='1': app.router.add_post('/v1/chat/completions',work_model)
    server=web.AppRunner(app); await server.setup()
    site=web.TCPSite(server,'127.0.0.1',0); await site.start()
    port=site._server.sockets[0].getsockname()[1]
    from src.common.runtime_context import RuntimeContext, RUNTIME_CONTEXT_ENV
    os.environ[RUNTIME_CONTEXT_ENV] = RuntimeContext(
        bot_id=uuid.uuid4().hex, http_endpoint='isolated-test',
        public_base_url=f'http://127.0.0.1:{port}', status_path=work/'worker-status.json').to_env()
    configs={
      'maibot-maihush-plugin':{'plugin':{'enabled':True,'config_version':'2'},'groups':[{'group_id':'987654321','bot_account_id':'123456789'}],
         'management':{'source':'identity'},'reply':{'enabled':True},'social':{'enabled':True,'task_name':'test'}},
      'maibot-maiIdentity-plugin':{'plugin':{'enabled':True,'config_version':'4'},'management':{'admin_accounts':['10001']},
         'identity':{'people':[{'qq':'10003','nickname':'妈妈'}]}},
      'adapter':{'plugin':{'enabled':True,'config_version':'2.7.1'},'client':{'server':'127.0.0.1','port':port,
         'client_type':'snowluma','heartbeat_interval':0,'action_timeout_sec':2},
         'chat_abilities':{'enable_poke_tool':True,'enable_emoji_like_tool':True}},
      'poke':{'plugin':{'enabled':True,'config_version':'1.9.0','adapter_plugin_id':ADAPTER,'record_self_poke_to_context':False},
         'reaction':{'react_probability':1.0,'cooldown_seconds':0,'max_reactions_per_minute':0,
            'text_weight':1.0,'llm_weight':0.0,'emoji_weight':0.0,'back_poke_weight':0.0,
            'min_delay_seconds':0.0,'max_delay_seconds':0.0,'back_poke_max_times':1,'silent_chat_probability':0.0},
         'bystander':{'enabled':False},'proactive':{'enabled':False}},
      'cateye':{'plugin':{'enabled':True,'config_version':'0.3.2'},'emoji_reaction':{'tool_cooldown_seconds':0}},
    }
    if os.environ.get('MAIWORK_TEST')=='1':
        from maiwork_native import configure
        configure(work, configs, port)
    if weave:
        configs['maiweave'] = {'plugin': {'enabled': True, 'config_version': '0.9.0'},
            'life': {'enabled': True, 'autonomous': False, 'model_task': 'test'},
            'world': {'weather_enabled': False, 'news_enabled': False, 'search_enabled': False, 'places_enabled': False},
            'proactive': {'enabled': False}, 'memory': {'enabled': False}}
        if 'maiwork' in configs: configs['maiwork']['together']['life_provider'] = 'maiweave'
    for folder,config in configs.items():
        (work/'plugins'/folder/'config.toml').write_text(tomli_w.dumps(config),encoding='utf-8')
    (work/'behavior.json').write_text(json.dumps({'enabled':True, 'life_provider':{'plugin_id':LIFE,'api':'evaluate_behavior','version':'1'},'targets':[{
        'platform':'qq','account_id':'123456789','scope':None,'chat_type':'group','target_id':'987654321',
        'providers':['life','hush'],'autonomous_plugins':[PROBE,POKE,CATEYE,ADAPTER,HUSH]+(['chartyr.maiwork'] if os.environ.get('MAIWORK_TEST')=='1' else [])}]}),encoding='utf-8')
    if weave:
        behavior=json.loads((work/'behavior.json').read_text())
        behavior['targets'][0]['providers']=['life','hush']
        behavior['targets'][0]['autonomous_plugins'].append('ilworkcn.maiweave')
        behavior['life_provider']={'plugin_id':'ilworkcn.maiweave','api':'get_life_status','version':'1','protocol':'maiweave_status_v1'}
        (work/'behavior.json').write_text(json.dumps(behavior),encoding='utf-8')
    from src.plugin_runtime.integration import get_plugin_runtime_manager
    from src.plugin_runtime.host.supervisor import PluginSupervisor
    from src.plugin_runtime.behavior_policy.runtime import get_policy
    from src.platform_io.manager import get_platform_io_manager
    from src.platform_io.types import RouteKey
    manager=get_plugin_runtime_manager(); manager.ensure_builtin_hook_specs_registered()
    supervisor=PluginSupervisor(plugin_dirs=[work/'plugins'],group_name='behavior-test',
        hook_spec_registry=manager._hook_spec_registry,max_restart_attempts=0,health_check_interval_sec=300,runner_spawn_timeout_sec=25)
    manager._third_party_supervisor=supervisor; manager._register_capability_impls(supervisor)
    async def models(plugin_id,capability,args): return ['test']
    generating=asyncio.Event(); generated=asyncio.Event()
    async def model(plugin_id,capability,args):
        if plugin_id==PROBE:
            generating.set(); await generated.wait()
            return {'success':True,'response':'test','model_name':'local-fake'}
        if plugin_id==HUSH:
            data=json.loads(args['prompt'][1]['content'])
            return {'success':True,'response':json.dumps({'schema_version':1,'intent':'pause','target':'bot',
                'decision':'soft_silence','duration_seconds':60,'reason_code':'RESPECT_REQUEST',
                'evidence_message_ids':[data['request']['id']],'reply':'好，你们先聊。'})}
        return {'success':False,'response':'','model_name':'local-fake'}
    supervisor.capability_service.register_capability('llm.get_available_models',models)
    supervisor.capability_service.register_capability('llm.generate',model)
    async def call(plugin,name,args=None):
        r=await supervisor.invoke_api(plugin,name,args or {},timeout_ms=8000)
        assert not r.error and r.payload.get('success'),r
        return r.payload['result']
    async def wait(predicate):
        async with asyncio.timeout(20):
            while not await predicate(): await asyncio.sleep(.05)
    from src.chat.message_receive.message import SessionMessage
    from src.common.data_models.mai_message_data_model import MessageInfo,UserInfo,GroupInfo
    from src.common.data_models.message_component_data_model import MessageSequence,TextComponent
    from src.plugin_runtime.component_query import component_query_service
    from src.plugin_runtime.hook_payloads import serialize_session_message
    def raw(text,actor='10001'):
        m=SessionMessage(message_id=uuid.uuid4().hex,timestamp=datetime.now(),platform='qq')
        m.message_info=MessageInfo(user_info=UserInfo(actor,'test'),group_info=GroupInfo('987654321','test'))
        m.session_id=stream;m.account_id='123456789';m.scope=None
        m.raw_message=MessageSequence([TextComponent(text)]);m.processed_plain_text=text
        return m
    async def command(text,actor='10001'):
        executor,groups,_=component_query_service.find_command_by_text(text)
        assert executor, text
        return await executor(message=raw(text,actor),matched_groups=groups,plugin_config={})
    async def probe(mode='text',action='send_poke',params=None):
        return await call(PROBE,'probe',dict(mode=mode,stream_id=stream,action=action,
            params=params or {'group_id':987654321,'user_id':10001}))
    async def gateway(segments):
        message=serialize_session_message(raw('gateway'))
        message['raw_message']=segments
        r=await supervisor.invoke_message_gateway(ADAPTER,'snowluma_gateway',{'message':message,'route':{}},timeout_ms=8000)
        assert not r.error,r
        return r.payload['result']
    from src.core.tooling import ToolInvocation,ToolExecutionContext
    async def tool(name,args):
        return await component_query_service.invoke_tool_as_tool(ToolInvocation(name,arguments=args),
            ToolExecutionContext(session_id=stream,stream_id=stream,group_id='987654321',user_id='10001',platform='qq',is_group_chat=True))
    async def life_state(state):
        return await call(LIFE,'set_state',{'state':state})
    async def sleeping(): return await life_state('sleeping')
    async def awake(): return await life_state('awake')
    cases=[]
    try:
        await supervisor.start()
        if weave:
            from weave_native import run_cases
            await run_cases(locals())
            return
        assert {LIFE,HUSH,IDENTITY,ADAPTER,POKE,CATEYE,PROBE} <= set(supervisor._registered_plugins),supervisor._registered_plugins
        for plugin in (LIFE,HUSH,IDENTITY,ADAPTER,POKE,CATEYE):
            inspected=await supervisor.inspect_plugin_config(plugin)
            assert not inspected.config_error,(plugin,inspected.config_error)
        async def ready():
            drivers=get_platform_io_manager().resolve_drivers(RouteKey('qq','123456789',None))
            return bool(drivers)
        await wait(ready)
        if os.environ.get('MAIBOT_LIFE_TEST')=='1':
            from life_native import run_cases
            await run_cases(locals())
            return
        if os.environ.get('MAIBOT_SLEEP_TEST')=='1':
            from sleep_native import run_cases
            await run_cases(locals())
            return
        if os.environ.get('MAIBOT_COMMUNITY_TEST')=='1':
            from community_native import run_cases
            await run_cases(locals())
            return
        for folder,plugin in [('maibot-maiIdentity-plugin',IDENTITY),('maibot-maihush-plugin',HUSH)]:
            assert await supervisor.notify_plugin_config_updated(plugin,config_data=configs[folder],
                config_version=configs[folder]['plugin']['config_version'])
        cases.append('active_core_config_update')
        before=len(writes)
        assert await probe(), 'normal text rejected: '+str(list(get_policy().audit))
        assert len(writes)==before+1,writes
        cases.append('normal_text_one_write')
        assert (await probe('api'))['success']
        assert writes[-1]['action']=='send_poke'
        cases.append('direct_poke_success')
        assert (await probe('api','set_msg_emoji_like',{'message_id':-999,'emoji_id':128512,'set':True}))['success']
        cases.append('negative_message_id_reaction_success')
        before=len(writes)
        result=await tool('emoji_like',{'stream_id':stream,'target_message_id':'-999','emoji':'128512'})
        assert len(writes)==before+1,(result,list(get_policy().audit))
        cases.append('original_cateye_tool_success')
        before=len(writes)
        result=await tool('react_emoji',{'message_id':'-999','emoji_id':128512})
        assert len(writes)==before+1,result
        cases.append('native_reaction_tool_success_control')
        await manager.invoke_hook('chat.receive.after_process',message=serialize_session_message(raw('麦麦先安静一会','10003')))
        async def soft_silent():
            return (await call(HUSH,'get_public_constraints',{'stream_id':stream}))['data']['soft']=='SOFT_SILENT'
        await wait(soft_silent)
        await asyncio.sleep(.1)
        before=len(writes)
        assert not await probe() and not (await probe('api'))['success']
        await tool('emoji_like',{'stream_id':stream,'target_message_id':'-999','emoji':'128512'})
        assert len(writes)==before
        assert (await command('/maihush unmute'))[0]
        cases.append('natural_soft_silence_all_paths_blocked')
        before=len(writes)
        result=await command('/maihush mute 5m'); assert result[0],result
        assert len(writes)==before+1, ('acknowledgement missing',writes,list(get_policy().audit))
        cases.append('mute_one_acknowledgement')
        before=len(writes)
        assert not await probe()
        assert not (await probe('api'))['success']
        assert not (await probe('api','set_msg_emoji_like',{'message_id':-999,'emoji_id':128512,'set':True}))['success']
        assert len(writes)==before
        cases.append('hard_mute_text_poke_reaction_no_writes')
        before=len(writes)
        await tool('emoji_like',{'stream_id':stream,'target_message_id':'-999','emoji':'128512'})
        denied_before=len(get_policy().audit)
        await tool('react_emoji',{'message_id':'-999','emoji_id':128512})
        assert len(get_policy().audit)>denied_before
        assert get_policy().audit[-1]['reason']=='hush:group_policy'
        assert len(writes)==before
        cases.append('original_cateye_and_native_reaction_mute_no_writes')
        assert (await probe('api','get_msg',{'message_id':-999}))['success']
        for action in ('send_packet','.handle_quick_operation','get_credentials','new_unknown_action'):
            assert not (await probe('api',action,{}))['success'],action
        cases.append('readonly_survives_unknown_and_sensitive_denied')
        before=len(writes)
        assert not (await probe('api','send_msg',{'message_type':'private','group_id':987654321,'user_id':10001,'message':'bad route'}))['success']
        assert not (await probe('api','send_like',{'group_id':987654321,'user_id':10001}))['success']
        assert len(writes)==before
        cases.append('conflicting_group_private_action_targets_rejected')
        before=len(writes)
        data=serialize_session_message(raw('poke','10003'));data['is_notify']=True
        data['message_info']['additional_config']={'napcat_notice_type':'notify','napcat_notice_sub_type':'poke',
            'napcat_notice_payload':{'self_id':'123456789','user_id':'10003','target_id':'123456789','group_id':'987654321'}}
        await manager.invoke_hook('chat.receive.before_process',message=data)
        await asyncio.sleep(2)
        assert len(writes)==before, writes[before:]
        cases.append('original_smart_poke_fallback_blocked')
        assert (await command('/maihush unmute'))[0]
        await supervisor.reload_plugins([HUSH],reason='isolated-reload')
        assert await probe()
        cases.append('reload_and_unmute_success')
        mixed=[{'type':'text','data':{'text':'before'}},
            {'type':'file','data':{'file_ref':'fixture','name':'test.txt','url':'http://127.0.0.1/test.txt'}},
            {'type':'text','data':{'text':'after'}}]
        before=len(writes); audit_before=len(get_policy().audit)
        tickets_before=set(get_policy().actions)
        assert (await gateway(mixed))['success']
        assert [w['action'] for w in writes[before:]]==['send_msg','upload_group_file','send_msg']
        permitted=[a for a in list(get_policy().audit)[audit_before:] if a['state']=='permitted']
        assert len(permitted)==3 and all(a['provider_calls']==2 for a in permitted)
        assert len(set(get_policy().actions)-tickets_before)==3, 'batch preflight leaked tickets'
        cases.append('mixed_text_file_gateway_three_leaf_checks')
        before=len(writes); faults['drop']='upload_group_file'
        result=await gateway(mixed); faults['drop']=None
        assert not result['success'] and result['metadata']['behavior_state']=='partial',result
        assert len(writes)==before+2
        cases.append('batch_partial_timeout_no_tail_or_retry')
        assert (await probe('api','send_group_forward_msg',{'group_id':987654321,
            'messages':[{'type':'node','data':{'uin':'10001','name':'test','content':[{'type':'text','data':{'text':'forward'}}]}}]}))['success']
        assert (await command('/maihush mute 5m'))[0]
        before=len(writes)
        assert not (await gateway(mixed))['success']
        assert not (await probe('api','send_group_forward_msg',{'group_id':987654321,'messages':[]}))['success']
        assert len(writes)==before
        assert (await command('/maihush unmute'))[0]
        cases.append('mixed_batch_forward_mute_no_writes')
        for provider in (LIFE,HUSH,IDENTITY):
            assert not (await call(PROBE,'probe',{'mode':'private','provider':provider}))['success']
        r=await supervisor.invoke_api(PROBE,'probe',{'mode':'forged'})
        assert not r.payload.get('success')
        cases.append('private_provider_and_adapter_capability_not_public')
        before=len(writes)
        assert not json.loads((await command('/control_test'))[1])['success']
        get_policy().management=[{'plugin':PROBE,'component':'control_test','actions':['set_group_ban']}]
        assert not json.loads((await command('/control_test','10003'))[1])['success']
        assert not json.loads((await command('/control_test cross'))[1])['success']
        assert len(writes)==before
        assert json.loads((await command('/control_test'))[1])['success']
        assert len(writes)==before+1 and writes[-1]['action']=='set_group_ban'
        get_policy().management=[]
        cases.append('explicit_command_identity_admin_only_no_argument_forgery')
        await sleeping()
        before=len(writes)
        assert not await probe()
        assert not (await probe('api'))['success']
        await tool('emoji_like',{'stream_id':stream,'target_message_id':'-999','emoji':'128512'})
        assert len(writes)==before
        assert await awake()
        assert await probe()
        cases.append('sleep_all_paths_blocked_trusted_wake_restores')
        pending=asyncio.create_task(probe('generate')); await asyncio.wait_for(generating.wait(),3)
        await sleeping(); before=len(writes); generated.set()
        assert not await pending and len(writes)==before
        assert await awake()
        cases.append('sleep_during_generation_blocks_submission')
        await life_state('busy')
        before=len(writes)
        assert not (await probe('api'))['success'] and len(writes)==before
        assert get_policy().audit[-1]['reason']=='life:busy'
        await awake()
        cases.append('busy_life_contract_blocks_social')
        assert (await supervisor.unload_plugins([LIFE],reason='provider-loss')).success
        before=len(writes)
        assert not (await probe('api'))['success']
        assert (await probe('api','get_msg',{'message_id':-999}))['success']
        assert len(writes)==before
        assert await supervisor.reload_plugins([LIFE],reason='provider-restored')
        cases.append('required_provider_unloaded_denies_only_writes')
        # A scheduling barrier around the real provider holds the adapter's send lock.
        # The second action must check the newly committed mute after it gets that lock.
        policy=get_policy(); original_provider=policy._provider
        entered=asyncio.Event(); release=asyncio.Event(); held=False
        async def held_provider(name,request):
            nonlocal held
            if name=='life' and not held:
                held=True; entered.set(); await release.wait()
            return await original_provider(name,request)
        policy._provider=held_provider
        before=len(writes)
        first=asyncio.create_task(probe('api'))
        await asyncio.wait_for(entered.wait(),2)
        second=asyncio.create_task(probe('api'))
        mute=asyncio.create_task(command('/maihush mute 5m'))
        async def is_muted():
            return (await call(HUSH,'get_public_constraints',{'stream_id':stream}))['data']['hard']=='HARD_SILENT'
        try:
            await wait(is_muted)
        finally:
            release.set(); policy._provider=original_provider
        first_result,second_result=await asyncio.gather(first,second)
        assert not first_result['success'] and not second_result['success']
        assert (await mute)[0]
        assert all(w['action']!='send_poke' for w in writes[before:])
        assert (await command('/maihush unmute'))[0]
        cases.append('queued_actions_recheck_committed_mute')
        before=len(writes)
        slow_provider=policy._provider
        async def timeout_provider(name,request):
            if name=='life': await asyncio.sleep(.4)
            return await slow_provider(name,request)
        policy._provider=timeout_provider
        try: assert not (await probe('api'))['success']
        finally: policy._provider=slow_provider
        assert len(writes)==before
        cases.append('provider_timeout_denies_without_write')
        before=len(writes)
        faults['drop']='send_poke'
        assert not (await probe('api'))['success']
        faults['drop']=None
        assert len(writes)==before+1
        assert get_policy().audit[-1]['state']=='unknown'
        cases.append('submitted_timeout_unknown_no_retry')
        before=len(writes)
        faults['bad_receipt']=True
        assert not await probe()
        faults['bad_receipt']=False
        assert len(writes)==before+1
        assert get_policy().audit[-1]['state']=='unknown'
        cases.append('unconfirmed_group_delivery_unknown_no_retry')
        before=len(writes)
        results=await asyncio.gather(*(probe('api') for _ in range(8)))
        assert all(r['success'] for r in results),results
        assert len(writes)==before+8
        cases.append('concurrent_actions_complete_without_deadlock')
        old=get_policy()._qq_contract().metadata['behavior_connection']
        await peers[-1].close()
        async def reconnected():
            state=get_policy()._qq_contract()
            return bool(state and state.metadata['behavior_connection']!=old)
        await wait(reconnected)
        assert (await probe('api'))['success']
        cases.append('websocket_reconnect_new_generation_success')
        # Route contract is mandatory, including generation/account/scope, not just the plugin ID.
        state=get_policy()._qq_contract(); before=len(writes)
        contract=state.metadata.pop('behavior_contract')
        assert not await probe() and len(writes)==before
        state.metadata['behavior_contract']=contract
        for key,value in [('account_id','222222222'),('scope','other')]:
            old_value=getattr(state,key);setattr(state,key,value)
            try:
                assert not (await probe('api'))['success'] and len(writes)==before
            finally: setattr(state,key,old_value)
        cases.append('missing_contract_account_scope_mismatch_fail_closed')
        await chat_manager.get_or_create_session('qq','10001','987654321',account_id='222222222',scope=None)
        get_policy().targets.append({**get_policy().targets[0],'account_id':'222222222'})
        assert (await command('/maihush mute 5m'))[0]
        async def switch_account(number):
            faults['account']=number
            await peers[-1].close()
            async def account_ready():
                value=get_policy()._qq_contract()
                return bool(value and value.account_id==str(number))
            await wait(account_ready)
        await switch_account(222222222)
        assert (await probe('api'))['success']  # Explicit Hush account binding excludes this account.
        await switch_account(123456789)
        before=len(writes)
        assert not (await probe('api'))['success'] and len(writes)==before
        assert (await command('/maihush unmute'))[0]
        cases.append('two_accounts_same_group_do_not_share_mute_authority')
        before=len(writes)
        await supervisor.stop()
        await supervisor.start()
        await wait(ready)
        await asyncio.sleep(.2)
        assert len(writes)==before
        assert (await probe('api'))['success']
        cases.append('runner_restart_keeps_records_no_unknown_replay')
        from src.plugin_runtime.host.circuit_breaker import get_plugin_circuit_breaker
        breaker=get_plugin_circuit_breaker()
        for _ in range(3):
            permit=breaker.try_acquire(HUSH,'test','hook:send_service.before_send')
            breaker.record_failure(permit,'isolated circuit test')
        before=len(writes)
        assert not await probe() and len(writes)==before
        cases.append('security_hook_open_circuit_fails_closed')
    finally:
        report={'cases':cases,'writes':len(writes),'onebot_calls':all_calls,'audit':list(get_policy().audit)}
        (work/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        await supervisor.stop()
        await get_platform_io_manager().stop()
        await server.cleanup()
    print(json.dumps({'passed':len(cases),'cases':cases,'writes':len(writes)},ensure_ascii=False))


if __name__=='__main__': asyncio.run(run(Path.cwd()))
