"""准备配套 QQ 连接器；指定 --apply 时同时安装 Host 修改。"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import tempfile

from assembly import CONTROL, assemble, baseline
from install import install


def fetch_adapter(target, pin):
    """只下载版本清单中的官方提交，不执行下载目录中的代码。"""
    subprocess.run(['git', 'init', '--quiet', str(target)], check=True, timeout=30)
    command = ['git', '-c', 'safe.directory=' + target.resolve().as_posix(),
               '-c', 'credential.helper=', '-C', str(target)]
    subprocess.run([*command, 'fetch', '--quiet', '--depth=1', pin['repository'], pin['commit']],
                   check=True, timeout=90, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))


def prepare(host, output, *, apply=False, adapter_source=None):
    host, output = host.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(host):
        raise ValueError('输出目录必须是主程序目录之外的一个新目录')
    # 先检查现有源码；下载失败或连接器校验失败时都不改 Host。
    checked = install(host)
    output.parent.mkdir(parents=True, exist_ok=True)
    pins = baseline()
    with tempfile.TemporaryDirectory(prefix='maitogether-prepare-', dir=output.parent) as temporary:
        work = Path(temporary)
        source = adapter_source
        if source is None:
            source = work / 'official-adapter'
            fetch_adapter(source, pins['adapter'])
        staged = work / 'ready'
        staged.mkdir()
        files = assemble(source.resolve(), 'adapter', staged / 'adapter')
        shutil.copyfile(CONTROL / 'behavior_control.example.json', staged / 'behavior_control.example.json')
        (staged / 'adapter-sources.json').write_text(
            json.dumps({'baseline': pins['adapter'], 'files': files}, indent=2) + '\n', encoding='utf-8')
        # 安装产物不写入运行实例；不复用用户已有的输出目录。
        if output.exists():
            raise ValueError('输出目录已存在，请换一个新目录')
        staged.rename(output)
    result = install(host, apply=True) if apply else checked
    result.update(adapter=str(output / 'adapter'), example=str(output / 'behavior_control.example.json'))
    (output / 'install-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True, help='已有的官方 MaiBot Git 源码目录')
    parser.add_argument('--output', type=Path, required=True, help='保存连接器与配置示例的新目录')
    parser.add_argument('--apply', action='store_true', help='备份受影响文件后安装 Host 修改；使用前停止 MaiBot')
    parser.add_argument('--adapter-source', type=Path, help='可选：用已有的官方连接器 Git 仓库代替下载')
    args = parser.parse_args()
    try:
        result = prepare(args.host, args.output, apply=args.apply, adapter_source=args.adapter_source)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'准备失败：{exc}\n')
    print('Host 修改已安装。' if result['written'] else 'Host 检查通过，未修改源码；需要安装时加 --apply 并使用新的输出目录。')
    if result.get('backup'):
        print('源码备份：' + result['backup'])
    print('QQ 连接器：' + result['adapter'])
    print('配置示例：' + result['example'])
    print('接下来按 docs/setup.md 安装连接器、选择插件并填写账号和群号。')


if __name__ == '__main__':
    main()
