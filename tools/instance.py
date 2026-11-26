"""Place the verified QQ connector and first-time configuration in one Bot instance."""
from pathlib import Path
import hashlib
import json
import os

from assembly import CONTROL, lock_path, normalize, upstream
from install import Update, local_bytes

ADAPTER_ID = 'maibot-team.snowluma-adapter'


def adapter_directory(instance):
    plugins = instance / 'plugins'
    if plugins.resolve() != plugins:
        raise ValueError(f'请使用实际插件目录：{plugins}')
    matches = []
    for manifest in plugins.glob('*/_manifest.json'):
        try:
            metadata = json.loads(manifest.read_text(encoding='utf-8-sig'))
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f'无法识别插件清单：{manifest}') from exc
        if not isinstance(metadata, dict):
            raise ValueError(f'无法识别插件清单：{manifest}')
        if metadata.get('id') == ADAPTER_ID:
            matches.append(manifest.parent)
    if len(matches) > 1:
        raise ValueError('实例有多个 SnowLuma 连接器：' + ', '.join(map(str, matches)))
    dest = matches[0] if matches else plugins / 'MaiBot-SnowLuma-Adapter'
    if dest.resolve() != dest or (not matches and dest.exists()):
        raise ValueError(f'无法安全识别连接器目录：{dest}')
    return dest


def installed_adapter(dest):
    if not dest.exists():
        return False
    locked = json.loads(lock_path('adapter').read_text(encoding='utf-8'))
    for path in dest.rglob('*.py'):
        if path.relative_to(dest).as_posix() not in locked:
            raise ValueError(f'连接器包含版本清单外的代码：{path}')
    for name, digest in locked.items():
        data = local_bytes(dest, name)
        if data is None or hashlib.sha256(normalize(data)).hexdigest() != digest:
            return False
    return True


def plan_adapter(dest, staged, files, source, pin):
    originals = upstream(source, pin) if dest.exists() else {}
    before = {}
    for name in files:
        data = local_bytes(dest, name)
        value = normalize(data) if data is not None else None
        if value != originals.get(name):
            raise ValueError(f'连接器与配套版本和官方原版均不符，请核对或恢复：{dest / name}')
        if value != (staged / name).read_bytes():
            before[name] = data
    return Update(dest, staged, before)


def plan_config(instance, staged, account, groups):
    config = instance / 'config/behavior_control.json'
    override = os.environ.get('MAIBOT_BEHAVIOR_CONFIG')
    if override and Path(override).resolve() != config:
        raise ValueError(f'正在使用自定义配置 {override}。请使用 --output 手工部署。')
    if local_bytes(instance, 'config/behavior_control.json') is not None:
        return None
    if not account or not groups or any(not n.isascii() or not n.isdecimal() or int(n) == 0
                                         for n in [account, *groups]):
        raise ValueError('首次配置请提供机器人 QQ 和至少一个群号（--account 和 --groups）')
    example = json.loads((CONTROL / 'behavior_control.example.json').read_text(encoding='utf-8'))
    targets = []
    for target in example['targets']:
        target['account_id'] = account
        if target['chat_type'] == 'group':
            targets.extend(dict(target, target_id=number) for number in dict.fromkeys(groups))
        elif target['chat_type'] == 'space':
            targets.append(dict(target, target_id=account))
        else:
            raise ValueError('无法初始化示例中的会话类型：' + target['chat_type'])
    example['targets'] = targets
    name = 'config/behavior_control.json'
    path = staged / name
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(example, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return Update(instance, staged, {name: None})
