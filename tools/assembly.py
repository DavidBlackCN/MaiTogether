"""Deterministic patch assembly shared by build, export and upgrade checks."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import zipfile

CONTROL = Path(__file__).resolve().parents[1]
PROFILES = {'full': ('behavior', 'sleep'), 'behavior': ('behavior',), 'sleep': ('sleep',)}


def git(source, *args):
    return subprocess.check_output(['git', '-c', 'safe.directory=' + source.resolve().as_posix(),
                                    '-C', str(source), *args])


def normalize(data):
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    return data.replace(b'\r\n', b'\n') if b'\0' not in data else data


def hashes(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*'), key=lambda p: p.relative_to(directory).as_posix())
            if p.is_file() and '__pycache__' not in p.parts}


def inputs_digest():
    paths = [CONTROL / 'baseline.json', CONTROL / 'patches/series.json']
    for folder in ('host', 'adapter', 'tools', 'tests', 'patches'):
        paths.extend(p for p in (CONTROL / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    values = {p.relative_to(CONTROL).as_posix(): hashlib.sha256(normalize(p.read_bytes())).hexdigest()
              for p in sorted(set(paths))}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def baseline():
    return json.loads((CONTROL / 'baseline.json').read_text(encoding='utf-8'))


def series():
    return json.loads((CONTROL / 'patches/series.json').read_text(encoding='utf-8'))


def groups(profile):
    selected = PROFILES[profile]
    spec = series()['groups']
    ordered = []
    def visit(name):
        if name in ordered:
            return
        for required in spec[name]['requires']:
            visit(required)
        ordered.append(name)
    for name in selected:
        visit(name)
    return [(name, spec[name]) for name in ordered]


def upstream(source, pin):
    if git(source, 'rev-parse', pin['commit'] + '^{commit}').decode().strip() != pin['commit']:
        raise ValueError('Upstream commit mismatch')
    with zipfile.ZipFile(io.BytesIO(git(source, 'archive', '--format=zip', pin['commit']))) as archive:
        return {entry.filename: normalize(archive.read(entry)) for entry in archive.infolist()
                if not entry.is_dir()}


def lock_path(kind, profile):
    suffix = '' if profile == 'full' else '-' + profile
    return CONTROL / 'locks' / f'{kind}{suffix}-files.json'


def assemble(source, kind, target, *, profile='full', pins=None, verify=True):
    pins = pins or baseline()
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=False)
    for name, data in upstream(source, pins[kind]).items():
        dest = (target / name).resolve()
        if not dest.is_relative_to(target):
            raise ValueError('Unsafe upstream path')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    for group, spec in groups(profile):
        item = spec.get(kind)
        if item is None:
            continue
        patch = CONTROL / item['patch']
        command = ['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'apply']
        check = subprocess.run([*command, '--check', str(patch)], cwd=target, capture_output=True, text=True)
        if check.returncode:
            raise ValueError(f'{kind}/{group}: patch conflict\n{check.stderr.strip()}')
        subprocess.run([*command, str(patch)], cwd=target, check=True)
        for name in item['modules']:
            dest = target / name
            if dest.exists():
                raise ValueError(f'{kind}/{group}: upstream now owns {name}')
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = normalize((CONTROL / kind / name).read_bytes())
            if name.endswith('/build_features.py') and profile != 'full':
                data = (f'"""Generated build features; do not edit in a running instance."""\n'
                        f'FEATURES = frozenset({PROFILES[profile]!r})\n').encode()
            dest.write_bytes(data)
    actual = hashes(target)
    if verify:
        expected = json.loads(lock_path(kind, profile).read_text(encoding='utf-8'))
        if actual != expected:
            changed = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
            raise ValueError(f'{kind}/{profile}: hash mismatch: {changed[:10]}')
    return actual


def build_pair(host_source, adapter_source, output, *, profile='full', pins=None, verify=True):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pins = pins or baseline()
    result = {kind: assemble(source, kind, output / kind, profile=profile, pins=pins, verify=verify)
              for kind, source in (('host', host_source), ('adapter', adapter_source))}
    manifest = {'profile': profile, 'baseline': pins, 'inputs_digest': inputs_digest(), 'files': result}
    (output / 'assembly.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (output / 'baseline.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
    return manifest
