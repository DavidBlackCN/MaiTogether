"""Real Host/Runner/Life Provider with isolated cognition and memory observers."""
import asyncio
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from native_scenario import LIFE


async def run_cases(values):
    c = SimpleNamespace(**values)
    from src.plugin_runtime.behavior_policy import sleep_guard as guard
    from src.plugin_runtime.behavior_policy.runtime import get_policy
    from src.chat.heart_flow.heartflow_message_processor import HeartFCMessageReceiver
    from src.chat.heart_flow.heartflow_manager import heartflow_manager
    from src.services.memory_flow_service import memory_automation_service, PersonFactWritebackService
    from src.maisaka.chat_loop_service import MaisakaChatLoopService
    from src.chat.replyer.maisaka_generator_base import BaseMaisakaReplyGenerator
    from src.maisaka.reasoning_engine import MaisakaReasoningEngine
    from src.core.tooling import ToolExecutionResult
    from src.common.database.database import get_db_session
    from src.common.database.database_model import Messages
    from src.common.data_models.mai_message_data_model import MaiMessage
    from sqlmodel import select

    def mark(name):
        c.cases.append(name)

    async def receive(text):
        m = c.raw(text)
        m.timestamp = datetime.now()
        await HeartFCMessageReceiver().process_message(m)
        with get_db_session() as db:
            stored = db.exec(select(Messages).where(Messages.message_id == m.message_id)).one()
            restored = MaiMessage.from_db_instance(stored)
        return m, restored

    registered = AsyncMock()
    memory = AsyncMock()
    with patch.object(heartflow_manager, 'get_or_create_heartflow_chat', AsyncMock(
            return_value=SimpleNamespace(register_message=registered,
                chat_stream=SimpleNamespace(is_group_session=True)))), \
         patch.object(memory_automation_service, 'on_incoming_message', memory):
        assert not await guard.pause_reason(c.stream)
        awake, _ = await receive('awake positive control')
        assert registered.await_count == 1 and memory.await_count == 1
        mark('awake_real_receiver_registers_chat_and_memory')
        await c.sleeping()
        assert await guard.pause_reason(c.stream) == 'sleeping'
        sleeping, persisted = await receive('sleep must remain raw only')
        assert guard.record_only(persisted)
        assert registered.await_count == 1 and memory.await_count == 1
        mark('sleep_raw_record_persisted_no_chat_or_memory_enqueue')

        from src.platform_io.manager import get_platform_io_manager
        io = get_platform_io_manager()
        io.set_inbound_dispatcher(c.manager._dispatch_platform_inbound)
        try:
            await c.peers[-1].send_json({'time': int(time.time()), 'self_id': 123456789,
                'post_type': 'message', 'message_type': 'group', 'sub_type': 'normal',
                'group_id': 987654321, 'user_id': 10003, 'message_id': -77701,
                'message': [{'type': 'text', 'data': {'text': 'sleep incoming via real websocket'}}],
                'raw_message': 'sleep incoming via real websocket',
                'sender': {'user_id': 10003, 'nickname': 'test', 'card': '', 'role': 'member'}})
            async def received():
                with get_db_session() as db:
                    row = db.exec(select(Messages).where(Messages.message_id == '-77701')).first()
                    return row is not None and guard.record_only(MaiMessage.from_db_instance(row))
            await c.wait(received)
            assert registered.await_count == 1 and memory.await_count == 1
            mark('real_websocket_chatbot_sleep_message_stored_without_cognition')
        finally:
            io.set_inbound_dispatcher(None)

        # Actual Planner entry must reject before it reads context or finds a model.
        planner = MaisakaChatLoopService.__new__(MaisakaChatLoopService)
        planner._session_id = c.stream
        try:
            await planner.chat_loop_step([])
        except guard.CognitionPaused:
            pass
        else:
            raise AssertionError('Planner reached model setup while sleeping')
        mark('sleep_planner_entry_zero_model_requests')

        replyer = BaseMaisakaReplyGenerator.__new__(BaseMaisakaReplyGenerator)
        replyer.express_model = object()
        replyer._persist_reply_preview = lambda *a, **kw: None
        ok, result = await replyer.generate_reply_with_context(stream_id=c.stream, chat_history=[])
        assert not ok and 'sleeping' in result.error_message
        mark('sleep_replyer_entry_zero_model_requests')

        from src.maisaka.focus.group_runtime import FocusChatLoopService
        shared = FocusChatLoopService.__new__(FocusChatLoopService)
        shared.cognition_members = {c.stream: object()}
        try:
            await shared.chat_loop_step([])
        except guard.CognitionPaused:
            pass
        else:
            raise AssertionError('shared Planner ignored sleeping member')
        mark('shared_planner_checks_real_member_session')

        # Process a queued turn with actual run_loop code: no history hydration or model work.
        queue = asyncio.Queue()
        queue.put_nowait('message')
        consumed = []
        runtime = SimpleNamespace(_running=True, _internal_turn_queue=queue, session_id=c.stream,
            _collect_pending_messages=lambda: consumed.append('messages'),
            _mark_message_turn_unscheduled=lambda: consumed.append('unscheduled'),
            _clear_forced_turn_state=lambda: None,
            _consume_proactive_trigger_message=lambda: consumed.append('proactive'),
            _consume_proactive_logical_turn_id=lambda: None)
        runtime._enter_stop_state = lambda: setattr(runtime, '_running', False)
        engine = MaisakaReasoningEngine.__new__(MaisakaReasoningEngine)
        engine._runtime = runtime
        await engine.run_loop()
        assert consumed == ['messages', 'unscheduled', 'proactive'] and queue.empty()
        mark('queued_sleep_turn_consumed_before_history_and_generation')

        # Stored sleep messages cannot re-enter automatic context after restart.
        assert await engine._build_history_message(persisted) is None
        assert not await guard.memory_allowed(persisted)
        assert PersonFactWritebackService._filter_target_user_messages(
            [persisted], SimpleNamespace(person_id=''), set()) == []
        mark('persisted_sleep_message_excluded_from_context_and_fact_evidence')

        assert await c.awake()
        assert not await guard.pause_reason(c.stream)
        await shared._check_life_state()
        assert not await guard.memory_allowed(persisted)
        await receive('new message after waking')
        assert registered.await_count == 2 and memory.await_count == 2
        mark('trusted_wake_works_and_only_new_message_scheduled')

        from src.A_memorix.core.utils import summary_importer
        importer = summary_importer.SummaryImporter.__new__(summary_importer.SummaryImporter)
        importer.plugin_config = {}
        importer._existing_summary_result = lambda **kwargs: None
        importer._ensure_runtime_self_check = AsyncMock(return_value=(True, ''))
        with patch.object(summary_importer.message_api, 'get_messages_by_time_in_chat', return_value=[persisted]):
            summary = await importer._import_from_stream_scoped(c.stream)
        assert not summary.success and '未找到有效' in summary.detail
        mark('after_wake_summary_excludes_sleep_record_before_model_call')

        # Host replaces an untrusted marker on an awake input.
        spoof = c.raw('awake marker reset')
        spoof.message_info.additional_config[guard.MARKER] = 'sleeping'
        assert not await guard.mark_incoming(spoof) and not guard.record_only(spoof)
        mark('incoming_marker_cannot_override_host_state')

        # State changes between early admission and a later request are rechecked.
        assert not await guard.pause_reason(c.stream)
        await c.sleeping()
        try:
            await guard.require_awake(c.stream)
        except guard.CognitionPaused:
            pass
        else:
            raise AssertionError('late sleep not detected')
        before = len(c.writes)
        if get_policy().behavior_enabled:
            assert not await c.probe()
            assert len(c.writes) == before
            mark('late_sleep_stops_new_request_and_preserves_final_send_check')
        else:
            assert await c.probe()
            assert len(c.writes) == before + 1
            mark('sleep_only_pauses_cognition_without_installing_send_control')

        # No model/context observer is called by any automatic memory path.
        for method, args in (
            (memory_automation_service.image_writeback._handle_message, (persisted,)),
            (memory_automation_service.fact_writeback._handle_message, (persisted,)),
            (memory_automation_service.chat_summary_writeback._handle_message, (persisted,)),
        ):
            await method(*args)
        mark('sleep_memory_workers_and_image_backfill_skip_record_only_message')

        assert await c.awake()
        assert (await c.supervisor.unload_plugins([LIFE], reason='sleep-test-missing')).success
        assert await guard.pause_reason(c.stream) == 'life_state_unavailable'
        await receive('missing Life Provider raw only')
        assert registered.await_count == 2
        assert await c.supervisor.reload_plugins([LIFE], reason='sleep-test-restore')
        assert not await guard.pause_reason(c.stream)
        mark('missing_provider_stops_cognition_restored_provider_allows_new_work')

        policy = get_policy()
        target = policy.targets.pop(0)
        try:
            assert not await guard.pause_reason(c.stream)
        finally:
            policy.targets.insert(0, target)
        mark('unmanaged_session_keeps_original_cognition')

    draft = 'UNSENT_PRIVATE_DRAFT'
    result = ToolExecutionResult(tool_name='reply', success=False,
        structured_content={'reply_segments': [draft]},
        metadata={'draft': draft, 'sent_message_ids': [], 'send_results': [{'segment': draft, 'success': False}]})
    guard.failed_reply(result)
    assert draft not in result.get_history_content() and draft not in str(result.metadata)
    assert result.stop_after_execution
    mark('failed_reply_has_no_draft_and_stops_retries')
    partial = ToolExecutionResult(tool_name='reply', success=False,
        metadata={'sent_message_ids': ['sent-id'], 'send_results': [
            {'message_id': 'sent-id', 'success': True, 'segment': draft}]})
    guard.failed_reply(partial)
    assert partial.metadata['sent_message_ids'] == ['sent-id'] and draft not in str(partial)
    mark('partial_reply_preserves_delivery_ids_without_unsent_draft')
    from reply_paths_native import run_cases as reply_paths
    await reply_paths(c)
