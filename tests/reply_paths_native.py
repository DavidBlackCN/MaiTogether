"""Exercise 1.4 reply cache and translation with real sleep-provider RPCs."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


async def run_cases(c):
    from src.chat.replyer import maisaka_generator_base as module
    from src.common.data_models.llm_service_data_models import LLMResponseResult
    from src.plugin_runtime.host.hook_dispatcher import HookDispatchResult
    from src.config.config import global_config

    creative = global_config.experimental.super_creative_mode
    try:
        for mode in ('normal', 'context', 'cache', 'translation'):
            await c.awake()
            global_config.experimental.super_creative_mode = mode == 'translation'
            generator = module.BaseMaisakaReplyGenerator.__new__(module.BaseMaisakaReplyGenerator)
            generator.request_type = 'replyer'
            generator._resolve_prompt_profile = lambda *a: 'retro' if mode == 'translation' else 'mai_replier'
            generator._resolve_session_id = lambda value: c.stream
            generator._persist_reply_preview = lambda *a, **kw: None
            generator._persist_super_creative_stage = AsyncMock()
            generator._build_generation_options = lambda *a: None
            generator._resolve_enable_visual_message = lambda *a: False
            generator._build_generation_messages = lambda **kw: []
            async def prepared(**kwargs):
                await c.sleeping()
                return []
            generator._invoke_before_model_request_hook = prepared
            async def hook(name, **kwargs):
                if mode == 'normal':
                    await c.sleeping()
                return HookDispatchResult(hook_name=name, kwargs=kwargs)
            generator._get_runtime_manager = lambda: SimpleNamespace(invoke_hook=hook)
            generated = []
            async def generate(**kwargs):
                if mode == 'context':
                    await kwargs['context_factory'](model)
                generated.append(mode)
                await c.sleeping()
                return LLMResponseResult.from_portable_output(response='synthetic draft')
            model = SimpleNamespace(task_name='replyer', generate_response_with_context=generate,
                                    generate_response_from_snapshot=AsyncMock(side_effect=AssertionError('cached call after sleep')))
            generator.express_model = model
            generator._llm_client_cls = lambda **kw: model
            generator._translate_super_creative_reply = AsyncMock(side_effect=AssertionError('translation after sleep'))
            snapshot = SimpleNamespace(request=SimpleNamespace(detached_snapshot=lambda: object())) if mode == 'cache' else None
            with patch.object(module, 'build_cached_reply_request', return_value=SimpleNamespace(context_items=[])):
                ok, result = await generator.generate_reply_with_context(
                    stream_id=c.stream, chat_history=[], planner_snapshot=snapshot)
            assert not ok and 'sleeping' in result.error_message, (mode, result)
            assert len(generated) == (1 if mode == 'translation' else 0)
            generator._translate_super_creative_reply.assert_not_awaited()
            model.generate_response_from_snapshot.assert_not_awaited()
            c.cases.append('late_sleep_blocks_reply_' + mode)
    finally:
        global_config.experimental.super_creative_mode = creative
        await c.awake()
