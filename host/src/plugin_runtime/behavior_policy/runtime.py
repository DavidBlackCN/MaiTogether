"""Host policy composition. No platform network calls occur inside the final check."""
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict
import asyncio
import json
import os
import logging
import secrets
import time

from .actions import MESSAGE_TARGET, category, fingerprint, text_digest
from .context import contexts, current, outbound, provider_request

ADAPTER = 'maibot-team.snowluma-adapter'
PROVIDERS = {
    'vita': 'davidblackcn.maibot-maivita-plugin',
    'hush': 'davidblackcn.maibot-maihush-plugin',
    'identity': 'davidblackcn.maibot-maiidentity-plugin',
}


def route_from_message(message):
    info = message.get('message_info') or {}
    group = info.get('group_info') or {}
    additional = info.get('additional_config') or {}
    return dict(platform=message.get('platform', ''), account_id=message.get('account_id', ''),
                scope=message.get('scope') or None, chat_type='group' if group else 'private',
                target_id=str(group.get('group_id') or additional.get('platform_io_target_user_id') or ''))


def route_matches(expected, actual):
    return all((expected.get(k) or None) == (actual.get(k) or None)
               for k in ('platform', 'account_id', 'scope', 'chat_type', 'target_id'))


class BehaviorPolicy:
    def __init__(self, config=None):
        if config is None:
            base = Path(os.environ.get('MAIBOT_INSTANCE_DIR', Path(__file__).resolve().parents[3]))
            path = Path(os.environ.get('MAIBOT_BEHAVIOR_CONFIG', base / 'config/behavior_control.json'))
            config = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'enabled': False}
        if type(config.get('enabled', False)) is not bool:
            raise ValueError('behavior_control.enabled must be boolean')
        self.enabled = config.get('enabled', False)
        self.targets = config.get('targets', [])
        self.management = config.get('management_commands', [])
        if self.enabled and not self.targets:
            raise ValueError('Enabled behavior control requires explicit targets')
        seen = set()
        for target in self.targets:
            if (not all(target.get(k) for k in ('platform', 'account_id', 'chat_type', 'target_id'))
                    or target['chat_type'] not in ('group', 'private')
                    or not isinstance(target.get('providers'), list)
                    or not target['providers'] or any(p not in ('vita','hush') for p in target['providers'])):
                raise ValueError('Invalid behavior target/providers')
            key=tuple(target.get(k) or None for k in ('platform','account_id','scope','chat_type','target_id'))
            if key in seen: raise ValueError('Duplicate behavior target')
            seen.add(key)
            target['providers']=[p for p in ('vita','hush') if p in target['providers']]
        self.actions: Dict[str, Dict[str, Any]] = {}
        self.audit = deque(maxlen=1024)
        self.manager = None

    def target(self, route):
        return next((item for item in self.targets if route_matches(item, route)), None)

    def check_origin(self, origin, stream, target):
        if origin.get('kind') == 'background' and origin.get('plugin') not in target.get('autonomous_plugins', []):
            raise PermissionError('BEHAVIOR_BACKGROUND_TARGET_DENIED')
        if (origin.get('kind') in ('tool', 'command') and origin.get('stream_id') != stream
                and origin.get('plugin') not in target.get('cross_target_plugins', [])):
            raise PermissionError('BEHAVIOR_CROSS_TARGET_DENIED')

    def delegates(self, message):
        return self.enabled and isinstance(message, dict) and self.target(route_from_message(message)) is not None

    def control_for(self, method, args):
        request = provider_request.get()
        return {'version': 1, 'enabled': self.enabled,
                'defer_send_guard': method == 'plugin.invoke_hook'
                    and args.get('hook_name') == 'send_service.before_send' and self.delegates(args.get('message')),
                'request': request}

    async def _provider(self, name, request):
        if self.manager is None:
            raise RuntimeError('BEHAVIOR_RUNTIME_UNAVAILABLE')
        plugin = PROVIDERS[name]
        supervisor = self.manager._get_supervisor_for_plugin(plugin)
        if supervisor is None:
            raise RuntimeError('BEHAVIOR_PROVIDER_MISSING:' + name)
        token = provider_request.set(request)
        try:
            envelope = await asyncio.wait_for(supervisor.invoke_api(
                plugin, 'evaluate_behavior', {}, timeout_ms=150), .15)
        finally:
            provider_request.reset(token)
        result = envelope.payload.get('result')
        if envelope.error or not envelope.payload.get('success') or not isinstance(result, dict):
            raise RuntimeError('BEHAVIOR_PROVIDER_FAILED:' + name)
        if result.get('version') != 1 or result.get('decision') not in ('allow', 'deny', 'abstain'):
            raise RuntimeError('BEHAVIOR_PROVIDER_PROTOCOL:' + name)
        # Abstain must be an explicit, successful exclusion, not an unavailable state.
        if result['decision'] == 'abstain' and result.get('reason') != 'not_managed':
            raise RuntimeError('BEHAVIOR_PROVIDER_ABSTAIN:' + name)
        return result

    async def _resolve(self, route):
        from src.chat.message_receive.chat_manager import chat_manager
        rows = await asyncio.to_thread(chat_manager.resolve_sessions_by_target,
            platform=route['platform'], target_id=route['target_id'], chat_type=route['chat_type'])
        rows = [r for r in rows if r.account_id == route['account_id'] and (r.scope or None) == route.get('scope')]
        if len(rows) != 1:
            raise PermissionError('BEHAVIOR_ROUTE_UNRESOLVED')
        return rows[0].session_id

    async def _adapter_route(self, args):
        from src.platform_io.manager import get_platform_io_manager
        from src.platform_io.types import RouteKey
        route = args['route']
        key = RouteKey(platform=route['platform'], account_id=route['account_id'], scope=route.get('scope'))
        manager = get_platform_io_manager()
        drivers = [d for d in manager.resolve_drivers(key) if d.descriptor.plugin_id == ADAPTER]
        if len(drivers) != 1:
            raise PermissionError('BEHAVIOR_ADAPTER_ROUTE_UNAVAILABLE')
        state = self._qq_contract()
        if (state is None or state.account_id != route['account_id'] or (state.scope or None) != route.get('scope')
                or (args.get('connection') and state.metadata.get('behavior_connection') != args['connection'])):
            raise PermissionError('BEHAVIOR_ADAPTER_CONTRACT_UNAVAILABLE')
        result = await manager.evaluate_target_policy(drivers[0], key, route['chat_type'], route['target_id'])
        if not result.allowed:
            raise PermissionError('BEHAVIOR_ADAPTER_POLICY')

    def _qq_contract(self):
        if self.manager is None:
            return None
        supervisor = self.manager._get_supervisor_for_plugin(ADAPTER)
        if supervisor is None:
            return None
        state = supervisor._message_gateway_states.get(ADAPTER, {}).get('snowluma_gateway')
        return state if state and state.ready and state.metadata.get('behavior_contract') == 1 else None

    def _record(self, entry, state, reason=''):
        entry['state'] = state
        if 'results' in entry:
            entry['results'].append({'action_id': entry['id'], 'state': state})
        event = dict(action_id=entry['id'], category=entry['category'], state=state, reason=reason,
                     route_fingerprint=fingerprint(entry['route']), at=time.time(),
                     final_ms=round((time.monotonic()-entry['checking_at'])*1000, 3) if state in ('permitted','denied') and 'checking_at' in entry else None,
                     provider_calls=entry.get('provider_calls', 0))
        self.audit.append(event)
        if state in ('denied','unknown','failed'):
            logging.getLogger('behavior_control').info('%s', json.dumps(event, ensure_ascii=False))
        return dict(allowed=state == 'permitted', state=state, reason=reason, action_id=entry['id'])

    async def prepare(self, plugin, args):
        if plugin != ADAPTER:
            raise PermissionError('BEHAVIOR_ADAPTER_ONLY')
        name = args.get('action', '')
        kind = category(name)
        if not self.enabled or kind == 'read':
            return {'allowed': True, 'reference': '', 'state': 'not_submitted'}
        if kind == 'unknown':
            return {'allowed': False, 'state': 'denied', 'reason': 'BEHAVIOR_ACTION_UNCLASSIFIED'}
        route = dict(args.get('route') or {})
        if route.get('platform') != 'qq' or not route.get('account_id') or not route.get('target_id'):
            raise PermissionError('BEHAVIOR_TARGET_INVALID')
        await self._adapter_route(args)
        target = self.target(route)
        if target is None:
            # Explicitly outside control. Existing adapter permission still applies.
            if kind == 'management':
                return {'allowed': False, 'state': 'denied', 'reason': 'BEHAVIOR_MANAGEMENT_NOT_CONFIGURED'}
        stream = await self._resolve(route) if target is not None else ''
        invocation = current.get()
        origin = dict(invocation.origin) if invocation else {'kind': 'background', 'plugin': plugin}
        if target is not None:
            try:
                self.check_origin(origin, stream, target)
            except PermissionError as exc:
                return {'allowed': False, 'state': 'denied', 'reason': str(exc)}
        if kind == 'management' and (origin.get('kind') != 'command' or origin.get('stream_id') != stream
                or not origin.get('actor') or not any(m.get('plugin') == origin.get('plugin')
                    and m.get('component') == origin.get('component') and name in m.get('actions', [])
                    for m in self.management)):
            return {'allowed': False, 'state': 'denied', 'reason': 'BEHAVIOR_MANAGEMENT_DENIED'}
        now = time.monotonic()
        self.actions = {k: v for k, v in self.actions.items() if now < v['expires']}
        if len(self.actions) >= 8192:
            raise PermissionError('BEHAVIOR_ACTION_CAPACITY')
        reference = secrets.token_hex(24)
        output = outbound.get() or {}
        self.actions[reference] = dict(id=contexts.generation + ':' + secrets.token_hex(16), owner=plugin,
            route=route, stream_id=stream, category=kind, action=name, origin=origin,
            connection=args.get('connection'), digest=args.get('digest'), text_digest=args.get('text_digest', ''),
            message_id=output.get('message_id', ''), state='prepared', expires=now+120,
            providers=target['providers'] if target else [], results=invocation.results if invocation else [])
        return {'allowed': True, 'reference': reference, 'state': 'not_submitted'}

    async def final(self, plugin, args):
        entry = self.actions.get(args.get('reference'))
        if (not entry or entry['owner'] != plugin or entry['expires'] <= time.monotonic()
                or entry['state'] != 'prepared' or entry['connection'] != args.get('connection')
                or entry['digest'] != args.get('digest')):
            return {'allowed': False, 'state': 'denied', 'reason': 'BEHAVIOR_ACTION_INVALID'}
        # Consume the reference before awaiting: concurrent/repeated calls cannot reuse a permit.
        entry['state'] = 'checking'
        entry['checking_at'] = time.monotonic()
        entry['provider_calls'] = 0
        request = {k: entry[k] for k in ('id', 'route', 'stream_id', 'category', 'action', 'origin',
                                        'text_digest', 'message_id')}
        try:
            async with asyncio.timeout(.3):
                # Recheck target policy after queueing. Never call the adapter here.
                await self._adapter_route({'route': entry['route'], 'connection': entry['connection']})
                names = ['identity'] if entry['category'] == 'management' else entry['providers']
                for name in names:
                    entry['provider_calls'] += 1
                    result = await self._provider(name, request)
                    if result['decision'] == 'deny':
                        return self._record(entry, 'denied', name + ':' + result.get('reason', 'policy'))
        except asyncio.CancelledError:
            self._record(entry, 'not_submitted', 'cancelled')
            raise
        except Exception as exc:
            return self._record(entry, 'denied', type(exc).__name__ + ':' + str(exc)[:160])
        return self._record(entry, 'permitted')

    async def capability(self, plugin, capability, args):
        if plugin != ADAPTER:
            raise PermissionError('BEHAVIOR_ADAPTER_ONLY')
        phase = args.get('phase')
        if phase == 'prepare':
            return await self.prepare(plugin, args)
        if phase == 'final':
            return await self.final(plugin, args)
        if phase == 'result':
            entry = self.actions.get(args.get('reference'))
            state = args.get('state')
            if (entry and entry['owner'] == plugin and entry['state'] in ('permitted', 'submitted')
                    and state in ('not_submitted', 'submitted', 'confirmed', 'unknown', 'failed')):
                return self._record(entry, state)
            return {'allowed': False, 'reason': 'BEHAVIOR_RESULT_INVALID'}
        raise ValueError('BEHAVIOR_PHASE_INVALID')

    @contextmanager
    def output(self, message_id):
        token = outbound.set({'message_id': message_id})
        try:
            yield
        finally:
            outbound.reset(token)

    async def platform_check(self, message, route_key, driver):
        """Non-QQ final gate; patched QQ performs the check on its concrete leaf actions."""
        if not self.enabled:
            return
        from src.plugin_runtime.host.message_utils import PluginMessageUtils
        data = PluginMessageUtils._session_message_to_dict(message, include_binary_data=False)
        route = route_from_message(data)
        route.update(platform=route_key.platform, account_id=route_key.account_id, scope=route_key.scope)
        target = self.target(route)
        if target is None:
            return
        if route['platform'] == 'qq':
            if driver.descriptor.plugin_id != ADAPTER or self._qq_contract() is None:
                raise PermissionError('BEHAVIOR_ADAPTER_CONTRACT_UNAVAILABLE')
            return
        invocation = current.get()
        origin = dict(invocation.origin) if invocation else {'kind': 'host'}
        stream = await self._resolve(route)
        self.check_origin(origin, stream, target)
        request = dict(id=contexts.generation + ':' + secrets.token_hex(16), route=route,
            stream_id=stream, category='social', action='platform.message', origin=origin,
            message_id=message.message_id, text_digest='')
        async with asyncio.timeout(.3):
            for name in target['providers']:
                result = await self._provider(name, request)
                if result['decision'] == 'deny':
                    raise PermissionError('BEHAVIOR_DENIED:' + name + ':' + result.get('reason', 'policy'))
        return dict(request, results=invocation.results if invocation else [])

    def platform_result(self, entry, state):
        if entry is not None:
            self._record(entry, state)


_policy = None


def get_policy():
    global _policy
    if _policy is None:
        _policy = BehaviorPolicy()
    return _policy


def send_outcome(sent):
    invocation = current.get()
    states = {r['action_id']: r['state'] for r in invocation.results}.values() if invocation else []
    states = set(states)
    if 'confirmed' in states and states-{'confirmed'}:
        return 'partial'
    if states & {'unknown', 'submitted', 'permitted'}:
        return 'unknown'
    if 'confirmed' in states or sent:
        return 'confirmed'
    if 'failed' in states:
        return 'failed'
    return 'not_submitted'
