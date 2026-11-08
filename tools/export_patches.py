"""Export only explicitly owned official-file edits; never expand patch scope silently."""
from pathlib import Path
import argparse
import difflib
import json
from assembly import CONTROL, baseline, series, upstream, build_pair, lock_path

def export(source, working, kind):
    originals = upstream(source, baseline()[kind])
    assigned = {}
    for group, spec in series()['groups'].items():
        for name in spec.get(kind, {}).get('files', []):
            if name in assigned:
                raise ValueError('Multiple patch owners: ' + name)
            assigned[name] = group
    patches = {group: [] for group in series()['groups']}
    for name, old in originals.items():
        from assembly import normalize
        new = normalize((working / name).read_bytes())
        if old == new:
            continue
        if name not in assigned:
            raise ValueError('Unreviewed upstream edit: ' + name)
        patches[assigned[name]].extend(difflib.unified_diff(
            old.decode('utf-8').splitlines(True), new.decode('utf-8').splitlines(True),
            fromfile='a/'+name, tofile='b/'+name))
    for group, spec in series()['groups'].items():
        item = spec.get(kind)
        if item is None:
            continue
        for name in item['modules']:
            from assembly import normalize
            if name in originals or normalize((working / name).read_bytes()) != normalize((CONTROL / kind / name).read_bytes()):
                raise ValueError('Module source mismatch: ' + name)
        path = CONTROL / item['patch']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(patches[group]), encoding='utf-8', newline='\n')
    print(kind + ': explicit patch groups exported')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-source', type=Path, required=True)
    parser.add_argument('--adapter-source', type=Path, required=True)
    parser.add_argument('--host-working', type=Path, required=True)
    parser.add_argument('--adapter-working', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory for the rebuilt Host and adapter')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Output already exists')
    export(args.host_source, args.host_working, 'host')
    export(args.adapter_source, args.adapter_working, 'adapter')
    result = build_pair(args.host_source, args.adapter_source, args.output, verify=False)
    for kind, files in result['files'].items():
        lock_path(kind).write_text(json.dumps(files, indent=2)+'\n', encoding='utf-8')
    print('Locks regenerated; regression validation is still required.')

if __name__ == '__main__':
    main()
