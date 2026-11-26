"""为已有 MaiBot 安装配套 Host 和 QQ 连接器，或导出离线安装文件。"""
from contextlib import ExitStack
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

from assembly import CONTROL, assemble, baseline, hashes, lock_path
from install import backup_path, host_result, installation_lock, plan_host
from instance import adapter_directory, installed_adapter, plan_adapter, plan_config


def fetch_adapter(target, pin):
    subprocess.run(['git', 'init', '--quiet', str(target)], check=True, timeout=30)
    subprocess.run(['git', '-c', 'safe.directory=' + target.resolve().as_posix(),
                    '-c', 'credential.helper=', '-C', str(target), 'fetch', '--quiet', '--depth=1',
                    pin['repository'], pin['commit']], check=True, timeout=90,
                   env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))


def verified_export(output, pin):
    if not output.exists():
        return False
    try:
        record = json.loads((output / 'adapter-sources.json').read_text(encoding='utf-8'))
        locked = json.loads(lock_path('adapter').read_text(encoding='utf-8'))
        matches = (record == {'baseline': pin, 'files': locked}
                   and hashes(output / 'adapter') == locked
                   and (output / 'behavior_control.example.json').read_bytes()
                   == (CONTROL / 'behavior_control.example.json').read_bytes())
    except (OSError, ValueError):
        matches = False
    if not matches:
        raise ValueError(f'输出目录已存在且内容与本版不同，请使用新目录：{output}')
    return True


def prepare(host, output=None, *, apply=False, instance=None, adapter_source=None, account=None, groups=None):
    host = host.resolve()
    pin = baseline()['adapter']
    if output is not None:
        output = output.resolve()
        if instance is not None or account or groups or output.is_relative_to(host):
            raise ValueError('--output 仅用于主程序目录之外的离线输出，不能同时设置实例或账号')
        reuse = verified_export(output, pin)
        output.parent.mkdir(parents=True, exist_ok=True)
    else:
        instance = (instance or Path(os.environ.get('MAIBOT_INSTANCE_DIR', host))).resolve()
        if not instance.is_dir() or (instance != host and not (instance / 'config').is_dir()):
            raise ValueError(f'找不到已有 Bot 实例的 config 目录：{instance}')

    with ExitStack() as stack:
        if apply:
            for root in sorted({host, instance} if instance else {host}):
                stack.enter_context(installation_lock(root))
        work = Path(stack.enter_context(tempfile.TemporaryDirectory(
            prefix='maitogether-', dir=output.parent if output else host.parent)))
        host_plan = plan_host(host, work / 'host')
        ready = work / 'ready'
        ready.mkdir()
        adapter_plan = None
        config_plan = None
        if instance:
            dest = adapter_directory(instance)
            reuse = installed_adapter(dest)
            config_plan = plan_config(instance, work / 'instance', account, groups)
        if not reuse:
            source = adapter_source or work / 'official-adapter'
            if adapter_source is None:
                fetch_adapter(source, pin)
            files = assemble(source.resolve(), 'adapter', ready / 'adapter')
            if instance:
                adapter_plan = plan_adapter(dest, ready / 'adapter', files, source, pin)
            else:
                shutil.copyfile(CONTROL / 'behavior_control.example.json', ready / 'behavior_control.example.json')
                (ready / 'adapter-sources.json').write_text(
                    json.dumps({'baseline': pin, 'files': files}, indent=2) + '\n', encoding='utf-8')

        backup = backup_path(host)
        result = host_result(host_plan, apply=apply, backup=backup)
        with ExitStack() as rollback:
            if apply:
                host_plan.apply(backup, rollback)
            if instance:
                instance_backup = backup if instance == host else backup_path(instance)
                for name, plan in [('adapter', adapter_plan), ('config', config_plan)]:
                    if apply and plan:
                        plan.apply(instance_backup / name, rollback)
                result.update(adapter=str(dest), config=str(instance / 'config/behavior_control.json'),
                              adapter_changed=bool(adapter_plan and apply), config_created=bool(config_plan and apply))
                if apply and (adapter_plan or config_plan):
                    result['instance_backup'] = str(instance_backup)
            else:
                result.update(adapter=str(output / 'adapter'), example=str(output / 'behavior_control.example.json'))
                record = ready / 'install-result.json'
                if not reuse or result['written']:
                    record.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
                if not reuse:
                    ready.rename(output)
                elif result['written']:
                    record.replace(output / record.name)
            rollback.pop_all()
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True, help='官方 MaiBot Git 源码目录')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--instance', type=Path, help='Bot 的实例目录，默认使用 MAIBOT_INSTANCE_DIR 或源码目录')
    mode.add_argument('--output', type=Path, help='仅导出连接器和配置示例，适合手工安装')
    parser.add_argument('--apply', action='store_true', help='停机后安装，省略时只检查或导出')
    parser.add_argument('--account', help='首次配置的机器人 QQ 号')
    parser.add_argument('--groups', nargs='+', help='首次配置的一个或多个群号，用空格分隔')
    parser.add_argument('--adapter-source', type=Path, help='使用已有的官方连接器 Git 仓库，省去下载')
    args = parser.parse_args()
    try:
        if args.output is None and sys.stdin.isatty():
            instance = args.instance or Path(os.environ.get('MAIBOT_INSTANCE_DIR', args.host))
            if not (instance / 'config/behavior_control.json').exists():
                args.account = args.account or input('机器人 QQ 号：').strip()
                args.groups = args.groups or input('受管理的群号（多个用空格分隔）：').split()
        result = prepare(**vars(args))
    except (ValueError, OSError, EOFError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'安装检查失败：{exc}\n')
    print('Host：' + ('本次已安装' if result['written'] else
                     '已是配套版本' if result['installed'] else '可安装（只检查）'))
    if args.output:
        print('连接器产物：' + result['adapter'])
        print('配置示例：' + result['example'])
    else:
        print('实例连接器：' + result['adapter'] + ('（已安装）' if result['adapter_changed'] else
              '（已是配套版本）' if args.apply else '（已检查）'))
        print('行为配置：' + result['config'] + ('（已创建）' if result['config_created'] else
              '（保留已有配置）' if args.apply else '（只检查）'))
    for path in dict.fromkeys(result[key] for key in ('backup', 'instance_backup') if key in result):
        print('备份：' + path)
    if args.output is None and args.apply:
        target = f'群 {args.groups[0]} ' if result['config_created'] else '配置中指定的群'
        print(f'按 docs/setup.md 安装核心插件，启动后到{target}检查静音和恢复。')


if __name__ == '__main__':
    main()
