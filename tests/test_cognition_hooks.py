"""Queue adapters keep explicit behavior when shared-chat membership changes."""
from types import SimpleNamespace
from pathlib import Path
import os
import sys

import pytest
sys.path.insert(0, os.environ.get('MAITOGETHER_TEST_HOST', str(Path(__file__).resolve().parents[1] / 'host')))
from src.plugin_runtime.behavior_policy import cognition_hooks


@pytest.mark.asyncio
async def test_shared_planner_membership_can_change_during_policy_query(monkeypatch):
    members = {'one': object(), 'two': object()}
    seen = []
    async def check(session):
        seen.append(session)
        members.pop('two', None)
    monkeypatch.setattr(cognition_hooks, 'require_awake', check)
    await cognition_hooks.check_planner(SimpleNamespace(cognition_members=members))
    assert seen == ['one', 'two']


@pytest.mark.asyncio
async def test_focus_pause_drains_new_queue_and_does_not_retry(monkeypatch):
    from unittest.mock import AsyncMock
    consumed = []
    async def paused():
        raise cognition_hooks.CognitionPaused('sleeping')
    entry = SimpleNamespace(progress={'one': 4}, inputs={'one': ['pending']})
    group = SimpleNamespace(_run_turn=paused, _take_pending_inputs=lambda: consumed.append(True),
        entries=[entry], _considered={'one': 2}, _wait_until=123, _wait_session_id='one',
        _wait_token='wait', checkpoint=AsyncMock())
    await cognition_hooks.run_focus_turn(group)
    assert consumed and group._considered == {'one': 4} and entry.inputs == {}
    assert group._wait_until is group._wait_session_id is group._wait_token is None
    group.checkpoint.assert_awaited_once()
