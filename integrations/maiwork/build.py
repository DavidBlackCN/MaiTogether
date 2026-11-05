"""Assemble the pinned MaiWork source and the reviewed adaptation patch."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent


def build(source, output, *, patch=True):
    pin = json.loads((ROOT / 'baseline.json').read_text(encoding='utf-8'))
    data = subprocess.check_output(['git', '-c', 'safe.directory='+source.resolve().as_posix(),
        '-C', str(source), 'archive', '--format=zip', pin['commit']])
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            if entry.is_dir(): continue
            dest = (output / entry.filename).resolve()
            if not dest.is_relative_to(output): raise ValueError('Unsafe archive path')
            dest.parent.mkdir(parents=True, exist_ok=True)
            blob = archive.read(entry)
            if b'\0' not in blob:
                try: blob = blob.decode('utf-8').replace('\r\n', '\n').encode()
                except UnicodeDecodeError: pass
            dest.write_bytes(blob)
    if patch:
        command = ['git', '-c', 'core.autocrlf=false', 'apply']
        subprocess.run([*command, '--check', str(ROOT/'maiwork.patch')], cwd=output, check=True)
        subprocess.run([*command, str(ROOT/'maiwork.patch')], cwd=output, check=True)
        for p in (ROOT/'modules').rglob('*.py'):
            dest = output / p.relative_to(ROOT/'modules')
            if dest.exists(): raise ValueError('Upstream now owns adaptation module: '+str(dest))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
        files = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(output.rglob('*')) if p.is_file()}
        inputs = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [ROOT/'maiwork.patch', *sorted((ROOT/'modules').rglob('*.py'))]}
        (output/'maitogether-build.json').write_text(json.dumps({'baseline':pin,'inputs':inputs,'files':files},indent=2)+'\n',encoding='utf-8')
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build(args.source,args.output)
