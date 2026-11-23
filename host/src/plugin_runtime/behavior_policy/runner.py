"""Attach the Host invocation context to registered Runner requests."""
from src.plugin_runtime.protocol.envelope import Envelope
from src.plugin_runtime.runner.rpc_client import MethodHandler, RPCClient

from .context import runner_scope


class ScopedRPCClient(RPCClient):
    def register_method(self, method: str, handler: MethodHandler) -> None:
        async def invoke(envelope: Envelope) -> Envelope:
            if not envelope.is_request():
                return await handler(envelope)
            with runner_scope(envelope.payload) as payload:
                return await handler(envelope.model_copy(update={'payload': payload}))

        super().register_method(method, invoke)
