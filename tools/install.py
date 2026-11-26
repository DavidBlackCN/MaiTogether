"""Install the pinned MaiTogether Host files into a stopped official checkout."""
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time

from assembly import assemble, baseline, git, groups, lock_path, normalize, upstream


def local_bytes(root, name):
    path = root / name
    if path.resolve() != path or (path.exists() and not path.is_file()):
        raise ValueError(f'文件路径异常：{path}')
    return path.read_bytes() if path.exists() else None


@dataclass
class Update:
    root: Path
    staged: Path
    before: dict

    def apply(self, backup, rollback):
        """Keep originals for offline recovery; undo completed writes on failure."""
        if not self.before:
            return
        backup.mkdir(parents=True, exist_ok=False)
        added = []
        for name, original in self.before.items():
            if local_bytes(self.root, name) != original:
                raise ValueError(f'检查后文件已改变：{self.root / name}')
            if original is None:
                added.append(name)
            else:
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.root / name, saved)
        (backup / 'restore.json').write_text(json.dumps({
            'host': str(self.root), 'changed': list(self.before), 'added': added
        }, ensure_ascii=False, indent=2), encoding='utf-8')

        for name, original in self.before.items():
            destination = self.root / name
            missing = []
            parent = destination.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                rollback.callback(directory.rmdir)
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temp:
                temp_path = Path(temp.name)
            try:
                shutil.copyfile(self.staged / name, temp_path)
                if local_bytes(self.root, name) != original:
                    raise ValueError(f'写入前文件已改变：{destination}')
                shutil.copymode(destination if original is not None else self.staged / name, temp_path)
                if original is None:
                    # Link the complete file without replacing one created since preflight.
                    os.link(temp_path, destination)
                    rollback.callback(destination.unlink, missing_ok=True)
                else:
                    os.replace(temp_path, destination)
                    rollback.callback(shutil.copy2, backup / name, destination)
            finally:
                temp_path.unlink(missing_ok=True)


@contextmanager
def installation_lock(root):
    path = root / '.maitogether-install.lock'
    try:
        path.mkdir()
    except FileExistsError:
        raise ValueError(f'安装锁已存在，请确认上次安装状态：{path}') from None
    try:
        yield
    finally:
        path.rmdir()


def plan_host(host, staged):
    pin = baseline()['host']
    if git(host, 'rev-parse', 'HEAD').decode().strip() != pin['commit']:
        raise ValueError(f'需要官方 MaiBot {pin.get("tag", "")} 提交 {pin["commit"]}')
    if Path(os.fsdecode(git(host, 'rev-parse', '--show-toplevel')).strip()).resolve() != host:
        raise ValueError(f'请指定 MaiBot Git 仓库根目录：{host}')
    files = []
    modules = []
    for _, group in groups():
        item = group.get('host', {})
        files.extend(item.get('files', []))
        modules.extend(item.get('modules', []))
    staged_changes = git(host, 'diff', '--cached', '--name-only', '-z').split(b'\0')
    dirty = git(host, '-c', 'core.safecrlf=false', 'diff', '--name-only', '-z').split(b'\0')
    unexpected = [os.fsdecode(n) for n in staged_changes if n]
    unexpected += [os.fsdecode(n) for n in dirty if n and os.fsdecode(n) not in files]
    if unexpected:
        raise ValueError('Host 有其他改动：' + ', '.join(unexpected))
    summary = git(host, '-c', 'core.safecrlf=false', 'diff', '--summary').decode(errors='replace').strip()
    if summary:
        raise ValueError('Host 文件模式或路径有改动：' + summary)
    locked = json.loads(lock_path('host').read_text(encoding='utf-8'))
    before = {}
    installed = []
    for name in files + modules:
        data = local_bytes(host, name)
        value = normalize(data) if data is not None else None
        if value is not None and hashlib.sha256(value).hexdigest() == locked[name]:
            installed.append(name)
        else:
            before[name] = data
    if not before:
        return Update(host, staged, {})
    originals = upstream(host, pin)
    for name, data in before.items():
        value = normalize(data) if data is not None else None
        if value != originals.get(name):
            raise ValueError(f'Host 源码与官方及配套版本均不符：{host / name}')
    if installed:
        raise ValueError(f'Host 仅部分安装，请先从备份恢复，例如：{host / next(iter(before))}')
    assemble(host, 'host', staged)
    return Update(host, staged, before)


def host_result(plan, *, apply=False, backup=None):
    result = {'checked': True, 'files': len(plan.before), 'written': bool(plan.before and apply),
              'installed': not plan.before or apply}
    if result['written']:
        result['backup'] = str(backup)
    return result


def backup_path(root):
    return root.parent / f'{root.name}-maitogether-backup-{time.time_ns()}'


def install(host, *, apply=False, backup=None):
    host = host.resolve()
    with ExitStack() as stack:
        if apply:
            stack.enter_context(installation_lock(host))
        temporary = stack.enter_context(tempfile.TemporaryDirectory(dir=host.parent))
        plan = plan_host(host, Path(temporary) / 'host')
        backup = (backup or backup_path(host)).resolve()
        if backup.is_relative_to(host):
            raise ValueError('备份目录必须位于 Host 之外')
        if apply:
            with ExitStack() as rollback:
                plan.apply(backup, rollback)
                rollback.pop_all()
        return host_result(plan, apply=apply, backup=backup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    print(json.dumps(install(args.host, apply=args.apply, backup=args.backup), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
