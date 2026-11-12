"""Real Runner lifecycle and public status with byte-identical upstream runtime."""
import os
from pathlib import Path
from types import SimpleNamespace


async def run_cases(values):
    c = SimpleNamespace(**values)
    from src.plugin_runtime.behavior_policy.runtime import get_policy
    from src.platform_io.manager import get_platform_io_manager
    from src.platform_io.types import RouteKey
    plugin = 'ilworkcn.maiweave'
    assert plugin in c.supervisor._registered_plugins
    assert not (c.work / 'plugins/maiweave/acceptance_probe.py').exists()
    source = Path(os.environ['MAIWEAVE_ORIGINAL_SOURCE'])
    for dest in (c.work / 'plugins/maiweave').rglob('*'):
        if dest.is_file() and dest.suffix in ('.py', '.json', '.html', '.sql'):
            assert dest.read_bytes() == (source / dest.relative_to(c.work / 'plugins/maiweave')).read_bytes()
    c.cases.append('upstream_runtime_byte_identical_and_actual_runner_loaded')
    inspected = await c.supervisor.inspect_plugin_config(plugin)
    assert not inspected.config_error
    policy = get_policy()
    async def decision():
        return await policy._provider('life', {'category': 'social', 'stream_id': c.stream,
            'route': dict(policy.targets[0]), 'origin': {'kind': 'host'}})
    status = await c.call(plugin, 'get_life_status')
    assert status['effective_sleeping'] is False, status
    assert (await decision())['decision'] == 'allow'
    c.cases.append('public_status_works_without_private_capability_or_test_api')
    async def ready():
        return bool(get_platform_io_manager().resolve_drivers(RouteKey('qq', '123456789', None)))
    await c.wait(ready)
    assert await c.probe()
    assert (await c.probe('api'))['success']
    c.cases.append('normal_sdk_and_qq_actions_with_upstream_provider')
    cfg = c.configs['maiweave']
    assert await c.supervisor.notify_plugin_config_updated(plugin, cfg, cfg['plugin']['config_version'])
    assert (await decision())['decision'] == 'allow'
    c.cases.append('upstream_configuration_reload')
    assert (await c.supervisor.unload_plugins([plugin], reason='original-smoke')).success
    try:
        await decision()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Unloaded upstream provider allowed actions')
    assert await c.supervisor.reload_plugins([plugin], reason='original-reload')
    assert (await decision())['decision'] == 'allow'
    c.cases.append('upstream_unload_fail_closed_and_reload')
