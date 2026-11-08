"""Preparation must finish verification before touching the user's Host."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare


@pytest.fixture
def setup(tmp_path, monkeypatch):
    host = tmp_path / 'host'
    host.mkdir()
    calls = []
    def install(path, **kwargs):
        calls.append(('install', kwargs.get('apply', False)))
        return {'checked': True, 'files': 16, 'written': kwargs.get('apply', False)}
    def assemble(source, kind, dest):
        calls.append(('assemble', kind))
        dest.mkdir()
        (dest / 'plugin.py').write_text('verified = True\n')
        return {'plugin.py': 'fixture'}
    monkeypatch.setattr(prepare, 'install', install)
    monkeypatch.setattr(prepare, 'assemble', assemble)
    monkeypatch.setattr(prepare, 'fetch_adapter', lambda *a: calls.append(('fetch', True)))
    return host, tmp_path / 'output', calls


def test_readonly_preparation_does_not_install(setup):
    host, output, calls = setup
    result = prepare.prepare(host, output)
    assert not result['written']
    assert calls == [('install', False), ('fetch', True), ('assemble', 'adapter')]
    assert (output / 'adapter/plugin.py').exists()
    assert json.loads((output / 'behavior_control.example.json').read_text())['enabled']
    assert list(host.iterdir()) == []


def test_apply_waits_for_adapter_verification_and_supports_offline_source(setup):
    host, output, calls = setup
    assert prepare.prepare(host, output, apply=True, adapter_source=host)['written']
    assert calls == [('install', False), ('assemble', 'adapter'), ('install', True)]


def test_bad_adapter_never_changes_host(setup, monkeypatch):
    host, output, calls = setup
    def fail(*args):
        raise ValueError('hash mismatch')
    monkeypatch.setattr(prepare, 'assemble', fail)
    with pytest.raises(ValueError, match='hash mismatch'):
        prepare.prepare(host, output, apply=True)
    assert ('install', True) not in calls
    assert not output.exists()


def test_existing_or_nested_output_is_rejected(setup):
    host, output, calls = setup
    output.mkdir()
    marker = output / 'keep.txt'
    marker.write_text('keep')
    for target in (output, host / 'new'):
        with pytest.raises(ValueError):
            prepare.prepare(host, target, apply=True)
    assert calls == [] and marker.read_text() == 'keep'


def test_example_uses_default_life_backend_and_explicit_permissions():
    from test_policy import BehaviorPolicy
    example = json.loads((prepare.CONTROL / 'behavior_control.example.json').read_text())
    policy = BehaviorPolicy(example)
    assert policy.life.plugin_id == 'ilworkcn.maiweave'
    assert policy.targets[0]['providers'] == ['life', 'hush']
    assert policy.management == []
    assert policy.targets[0]['cross_target_plugins'] == []
    assert '*' not in policy.targets[0]['autonomous_plugins']
