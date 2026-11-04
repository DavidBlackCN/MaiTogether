"""Stage real plugins and run the patched Host with loopback-only external substitutes."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import importlib.metadata

ROOT = Path(__file__).resolve().parents[2]
CONTROL = Path(__file__).resolve().parents[1]


def stage(work, adapter_source, workspace, pins, vita_next=False):
    sources = {name: workspace / name for name in ('maibot-maivita-plugin', 'maibot-maihush-plugin',
                'maibot-maiIdentity-plugin', 'maibot-maicoordinate-plugin')}
    sources.update(adapter=adapter_source,
                   poke=workspace / '.implementation/vendor/smart_poke_plugin',
                   cateye=workspace / '.implementation/vendor/Cateye-audit')
    if vita_next:
        sources['date']=workspace/'.implementation/vendor/date_context_plugin'
    evidence = {}
    for name, source in sources.items():
        target = work / 'plugins' / name
        target.mkdir(parents=True)
        for path in source.rglob('*'):
            relative = path.relative_to(source)
            if (not path.is_file() or any(p.startswith('.') or p in ('__pycache__', 'tests', 'docs', 'ecosystem', 'data')
                                         for p in relative.parts)
                    or path.suffix not in ('.py', '.json', '.sql', '.txt', '.html') or path.name == 'requirements.txt'):
                continue
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            evidence[name+'/'+relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    probe = work / 'plugins/probe'
    probe.mkdir()
    shutil.copyfile(CONTROL / 'tests/probe_plugin.py', probe / 'plugin.py')
    (probe / '_manifest.json').write_text(json.dumps(dict(manifest_version=2, id='test.behavior-probe',
        name='Behavior probe', version='1.0.0', description='Isolated fixture', author={'name':'test','url':'https://example.invalid'},
        license='MIT', urls={'repository':'https://example.invalid/test'},
        i18n={'default_locale':'zh-CN','supported_locales':['zh-CN']},
        host_application={'min_version':pins['host']['tag'].removeprefix('v'),'max_version':pins['host']['tag'].removeprefix('v')},
        sdk={'min_version':pins['sdk']['tag'].removeprefix('v'),'max_version':pins['sdk']['tag'].removeprefix('v')}, plugin_type='extension',
        capabilities=['send.text','send.emoji','send.custom','api.call','llm.generate','behavior.check'])), encoding='utf-8')
    (work / 'sources.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workspace', type=Path, default=ROOT)
    parser.add_argument('--host',type=Path,default=ROOT/'maibot')
    parser.add_argument('--adapter',type=Path,default=ROOT/'.implementation/behavior-control/adapter')
    parser.add_argument('--community',action='store_true',help='Focused unchanged-community plugin acceptance')
    parser.add_argument('--sleep',action='store_true',help='Sleeping cognition and automatic memory acceptance')
    parser.add_argument('--vita-next',action='store_true',help='Life WebUI, calendar and frequency acceptance')
    parser.add_argument('--browser',type=Path,help='Chromium executable for isolated browser acceptance')
    args = parser.parse_args()
    pins_path = args.host.resolve().parent / 'baseline.json'
    if not pins_path.exists():
        pins_path = CONTROL / 'baseline.json'
    pins = json.loads(pins_path.read_text(encoding='utf-8'))
    if importlib.metadata.version('maibot-plugin-sdk') != pins['sdk']['tag'].removeprefix('v'):
        raise RuntimeError('Installed SDK does not match the candidate baseline')
    work = (args.output or ROOT / ('.implementation/behavior-control/native-' + str(time.time_ns()))).resolve()
    work.mkdir(parents=True, exist_ok=False)
    stage(work,args.adapter.resolve(),args.workspace.resolve(),pins,args.vita_next)
    safety = work / 'safety'
    safety.mkdir()
    (safety / 'sitecustomize.py').write_text(
        "import sys\ndef audit(e,a):\n    if e=='socket.connect':\n        t=a[1]\n"
        "        if not isinstance(t,tuple) or t[0] not in ('127.0.0.1','::1'): raise PermissionError('EXTERNAL_NETWORK_DENIED')\n"
        "sys.addaudithook(audit)\n", encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS')}
    env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=os.pathsep.join([str(safety), str(CONTROL / 'tests'), str(args.workspace.resolve()/'tools'), str(args.host.resolve())]),
        MAIBOT_HOST_VERSION=pins['host']['tag'].removeprefix('v'), MAIBOT_INSTANCE_DIR=str(work),
        MAIBOT_COMMUNITY_TEST=str(int(args.community)),
        MAIBOT_SLEEP_TEST=str(int(args.sleep)),
        MAIVITA_NEXT_TEST=str(int(args.vita_next)),
        MAIBOT_WEBUI_USE_LOCAL_DASHBOARD='1',
        MAIBOT_BEHAVIOR_CONFIG=str(work / 'behavior.json'), TEMP=str(work), TMP=str(work), USERPROFILE=str(work))
    if args.browser:env['MAIVITA_BROWSER']=str(args.browser.resolve())
    with (work / 'console.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, '-m', 'native_scenario'], cwd=work, env=env, stdout=log,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        print(json.dumps({'work': str(work), 'pid': process.pid}), flush=True)
        try:
            code = process.wait(timeout=600 if args.vita_next else 240)
        except BaseException:
            if os.name == 'nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], capture_output=True)
            else:
                process.kill()
            raise
    if code:
        print((work / 'console.log').read_text(encoding='utf-8')[-6500:])
    else:
        result=json.loads((work/'result.json').read_text(encoding='utf-8'))
        (work/'acceptance.json').write_text(json.dumps({
            'passed':True,'kind':'vita-next' if args.vita_next else 'community' if args.community else 'sleep' if args.sleep else 'behavior',
            'baseline':pins,'cases':result['cases'],
            'sources_sha256':hashlib.sha256((work/'sources.json').read_bytes()).hexdigest(),
        },indent=2),encoding='utf-8')
        print(json.dumps({'passed':len(result['cases']),'writes':result['writes'],'evidence':str(work)},ensure_ascii=False))
    raise SystemExit(code)


if __name__ == '__main__': main()
