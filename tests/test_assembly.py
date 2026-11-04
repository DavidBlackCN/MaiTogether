"""Maintenance checks use small real Git repositories, never a running instance."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import assembly
import install
import upgrade


@pytest.fixture
def official(tmp_path, monkeypatch):
    source = tmp_path / 'official'
    source.mkdir()
    subprocess.run(['git', 'init', str(source)], check=True, capture_output=True)
    assembly.git(source, 'config', 'core.autocrlf', 'false')
    assembly.git(source, 'config', 'user.name', 'Test')
    assembly.git(source, 'config', 'user.email', 'test@example.invalid')
    (source / 'main.py').write_text('value = 1\n', encoding='utf-8')
    assembly.git(source, 'add', 'main.py')
    assembly.git(source, 'commit', '-m', 'fixture')
    pin = {'commit': assembly.git(source, 'rev-parse', 'HEAD').decode().strip()}
    control = tmp_path / 'control'
    (control / 'patches').mkdir(parents=True)
    (control / 'host').mkdir()
    (control / 'host/helper.py').write_text('helper = True\n', encoding='utf-8')
    (control / 'baseline.json').write_text(json.dumps({'host': pin}))
    (control / 'patches/series.json').write_text(json.dumps({'groups': {'behavior': {
        'requires': [], 'host': {'patch': 'patches/test.patch', 'files': ['main.py'], 'modules': ['helper.py']}}}}))
    (source / 'main.py').write_text('value = 2\n', encoding='utf-8')
    (control / 'patches/test.patch').write_bytes(assembly.normalize(assembly.git(source, 'diff')))
    assembly.git(source, 'checkout', '--', 'main.py')
    monkeypatch.setattr(assembly, 'CONTROL', control)
    monkeypatch.setitem(assembly.PROFILES, 'full', ('behavior',))
    staged = tmp_path / 'staged'
    files = assembly.assemble(source, 'host', staged, verify=False)
    (control / 'locks').mkdir()
    assembly.lock_path('host', 'full').write_text(json.dumps(files))
    return source, control


def test_install_checks_then_applies_without_touching_configuration(official, tmp_path):
    source, _ = official
    (source / 'config.toml').write_text('private = "keep"\n')
    assert not install.install(source)['written']
    assert (source / 'main.py').read_text() == 'value = 1\n'
    backup = tmp_path / 'backup'
    assert install.install(source, apply=True, backup=backup)['written']
    assert (source / 'main.py').read_text() == 'value = 2\n'
    assert (source / 'helper.py').exists()
    assert (source / 'helper.py').stat().st_mode & 0o777 == (tmp_path / 'staged/helper.py').stat().st_mode & 0o777
    assert (source / 'config.toml').read_text() == 'private = "keep"\n'
    assert (backup / 'main.py').read_text() == 'value = 1\n'
    with pytest.raises(ValueError, match='local changes'):
        install.install(source, apply=True)


def test_install_rolls_back_on_partial_write(official, tmp_path, monkeypatch):
    source, _ = official
    replace = install.os.replace
    calls = []
    def fail_second(src, dest):
        calls.append(dest)
        if len(calls) == 2:
            raise OSError('test disk failure')
        replace(src, dest)
    monkeypatch.setattr(install.os, 'replace', fail_second)
    with pytest.raises(OSError, match='disk failure'):
        install.install(source, apply=True, backup=tmp_path / 'backup')
    assert (source / 'main.py').read_text() == 'value = 1\n'
    assert not (source / 'helper.py').exists()
    assert not assembly.git(source, 'status', '--porcelain').strip()


def test_upgrade_conflict_is_localized_and_does_not_touch_source(official, tmp_path):
    source, _ = official
    (source / 'main.py').write_text('upstream_changed = True\n', encoding='utf-8')
    assembly.git(source, 'add', 'main.py')
    assembly.git(source, 'commit', '-m', 'next stable fixture')
    pins = {'host': {'commit': assembly.git(source, 'rev-parse', 'HEAD').decode().strip()}}
    with pytest.raises(ValueError, match='host/behavior: patch conflict'):
        assembly.assemble(source, 'host', tmp_path / 'candidate', pins=pins, verify=False)
    assert not assembly.git(source, 'status', '--porcelain').strip()


def test_overlay_collision_is_rejected(official, tmp_path):
    source, _ = official
    (source / 'helper.py').write_text('upstream = True\n')
    assembly.git(source, 'add', 'helper.py')
    assembly.git(source, 'commit', '-m', 'upstream adds same module')
    pins = {'host': {'commit': assembly.git(source, 'rev-parse', 'HEAD').decode().strip()}}
    with pytest.raises(ValueError, match='upstream now owns helper.py'):
        assembly.assemble(source, 'host', tmp_path / 'candidate', pins=pins, verify=False)


def test_patch_ownership_and_overlay_manifest_are_complete():
    spec = assembly.series()['groups']
    for kind in ('host', 'adapter'):
        owned = []
        modules = []
        for group in spec.values():
            item = group.get(kind)
            if not item:
                continue
            owned.extend(item['files'])
            modules.extend(item['modules'])
            lines = (assembly.CONTROL / item['patch']).read_text(encoding='utf-8').splitlines()
            assert sorted(line[6:] for line in lines if line.startswith('--- a/')) == sorted(item['files'])
        assert len(owned) == len(set(owned))
        actual = {p.relative_to(assembly.CONTROL / kind).as_posix()
                  for p in (assembly.CONTROL / kind).rglob('*.py')}
        assert set(modules) == actual


def test_upgrade_does_not_promote_incomplete_or_stale_validation(tmp_path):
    from types import SimpleNamespace
    pins = assembly.baseline()
    digest = assembly.inputs_digest()
    (tmp_path / 'candidate.json').write_text(json.dumps(pins))
    (tmp_path / 'upgrade-check.json').write_text(json.dumps({'applicable': True, 'inputs_digest': digest}))
    incomplete = {'passed': True, 'candidate': pins, 'inputs_digest': digest, 'checks': []}
    (tmp_path / 'validation.json').write_text(json.dumps(incomplete))
    with pytest.raises(ValueError, match='validation is incomplete'):
        upgrade.promote(SimpleNamespace(candidate=tmp_path))
    incomplete.update(inputs_digest='previous source', checks=[{'name': name, 'exit_code': 0}
                                                             for name in upgrade.REQUIRED_CHECKS])
    (tmp_path / 'validation.json').write_text(json.dumps(incomplete))
    with pytest.raises(ValueError, match='validation is incomplete'):
        upgrade.promote(SimpleNamespace(candidate=tmp_path))
