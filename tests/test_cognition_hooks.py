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
