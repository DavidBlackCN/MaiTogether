"""Synthetic life state for Host regression; never shipped as a life engine."""
from maibot_sdk import API, MaiBotPlugin


class LifeFixture(MaiBotPlugin):
    async def on_load(self):
        self.state = 'awake'

    async def on_unload(self): pass
    async def on_config_update(self, scope, config_data, version): pass

    @API('set_state', public=False, version='1')
    async def set_state(self, state):
        assert state in ('awake', 'busy', 'sleeping')
        self.state = state
        return True

    @API('evaluate_behavior', public=False, version='1')
    async def evaluate_behavior(self, **kwargs):
        request = self.ctx.behavior_context().get('request')
        if not isinstance(request, dict):
            return {'version': 1, 'decision': 'deny', 'reason': 'untrusted_request'}
        denied = self.state == 'sleeping' or (self.state == 'busy' and request.get('category') != 'cognition')
        return {'version': 1, 'decision': 'deny' if denied else 'allow',
                'reason': self.state if denied else 'available'}


def create_plugin(): return LifeFixture()
