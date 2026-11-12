"""给上游阅读节奏用例补充新版详细交付替身，不改变其生活断言。"""
from unittest.mock import AsyncMock
import pytest


@pytest.fixture(autouse=True)
def detailed_delivery(plugin):
    async def capability(name, **kwargs):
        assert name == 'behavior.send_v1' and kwargs['operation'] == 'message'
        args = kwargs['args']
        result = await plugin.ctx.send.text(args['processed_plain_text'], args['stream_id'],
            return_details=True, storage_message=True, sync_to_maisaka_history=True)
        return {'version': 1, 'state': 'confirmed' if result['sent'] else 'failed',
                'message_id': result.get('message_id')}
    plugin.ctx.call_capability = AsyncMock(side_effect=capability)
