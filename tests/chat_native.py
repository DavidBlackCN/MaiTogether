"""Official message reception continues; life policy controls only outgoing actions."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from native_scenario import LIFE


async def run_cases(values):
    c = SimpleNamespace(**values)
    from src.chat.heart_flow.heartflow_message_processor import HeartFCMessageReceiver
    from src.chat.heart_flow.heartflow_manager import heartflow_manager
    from src.services.memory_flow_service import memory_automation_service
    from src.common.database.database import get_db_session
    from src.common.database.database_model import Messages
    from src.platform_io.manager import get_platform_io_manager
    from sqlmodel import select

    registered = AsyncMock()
    memory = AsyncMock()
    chat = SimpleNamespace(register_message=registered,
                           chat_stream=SimpleNamespace(is_group_session=True))

    def stored(message_id):
        with get_db_session() as db:
            return db.exec(select(Messages).where(Messages.message_id == message_id)).first() is not None

    async def receive(text):
        message = c.raw(text)
        before = registered.await_count, memory.await_count
        await HeartFCMessageReceiver().process_message(message)
        assert stored(message.message_id)
        assert (registered.await_count, memory.await_count) == (before[0] + 1, before[1] + 1)

    with patch.object(heartflow_manager, 'get_or_create_heartflow_chat', AsyncMock(return_value=chat)), \
         patch.object(memory_automation_service, 'on_incoming_message', memory):
        await receive('awake reception')
        assert await c.probe()
        c.cases.append('awake_reception_memory_and_outbound_control')

        await c.sleeping()
        await receive('sleeping reception still reaches official chat and memory')
        before = len(c.writes)
        assert not await c.probe()
        assert not (await c.probe('api'))['success']
        assert len(c.writes) == before
        c.cases.append('sleep_keeps_chat_and_memory_entry_but_denies_outbound')

        io = get_platform_io_manager()
        io.set_inbound_dispatcher(c.manager._dispatch_platform_inbound)
        try:
            before = registered.await_count, memory.await_count
            await c.peers[-1].send_json({'time': int(time.time()), 'self_id': 123456789,
                'post_type': 'message', 'message_type': 'group', 'sub_type': 'normal',
                'group_id': 987654321, 'user_id': 10003, 'message_id': -77701,
                'message': [{'type': 'text', 'data': {'text': 'sleep incoming via real websocket'}}],
                'raw_message': 'sleep incoming via real websocket',
                'sender': {'user_id': 10003, 'nickname': 'test', 'card': '', 'role': 'member'}})
            async def received():
                return (stored('-77701') and registered.await_count == before[0] + 1
                        and memory.await_count == before[1] + 1)
            await c.wait(received)
            c.cases.append('real_websocket_sleep_reception_reaches_official_chat_and_memory')
        finally:
            io.set_inbound_dispatcher(None)

        assert (await c.supervisor.unload_plugins([LIFE], reason='native-chat-test')).success
        try:
            await receive('provider unavailable does not suppress incoming history')
            before = len(c.writes)
            assert not (await c.probe('api'))['success']
            assert len(c.writes) == before
            c.cases.append('missing_provider_denies_outbound_without_suppressing_reception')
        finally:
            assert await c.supervisor.reload_plugins([LIFE], reason='native-chat-restore')
            await c.wait(c.ready)

        await c.awake()
        await receive('awake reception restored')
        assert await c.probe()
        assert (await c.probe('api'))['success']
        c.cases.append('awake_resumes_outbound_without_special_history_replay')
