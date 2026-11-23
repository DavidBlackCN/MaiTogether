"""Exercise the upstream plugin through its registered message hook."""
import json
import socket
import sqlite3
from contextlib import closing
from types import SimpleNamespace


def configure(work, configs):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    configs['maiwork'] = {
        'plugin': {'enabled': True, 'config_version': '0.5.4'},
        'groups': {'serve': [{'group': 'qq:987654321'}]},
        'approval': {'admins': ['qq:10003'], 'auto_review': False},
        'console': {'listen': f'127.0.0.1:{port}', 'update_check': False, 'herenow_share': False},
        'environments': {'railway': False, 'freestyle': False, 'workspace_root': str(work / 'workspaces')},
        'storage': {'data_dir': str(work / 'maiwork-data')},
        'jev': {'enabled': False},
    }


async def check_commands(values):
    from src.plugin_runtime.hook_payloads import serialize_session_message

    c = SimpleNamespace(**values)
    assert 'chartyr.maiwork' in c.supervisor._registered_plugins
    inspected = await c.supervisor.inspect_plugin_config('chartyr.maiwork')
    assert not inspected.config_error, inspected.config_error
    for message_id, actor, expected in [('-801', '10001', '只有'), ('-802', '10003', '没找到请求')]:
        before = len(c.writes)
        message = c.raw('/mw 批准 R-fixture', actor)
        message.message_id = message_id
        await c.manager.invoke_hook('chat.receive.after_process', message=serialize_session_message(message))

        async def replied():
            return any(expected in json.dumps(row['params'], ensure_ascii=False) for row in c.writes[before:])
        await c.wait(replied)
    c.cases.append('original_maiwork_group_approver_and_identity_admin_receive_distinct_qq_replies')


async def check_paused_reply(c, message_id):
    """Wait until MaiWork itself has attempted delivery on the fake QQ route."""
    from src.plugin_runtime.hook_payloads import serialize_session_message

    message = c.raw('/mw 批准 R-fixture', '10003')
    message.message_id = message_id
    before = len(c.writes)
    await c.manager.invoke_hook('chat.receive.after_process', message=serialize_session_message(message))
    db = (c.work / 'maiwork-data/maiwork.db').as_uri() + '?mode=ro'
    async def attempted():
        with closing(sqlite3.connect(db, uri=True)) as conn:
            row = conn.execute('SELECT status, error FROM outbox WHERE key=?', ('cmd:' + message_id,)).fetchone()
        return row and row[0] in ('pending', 'failed', 'uncertain') and row[1]

    await c.wait(attempted)
    assert len(c.writes) == before, c.writes[before:]
