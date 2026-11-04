"""Check or apply the default Host patch set to an existing, stopped official checkout."""
from pathlib import Path
import argparse
import json
import os
import shutil
import tempfile
import time

from assembly import assemble, baseline, git, hashes, normalize, upstream


def install(host, *, apply=False, backup=None):
    host = host.resolve()
    pins = baseline()
    if git(host, 'rev-parse', 'HEAD').decode().strip() != pins['host']['commit']:
        raise ValueError('Use the official Host commit specified in baseline.json')
    if git(host, 'status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Tracked source has local changes; installation stopped')
    originals = upstream(host, pins['host'])
    with tempfile.TemporaryDirectory(prefix='maitogether-check-', dir=host.parent) as temporary:
        staged = Path(temporary) / 'host'
        assemble(host, 'host', staged)
        changed = [name for name in hashes(staged)
                   if name not in originals or (staged / name).read_bytes() != originals[name]]
        for name in changed:
            dest = host / name
            if not dest.resolve().is_relative_to(host):
                raise ValueError('Source path leaves Host directory: ' + name)
            if name not in originals and dest.exists():
                raise ValueError('New module already exists: ' + name)
            if name in originals and normalize(dest.read_bytes()) != originals[name]:
                raise ValueError('Source changed during check: ' + name)
        if not apply:
            return {'checked': True, 'files': len(changed), 'written': False}
        backup = (backup or host.parent / (host.name + '-maitogether-backup-' + str(time.time_ns()))).resolve()
        if backup.is_relative_to(host):
            raise ValueError('Backup must be outside Host')
        backup.mkdir(parents=True, exist_ok=False)
        added = []
        for name in changed:
            if name in originals:
                dest = backup / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(host / name, dest)
            else:
                added.append(name)
        (backup / 'restore.json').write_text(json.dumps({'host': str(host), 'changed': changed, 'added': added}, indent=2), encoding='utf-8')
        written = []
        try:
            for name in changed:
                dest = host / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Replace one complete file at a time; partial writes never become source.
                with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as temp:
                    temp.write((staged / name).read_bytes())
                    temp_path = Path(temp.name)
                try:
                    # New files must inherit normal source permissions, not mkstemp's owner-only mode.
                    shutil.copymode(dest if dest.exists() else staged / name, temp_path)
                    os.replace(temp_path, dest)
                finally:
                    temp_path.unlink(missing_ok=True)
                written.append(name)
        except BaseException:
            for name in reversed(written):
                if name in added:
                    (host / name).unlink()
                else:
                    shutil.copyfile(backup / name, host / name)
            raise
    return {'checked': True, 'files': len(changed), 'written': True, 'backup': str(backup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Write only after all checks succeed; default is check-only')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    print(json.dumps(install(args.host, apply=args.apply, backup=args.backup), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
