"""MaiWork + actual Host/Runner/core plugins; QQ and model services remain local substitutes."""
import asyncio
import json
import uuid
import socket

WORK='chartyr.maiwork'
VITA='davidblackcn.maibot-maivita-plugin'


def configure(work, configs, model_port):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    configs['maiwork']={
        'plugin':{'enabled':True,'config_version':'0.5.4'},
        'groups':{'serve':[{'group':'qq:987654321'}]},
        'together':{'enabled':True,'public_publish':False},
        'approval':{'auto_review':False,'admins':[]},
        'focus':{'personal_profile':False,'personal_feeds':False},
        'environments':{'railway':False,'freestyle':False,'workspace_root':str(work/'workspaces')},
        'group_space':{'enabled':False},
        'console':{'listen':f'127.0.0.1:{port}','update_check':False,'herenow_share':False},
        'storage':{'data_dir':str(work/'maiwork-data')},
        'jev':{'enabled':False},
        'endpoints':[{'id':'local','protocol':'openai','base_url':f'http://127.0.0.1:{model_port}/v1','api_key':'fixture','retries':0}],
        'model_list':[{'id':'fixture','endpoint':'local','model':'fixture','max_tokens':1024}],
    }


async def run_cases(c):
    call,command,supervisor=c['call'],c['command'],c['supervisor']
    cases,writes,stream=c['cases'],c['writes'],c['stream']
    async def probe(mode='status',**args):return await call(WORK,'acceptance_probe',dict(mode=mode,stream_id=stream,**args))
    assert WORK in supervisor._registered_plugins,supervisor._registered_plugins
    state=await probe();assert state['started'],state
    inspected=await supervisor.inspect_plugin_config(WORK)
    assert not inspected.config_error,inspected.config_error
    cases.append('maiwork_actual_runner_enabled_start')
    assert (await probe('available'))['available']
    assert not (await probe('publish'))['allowed']
    r=await probe('model'); assert r['ok'],r
    assert c['model_calls'] and '群昵称' in str(c['model_calls'][-1])
    cases.append('actual_maiwork_model_uses_loopback_service_with_identity_rule')
    n=len(writes);assert (await probe('send'))['state']=='confirmed'
    assert len(writes)==n+1
    assert (await probe('file'))['file_id']=='fixture-file'
    cases.append('detailed_message_and_file_receipts_through_native_sdk')
    assert (await command('/maihush mute 5m'))[0]
    n=len(writes);r=await probe('send');assert r['state']=='deferred',r
    r=await probe('file');assert r['state']=='deferred',r
    assert len(writes)==n
    cases.append('hush_policy_defers_text_and_file_without_public_fallback')
    assert (await command('/maihush unmute'))[0]
    c['faults']['drop']='send_msg'
    n=len(writes);r=await probe('outbox',key='unknown-native');assert r['status']=='uncertain',r
    c['faults']['drop']=None
    await probe('flush');assert len(writes)==n+1
    cases.append('unknown_actual_websocket_timeout_no_outbox_retry')
    # Persist a real Host message; Identity must verify its author and route.
    from src.services import message_service
    from src.chat.message_receive.message import SessionMessage
    from src.common.database.database_model import Messages
    # Use the same persistence service as inbound messages (signature checked below).
    message=c['raw']('/mw 批准 R-fixture')
    from src.common.utils.utils_message import MessageUtils
    await MessageUtils.store_message_to_db_async(message)
    shape=await probe('message_shape',mid=message.message_id)
    (c['work']/'message-shape.json').write_text(json.dumps(shape,ensure_ascii=False,indent=2),encoding='utf-8')
    r=await probe('admin',mid=message.message_id,user_id='10001',raw=message.processed_plain_text)
    assert r['allowed'],shape
    assert not (await probe('admin',mid=message.message_id,user_id='10003',raw=message.processed_plain_text))['allowed']
    assert not (await probe('admin',mid=message.message_id,user_id='10001',raw='/mw 批准 R-other'))['allowed']
    allowed=await probe('approval',mid=message.message_id,user_id='10001',raw=message.processed_plain_text)
    denied=await probe('approval',mid=message.message_id,user_id='10003',raw=message.processed_plain_text)
    assert '没找到请求' in allowed['reply'] and '只有配置的任务管理员' in denied['reply'],(allowed,denied)
    identity='davidblackcn.maibot-maiidentity-plugin'
    assert (await supervisor.unload_plugins([identity],reason='identity-fixture')).success
    assert not (await probe('admin',mid=message.message_id,user_id='10001',raw=message.processed_plain_text))['allowed']
    assert await supervisor.reload_plugins([identity],reason='identity-fixture')
    cases.append('identity_admin_actual_message_author_and_text_validation')
    import tomli_w
    config=c['configs']['maibot-maivita-plugin']
    config['availability']={'enabled':True,'busy_fatigue_threshold':0}
    path=c['work']/'plugins/maibot-maivita-plugin/config.toml'
    path.write_text(tomli_w.dumps(config),encoding='utf-8')
    assert await supervisor.reload_plugins([VITA],reason='busy-fixture')
    assert not (await probe('available'))['available']
    n=len(writes);assert (await probe('send'))['state']=='deferred';assert len(writes)==n
    config.pop('availability');path.write_text(tomli_w.dumps(config),encoding='utf-8')
    assert await supervisor.reload_plugins([VITA],reason='busy-fixture-end')
    cases.append('busy_state_blocks_new_work_and_delivery')
    c['faults'].update(hold_model=True,model_started=asyncio.Event(),model_release=asyncio.Event())
    pending=asyncio.create_task(probe('generate_send'))
    await asyncio.wait_for(c['faults']['model_started'].wait(),3)
    await c['sleeping']()
    c['faults']['model_release'].set();c['faults']['hold_model']=False
    assert (await pending)['state']=='deferred'
    cases.append('sleep_during_actual_model_generation_prevents_send')
    n=len(writes)
    assert not (await probe('available'))['available']
    assert not (await probe('model_guard'))['allowed']
    before_models=len(c['model_calls']);assert not (await probe('model'))['ok']
    assert len(c['model_calls'])==before_models
    r=await probe('outbox',key='sleep-native');assert r['status']=='pending' and r['attempts']==0,r
    assert (await probe('send'))['state']=='deferred'
    assert len(writes)==n
    cases.append('vita_sleep_stops_new_model_work_and_defers_delivery')
    assert (await supervisor.unload_plugins([VITA],reason='provider-fixture')).success
    assert not (await probe('available'))['available']
    assert (await probe('send'))['state']=='deferred'
    assert len(writes)==n
    assert await supervisor.reload_plugins([VITA],reason='restore-fixture')
    cases.append('missing_vita_provider_fails_closed')
    assert (await command('/maivita wake'))[0]
    assert (await supervisor.unload_plugins([WORK],reason='lifecycle-fixture')).success
    assert await supervisor.reload_plugins([WORK],reason='lifecycle-fixture')
    assert (await probe())['started']
    for attempt in range(4):
        await asyncio.sleep(.3)
        rows=await probe('flush',offset=301+attempt*120)
        if next(r for r in rows if r['key']=='sleep-native')['status']=='sent':break
    assert next(r for r in rows if r['key']=='unknown-native')['status']=='uncertain'
    assert next(r for r in rows if r['key']=='sleep-native')['status']=='sent'
    cases.append('reload_preserves_unknown_and_delivers_deferred_after_wake')
