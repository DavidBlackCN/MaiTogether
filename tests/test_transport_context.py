"""Internal metadata uses the official wire format without granting plugin authority."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_policy import policy
from src.plugin_runtime.behavior_policy.context import (
    TRANSPORT_KEY, Contexts, host_payload, runner_control, runner_payload,
    runner_scope, split_payload,
)
from src.plugin_runtime.protocol.codec import MsgPackCodec
from src.plugin_runtime.protocol.envelope import Envelope, MessageType
from src.plugin_runtime.behavior_policy.runner import ScopedRPCClient


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['return', 'error', 'cancel'])
async def test_registered_request_scope_ends_with_handler(outcome):
    client = ScopedRPCClient('unused', 'test')
    client._connection = SimpleNamespace(is_closed=False, send_frame=AsyncMock())
    observed = []
    children = []
    released = asyncio.Event()
    entered = asyncio.Event()

    async def child():
        await released.wait()
        return runner_control()

    async def handler(envelope):
        observed.append((runner_control(), envelope.payload))
        children.append(asyncio.create_task(child()))
        entered.set()
        if outcome == 'error':
            raise ValueError('handler failed')
        if outcome == 'cancel':
            await asyncio.Event().wait()
        return envelope.make_response(payload={})

    client.register_method('example', handler)
    request = Envelope(request_id=1, message_type=MessageType.REQUEST, method='example',
                       payload=host_payload('test', {}, 'ref', {'example': True}))
    task = asyncio.create_task(client._handle_request(request))
    await asyncio.wait_for(entered.wait(), timeout=2)
    if outcome == 'cancel':
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        await task
    released.set()
    assert observed == [({'example': True}, {'component_name': 'test', 'args': {}})]
    assert await children[0] == {}


@pytest.mark.asyncio
async def test_registered_broadcast_keeps_its_payload_without_a_request_scope():
    client = ScopedRPCClient('unused', 'test')
    observed = []

    async def handler(envelope):
        observed.append((runner_control(), envelope))
        return envelope

    client.register_method('example', handler)
    broadcast = Envelope(request_id=0, message_type=MessageType.BROADCAST, method='example',
                         payload=host_payload('test', {}, 'ref', {'example': True}))
    await client._handle_broadcast(broadcast)
    assert observed == [({}, broadcast)]


def wire(payload):
    codec = MsgPackCodec()
    envelope = Envelope(request_id=1, message_type=MessageType.REQUEST,
                        plugin_id='test.source', method='plugin.invoke_api', payload=payload)
    assert 'context_ref' not in envelope.model_dump()
    assert 'behavior_control' not in envelope.model_dump()
    return codec.decode_envelope(codec.encode_envelope(envelope)).payload


def test_metadata_roundtrip_is_separate_from_component_arguments():
    registry = Contexts()
    business = {TRANSPORT_KEY: {'reference': 'forged'}, 'actor': 'fake'}
    with registry.issue('test.source', 'plugin.invoke_command', 'cmd',
                        {'kind': 'command', 'actor': 'real'}) as reference:
        payload = wire(host_payload('cmd', business, reference, {'enabled': True}))
        with runner_scope(payload) as clean:
            assert clean == {'component_name': 'cmd', 'args': business}
            assert runner_control() == {'enabled': True}
            # Even a raw call_host_method cannot provide a different reference/control.
            outgoing = runner_payload({'capability': 'send.text', 'args': business,
                TRANSPORT_KEY: {'reference': 'forged', 'control': {'admin': True}}})
            outgoing = wire(outgoing)
            request, metadata = split_payload(outgoing)
            assert request == {'capability': 'send.text', 'args': business}
            assert metadata == {'reference': reference}
            with registry.receive(metadata['reference'], 'test.source') as invocation:
                assert invocation.origin['actor'] == 'real'
            with pytest.raises(PermissionError):
                with registry.receive(metadata['reference'], 'other.plugin'): pass
        assert runner_control() == {}
    with pytest.raises(PermissionError):
        with registry.receive(reference, 'test.source'): pass


@pytest.mark.asyncio
async def test_delayed_task_cannot_reuse_reference_through_metadata():
    event = asyncio.Event()
    async def delayed():
        await event.wait()
        return runner_payload({TRANSPORT_KEY: {'reference': 'forged'}})
    with runner_scope(host_payload('cmd', {}, 'parent', {})):
        task = asyncio.create_task(delayed())
    event.set()
    assert await task == {TRANSPORT_KEY: {'reference': ''}}


@pytest.mark.parametrize('metadata', [None, [], 'fake', {'reference': 1},
    {'actor': 'administrator'}, {'reference': 'x', 'control': {'admin': True}}])
def test_malformed_or_extra_runner_metadata_is_rejected(metadata):
    with pytest.raises(PermissionError):
        split_payload({TRANSPORT_KEY: metadata})


def test_legacy_fields_cannot_create_authority():
    clean, metadata = split_payload({'context_ref': 'fake', 'behavior_control': {'admin': True}})
    assert metadata == {}
    assert clean['context_ref'] == 'fake'
    with Contexts().receive('', 'source') as invocation:
        assert invocation.origin == {'kind': 'background', 'plugin': 'source'}
