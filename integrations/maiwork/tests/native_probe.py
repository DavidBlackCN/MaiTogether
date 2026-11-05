"""Injected only into the isolated test copy, never distributed with MaiWork."""
from maibot_sdk import API
import time
from pathlib import Path


class NativeProbe:
    @API('acceptance_probe', public=True, version='1')
    async def acceptance_probe(self, mode='status', **args):
        from .maiwork.together import DeliveryError
        app=self._app
        if mode=='status':
            return {'started':bool(app and app._started),'reason':getattr(getattr(app,'together',None),'last_reason',''),
                    'problems':app.problems if app else []}
        if not app or not app._started: raise RuntimeError('MaiWork not started')
        try:
            if mode=='send':
                result=await app.host.send_text(args['stream_id'],'MaiWork native fixture')
                return {'state':'confirmed','sent':result.sent}
            if mode=='file':
                path=app.get_settings().workspace_root/'fixture.txt';path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('isolated fixture',encoding='utf-8')
                return {'state':'confirmed','file_id':await app.host.upload_group_file('987654321',str(path),'fixture.txt')}
            if mode=='available':return {'available':await app.together.available('987654321')}
            if mode in ('model','generate_send'):
                try:
                    app.agents.update_profile('main',{'model':'fixture'})
                    result=await app.models.chat(agent='main',messages=[{'role':'user','content':'fixture'}],group_id='987654321',purpose='acceptance',retries=0,timeout=3)
                    if mode=='generate_send':
                        try:
                            sent=await app.host.send_text(args['stream_id'],result.text)
                            return {'state':'confirmed','sent':sent.sent}
                        except DeliveryError as exc:return {'state':exc.state}
                    return {'ok':True,'text':result.text}
                except Exception as exc:return {'ok':False,'error':str(exc)}
            if mode=='model_guard':
                try: await app.together.model_guard('987654321','')
                except Exception: return {'allowed':False}
                return {'allowed':True}
            if mode=='outbox':
                app._remember_session_row('987654321',args['stream_id'],time.time())
                app.outbox.enqueue(args['key'],'987654321','text',{'text':'fixture','push_kind':'command'})
                await app.outbox.flush(time.time())
                row=app.store.read().execute('SELECT status, attempts FROM outbox WHERE key=?',(args['key'],)).fetchone()
                return dict(row)
            if mode=='flush':
                await app.outbox.flush(time.time()+args.get('offset',301))
                return [dict(r) for r in app.store.read().execute('SELECT key,status,attempts FROM outbox')]
            if mode=='publish':return {'allowed':await app.together.can_publish()}
            if mode=='admin':return {'allowed':await app.together.command_admin('987654321',args['user_id'],args['mid'],args['raw'])}
            if mode=='message_shape':return await app.host.message_by_id(args['mid'],args['stream_id'])
            if mode=='approval':
                return {'reply':await app.commands._dispatch('987654321',args['user_id'],'fixture',args['raw'].split(),raw=args['raw'],message_id=args['mid'])}
            raise ValueError(mode)
        except DeliveryError as exc:
            return {'state':exc.state,'reason':str(exc)}
