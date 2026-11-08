"""Check official stable releases in isolation; promote only a validated candidate."""
from pathlib import Path
import argparse
import json
import urllib.request

from assembly import CONTROL, baseline, build_pair, git, hashes, inputs_digest, lock_path, series, upstream
from validate import REQUIRED_CHECKS


def latest(pin):
    repository = pin['repository'].removeprefix('https://github.com/').removesuffix('.git')
    request = urllib.request.Request('https://api.github.com/repos/' + repository + '/releases/latest',
                                     headers={'User-Agent': 'MaiTogether-upgrade'})
    with urllib.request.urlopen(request, timeout=20) as response:
        release = json.load(response)
    if release['draft'] or release['prerelease']:
        raise ValueError('Only official stable releases are supported')
    return release


def check(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    current = baseline()
    candidate = json.loads(json.dumps(current))
    sources = {kind: getattr(args, kind + '_source').resolve() for kind in ('host', 'sdk', 'adapter')}
    releases = {}
    for kind, source in sources.items():
        release = latest(current[kind])
        ref = release['tag_name']
        commit = git(source, 'rev-parse', ref + '^{commit}').decode().strip()
        candidate[kind].update(tag=ref, commit=commit)
        releases[kind] = {'tag': ref, 'commit': commit, 'url': release['html_url'],
                          'published_at': release['published_at']}
    (out / 'candidate.json').write_text(json.dumps(candidate, indent=2) + '\n', encoding='utf-8')
    impact = {}
    for kind in ('host', 'adapter'):
        old = upstream(sources[kind], current[kind])
        new = upstream(sources[kind], candidate[kind])
        owned = {name for spec in series()['groups'].values() for name in spec.get(kind, {}).get('files', [])}
        impact[kind] = sorted(name for name in owned if old.get(name) != new.get(name))
    report = {'inputs_digest': inputs_digest(), 'stable_releases': releases,
              'upstream_changed_files': impact, 'regression_required': True}
    try:
        build_pair(sources['host'], sources['adapter'], out / 'build', pins=candidate, verify=False)
        report['applicable'] = True
    except Exception as exc:
        report.update(applicable=False, error=str(exc))
    (out / 'upgrade-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['applicable']:
        raise SystemExit(1)


def promote(args):
    folder = args.candidate.resolve()
    report = json.loads((folder / 'upgrade-check.json').read_text(encoding='utf-8'))
    validation = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
    pins = json.loads((folder / 'candidate.json').read_text(encoding='utf-8'))
    if (not report['applicable'] or not validation.get('passed')
            or not REQUIRED_CHECKS <= {item['name'] for item in validation.get('checks', []) if item['exit_code'] == 0}
            or validation.get('candidate') != pins
            or report['inputs_digest'] != inputs_digest()
            or validation.get('inputs_digest') != inputs_digest()):
        raise ValueError('Candidate or source changed, or regression validation is incomplete')
    # Do not promote yesterday's release after a newer stable release has appeared.
    for kind in ('host', 'sdk', 'adapter'):
        if latest(pins[kind])['tag_name'] != pins[kind]['tag']:
            raise ValueError('A newer stable release is available: ' + kind)
    assembled = json.loads((folder / 'build/assembly.json').read_text(encoding='utf-8'))
    if assembled['baseline'] != pins or assembled['inputs_digest'] != inputs_digest():
        raise ValueError('Candidate baseline changed')
    for kind in ('host', 'adapter'):
        if hashes(folder / 'build' / kind) != assembled['files'][kind]:
            raise ValueError('Validated output changed: ' + kind)
    (CONTROL / 'baseline.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
    for kind, files in assembled['files'].items():
        lock_path(kind).write_text(json.dumps(files, indent=2) + '\n', encoding='utf-8')
    print('Validated stable baseline promoted. No running instance was modified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('check')
    for kind in ('host', 'sdk', 'adapter'):
        create.add_argument('--' + kind + '-source', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    accept = commands.add_parser('promote')
    accept.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    check(args) if args.command == 'check' else promote(args)


if __name__ == '__main__':
    main()
