"""Pin upstream plugin checkouts for packaging and isolated tests."""
import json
from pathlib import Path
import shutil

from assembly import CONTROL, git


def verify_reviewed(source, name):
    pin = json.loads((CONTROL / 'locks/community-plugins.json').read_text(encoding='utf-8'))[name]
    if git(source, 'rev-parse', 'HEAD').decode().strip() != pin['commit'] or git(source, 'status', '--porcelain').strip():
        raise ValueError(f'{name} requires a clean checkout of {pin["commit"]}')
    if json.loads((source / '_manifest.json').read_text(encoding='utf-8'))['version'] != pin['version']:
        raise ValueError(f'{name} manifest differs from the reviewed version')
    return pin


def copy_reviewed(source, name, target):
    pin = verify_reviewed(source, name)
    target.mkdir(parents=True, exist_ok=False)
    for filename in git(source, 'ls-files', '-z').decode('utf-8').split('\0'):
        if filename:
            dest = target / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / filename, dest)
    return pin
