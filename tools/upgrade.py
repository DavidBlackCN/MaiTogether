"""Check official stable releases in isolation; promote only a validated candidate."""
from pathlib import Path
import argparse
import json
import re
import urllib.request

from assembly import CONTROL, baseline, build_pair, git, hashes, inputs_digest, lock_path, series, upstream
from validate import REQUIRED_CHECKS


def read_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'MaiTogether-upgrade'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def latest(pin):
    repository = pin['repository'].removeprefix('https://github.com/').removesuffix('.git')
    release = read_json('https://api.github.com/repos/' + repository + '/releases/latest')
    if release['draft'] or release['prerelease']:
        raise ValueError('Only official stable releases are supported')
    return release


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('Expected a stable semantic version: ' + str(value))
    return tuple(map(int, value.removeprefix('v').split('.')))


def adapter_compatible(manifest, host, sdk):
    for key, selected in (('host_application', host), ('sdk', sdk)):
        limits = manifest[key]
        if not version(limits['min_version']) <= version(selected) <= version(limits['max_version']):
            return False
    return True


def select_releases(pins, adapter_tag=None):
    """Prefer the newest stable Host/SDK and a released adapter that supports both."""
    selected = {kind: latest(pins[kind]) for kind in ('host', 'sdk')}
    repository = pins['adapter']['repository'].removeprefix('https://github.com/').removesuffix('.git')
    skipped = []
    stable = []
    # Do not select unpublished tags or remove the adapter's compatibility bounds.
    for page in range(1, 11):
        releases = read_json(f'https://api.github.com/repos/{repository}/releases?per_page=100&page={page}')
        for release in releases:
            if release['draft'] or release['prerelease']:
                continue
            version(release['tag_name'])
            stable.append(release)
        if len(releases) < 100:
            break
    else:
        raise ValueError('Too many adapter releases; narrow the supported release catalogue')
    if adapter_tag:
        for release in stable:
            if release['tag_name'] == adapter_tag:
                selected['adapter'] = release
                return selected, skipped
        raise ValueError('Requested adapter tag is not an official stable release')
    for release in sorted(stable, key=lambda r: version(r['tag_name']), reverse=True):
        tag = release['tag_name']
        manifest = read_json(f'https://raw.githubusercontent.com/{repository}/{tag}/_manifest.json')
        if adapter_compatible(manifest, selected['host']['tag_name'], selected['sdk']['tag_name']):
            selected['adapter'] = release
            return selected, skipped
        skipped.append({'tag': tag, 'host': manifest['host_application'], 'sdk': manifest['sdk']})
    raise ValueError('No released adapter supports the latest stable Host and SDK; '
                     'review the maintained adapter patch before selecting --adapter-tag')


def check(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    current = baseline()
    candidate = json.loads(json.dumps(current))
    sources = {kind: getattr(args, kind + '_source').resolve() for kind in ('host', 'sdk', 'adapter')}
    adapter_tag = getattr(args, 'adapter_tag', None)
    selected, skipped = select_releases(current, adapter_tag)
    releases = {}
    for kind, source in sources.items():
        release = selected[kind]
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
              'incompatible_adapter_releases': skipped,
              'reviewed_adapter_tag': adapter_tag,
              'upstream_changed_files': impact, 'regression_required': True}
    try:
        build_pair(sources['host'], sources['adapter'], out / 'build', pins=candidate, verify=False)
        manifest = json.loads((out / 'build/adapter/_manifest.json').read_text(encoding='utf-8'))
        if not adapter_compatible(manifest, candidate['host']['tag'], candidate['sdk']['tag']):
            raise ValueError('Assembled adapter does not declare support for the candidate Host and SDK')
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
    selected, _ = select_releases(pins, report.get('reviewed_adapter_tag'))
    for kind in ('host', 'sdk', 'adapter'):
        if selected[kind]['tag_name'] != pins[kind]['tag']:
            raise ValueError('A newer compatible stable release is available: ' + kind)
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
    create.add_argument('--adapter-tag', help='Reviewed stable adapter release; assembled bounds and full regression remain mandatory')
    accept = commands.add_parser('promote')
    accept.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    check(args) if args.command == 'check' else promote(args)


if __name__ == '__main__':
    main()
