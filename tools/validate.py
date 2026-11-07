"""Run the regression matrix against an upgrade candidate, binding evidence to source hashes."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

from assembly import CONTROL, PROFILES, hashes, inputs_digest

CORE_PLUGINS = ('maibot-maihush-plugin', 'maibot-maiIdentity-plugin')
REQUIRED_CHECKS = {'unit', 'adapter', 'full-control', 'full-community', 'full-sleep',
                   'behavior-control', 'behavior-community', 'sleep-sleep',
                   'full-life', 'behavior-life', 'sleep-life', *CORE_PLUGINS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--maiweave', type=Path, help='Reviewed latest source for no-Vita acceptance on all build profiles')
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
    for profile in PROFILES:
        manifest = json.loads((folder / profile / 'assembly.json').read_text(encoding='utf-8'))
        if manifest['baseline'] != pins or manifest['inputs_digest'] != inputs_digest():
            raise ValueError('Mismatched assembly')
        for kind in ('host', 'adapter'):
            if hashes(folder / profile / kind) != manifest['files'][kind]:
                raise ValueError('Assembly changed: ' + profile + '/' + kind)
    commands = [('unit', [sys.executable, '-m', 'pytest', str(CONTROL / 'tests'), '-q', '-p', 'no:cacheprovider',
                           '--basetemp=' + str(evidence / 'pytest'), '-o', 'asyncio_default_fixture_loop_scope=function'])]
    for profile, modes in [('full', ('control', 'community', 'sleep')),
                           ('behavior', ('control', 'community')), ('sleep', ('sleep',))]:
        for mode in modes:
            command = [sys.executable, str(CONTROL / 'tools/run_native.py'), '--workspace', str(args.workspace.resolve()),
                       '--host', str(folder / profile / 'host'), '--adapter', str(folder / profile / 'adapter'),
                       '--output', str(evidence / (profile + '-' + mode))]
            if mode != 'control':
                command.append('--' + mode)
            commands.append((profile + '-' + mode, command))
    for profile, mode, flags in (
        ('full', 'life', ['--life-provider']),
        ('behavior', 'life', ['--life-provider']),
        ('sleep', 'life', ['--life-provider']),
    ):
        commands.append((profile + '-' + mode, [sys.executable, str(CONTROL / 'tools/run_native.py'),
            '--workspace', str(args.workspace.resolve()), '--host', str(folder / profile / 'host'),
            '--adapter', str(folder / profile / 'adapter'),
            '--output', str(evidence / (profile + '-' + mode)), *flags]))
    commands.append(('adapter', [sys.executable, str(CONTROL / 'tools/test_adapter.py'),
                                '--adapter', str(folder / 'full/adapter'), '--temp', str(evidence / 'adapter-pytest')]))
    if args.maiweave:
        for profile in PROFILES:
            command=[sys.executable,str(CONTROL/'tools/run_native.py'),'--workspace',str(args.workspace.resolve()),
                '--host',str(folder/profile/'host'),'--adapter',str(folder/profile/'adapter'),
                '--maiweave',str(args.maiweave.resolve()),'--output',str(evidence/(profile+'-weave'))]
            if profile=='full' and args.maiwork: command+=['--maiwork',str(args.maiwork.resolve())]
            commands.append((profile+'-weave',command))
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
               MAITOGETHER_TEST_HOST=str(folder / 'full/host'))
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
