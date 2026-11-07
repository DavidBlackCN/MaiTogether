"""Native RPC to independent life providers, without changing production plugins."""
from types import SimpleNamespace

from native_scenario import LIFE, PROBE


async def run_cases(values):
    c = SimpleNamespace(**values)
    from src.plugin_runtime.behavior_policy import runtime
    from src.plugin_runtime.behavior_policy.life import LifeProvider

    original = runtime.get_policy()
    if original.sleep_enabled:
        from src.plugin_runtime.behavior_policy import sleep_guard
    request = dict(category='cognition', action='host.cognition', stream_id=c.stream,
                   route=dict(original.targets[0]), origin={'kind': 'host'})
    initial = await original._provider('life', request)
    assert initial['decision'] == 'allow', initial
    c.cases.append('configured_life_uses_registered_private_v1')
    # Change only the configuration in this isolated Host; no Vita implementation is reused.
    custom = runtime.BehaviorPolicy({'enabled': True, 'targets': original.targets,
        'life_provider': {'plugin_id': PROBE, 'api': 'fixture_life', 'version': '1'}})
    custom.manager = c.manager
    def select(policy):
        # Rebind the Host capability as startup does; changing the singleton alone
        # would leave the adapter calling the old policy's bound method.
        runtime._policy = policy
        c.supervisor.capability_service.register_capability('behavior.check', policy.capability)
    try:
        select(custom)
        assert (await c.supervisor.unload_plugins([LIFE], reason='independent-life-test')).success
        assert (await custom._provider('life', request))['decision'] == 'allow'
        if custom.sleep_enabled: assert not await sleep_guard.pause_reason(c.stream)
        if custom.behavior_enabled:
            assert (await c.probe('api'))['success']
        c.cases.append('unrelated_provider_allows_without_default_provider_loaded')

        forged = await c.call(PROBE, 'fixture_life', {'is_owner': True, 'request': request})
        assert forged['reason'] == 'untrusted_request'
        result = await c.manager._cap_api_call('github.cateye.set-msg-emoji-like', 'api.call', {
            'api_name': PROBE + '.fixture_life', 'version': '1', 'args': {}})
        assert not result.get('success')
        c.cases.append('business_arguments_cannot_forge_provider_context')

        # Use the actual API registry to reject public, changed-version and disabled components.
        entry = c.supervisor.api_registry.get_apis(plugin_id=PROBE, name='fixture_life', version='1')[0]
        for field, value in [('public', True), ('version', '2'), ('enabled', False)]:
            old = getattr(entry, field)
            setattr(entry, field, value)
            try:
                try: await custom._provider('life', request)
                except RuntimeError: pass
                else: raise AssertionError('invalid registered contract allowed')
                if custom.sleep_enabled:
                    assert await sleep_guard.pause_reason(c.stream) == 'life_state_unavailable'
            finally: setattr(entry, field, old)
        c.cases.append('registered_api_version_visibility_and_enabled_checked')

        for result, delay in [
            ({'version': 1, 'decision': 'deny', 'reason': 'sleeping'}, 0),
            ({'version': 1, 'decision': 'deny', 'reason': 'not_ready'}, 0),
            ({'version': 1, 'decision': 'allow', 'reason': 'state_unknown'}, 0),
            ({'version': 2, 'decision': 'allow', 'reason': 'available'}, 0),
            ({'version': 1, 'decision': 'allow', 'reason': 'available'}, .5),
        ]:
            await c.call(PROBE, 'set_fixture_life', {'result': result, 'delay': delay})
            if custom.sleep_enabled: assert await sleep_guard.pause_reason(c.stream)
            before = len(c.writes)
            if custom.behavior_enabled:
                assert not (await c.probe('api'))['success']
                assert len(c.writes) == before
        c.cases.append('sleep_unknown_not_ready_version_and_timeout_fail_closed')

        assert (await c.supervisor.unload_plugins([PROBE], reason='provider-unload-test')).success
        if custom.sleep_enabled: assert await sleep_guard.pause_reason(c.stream) == 'life_state_unavailable'
        try: await custom._provider('life', request)
        except RuntimeError: pass
        else: raise AssertionError('missing provider fell back')
        assert await c.supervisor.reload_plugins([PROBE], reason='provider-reload-test')
        assert (await custom._provider('life', request))['decision'] == 'allow'
        c.cases.append('provider_unload_denies_reload_restores_without_fallback')
    finally:
        select(original)
        assert await c.supervisor.reload_plugins([LIFE], reason='restore-original-life')
        await c.wait(c.ready)
    assert (await original._provider('life', request))['decision'] == 'allow'
    if original.sleep_enabled: assert not await sleep_guard.pause_reason(c.stream)
    if original.behavior_enabled: assert (await c.probe('api'))['success']
    c.cases.append('rollback_to_original_life_config_restores_operation')
