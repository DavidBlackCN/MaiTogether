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
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
CONTROL = Path(__file__).resolve().parents[1]


def stage(work, adapter_source, workspace, pins, maiweave=None, post_processing=None, segmentation=None, smart_poke=None, weave_smoke=False):
    sources = {name: workspace / name for name in ('maibot-maihush-plugin', 'maibot-maiIdentity-plugin')}
    sources.update(adapter=adapter_source,
                   poke=smart_poke or workspace / '.implementation/vendor/smart_poke_plugin',
                   cateye=workspace / '.implementation/vendor/Cateye-audit')
    if maiweave:
        sources['maiweave'] = maiweave
    if post_processing:
        sources.update(post_processing=post_processing, segmentation=segmentation)
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
    if not maiweave:
        fixture = work / 'plugins/life-fixture'
        fixture.mkdir()
        shutil.copyfile(CONTROL / 'tests/fixture_life_plugin.py', fixture / 'plugin.py')
        manifest = json.loads((probe / '_manifest.json').read_text(encoding='utf-8'))
        manifest.update(id='test.life-provider', name='Synthetic life state', capabilities=[])
        (fixture / '_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    if maiweave and not weave_smoke:
        target = work/'plugins/maiweave'
        shutil.copyfile(CONTROL/'tests/weave_probe.py', target/'acceptance_probe.py')
        entry=target/'plugin.py'
        text=entry.read_text(encoding='utf-8')
        old='class MaiWeavePlugin(WebUI, FeatureTools, MaiBotPlugin):'
        if old not in text: raise ValueError('MaiWeave fixture entry changed; review latest source')
        if text.count('    async def on_load(self):') != 1: raise ValueError('MaiWeave fixture lifecycle changed')
        text=text.replace('    async def on_load(self):','    async def _upstream_load(self):')
        entry.write_text(text.replace(old, 'from .acceptance_probe import AcceptanceProbe\n\nclass MaiWeavePlugin(AcceptanceProbe, WebUI, FeatureTools, MaiBotPlugin):'), encoding='utf-8')
        for path in target.rglob('*'):
            if path.is_file(): evidence['maiweave/'+path.relative_to(target).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (work / 'plugins').rglob('*'):
        if path.is_file():
            evidence[path.relative_to(work / 'plugins').as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (work / 'sources.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workspace', type=Path, default=ROOT)
    parser.add_argument('--host',type=Path,default=ROOT/'maibot')
    parser.add_argument('--adapter',type=Path,default=ROOT/'.implementation/behavior-control/adapter')
    parser.add_argument('--community',action='store_true',help='Focused unchanged-community plugin acceptance')
    parser.add_argument('--native-chat',action='store_true',help='Official reception and memory continue while outbound sleep control remains active')
    parser.add_argument('--life-provider',action='store_true',help='Generic Life Provider and unavailable-backend acceptance')
    parser.add_argument('--maiwork',type=Path,help='Assembled MaiWork adaptation for isolated acceptance')
    parser.add_argument('--maiweave',type=Path,help='Clean reviewed upstream MaiWeave source')
    parser.add_argument('--maiweave-smoke',action='store_true',help='Load original MaiWeave without test entry injection')
    parser.add_argument('--post-processing',type=Path,help='Cateye Host 1.4 branch source')
    parser.add_argument('--segmentation',type=Path,help='Smart segmentation source')
    parser.add_argument('--smart-poke',type=Path,help='Optional newer Smart Poke source for compatibility checks')
    args = parser.parse_args()
    if args.maiweave_smoke and not args.maiweave:
        parser.error('--maiweave-smoke requires --maiweave')
    if bool(args.post_processing) != bool(args.segmentation):
        parser.error('Post-processing acceptance requires both source directories')
    if args.maiwork and not args.maiweave:
        parser.error("--maiwork requires --maiweave; the Vita matrix is retired")
    weave_pin = None
    if args.maiweave:
        weave_pin=json.loads((CONTROL/'integrations/maiweave/baseline.json').read_text(encoding='utf-8'))
        spec=importlib.util.spec_from_file_location('weave_source',CONTROL/'integrations/maiweave/source.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.verify(args.maiweave.resolve())
    pins_path = args.host.resolve().parent / 'baseline.json'
    if not pins_path.exists():
        pins_path = CONTROL / 'baseline.json'
    pins = json.loads(pins_path.read_text(encoding='utf-8'))
    if importlib.metadata.version('maibot-plugin-sdk') != pins['sdk']['tag'].removeprefix('v'):
        raise RuntimeError('Installed SDK does not match the candidate baseline')
    work = (args.output or ROOT / ('.implementation/behavior-control/native-' + str(time.time_ns()))).resolve()
    work.mkdir(parents=True, exist_ok=False)
    if args.maiweave and any((args.life_provider,args.native_chat,args.community)):
        parser.error('--maiweave selects its own acceptance scenario')
    stage(work,args.adapter.resolve(),args.workspace.resolve(),pins,args.maiweave,args.post_processing,args.segmentation,args.smart_poke,args.maiweave_smoke)
    if args.maiwork:
        spec=importlib.util.spec_from_file_location('work_build',CONTROL/'integrations/maiwork/build.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.verify(args.maiwork.resolve())
        shutil.copytree(args.maiwork, work/'plugins/maiwork', ignore=shutil.ignore_patterns(
            '.git','__pycache__','tests','docs','config.toml'))
        shutil.copyfile(CONTROL/'integrations/maiwork/tests/native_probe.py', work/'plugins/maiwork/native_probe.py')
        entry=work/'plugins/maiwork/plugin.py'
        text=entry.read_text(encoding='utf-8').replace('class MaiWorkPlugin(MaiBotPlugin):',
            'from .native_probe import NativeProbe\n\nclass MaiWorkPlugin(NativeProbe, MaiBotPlugin):')
        entry.write_text(text,encoding='utf-8')
        sources_path=work/'sources.json'
        evidence=json.loads(sources_path.read_text(encoding='utf-8'))
        for path in sorted((work/'plugins/maiwork').rglob('*')):
            if path.is_file():
                evidence['maiwork/'+path.relative_to(work/'plugins/maiwork').as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        sources_path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    safety = work / 'safety'
    safety.mkdir()
    (safety / 'sitecustomize.py').write_text(
        "import sys\ndef audit(e,a):\n    if e=='socket.connect':\n        t=a[1]\n"
        "        if not isinstance(t,tuple) or t[0] not in ('127.0.0.1','::1'): raise PermissionError('EXTERNAL_NETWORK_DENIED')\n"
        "sys.addaudithook(audit)\n", encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS')}
    env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=os.pathsep.join([str(safety), str(CONTROL / 'tests'), str(CONTROL/'integrations/maiwork/tests'), str(args.workspace.resolve()/'tools'), str(args.host.resolve())]),
        MAIBOT_HOST_VERSION=pins['host']['tag'].removeprefix('v'), MAIBOT_INSTANCE_DIR=str(work),
        MAIBOT_COMMUNITY_TEST=str(int(args.community)),
        MAIBOT_NATIVE_CHAT_TEST=str(int(args.native_chat)),
        MAIBOT_LIFE_TEST=str(int(args.life_provider)),
        MAIWORK_TEST=str(int(bool(args.maiwork))),
        MAIWEAVE_TEST=str(int(bool(args.maiweave))),
        MAIWEAVE_SMOKE=str(int(args.maiweave_smoke)),
        MAIWEAVE_ORIGINAL_SOURCE=str(args.maiweave.resolve()) if args.maiweave else '',
        POST_PROCESSING_TEST=str(int(bool(args.post_processing))),
        MAIBOT_WEBUI_USE_LOCAL_DASHBOARD='1',
        MAIBOT_BEHAVIOR_CONFIG=str(work / 'behavior.json'), TEMP=str(work), TMP=str(work), USERPROFILE=str(work))
    with (work / 'console.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, '-m', 'native_scenario'], cwd=work, env=env, stdout=log,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        print(json.dumps({'work': str(work), 'pid': process.pid}), flush=True)
        try:
            code = process.wait(timeout=240)
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
            'passed':True,'kind':'maiweave' if args.maiweave else 'life-provider' if args.life_provider else 'maiwork' if args.maiwork else 'community' if args.community else 'native-chat' if args.native_chat else 'behavior',
            'baseline':pins,'cases':result['cases'],
            'maiweave':weave_pin,
            'maiweave_test_entry': bool(args.maiweave and not args.maiweave_smoke),
            'sources_sha256':hashlib.sha256((work/'sources.json').read_bytes()).hexdigest(),
        },indent=2),encoding='utf-8')
        print(json.dumps({'passed':len(result['cases']),'writes':result['writes'],'evidence':str(work)},ensure_ascii=False))
    raise SystemExit(code)


if __name__ == '__main__': main()
