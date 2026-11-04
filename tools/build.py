"""Rebuild into a new directory from locked, local upstream Git objects."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import subprocess
import zipfile

CONTROL=Path(__file__).resolve().parents[1]


def git(source,*args):
    return subprocess.check_output(['git','-c','safe.directory='+source.resolve().as_posix(),'-C',str(source),*args])


def hashes(directory):
    return {p.relative_to(directory).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def normalize(data):
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    return data.replace(b'\r\n',b'\n') if b'\0' not in data else data


def build(source,kind,target):
    lock=json.loads((CONTROL/'baseline.json').read_text(encoding='utf-8'))[kind]
    # The exact object is archived: local uncommitted files never become input.
    commit=git(source,'rev-parse',lock['commit']+'^{commit}').decode().strip()
    if commit!=lock['commit']: raise RuntimeError('Upstream commit mismatch')
    target.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(git(source,'archive','--format=zip',commit))) as archive:
        for entry in archive.infolist():
            if entry.is_dir(): continue
            dest=(target/entry.filename).resolve()
            if not dest.is_relative_to(target.resolve()): raise RuntimeError('Unsafe upstream archive path')
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(normalize(archive.read(entry)))
    patch=CONTROL/'patches'/f'{kind}.patch'
    apply=['git','-c','core.autocrlf=false','-c','core.eol=lf','apply']
    subprocess.run([*apply,'--check',str(patch)],cwd=target,check=True)
    subprocess.run([*apply,str(patch)],cwd=target,check=True)
    for path in (CONTROL/kind).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts: continue
        relative=path.relative_to(CONTROL/kind);dest=target/relative
        if dest.exists(): raise RuntimeError('Overlay collides with upstream: '+str(relative))
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
    actual=hashes(target)
    expected=json.loads((CONTROL/'locks'/f'{kind}-files.json').read_text(encoding='utf-8'))
    if actual!=expected: raise RuntimeError('Rebuilt file hash mismatch: '+kind)
    return actual


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-source',type=Path,required=True)
    parser.add_argument('--adapter-source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();target=args.output.resolve()
    if target.exists(): raise SystemExit('Output must not exist; running instances are never overwritten.')
    target.mkdir(parents=True)
    for kind,source in [('host',args.host_source),('adapter',args.adapter_source)]:
        result=build(source,kind,target/kind)
        print(f'{kind}: {len(result)} files verified')
    (target/'baseline.json').write_bytes((CONTROL/'baseline.json').read_bytes())


if __name__=='__main__':main()
