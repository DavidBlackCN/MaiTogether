"""Isolated acceptance client, never included in a deployment bundle."""
from maibot_sdk import API, Command, MaiBotPlugin
import json


class Probe(MaiBotPlugin):
    async def on_load(self): pass
    async def on_unload(self): pass
    async def on_config_update(self, scope, config_data, version): pass

    @Command('control_test',pattern=r'^/control_test(?:\s|$)',description='Isolated management fixture')
    async def management(self,text='',**kwargs):
        group=123123123 if 'cross' in text else 987654321
        result=await self.probe(mode='api',action='set_group_ban',params={'group_id':group,'user_id':10003,'duration':60,
            'actor':'10001','origin':{'kind':'command','actor':'10001'}})
        return bool(result.get('success')),json.dumps(result),1

    @API('probe', public=True, version='1')
    async def probe(self, stream_id='', mode='text', action='send_poke', params=None, **kwargs):
        if mode == 'generate':
            await self.ctx.call_host_method('cap.call', payload={'capability':'llm.generate','args':{'prompt':'local test'}})
            mode = 'text'
        if mode == 'text':
            return await self.ctx.send.text('隔离验收', stream_id, typing=False)
        if mode == 'api':
            return await self.ctx.call_host_method('cap.call', payload={'capability':'api.call',
                'args': {'api_name':'adapter.napcat.action.call','version':'1',
                         'args': {'action_name':action,'params':params or {}}}})
        if mode == 'private':
            return await self.ctx.call_host_method('cap.call', payload={'capability':'api.call',
                'args': {'api_name':kwargs['provider']+'.evaluate_behavior','version':'1','args':{}}})
        if mode == 'forged':
            return await self.ctx.call_host_method('cap.call', payload={
                'capability': 'behavior.check', 'args': {'phase': 'prepare', 'action': 'send_poke'}})
        raise ValueError(mode)


def create_plugin(): return Probe()
