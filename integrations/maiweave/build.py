"""从固定上游提交组装 MaiWeave，保留来源并记录文件哈希。"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('assembly', ROOT.parents[1] / 'tools/assembly.py')
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


def build(source, output):
    pin = json.loads((ROOT / 'baseline.json').read_text(encoding='utf-8'))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name, blob in assembly.upstream(source, pin).items():
        dest = (output / name).resolve()
        if not dest.is_relative_to(output):
            raise ValueError('Unsafe source path')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    command = ['git', '-c', 'core.autocrlf=false', 'apply']
    patch = ROOT / 'maiweave.patch'
    subprocess.run([*command, '--check', str(patch)], cwd=output, check=True)
    subprocess.run([*command, str(patch)], cwd=output, check=True)
    for path in (ROOT / 'modules').rglob('*.py'):
        dest = output / path.relative_to(ROOT / 'modules')
        if dest.exists():
            raise ValueError('Upstream owns adaptation module: ' + str(dest))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(assembly.normalize(path.read_bytes()))
    record = {'baseline': pin, 'files': assembly.hashes(output),
              'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest()}
    (output / 'maitogether-build.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return output


def verify(directory):
    record = json.loads((directory / 'maitogether-build.json').read_text(encoding='utf-8'))
    pin = json.loads((ROOT / 'baseline.json').read_text(encoding='utf-8'))
    actual = assembly.hashes(directory)
    actual.pop('maitogether-build.json', None)
    if record['baseline'] != pin or record['files'] != actual:
        raise ValueError('MaiWeave build changed; rebuild before acceptance')
    if record['patch_sha256'] != hashlib.sha256((ROOT / 'maiweave.patch').read_bytes()).hexdigest():
        raise ValueError('MaiWeave adaptation patch changed')
    for path in (ROOT / 'modules').rglob('*.py'):
        if (directory / path.relative_to(ROOT / 'modules')).read_bytes() != assembly.normalize(path.read_bytes()):
            raise ValueError('MaiWeave adaptation module changed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
