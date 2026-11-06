"""One configured life backend, shared by cognition and external behavior checks."""
from dataclasses import dataclass
import asyncio

from .context import provider_request
from .life_status import WEAVE_PLUGIN, WEAVE_API, evaluate_status


DEFAULT_PLUGIN = 'davidblackcn.maibot-maivita-plugin'


@dataclass(frozen=True)
class LifeProvider:
    plugin_id: str = DEFAULT_PLUGIN
    api: str = 'evaluate_behavior'
    version: str = '1'
    protocol: str = 'decision_v1'
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
                or result.protocol not in ('decision_v1', 'maiweave_status_v1')
                or type(result.max_age_seconds) is not int or not 10 <= result.max_age_seconds <= 3600):
            raise ValueError('Life Provider requires a plugin, API name and version "1"')
        if result.protocol == 'maiweave_status_v1' and (result.plugin_id, result.api) != (WEAVE_PLUGIN, WEAVE_API):
            raise ValueError('MaiWeave status protocol requires the official plugin and API')
        return result

    def normalize(self, names):
        """Keep the existing Vita selector as an unambiguous compatibility alias."""
        if (not isinstance(names, list) or not names
                or any(name not in ('vita', 'life', 'hush') for name in names)):
            raise ValueError('Invalid behavior target/providers')
        if 'vita' in names:
            if 'life' in names or self != LifeProvider():
                raise ValueError('Legacy vita selector requires the default Vita backend')
            names = ['life' if name == 'vita' else name for name in names]
        return [name for name in ('life', 'hush') if name in names]

    def _entry(self, supervisor, stream):
        entries = supervisor.api_registry.get_apis(
            plugin_id=self.plugin_id, name=self.api, version=self.version,
            enabled_only=True, session_id=stream)
        if (len(entries) != 1 or entries[0].public != (self.protocol == 'maiweave_status_v1') or entries[0].dynamic
                or entries[0].version != self.version):
            raise RuntimeError('LIFE_PROVIDER_CONTRACT_UNAVAILABLE')
        return entries[0]

    async def evaluate(self, manager, request):
        if manager is None:
            raise RuntimeError('LIFE_PROVIDER_RUNTIME_UNAVAILABLE')
        if (request.get('category') not in ('cognition', 'social')
                or not isinstance(request.get('stream_id'), str) or not request['stream_id']):
            raise RuntimeError('LIFE_PROVIDER_REQUEST_INVALID')
        supervisor = manager._get_supervisor_for_plugin(self.plugin_id)
        if supervisor is None:
            raise RuntimeError('LIFE_PROVIDER_MISSING')
        entry = self._entry(supervisor, request['stream_id'])
        token = provider_request.set(request)
        try:
            envelope = await asyncio.wait_for(supervisor.invoke_api(
                self.plugin_id, entry.handler_name, {}, timeout_ms=150), .15)
        finally:
            provider_request.reset(token)
        # Never use a result produced by a component unloaded/replaced in flight.
        if (manager._get_supervisor_for_plugin(self.plugin_id) is not supervisor
                or self._entry(supervisor, request['stream_id']) is not entry):
            raise RuntimeError('LIFE_PROVIDER_CHANGED')
        payload = envelope.payload
        if envelope.error or not isinstance(payload, dict) or payload.get('success') is not True:
            raise RuntimeError('LIFE_PROVIDER_FAILED')
        if self.protocol == 'maiweave_status_v1':
            return evaluate_status(payload.get('result'), request['category'], max_age_seconds=self.max_age_seconds)
        return validate_result(payload.get('result'))


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
