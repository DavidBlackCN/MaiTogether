"""Offline snapshot/restore to a NEW directory. Stop Host and all Runners first."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and p.name!='snapshot-files.json'}


def verify(root):
    manifest=json.loads((root/'snapshot-files.json').read_text(encoding='utf-8'))
    if hashes(root)!=manifest: raise RuntimeError('Snapshot checksum mismatch')
    checked=0
    for name in manifest:
        path=root/name
        if path.suffix not in ('.db','.sqlite','.sqlite3'): continue
        with path.open('rb') as file: header=file.read(16)
        if header!=b'SQLite format 3\0': continue
        # Even mode=ro may update/create shared-memory files for WAL databases.
        # Verify an isolated copy, including WAL, so the snapshot stays byte-identical.
        with tempfile.TemporaryDirectory(prefix='snapshot-check-',dir=root.parent) as scratch:
            copy=Path(scratch)/path.name
            for suffix in ('','-wal','-shm'):
                source=Path(str(path)+suffix)
                if source.exists(): shutil.copyfile(source,Path(str(copy)+suffix))
            conn=sqlite3.connect(copy.as_uri()+'?mode=ro',uri=True)
            try:
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise RuntimeError('SQLite integrity failed: '+name)
            finally: conn.close()
        checked+=1
    return {'files':len(manifest),'sqlite_databases':checked}


def create(code,runtime,output):
    if output.exists(): raise ValueError('Output must not exist')
    output.mkdir(parents=True)
    shutil.copytree(code,output/'code',ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    for name in ('config','data','plugins'):
        source=runtime/name
        if source.exists():shutil.copytree(source,output/'runtime'/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    for name in ('behavior.json','sources.json'):
        if (runtime/name).exists():shutil.copyfile(runtime/name,output/'runtime'/name)
    (output/'snapshot-files.json').write_text(json.dumps(hashes(output),indent=2)+'\n',encoding='utf-8')
    return verify(output)


def restore(source,output):
    result=verify(source)
    if output.exists(): raise ValueError('Restore destination must not exist')
    shutil.copytree(source,output)
    assert verify(output)==result
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--code',type=Path);parser.add_argument('--runtime',type=Path)
    parser.add_argument('--restore-to',type=Path)
    args=parser.parse_args()
    result=restore(args.snapshot.resolve(),args.restore_to.resolve()) if args.restore_to else create(args.code.resolve(),args.runtime.resolve(),args.snapshot.resolve())
    print(json.dumps(result))
