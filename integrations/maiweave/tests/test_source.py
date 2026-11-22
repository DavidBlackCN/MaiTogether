"""Delivery contains upstream bytes, without a private runtime or manifest change."""
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(os.environ['MAIWEAVE_SOURCE']).resolve()


def test_package_preserves_upstream_runtime_and_license(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tools'))
    spec = importlib.util.spec_from_file_location('weave_package_test', ROOT / 'tools/package.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    names = package.tracked_files(SOURCE)
    package.copy_files(SOURCE, tmp_path, names)
    for name in names:
        path = Path(name)
        if path.parts[0] in ('tests', 'tools', '.github'):
            continue
        if path.suffix in ('.py', '.html', '.sql', '.json') or path.name.startswith('LICENSE'):
            assert (tmp_path / path).read_bytes() == (SOURCE / path).read_bytes(), name
    assert (tmp_path / '_manifest.json').read_bytes() == (SOURCE / '_manifest.json').read_bytes()
    assert not (tmp_path / 'integrations/together.py').exists()
    assert not (tmp_path / 'maitogether-build.json').exists()
    manifest = json.loads((tmp_path / '_manifest.json').read_text(encoding='utf-8'))
    assert 'behavior.send_v1' not in manifest['capabilities']
