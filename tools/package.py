"""Create a source-only install bundle; never include an instance's configuration or data."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import zipfile
from build import CONTROL,build,git,hashes


def tracked_files(source):
    # NUL separation preserves Chinese names, spaces and Git's quotePath settings.
    return [name for name in git(source,'ls-files','-z').decode('utf-8').split('\0') if name]


def copy_files(source,target,names):
    for name in names:
        path=Path(name)
        if any(x in ('.git','.github','tests','tools','ecosystem','__pycache__','data','logs','.pytest_cache') for x in path.parts):continue
        if path.name in ('config.toml','requirements-dev.txt','pytest.ini') or path.suffix in ('.pyc','.db','.sqlite3','.log'):continue
        dest=target/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/path,dest)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--maiwork-source',type=Path,help='Include the pinned MaiWork adaptation')
    p.add_argument('--maiweave-source',type=Path,help='Include the reviewed MaiWeave source')
    a=p.parse_args()
    root=a.workspace.resolve();out=a.output.resolve()
    baseline=json.loads((CONTROL/'baseline.json').read_text(encoding='utf-8'))
    if a.maiwork_source:
        work_pin=json.loads((CONTROL/'integrations/maiwork/baseline.json').read_text(encoding='utf-8'))
        if work_pin['host'] != baseline['host']['tag'].removeprefix('v'):
            raise ValueError('MaiWork adaptation has not been validated on this Host baseline')
    archive=out.with_name(out.name+'.zip')
    if out.exists() or archive.exists():raise ValueError('Delivery output must not exist')
    out.mkdir(parents=True)
    for kind,prefix in [('host','Host'),('adapter','QQ-Adapter')]:
        folder=prefix+'-'+baseline[kind]['tag'].removeprefix('v')
        build(root/'.implementation/vendor'/folder,kind,out/kind)
    pins={}
    core=('maibot-maiIdentity-plugin','maibot-maihush-plugin')
    for folder in core:
        source=root/folder
        if git(source,'status','--porcelain').strip(): raise RuntimeError('Uncommitted source: '+folder)
        names=tracked_files(source)
        copy_files(source,out/'plugins'/folder,names)
        pins[folder]={'commit':git(source,'rev-parse','HEAD').decode().strip(),
                      'version':json.loads((source/'_manifest.json').read_text(encoding='utf-8'))['version']}
    if a.maiweave_source:
        source=a.maiweave_source.resolve()
        pin=json.loads((CONTROL/'integrations/maiweave/baseline.json').read_text(encoding='utf-8'))
        if git(source,'status','--porcelain').strip() or git(source,'rev-parse','HEAD').decode().strip()!=pin['commit']:
            raise ValueError('MaiWeave source differs from the reviewed clean commit')
        copy_files(source,out/'plugins/MaiWeave',tracked_files(source))
        pins['MaiWeave']=pin
    if a.maiwork_source:
        spec=importlib.util.spec_from_file_location('maiwork_build',CONTROL/'integrations/maiwork/build.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.build(a.maiwork_source,out/'plugins/MaiWork')
        pins['MaiWork']=json.loads((CONTROL/'integrations/maiwork/baseline.json').read_text(encoding='utf-8'))
    shutil.copytree(CONTROL,out/'maintenance',ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git','.pytest_cache'))
    (out/'core-versions.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
    version=json.loads((CONTROL/'baseline.json').read_text(encoding='utf-8'))['adaptation_version']
    (out/'README.md').write_text(f'# MaiTogether {version}\n\n'
        + ('包含的 MaiWeave 接口范围见 [接入说明](maintenance/docs/maiweave.md)。\n\n' if a.maiweave_source else '生活引擎请另行安装，并设置 Life Provider。\n\n') +
        f'`host/` 为组装后的 Host {baseline["host"]["tag"]}；将 `plugins/` 中的插件及 `adapter/` 连接器安装到所选 Bot 实例的插件目录，同一插件仅保留一份。\n\n'
        f'依赖、配置、测试和回滚说明见 [维护说明](maintenance/README.md)。SDK 固定为 {baseline["sdk"]["tag"]}，详见 maintenance/baseline.json。\n\n'
        '本包不含运行配置、账号、数据库、日志或虚拟环境。启用前填写完整目标与受管范围；真实 QQ、SnowLuma 和 Linux 服务器仍须验收。\n',encoding='utf-8')
    manifest=hashes(out)
    (out/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(out.rglob('*')):
            if file.is_file():z.write(file,out.name+'/'+file.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in manifest.items():
            assert hashlib.sha256(z.read(out.name+'/'+name)).hexdigest()==digest
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'archive':str(archive),'files':len(manifest),'sha256':digest,'core':pins},ensure_ascii=False))


if __name__=='__main__':main()
