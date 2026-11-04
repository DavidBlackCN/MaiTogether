"""Final OneBot check. Only this pinned adapter may call the Host capability."""
from copy import deepcopy
import asyncio

from .behavior_actions import MESSAGE_TARGET, category, fingerprint, text_digest


class BehaviorDenied(RuntimeError):
    def __init__(self, reason, state='denied'):
        self.state = state
        super().__init__(reason)


class BehaviorGate:
    def __init__(self, ctx, runtime):
        self.ctx = ctx
        self.runtime = runtime

    async def rpc(self, phase, **args):
        return await self.ctx.call_host_method('cap.call', payload={
            'capability': 'behavior.check', 'args': {'phase': phase, **args}}, timeout_ms=2000)

    async def prepare(self, name, params, connection, *, preflight=False):
        kind = category(name)
        if kind == 'read':
            return {'reference': '', 'connection': connection}
        state = self.runtime.runtime_state
        resolved = params
        if name in MESSAGE_TARGET:
            mid = params.get('message_id')
            if isinstance(mid, bool) or not str(mid).removeprefix('-').isdigit() or int(mid) == 0:
                raise BehaviorDenied('BEHAVIOR_MESSAGE_ID_INVALID')
            # Read before entering the send lock; no recursive RPC while it is held.
            response = await self.runtime.transport.call_action('get_msg', {'message_id': mid})
            resolved = response.get('data')
            if (response.get('status') != 'ok' or not isinstance(resolved, dict)
                    or str(resolved.get('message_id')) != str(mid)):
                raise BehaviorDenied('BEHAVIOR_MESSAGE_TARGET_UNKNOWN')
        group = resolved.get('group_id')
        user = resolved.get('user_id') or resolved.get('target_id')
        if kind != 'unknown':
            def positive(value):
                return not isinstance(value, bool) and str(value).isdigit() and int(value) > 0
            if (group and not positive(group)) or (not group and not positive(user)):
                raise BehaviorDenied('BEHAVIOR_TARGET_INVALID')
            if isinstance(group,bool) or isinstance(user,bool):
                raise BehaviorDenied('BEHAVIOR_TARGET_INVALID')
            if name in ('send_msg','send_forward_msg'):
                kind_hint=params.get('message_type')
                if kind_hint not in (None,'group','private') or (kind_hint and kind_hint!=('group' if group else 'private')):
                    raise BehaviorDenied('BEHAVIOR_TARGET_CONFLICT')
            if name in ('send_private_msg','send_private_forward_msg','upload_private_file','friend_poke','send_like') and group:
                raise BehaviorDenied('BEHAVIOR_TARGET_CONFLICT')
            if name in ('send_group_msg','send_group_forward_msg','upload_group_file','group_poke',
                        'set_group_sign','send_group_sign','send_group_ai_record') and not group:
                raise BehaviorDenied('BEHAVIOR_TARGET_CONFLICT')
            if name in MESSAGE_TARGET and resolved.get('message_type') not in ('group','private'):
                raise BehaviorDenied('BEHAVIOR_MESSAGE_TARGET_UNKNOWN')
            if name in MESSAGE_TARGET and resolved['message_type']!=('group' if group else 'private'):
                raise BehaviorDenied('BEHAVIOR_MESSAGE_TARGET_CONFLICT')
        route = dict(platform='qq', account_id=state.account_id, scope=state.scope,
                     chat_type='group' if group else 'private', target_id=str(group or user or ''))
        digest = fingerprint({'action': name, 'params': params})
        result = await self.rpc('preflight' if preflight else 'prepare', action=name, route=route, connection=connection,
                                digest=digest, text_digest=text_digest(params))
        if not result.get('allowed'):
            raise BehaviorDenied(result.get('reason', 'BEHAVIOR_DENIED'))
        return {**result, 'connection': connection, 'digest': digest}

    async def final(self, ticket, name, params, connection):
        if connection != ticket['connection']:
            raise BehaviorDenied('BEHAVIOR_CONNECTION_CHANGED', 'not_submitted')
        if not ticket['reference']:
            return
        result = await self.rpc('final', reference=ticket['reference'], connection=connection,
                                digest=fingerprint({'action': name, 'params': params}))
        if not result.get('allowed'):
            raise BehaviorDenied(result.get('reason', 'BEHAVIOR_DENIED'))

    async def result(self, ticket, state):
        if not ticket.get('reference'):
            return
        try:
            await self.rpc('result', reference=ticket['reference'], state=state)
        except (Exception, asyncio.CancelledError):
            # Reporting failure cannot cause a second platform submission.
            self.ctx.logger.warning('Behavior result unavailable: state=%s', state)

    async def preflight_batch(self, actions, connection):
        # Resolve every target/classification before the first visible action.
        for name, params in actions:
            await self.prepare(name, deepcopy(params), connection, preflight=True)
