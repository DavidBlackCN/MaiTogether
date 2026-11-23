"""One configured life backend for external behavior checks."""
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio

from .context import provider_request
WEAVE_PLUGIN = 'ilworkcn.maiweave'
WEAVE_API = 'evaluate_behavior'


@dataclass(frozen=True)
class LifeProvider:
    plugin_id: str = WEAVE_PLUGIN
    api: str = WEAVE_API
    version: str = '1'
    protocol: str = 'maiweave_behavior_v1'
    max_age_seconds: int = 180

    @classmethod
    def from_config(cls, config):
        value = config.get('life_provider', {})
        if not isinstance(value, dict) or set(value) - {'plugin_id', 'api', 'version', 'protocol', 'max_age_seconds'}:
            raise ValueError('Invalid life_provider configuration')
        result = cls(**value)
        if (not isinstance(result.plugin_id, str) or not result.plugin_id.strip()
                or result.plugin_id != result.plugin_id.strip()
                or not isinstance(result.api, str) or not result.api.isidentifier()
                or result.version != '1'
                or result.protocol not in ('decision_v1', 'maiweave_behavior_v1')
                or type(result.max_age_seconds) is not int or not 10 <= result.max_age_seconds <= 3600):
            raise ValueError('Life Provider requires a plugin, API name and version "1"')
        if result.protocol == 'maiweave_behavior_v1' and (result.plugin_id, result.api) != (WEAVE_PLUGIN, WEAVE_API):
            raise ValueError('MaiWeave behavior protocol requires the official plugin and API')
        return result

    def normalize(self, names):
        """Validate the configured policies without historical plugin aliases."""
        if (not isinstance(names, list) or not names
                or any(name not in ('life', 'hush') for name in names)):
            raise ValueError('Invalid behavior target/providers')
        return [name for name in ('life', 'hush') if name in names]

    def _entry(self, supervisor, stream):
        entries = supervisor.api_registry.get_apis(
            plugin_id=self.plugin_id, name=self.api, version=self.version,
            enabled_only=True, session_id=stream)
        if (len(entries) != 1 or entries[0].public != (self.protocol == 'maiweave_behavior_v1') or entries[0].dynamic
                or entries[0].version != self.version):
            raise RuntimeError('LIFE_PROVIDER_CONTRACT_UNAVAILABLE')
        return entries[0]

    async def evaluate(self, manager, request):
        if manager is None:
            raise RuntimeError('LIFE_PROVIDER_RUNTIME_UNAVAILABLE')
        space = request.get('route', {}).get('chat_type') == 'space'
        if (request.get('category') != 'social'
                or not isinstance(request.get('stream_id'), str) or (not request['stream_id'] and not space)):
            raise RuntimeError('LIFE_PROVIDER_REQUEST_INVALID')
        supervisor = manager._get_supervisor_for_plugin(self.plugin_id)
        if supervisor is None:
            raise RuntimeError('LIFE_PROVIDER_MISSING')
        # Only a Host chat message passing through Platform IO can use the conversation verdict.
        host_reply = (request.get('origin', {}).get('kind') == 'host'
                      and request.get('action') in ('platform.message', 'send_msg', 'send_private_msg', 'send_group_msg')
                      and bool(request.get('message_id')) and not space)
        behavior = 'conversation' if host_reply else 'proactive'
        args = {'behavior': behavior} if self.protocol == 'maiweave_behavior_v1' else {}
        token = provider_request.set(request)
        try:
            entry = self._entry(supervisor, request['stream_id'])
            envelope = await asyncio.wait_for(supervisor.invoke_api(
                self.plugin_id, entry.handler_name, args, timeout_ms=150), .15)
            if (manager._get_supervisor_for_plugin(self.plugin_id) is not supervisor
                    or self._entry(supervisor, request['stream_id']) is not entry):
                raise RuntimeError('LIFE_PROVIDER_CHANGED')
            payload = envelope.payload
            if envelope.error or not isinstance(payload, dict) or payload.get('success') is not True:
                raise RuntimeError('LIFE_PROVIDER_FAILED')
            result = payload.get('result')
            if self.protocol == 'decision_v1':
                return validate_result(result)
            return weave_decision(result, behavior, self.max_age_seconds)
        finally:
            provider_request.reset(token)


def weave_decision(result, behavior, max_age_seconds):
    if (not isinstance(result, dict) or type(result.get('version')) is not int
            or result['version'] != 1 or result.get('behavior') != behavior):
        raise RuntimeError('LIFE_PROVIDER_PROTOCOL')
    try:
        queried = datetime.fromisoformat(result['queried_at'])
        if queried.utcoffset() is None:
            raise ValueError('missing timezone')
        age = (datetime.now(timezone.utc) - queried).total_seconds()
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise RuntimeError('LIFE_PROVIDER_PROTOCOL') from exc
    if not -5 <= age <= max_age_seconds:
        return {'version': 1, 'decision': 'deny', 'reason': 'life_state_stale'}
    decision, reason = result.get('decision'), result.get('reason')
    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError('LIFE_PROVIDER_PROTOCOL')
    if decision == 'allow' and reason == 'available':
        return {'version': 1, 'decision': 'allow', 'reason': reason}
    if decision in ('defer', 'unknown', 'abstain'):
        return {'version': 1, 'decision': 'deny', 'reason': reason}
    raise RuntimeError('LIFE_PROVIDER_PROTOCOL')


def validate_result(result):
    if (not isinstance(result, dict) or type(result.get('version')) is not int
            or result['version'] != 1 or result.get('decision') not in ('allow', 'deny', 'abstain')
            or not isinstance(result.get('reason'), str) or not result['reason'].strip()):
        raise RuntimeError('LIFE_PROVIDER_PROTOCOL')
    decision, reason = result['decision'], result['reason']
    if decision == 'abstain' and reason != 'not_managed':
        raise RuntimeError('LIFE_PROVIDER_ABSTAIN')
    # v1 has one affirmative state. Unknown or contradictory state is not a permit.
    if (decision == 'allow' and reason != 'available') or (decision != 'deny'
            and 'ready' in result and result['ready'] is not True):
        raise RuntimeError('LIFE_PROVIDER_STATE_UNKNOWN')
    return result
