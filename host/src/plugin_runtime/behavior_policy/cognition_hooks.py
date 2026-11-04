"""Explicit adapters for the pinned Host cognition entry points.

No runtime monkey-patching: upstream call sites import these functions or apply
the decorators directly. Host-specific queue details are kept in this module.
"""
from functools import wraps
from .sleep_guard import CognitionPaused, failed_reply, memory_allowed, pause_reason, require_awake


async def check_planner(service):
    members = getattr(service, 'cognition_members', None)
    # Membership can change while a provider RPC is awaiting its reply.
    for session in tuple(members) if members is not None else (service._session_id,):
        await require_awake(session)


async def pause_turn(runtime, *, queued=False):
    if not await pause_reason(runtime.session_id):
        return False
    runtime._collect_pending_messages()
    runtime._clear_forced_turn_state()
    if queued:
        runtime._mark_message_turn_unscheduled()
        runtime._consume_proactive_trigger_message()
        runtime._consume_proactive_logical_turn_id()
        runtime._enter_stop_state()
    return True


async def run_focus_turn(group):
    try:
        await group._run_turn()
    except CognitionPaused:
        group._take_ready_inputs()
        for entry in group.entries:
            for session, sequence in entry.progress.items():
                group._considered[session] = max(group._considered.get(session, 0), sequence)
            entry.inputs = {}
        group._wait_until = group._wait_session_id = group._wait_token = None
        await group.checkpoint()


def memory_guard(empty=None):
    def decorate(method):
        @wraps(method)
        async def guarded(self, message, *args, **kwargs):
            if not await memory_allowed(message):
                return empty
            return await method(self, message, *args, **kwargs)
        return guarded
    return decorate


def reply_guard(method):
    @wraps(method)
    async def guarded(tool_ctx, *args, **kwargs):
        if reason := await pause_reason(tool_ctx.runtime.session_id):
            result = tool_ctx.build_failure_result('reply', '生活状态暂停回复：' + reason)
            result.metadata['cognition_paused'] = True
            result.stop_after_execution = True
        else:
            result = await method(tool_ctx, *args, **kwargs)
        return failed_reply(result)
    return guarded
