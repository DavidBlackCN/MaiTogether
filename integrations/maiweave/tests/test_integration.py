import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_proactive_modes import prepare
from maiweave.integrations.share_receipts import ShareReceipts
from maiweave.integrations.together import DeliveryProblem, people_context


@pytest.mark.parametrize('state,blocked', [('confirmed', True), ('unknown', True), ('partial', True), ('failed', False), ('deferred', False)])
async def test_delivery_retry_rules_and_restart(plugin, monkeypatch, state, blocked):
    now = prepare(plugin, monkeypatch)
    plugin.ctx.call_capability = AsyncMock(return_value={'version': 1, 'state': state, 'message_id': '42'})
    if state == 'confirmed':
        await plugin.living.share(now)
    else:
        with pytest.raises(DeliveryProblem): await plugin.living.share(now)
    row, = plugin.store.all('share_receipt')
    assert plugin.living.share_ready(row['record_id'], 'chat-a', now + timedelta(hours=2)) is not blocked
    ShareReceipts(plugin.store, plugin.ctx)
    assert plugin.living.share_ready(row['record_id'], 'chat-a', now + timedelta(hours=2)) is not blocked
    plugin.ctx.send.text.assert_not_called()


@pytest.mark.parametrize('state', ['unknown', 'partial'])
async def test_unknown_survives_cleanup_and_operator_can_reconcile(plugin, monkeypatch, state):
    now = prepare(plugin, monkeypatch)
    plugin.ctx.call_capability = AsyncMock(return_value={'version': 1, 'state': state})
    with pytest.raises(DeliveryProblem): await plugin.living.share(now)
    row, = plugin.store.all('share_receipt')
    deletion, _, _ = plugin.retention.collect(now + timedelta(days=400))
    assert row['id'] not in deletion['share_receipt']
    await plugin.ui_reconcile_share(row['id'], True)
    assert not plugin.living.share_ready(row['record_id'], 'chat-a', now + timedelta(days=1))
    with pytest.raises(ValueError): await plugin.ui_reconcile_share(row['id'], False)


@pytest.mark.parametrize('phase', ['generation', 'submission'])
async def test_cancel_and_restart(plugin, monkeypatch, phase):
    now = prepare(plugin, monkeypatch)
    entered = asyncio.Event()
    async def wait(*args, **kwargs):
        entered.set(); await asyncio.Event().wait()
    plugin.ctx.call_capability = AsyncMock(side_effect=wait)
    if phase == 'generation': plugin.ctx.maisaka.reply.generate.side_effect = wait
    task = asyncio.create_task(plugin.living.share(now))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    ShareReceipts(plugin.store, plugin.ctx)
    row, = plugin.store.all('share_receipt')
    assert (row['outcome'] == '待核对') == (phase == 'submission')
    assert plugin.living.share_ready(row['record_id'], 'chat-a', now + timedelta(hours=2)) == (phase == 'generation')


async def test_natural_unknown_and_request_timeout_not_replayed(plugin, monkeypatch):
    now = prepare(plugin, monkeypatch)
    plugin.config.proactive.mode = '自然交流'
    await plugin.living.share(now)
    await plugin.living.receipts.refresh(now + timedelta(hours=2))
    row, = plugin.store.all('share_receipt')
    assert row['outcome'] == '待核对'
    assert not plugin.living.share_ready(row['record_id'], 'chat-a', now + timedelta(hours=4))
    await plugin.ui_reconcile_share(row['id'], False)
    plugin.ctx.maisaka.proactive.trigger.side_effect = TimeoutError('timeout')
    with pytest.raises(TimeoutError): await plugin.living.share(now + timedelta(hours=3))
    assert any(r['outcome'] == '待核对' for r in plugin.store.all('share_receipt'))


async def test_concurrent_share_does_not_submit_same_record(plugin, monkeypatch):
    now = prepare(plugin, monkeypatch)
    async def send(*args, **kwargs):
        await asyncio.sleep(.02)
        return {'version': 1, 'state': 'unknown'}
    plugin.ctx.call_capability = AsyncMock(side_effect=send)
    await asyncio.gather(plugin.living.share(now), plugin.living.share(now), return_exceptions=True)
    rows = plugin.store.all('share_receipt')
    assert len({r['record_id'] for r in rows}) == len(rows)


async def test_cross_chat_privacy_and_existing_records(plugin):
    now = plugin.now()
    for session in ('private', 'group'):
        await plugin.identify_person(session, '10001', 'qq')
    plugin.presence.declare('private', '10001', '准备睡觉', now)
    plugin.presence.receive('group', '10001', '你好', now + timedelta(minutes=1))
    assert plugin.presence.context('private', now)
    assert not plugin.presence.context('group', now + timedelta(minutes=1))
    plugin.config.context.cross_chat_presence = True
    assert plugin.presence.context('group', now + timedelta(minutes=1))
    plugin.config.context.cross_chat_presence = False
    assert not plugin.presence.context('group', now + timedelta(minutes=1))


async def test_identity_claims_do_not_grant_wake_or_enter_profile_context(plugin):
    profile = plugin.anniversaries.save_profile('麦麦的妈妈', 'chat-a', user_id='10001', notes='喜欢阅读')
    profile.update(relationship='恋人', intimacy=3, intimacy_mode='auto')
    with plugin.store.db: plugin.store.put('profile', profile)
    assert plugin.living.intimacy('chat-a', '10001') == 0
    context = people_context([profile])[0]
    assert 'name' not in context and 'relationship' not in context and context['notes'] == '喜欢阅读'
    profile['intimacy_mode'] = 'manual'
    with plugin.store.db: plugin.store.put('profile', profile)
    assert plugin.living.intimacy('chat-a', '10001') == 3
    assert plugin.living.intimacy('chat-a', '10002') == 0


@pytest.mark.parametrize('state,status', [('confirmed', '已发布'), ('deferred', '草稿'), ('failed', '草稿'), ('unknown', '待核对'), ('partial', '待核对')])
async def test_space_receipts_and_no_second_publish(plugin, state, status):
    now = plugin.now(); day = now.date().isoformat()
    pub = plugin.diary_publisher
    plugin.config.diary.publish_mode = '手动发布'
    pub.connection = {'account': '123456789'}
    pub.check_connection = AsyncMock()
    pub.put({'id': day, 'status': '草稿', 'content': '读书随笔', 'day': day})
    plugin.ctx.call_capability = AsyncMock(return_value={'version': 1, 'state': state, 'post_id': 'tid42'})
    if state == 'confirmed': await pub.publish(day, now)
    else:
        with pytest.raises(DeliveryProblem): await pub.publish(day, now)
    assert plugin.store.get('diary_publication', day)['status'] == status
    if status == '待核对':
        with pytest.raises(ValueError): await pub.publish(day, now)
        assert plugin.ctx.call_capability.await_count == 1
