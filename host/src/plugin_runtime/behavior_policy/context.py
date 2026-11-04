"""Internal invocation references; business arguments never grant authority."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict
import secrets
import time


@dataclass
class Invocation:
    root: str
    plugin: str
    origin: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    deadline: float = 0
    results: list = field(default_factory=list)
    parent: Any = None


def live(invocation, now):
    while invocation is not None:
        if not invocation.active or invocation.deadline <= now:
            return False
        invocation = invocation.parent
    return True


current: ContextVar[Invocation | None] = ContextVar('behavior_invocation', default=None)
outbound: ContextVar[Dict[str, Any] | None] = ContextVar('behavior_outbound', default=None)
provider_request: ContextVar[Dict[str, Any] | None] = ContextVar('behavior_provider', default=None)
runner_call: ContextVar[Dict[str, Any] | None] = ContextVar('behavior_runner', default=None)


class Contexts:
    def __init__(self):
        self.generation = secrets.token_hex(16)
        self.entries: Dict[str, Invocation] = {}

    @contextmanager
    def issue(self, plugin, method, component, origin=None):
        parent = current.get()
        now = time.monotonic()
        if parent is not None and live(parent, now):
            invocation = Invocation(parent.root, plugin, deepcopy(parent.origin))
            invocation.results = parent.results
            invocation.parent = parent
        else:
            default_kind = 'host' if method == 'plugin.invoke_message_gateway' else 'background'
            invocation = Invocation(secrets.token_hex(16), plugin,
                                    deepcopy(origin or {'kind': default_kind, 'plugin': plugin}))
        if outbound.get() is not None:
            invocation.origin['_outbound'] = deepcopy(outbound.get())
        invocation.origin.setdefault('plugin', plugin)
        invocation.origin.setdefault('component', component)
        invocation.deadline = min(now + 300, parent.deadline) if invocation.parent else now + 300
        reference = self.generation + ':' + secrets.token_hex(24)
        if len(self.entries) >= 8192:
            raise RuntimeError('BEHAVIOR_CONTEXT_CAPACITY')
        self.entries[reference] = invocation
        try:
            yield reference
        finally:
            invocation.active = False
            self.entries.pop(reference, None)

    @contextmanager
    def receive(self, reference, plugin):
        if reference:
            invocation = self.entries.get(reference)
            if invocation is None or invocation.plugin != plugin or not live(invocation, time.monotonic()):
                raise PermissionError('BEHAVIOR_CONTEXT_INVALID')
        else:
            invocation = Invocation(secrets.token_hex(16), plugin,
                                    {'kind': 'background', 'plugin': plugin}, deadline=time.monotonic()+300)
        token = current.set(invocation)
        output_token = outbound.set(invocation.origin.get('_outbound'))
        try:
            yield invocation
        finally:
            outbound.reset(output_token)
            current.reset(token)


contexts = Contexts()


@contextmanager
def runner_scope(envelope):
    state = {'reference': envelope.context_ref, 'control': deepcopy(envelope.behavior_control), 'active': True}
    token = runner_call.set(state)
    try:
        yield
    finally:
        state['active'] = False  # Child tasks share the lifetime marker, not continuing human authority.
        runner_call.reset(token)


def runner_reference():
    state = runner_call.get()
    return state['reference'] if state and state['active'] else ''


def runner_control():
    state = runner_call.get()
    return deepcopy(state['control']) if state and state['active'] else {}
