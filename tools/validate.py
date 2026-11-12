"""Run the regression matrix against an upgrade candidate, binding evidence to source hashes."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

from assembly import CONTROL, hashes, inputs_digest

CORE_PLUGINS = ('maibot-maihush-plugin', 'maibot-maiIdentity-plugin')
REQUIRED_CHECKS = {'unit', 'adapter', 'control', 'community', 'native-chat',
                   'life', *CORE_PLUGINS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--maiweave', type=Path, help='Clean reviewed upstream MaiWeave source for acceptance')
    parser.add_argument('--maiwork', type=Path, help='Built adaptation; enables work unit and native tests')
    args = parser.parse_args()
    if args.maiwork and not args.maiweave:
        parser.error("--maiwork requires --maiweave")
    folder = args.candidate.resolve()
    evidence = folder / 'validation'
    evidence.mkdir(exist_ok=False)
    check = json.loads((folder / 'upgrade-check.json').read_text(encoding='utf-8'))
    pins = json.loads((folder / 'candidate.json').read_text(encoding='utf-8'))
    if not check['applicable'] or check['inputs_digest'] != inputs_digest():
        raise ValueError('Rebuild the candidate after changing maintenance sources or tests')
    build = folder / 'build'
    manifest = json.loads((build / 'assembly.json').read_text(encoding='utf-8'))
    if manifest['baseline'] != pins or manifest['inputs_digest'] != inputs_digest():
        raise ValueError('Mismatched assembly')
    for kind in ('host', 'adapter'):
        if hashes(build / kind) != manifest['files'][kind]:
            raise ValueError('Assembly changed: ' + kind)
    commands = [('unit', [sys.executable, '-m', 'pytest', str(CONTROL / 'tests'), '-q', '-p', 'no:cacheprovider',
                           '--basetemp=' + str(evidence / 'pytest'), '-o', 'asyncio_default_fixture_loop_scope=function'])]
    for mode, flags in (('control', []), ('community', ['--community']),
                        ('native-chat', ['--native-chat']), ('life', ['--life-provider'])):
        commands.append((mode, [sys.executable, str(CONTROL / 'tools/run_native.py'),
            '--workspace', str(args.workspace.resolve()), '--host', str(build / 'host'),
            '--adapter', str(build / 'adapter'), '--output', str(evidence / mode), *flags]))
    commands.append(('adapter', [sys.executable, str(CONTROL / 'tools/test_adapter.py'),
                                '--adapter', str(build / 'adapter'), '--temp', str(evidence / 'adapter-pytest')]))
    if args.maiweave:
        commands.append(('maiweave-unit', [sys.executable, str(CONTROL / 'integrations/maiweave/tests/run.py'),
            '--source', str(args.maiweave.resolve()), '--output', str(evidence / 'maiweave-unit')]))
        command = [sys.executable, str(CONTROL / 'tools/run_native.py'), '--workspace', str(args.workspace.resolve()),
            '--host', str(build / 'host'), '--adapter', str(build / 'adapter'),
            '--maiweave', str(args.maiweave.resolve()), '--output', str(evidence / 'weave')]
        if args.maiwork:
            command += ['--maiwork', str(args.maiwork.resolve())]
        commands.append(('weave', command))
        commands.append(('weave-original-load', [sys.executable, str(CONTROL / 'tools/run_native.py'),
            '--workspace', str(args.workspace.resolve()), '--host', str(build / 'host'),
            '--adapter', str(build / 'adapter'), '--maiweave', str(args.maiweave.resolve()),
            '--maiweave-smoke', '--output', str(evidence / 'weave-original-load')]))
    if args.maiwork:
        commands.append(('maiwork-unit',[sys.executable,str(CONTROL/'integrations/maiwork/tests/run.py'),
            '--source',str(args.maiwork.resolve()),'--output',str(evidence/'maiwork-unit')]))
    for name in CORE_PLUGINS:
        commands.append((name, [sys.executable, '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider',
                                '--basetemp=' + str(evidence / (name + '-pytest')),
                                '-o', 'asyncio_default_fixture_loop_scope=function']))
    report = {'candidate': pins, 'inputs_digest': inputs_digest(), 'checks': [], 'passed': False,
              'requested_checks':[name for name,_ in commands]}
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               MAITOGETHER_TEST_HOST=str(build / 'host'))
    try:
        for name, command in commands:
            with (evidence / (name + '.log')).open('wb') as output:
                cwd = args.workspace.resolve() / name if name in CORE_PLUGINS else CONTROL
                check_env = dict(env, MAIBOT_EVIDENCE_DIR=str(evidence / (name + '-evidence')))
                result = subprocess.run(command, cwd=cwd, env=check_env, stdout=output,
                                        stderr=subprocess.STDOUT, timeout=300)
            report['checks'].append({'name': name, 'exit_code': result.returncode})
            print(name, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
            if result.returncode:
                raise RuntimeError('Regression failed: ' + name)
        report['passed'] = True
    finally:
        (folder / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
