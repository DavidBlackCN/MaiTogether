"""Versioned detailed delivery through the existing Host capabilities and final gates."""
from dataclasses import replace
import asyncio

from .context import current
from .runtime import get_policy, send_outcome


def annotate_send_result(capability, args, result):
    """Attach receipts at the capability boundary, not inside Host send helpers."""
    if (capability in {'send.text', 'send.emoji', 'send.image', 'send.forward',
                       'send.hybrid', 'send.command', 'send.custom'}
            and args.get('return_details') and isinstance(result, dict) and 'sent' in result):
        return {**result, 'behavior_state': send_outcome(result['sent'])}
    return result


def register(manager, supervisor):
    async def deliver(plugin, capability, request):
        if request.get('version') != 1 or set(request) != {'version', 'operation', 'args'}:
            raise ValueError('DELIVERY_CONTRACT_INVALID')
        operation, args = request['operation'], request['args']
        if not isinstance(args, dict):
            raise ValueError('DELIVERY_ARGUMENTS_INVALID')
        if not get_policy().behavior_enabled:
            raise PermissionError('BEHAVIOR_CONTROL_REQUIRED')
        if operation == 'message':
            required = 'send.hybrid'
            call_args = dict(args, return_details=True)
            impl = manager._cap_send_hybrid
        elif operation == 'file':
            required = 'api.call'
            if set(args) != {'group_id', 'file', 'name'}:
                raise ValueError('DELIVERY_FILE_ARGUMENTS_INVALID')
            call_args = dict(api_name='adapter.napcat.file.upload_group_file', version='1', args={'params': args})
            impl = manager._cap_api_call
        else:
            raise ValueError('DELIVERY_OPERATION_INVALID')
        allowed, reason = supervisor.capability_service._authorization.check_capability(plugin, required)
        if not allowed:
            raise PermissionError(reason)
        invocation = current.get()
        if invocation is None:
            raise PermissionError('BEHAVIOR_CONTEXT_REQUIRED')
        # An operation owns its results, even when siblings share a live parent call.
        token = current.set(replace(invocation, results=[]))
        try:
            try:
                raw = await impl(plugin, required, call_args)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raw = {'success': False, 'error': str(exc)[:240]}
            raw = raw if isinstance(raw, dict) else {}
            result = raw.get('result', raw) if operation == 'file' else raw
            result = result if isinstance(result, dict) else {}
            ok = (result.get('status') == 'ok' and result.get('retcode', 0) == 0
                  if operation == 'file' else raw.get('sent') is True)
            state = send_outcome(ok)
            # No final gate evidence is not a delivery confirmation.
            if state == 'confirmed' and not current.get().results:
                state = 'unknown'
            states = {r['state'] for r in current.get().results}
            reason = str(raw.get('error') or result.get('error') or '')[:240]
            if not reason:
                reason = next((r.get('reason','') for r in reversed(current.get().results) if r.get('reason')), '')[:240]
            if state == 'not_submitted':
                state = 'deferred' if 'denied' in states or not reason or 'BEHAVIOR_' in reason else 'failed'
            data = result.get('data') or {}
            return {'version': 1, 'state': state, 'sent': state == 'confirmed',
                    'message_id': raw.get('message_id'), 'file_id': data.get('file_id'),
                    'reason': reason}
        finally:
            current.reset(token)

    supervisor.capability_service.register_capability('behavior.send_v1', deliver)
