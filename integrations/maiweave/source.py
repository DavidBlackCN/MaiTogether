"""Verify a reviewed upstream checkout for reproducible tests and packaging only.

Runtime integration uses the public API contract, never this commit check.
"""
import json
from pathlib import Path
import subprocess


def verify(source):
    source = Path(source).resolve()
    pin = json.loads(Path(__file__).with_name('baseline.json').read_text(encoding='utf-8'))
    def git(*args):
        return subprocess.check_output(['git', '-c', 'safe.directory=' + source.as_posix(),
                                        '-C', str(source), *args]).decode('utf-8').strip()
    if git('rev-parse', 'HEAD') != pin['commit'] or git('status', '--porcelain'):
        raise ValueError('MaiWeave tests/package require the reviewed clean upstream commit')
    manifest = json.loads((source / '_manifest.json').read_text(encoding='utf-8'))
    if manifest['version'] != pin['version']:
        raise ValueError('MaiWeave manifest differs from the review record')
    return pin
