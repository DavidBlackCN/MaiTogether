"""Keep sleeping conversations out of generation and automatic memory.

Raw messages remain in the normal database. The persisted marker is assigned by
Host, not interpreted as a permission supplied by plugins or message authors.
"""
import asyncio
import logging

from .runtime import get_policy

MARKER = 'maitogether_record_only'


class CognitionPaused(Exception):
    """Expected end of a chat turn, not a model failure to retry."""


def record_only(message):
    info = getattr(message, 'message_info', None)
    return bool((getattr(info, 'additional_config', None) or {}).get(MARKER))


async def pause_reason(session_id):
    policy = get_policy()
    if not policy.sleep_enabled:
        return ''
    from src.chat.message_receive.chat_manager import chat_manager
    session = await asyncio.to_thread(chat_manager.get_existing_session_by_session_id, session_id)
    if session is None:
        return 'unknown_session'
    route = dict(platform=session.platform, account_id=session.account_id,
                 scope=session.scope, chat_type='group' if session.group_id else 'private',
                 target_id=str(session.group_id or session.user_id))
    target = policy.target(route)
    if target is None or 'life' not in target['providers']:
        return ''
    try:
        async with asyncio.timeout(.3):
            result = await policy._provider('life', dict(
                category='cognition', action='host.cognition', stream_id=session_id,
                route=route, origin={'kind': 'host'}))
        return result.get('reason', 'unavailable') if result['decision'] == 'deny' else ''
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logging.getLogger('behavior_control').warning('Cognition paused: %s', type(exc).__name__)
        return 'life_state_unavailable'


async def require_awake(session_id):
    reason = await pause_reason(session_id)
    if reason:
        raise CognitionPaused(reason)


async def mark_incoming(message):
    reason = await pause_reason(message.session_id)
    config = dict(message.message_info.additional_config or {})
    config.pop(MARKER, None)
    if reason:
        config[MARKER] = reason
    message.message_info.additional_config = config
    return reason


async def memory_allowed(message):
    return not record_only(message) and not await pause_reason(message.session_id)


def failed_reply(result):
    """Only delivery facts, never an unsent draft, belong in model history."""
    if result.tool_name != 'reply' or result.success:
        return result
    has_draft = (isinstance(result.structured_content, dict) and 'reply_segments' in result.structured_content
                 or any(key in result.metadata for key in ('draft', 'send_results', 'monitor_detail')))
    if not has_draft and not result.stop_after_execution:
        return result
    ids = list(result.metadata.get('sent_message_ids') or [])
    result.content = ('因生活状态暂停，回复未发送。' if result.metadata.get('cognition_paused') else
                     '部分回复已发送，剩余内容未确认发送；不要自动重发。' if ids
                      else '回复未确认发送；不要把草稿当作已经说过的话。')
    result.error_message = result.content
    result.structured_content = None
    result.content_items = []
    result.post_history_messages = []
    receipts = [{key: item[key] for key in ('index', 'success', 'message_id') if key in item}
                for item in result.metadata.get('send_results', []) if isinstance(item, dict)]
    result.metadata = {'sent_message_ids': ids, 'send_results': receipts,
                       'cognition_paused': bool(result.metadata.get('cognition_paused'))}
    result.stop_after_execution = True
    return result
