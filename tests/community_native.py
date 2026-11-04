"""Untouched Cateye/Smart Poke through real incoming OneBot and outgoing Tools.

The cognition boundary is a local observer, not a real model. Incoming transport,
codec, Platform IO, ChatBot, Hooks, Commands, Tools, Runner and policy remain real.
"""
import asyncio
from copy import deepcopy
import json
import time
from types import SimpleNamespace

from native_scenario import CATEYE,POKE,VITA,HUSH


async def run_cases(values):
    c=SimpleNamespace(**values)
    from src.chat.message_receive.bot import chat_bot
    from src.common.utils.utils_message import MessageUtils
    from src.platform_io.manager import get_platform_io_manager
    from src.plugin_runtime.behavior_policy.runtime import get_policy
    from src.plugin_runtime.hook_payloads import serialize_session_message
    policy=get_policy();io=get_platform_io_manager()
    received=[];counter=0;context_records=[];history_shapes=[]
    old_receiver=chat_bot.heartflow_message_receiver.process_message
    async def cognition_boundary(message):
        await MessageUtils.store_message_to_db_async(message)
        received.append({'id':message.message_id,'notify':message.is_notify,'text':message.processed_plain_text})
    chat_bot.heartflow_message_receiver.process_message=cognition_boundary
    io.set_inbound_dispatcher(c.manager._dispatch_platform_inbound)
    # Keep synthetic event bookkeeping visible without starting a real model loop.
    async def context_append(plugin_id,capability,args):
        context_records.append({'plugin':plugin_id,'args':args})
        return {'success':True}
    c.supervisor.capability_service.register_capability('maisaka.context.append',context_append)
    original_history=c.manager._cap_message_get_by_time_in_chat
    async def history(plugin_id,capability,args):
        result=await original_history(plugin_id,capability,args)
        if plugin_id==CATEYE:
            history_shapes.append([{'id':m.get('message_id'),'account_id':m.get('account_id'),
                'additional_keys':list((m.get('message_info',{}).get('additional_config') or {}).keys())}
                for m in result.get('messages',[]) if isinstance(m,dict)])
        return result
    c.supervisor.capability_service.register_capability('message.get_by_time_in_chat',history)
    async def eventually(test):
        async with asyncio.timeout(8):
            while not test(): await asyncio.sleep(.02)
    async def configure(extra):
        config=deepcopy(c.configs['cateye']);config.update(extra)
        normalized=await c.supervisor.validate_plugin_config(CATEYE,config)
        assert await c.supervisor.notify_plugin_config_updated(CATEYE,normalized,'0.3.2')
    async def incoming(actor=10003,text='隔离测试普通聊天',await_entry=True):
        nonlocal counter
        counter+=1;mid=-10000-counter
        await c.peers[-1].send_json({'time':int(time.time()),'self_id':123456789,'post_type':'message',
            'message_type':'group','sub_type':'normal','group_id':987654321,'user_id':actor,'message_id':mid,
            'message':[{'type':'text','data':{'text':text}}],'raw_message':text,
            'sender':{'user_id':actor,'nickname':'test','card':'','role':'member'}})
        if await_entry: await eventually(lambda:any(r['id']==str(mid) for r in received))
        return mid
    async def reaction(emoji='128512'):
        return await c.tool('emoji_like',{'stream_id':c.stream,'target_message_id':'-999','emoji':emoji})
    async def poke_notice():
        nonlocal counter
        counter+=1
        await c.peers[-1].send_json({'time':int(time.time())+counter,'self_id':123456789,'post_type':'notice',
            'notice_type':'notify','sub_type':'poke','group_id':987654321,'user_id':10003,
            'target_id':123456789,'operator_id':10003})
    def mark(name,before,expected):
        assert len(c.writes)-before==expected,(name,c.writes[before:],list(policy.audit)[-5:])
        c.cases.append(name)
    async def blocked_state(label):
        before=len(c.writes);audit=len(policy.audit);records=len(context_records)
        await incoming();await incoming(10004)
        assert len(policy.audit)>=audit+2
        await reaction();await reaction('并不存在的表情描述')
        assert not await c.probe()
        assert len(context_records)==records  # Denied reactions must not be recorded as successful experiences.
        mark(label,before,0)
    try:
        before=len(c.writes)
        await incoming()
        mark('cateye_default_auto_off_receives_without_reacting',before,0)
        before=len(c.writes)
        await reaction();await reaction('并不存在的表情描述')
        assert [int(w['params']['emoji_id']) for w in c.writes[before:]]==[128512,12951]
        mark('cateye_tool_and_default_emoji_fallback_positive',before,2)
        await configure({'pig_friends':{'enabled':True,'group_list':['987654321'],'normal_probability':1.0,
            'normal_cooldown_seconds':0,'pig_users':['10004'],'pig_cooldown_seconds':0,'pig_chain_skip_cooldown_probability':1.0}})
        before=len(c.writes)
        await incoming();await incoming(10004);await incoming(10004)
        mark('cateye_real_inbound_normal_and_pig_chain_positive',before,3)
        before=len(c.writes)
        await c.tool('emoji_like',{'stream_id':c.stream,'emoji':'76'})
        mark('cateye_tool_resolves_latest_real_message_from_history',before,1)
        allowed=policy.targets[0]['autonomous_plugins'];policy.targets[0]['autonomous_plugins']=[p for p in allowed if p!=CATEYE]
        try:
            before=len(c.writes);await incoming()
            mark('unlisted_background_cateye_denied',before,0)
            before=len(c.writes);await reaction()
            mark('same_session_tool_remains_allowed_without_background_permission',before,1)
        finally: policy.targets[0]['autonomous_plugins']=allowed
        before=len(c.writes)
        await poke_notice();await eventually(lambda:len(c.writes)>before)
        await asyncio.sleep(.2)
        assert any(w['action']=='send_msg' for w in c.writes[before:])
        c.cases.append('smart_poke_real_notice_positive')
        await c.sleeping()
        await blocked_state('sleep_blocks_auto_pig_tool_fallback_and_text')
        before=len(c.writes)
        policy.enabled=False
        try:
            await incoming();await reaction()
            mark('ab_sleep_without_unified_control_original_cateye_still_writes',before,2)
        finally: policy.enabled=True
        before=len(c.writes);await incoming();await reaction()
        mark('ab_same_sleep_with_unified_control_zero_writes',before,0)
        before=len(c.writes);audit=len(policy.audit)
        await poke_notice();await eventually(lambda:len(policy.audit)>audit)
        await asyncio.sleep(.3)
        mark('sleep_blocks_smart_poke_text_and_back_poke_fallback',before,0)
        for hook in ('maisaka.planner.before_request','maisaka.replyer.before_request'):
            result=await c.manager.invoke_hook(hook,session_id=c.stream,extra_prompt='')
            assert not result.aborted
            assert '睡眠' in result.kwargs['extra_prompt']
        c.cases.append('sleep_keeps_cognition_hook_available_with_life_context')
        before=len(c.writes);notices=len(received)
        await c.peers[-1].send_json({'time':int(time.time())+100,'self_id':123456789,'post_type':'notice',
            'notice_type':'group_msg_emoji_like','sub_type':'add','group_id':987654321,'user_id':10003,
            'operator_id':10003,'message_id':-999,'likes':[{'emoji_id':'76','count':1}]})
        await eventually(lambda:len(received)>notices)
        assert any(r['notify'] and '表达了' in r['text'] for r in received[notices:]),received[notices:]
        mark('sleep_receives_and_translates_friend_reaction_without_echo',before,0)
        before=len(c.writes)
        await c.tool('emoji_like_list',{})
        mark('sleep_readonly_emoji_list_remains_available',before,0)
        assert (await c.command('/maivita wake'))[0]
        before=len(c.writes);await incoming()
        mark('wake_new_message_reacts_without_backlog',before,1)
        await incoming(text='麦麦先安静一会',await_entry=False)
        async def soft_silent():
            return (await c.call(HUSH,'get_public_constraints',{'stream_id':c.stream}))['data']['soft']=='SOFT_SILENT'
        await c.wait(soft_silent);await asyncio.sleep(.2)
        await blocked_state('soft_mute_blocks_cateye_all_outgoing_paths')
        assert (await c.command('/maihush unmute'))[0]
        assert (await c.command('/maihush mute 5m'))[0]
        await blocked_state('hard_mute_blocks_cateye_all_outgoing_paths')
        assert (await c.command('/maihush unmute'))[0]
        # Busy uses Vita's real configured body threshold, not a fake policy answer.
        cfg=deepcopy(c.configs['maibot-maivita-plugin']);cfg['availability']={'enabled':True,'busy_energy_threshold':100}
        import tomli_w
        path=c.work/'plugins/maibot-maivita-plugin/config.toml';path.write_text(tomli_w.dumps(cfg),encoding='utf-8')
        assert await c.supervisor.reload_plugins([VITA],reason='community-busy-test')
        await blocked_state('busy_blocks_cateye_all_outgoing_paths')
        path.write_text(tomli_w.dumps(c.configs['maibot-maivita-plugin']),encoding='utf-8')
        assert await c.supervisor.reload_plugins([VITA],reason='community-busy-end')
        before=len(c.writes)
        audit_before=len(policy.audit)
        entered=asyncio.Event();release=asyncio.Event()
        c.faults.update(read_entered=entered,read_release=release)
        pending=asyncio.create_task(reaction())
        try:
            await asyncio.wait_for(entered.wait(),3)
            await c.sleeping()
        finally: release.set()
        await pending
        assert any(e['reason']=='vita:sleeping' for e in list(policy.audit)[audit_before:])
        mark('cateye_prepared_while_awake_but_sleep_before_submission',before,0)
        assert (await c.command('/maivita wake'))[0]
        assert (await c.supervisor.unload_plugins([VITA],reason='community-provider-loss')).success
        await blocked_state('missing_vita_blocks_cateye_all_outgoing_paths')
        assert await c.supervisor.reload_plugins([VITA],reason='community-provider-restored')
        before=len(c.writes);await incoming()
        mark('provider_restore_new_request_success_no_replay',before,1)
    finally:
        chat_bot.heartflow_message_receiver.process_message=old_receiver
        io.set_inbound_dispatcher(None)
        (c.work/'community-observations.json').write_text(json.dumps({'received':received,'context_records':context_records,
            'history_route_shapes':history_shapes,
            'cognition':'local observer at HeartFC.process_message; actual LLM selection not tested',
            'cases':c.cases},ensure_ascii=False,indent=2),encoding='utf-8')
