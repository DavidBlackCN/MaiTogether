"""Exercise instance installs without network access or a running QQ account."""
from pathlib import Path
import hashlib
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import instance
import prepare
from install import Update


@pytest.fixture
def setup(tmp_path, monkeypatch):
    host = tmp_path / 'host'
    host.mkdir()
    original = {'_manifest.json': json.dumps({'id': instance.ADAPTER_ID}).encode(),
                'plugin.py': b'original\n'}
    patched = dict(original, **{'plugin.py': b'patched\n', 'extra.py': b'new\n'})
    locked = {name: hashlib.sha256(data).hexdigest() for name, data in patched.items()}
    lock = tmp_path / 'adapter-files.json'
    lock.write_text(json.dumps(locked))
    monkeypatch.setattr(prepare, 'lock_path', lambda kind: lock)
    monkeypatch.setattr(instance, 'lock_path', lambda kind: lock)
    monkeypatch.setattr(instance, 'upstream', lambda source, pin: original)
    def host_plan(root, staged):
        staged.mkdir()
        (staged / 'host.py').write_text('installed')
        return Update(root, staged, {} if (root / 'host.py').exists() else {'host.py': None})
    def assemble(source, kind, dest):
        dest.mkdir()
        for name, data in patched.items():
            (dest / name).write_bytes(data)
        return locked
    monkeypatch.setattr(prepare, 'plan_host', host_plan)
    monkeypatch.setattr(prepare, 'assemble', assemble)
    monkeypatch.setattr(prepare, 'fetch_adapter', lambda *args: pytest.fail('unexpected download'))
    monkeypatch.delenv('MAIBOT_INSTANCE_DIR', raising=False)
    monkeypatch.delenv('MAIBOT_BEHAVIOR_CONFIG', raising=False)
    return host, original


def test_export_check_then_apply_and_reuse(setup, tmp_path):
    host, _ = setup
    output = tmp_path / 'ready'
    result = prepare.prepare(host, output, adapter_source=host)
    assert not result['installed'] and (output / 'adapter/plugin.py').exists()
    assert not list(host.iterdir())
    assert prepare.prepare(host, output, apply=True)['written']
    assert json.loads((output / 'install-result.json').read_bytes())['written']
    assert not prepare.prepare(host, output, apply=True)['written']
    (output / 'adapter/plugin.py').write_text('edited')
    with pytest.raises(ValueError, match='输出目录'):
        prepare.prepare(host, output, apply=True)


def test_existing_or_nested_output_is_rejected(setup, tmp_path):
    host, _ = setup
    for target in (tmp_path, host / 'new'):
        with pytest.raises(ValueError):
            prepare.prepare(host, target, apply=True)
    assert not list(host.iterdir())


def test_instance_upgrade_keeps_user_files_and_rerun_needs_no_source(setup):
    host, original = setup
    dest = host / 'plugins/renamed'
    dest.mkdir(parents=True)
    for name, data in original.items():
        (dest / name).write_bytes(data)
    (dest / 'config.toml').write_text('port = 42')
    (dest / 'data.db').write_bytes(b'keep')
    result = prepare.prepare(host, apply=True, adapter_source=host, account='111', groups=['222', '333', '222'])
    assert result['adapter_changed'] and result['config_created']
    assert (Path(result['instance_backup']) / 'adapter/plugin.py').read_bytes() == original['plugin.py']
    config = Path(result['config'])
    from test_policy import BehaviorPolicy
    policy = BehaviorPolicy(json.loads(config.read_bytes()))
    assert [(t['chat_type'], t['account_id'], t['target_id']) for t in policy.targets] == [
        ('group', '111', '222'), ('group', '111', '333'), ('space', '111', '111')]
    assert policy.management == [] and policy.targets[0]['cross_target_plugins'] == []
    config.write_bytes(b'{"enabled":false}')
    result = prepare.prepare(host, apply=True)
    assert not any(result[k] for k in ('written', 'adapter_changed', 'config_created'))
    assert config.read_bytes() == b'{"enabled":false}'
    assert (dest / 'config.toml').read_text() == 'port = 42'
    assert (dest / 'data.db').read_bytes() == b'keep'


@pytest.mark.parametrize('issue', ['duplicate', 'edited', 'extra', 'invalid_account', 'occupied'])
def test_refuses_conflicts_before_writing_host(setup, issue):
    host, original = setup
    dest = host / 'plugins/one'
    dest.mkdir(parents=True)
    for name, data in original.items():
        (dest / name).write_bytes(data)
    if issue == 'duplicate':
        other = host / 'plugins/two'
        other.mkdir()
        (other / '_manifest.json').write_bytes(original['_manifest.json'])
    if issue == 'edited':
        (dest / 'plugin.py').write_text('custom')
    if issue == 'extra':
        (dest / 'custom.py').write_text('custom')
    if issue == 'occupied':
        (dest / '_manifest.json').unlink()
        dest.rename(host / 'plugins/MaiBot-SnowLuma-Adapter')
    with pytest.raises(ValueError):
        prepare.prepare(host, apply=True, adapter_source=host, account='111',
                        groups=['x' if issue == 'invalid_account' else '222'])
    assert not (host / 'host.py').exists()
    assert not (host / 'config/behavior_control.json').exists()


def test_failure_in_last_step_restores_host_and_new_instance(setup, monkeypatch):
    host, _ = setup
    apply = Update.apply
    def fail_config(self, backup, rollback):
        if backup.name == 'config':
            raise OSError('disk error')
        apply(self, backup, rollback)
    monkeypatch.setattr(Update, 'apply', fail_config)
    with pytest.raises(OSError, match='disk error'):
        prepare.prepare(host, apply=True, adapter_source=host, account='111', groups=['222'])
    assert not list(host.iterdir())


def test_failed_upgrade_restores_existing_connector(setup, monkeypatch):
    host, original = setup
    dest = host / 'plugins/snowluma'
    dest.mkdir(parents=True)
    for name, data in original.items():
        (dest / name).write_bytes(data)
    (dest / 'config.toml').write_bytes(b'keep')
    apply = Update.apply
    def fail_config(self, backup, rollback):
        if backup.name == 'config':
            raise OSError('disk error')
        apply(self, backup, rollback)
    monkeypatch.setattr(Update, 'apply', fail_config)
    with pytest.raises(OSError, match='disk error'):
        prepare.prepare(host, apply=True, adapter_source=host, account='111', groups=['222'])
    assert (dest / 'plugin.py').read_bytes() == original['plugin.py']
    assert (dest / 'config.toml').read_bytes() == b'keep'
    assert not (dest / 'extra.py').exists() and not (host / 'host.py').exists()


def test_failed_adapter_verification_does_not_write_host(setup, monkeypatch):
    host, _ = setup
    def broken_source(*args):
        raise ValueError('hash mismatch')
    monkeypatch.setattr(prepare, 'assemble', broken_source)
    with pytest.raises(ValueError, match='hash mismatch'):
        prepare.prepare(host, apply=True, adapter_source=host, account='111', groups=['222'])
    assert not list(host.iterdir())
