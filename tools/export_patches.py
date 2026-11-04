"""Maintainer tool: regenerate patches and complete output hashes after reviewed edits."""
from pathlib import Path
import argparse
import difflib
import json
import io
import zipfile
from build import CONTROL,git,normalize


def export(source,working,kind):
    lock=json.loads((CONTROL/'baseline.json').read_text(encoding='utf-8'))[kind]
    archive=zipfile.ZipFile(io.BytesIO(git(source,'archive','--format=zip',lock['commit'])))
    paths=[e.filename for e in archive.infolist() if not e.is_dir()]
    patch=[];hashes={}
    import hashlib
    for name in paths:
        old=normalize(archive.read(name))
        path=working/name
        if not path.is_file(): raise RuntimeError('Missing upstream file: '+name)
        new=normalize(path.read_bytes())
        if old!=new:
            patch.extend(difflib.unified_diff(old.decode('utf-8').splitlines(True),new.decode('utf-8').splitlines(True),
                         fromfile='a/'+name,tofile='b/'+name))
        hashes[name]=hashlib.sha256(new).hexdigest()
    for path in (CONTROL/kind).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            name=path.relative_to(CONTROL/kind).as_posix()
            if name in hashes: raise RuntimeError('Overlay collision: '+name)
            actual=(working/name).read_bytes()
            if actual!=path.read_bytes(): raise RuntimeError('Overlay/runtime mismatch: '+name)
            hashes[name]=hashlib.sha256(actual).hexdigest()
    (CONTROL/'patches').mkdir(exist_ok=True);(CONTROL/'locks').mkdir(exist_ok=True)
    (CONTROL/'patches'/f'{kind}.patch').write_text(''.join(patch),encoding='utf-8',newline='\n')
    (CONTROL/'locks'/f'{kind}-files.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(kind,len(hashes),'files')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--working',type=Path,required=True);p.add_argument('--kind',choices=['host','adapter'],required=True)
    a=p.parse_args();export(a.source,a.working,a.kind)
