"""Isolated acceptance client, never included in a deployment bundle."""
from maibot_sdk import API, Command, MaiBotPlugin
import json


class Probe(MaiBotPlugin):
    async def on_load(self):
        self.life_result = {'version': 1, 'decision': 'allow', 'reason': 'available'}
        self.life_delay = 0
    async def on_unload(self): pass
    async def on_config_update(self, scope, config_data, version): pass

    @API('fixture_life', public=False, version='1')
    async def fixture_life(self, **kwargs):
        import asyncio
        control = self.ctx.behavior_context()
        if not isinstance(control.get('request'), dict):
            return {'version': 1, 'decision': 'deny', 'reason': 'untrusted_request'}
        await asyncio.sleep(self.life_delay)
        return dict(self.life_result)

    @API('set_fixture_life', public=False, version='1')
    async def set_fixture_life(self, result, delay=0):
        self.life_result, self.life_delay = result, delay
        return True

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
        if mode == 'forged_metadata':
            return await self.ctx.call_host_method('cap.call', payload={
                '_maitogether': {'reference': 'forged', 'control': {'admin': True}},
                'context_ref': 'forged', 'behavior_control': {'admin': True},
                'capability': 'api.call', 'args': {
                    'api_name': 'adapter.napcat.action.call', 'version': '1',
                    'args': {'action_name': 'set_group_ban', 'params': {
                        'group_id': 987654321, 'user_id': 10003, 'duration': 60,
                        'origin': {'kind': 'command', 'actor': '10001'}}}}})
        if mode == 'details':
            return await self.ctx.call_host_method('cap.call', payload={
                'capability': 'send.text', 'args': {
                    'text': 'receipt fixture', 'stream_id': stream_id, 'return_details': True}})
        if mode == 'private':
            return await self.ctx.call_host_method('cap.call', payload={'capability':'api.call',
                'args': {'api_name':kwargs['provider']+'.evaluate_behavior','version':'1','args':{}}})
        if mode == 'forged':
            return await self.ctx.call_host_method('cap.call', payload={
                'capability': 'behavior.check', 'args': {'phase': 'prepare', 'action': 'send_poke'}})
        raise ValueError(mode)


def create_plugin(): return Probe()
