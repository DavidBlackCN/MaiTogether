"""Run unmodified upstream tests with their expected import package name."""
from pathlib import Path
from types import ModuleType
import argparse
from importlib import import_module
import sys
import pytest

p=argparse.ArgumentParser();p.add_argument('--adapter',type=Path,required=True);p.add_argument('--temp',type=Path,required=True)
a=p.parse_args();source=a.adapter.resolve()
package=ModuleType('plugins');package.__path__=[str(source.parent)];sys.modules['plugins']=package
name='plugins.MaiBot-SnowLuma-Adapter-main'
package=ModuleType(name);package.__path__=[str(source)];sys.modules[name]=package
setattr(sys.modules['plugins'], name.split('.')[1], package)


class StandaloneHandshake:
    @pytest.fixture(autouse=True)
    def bind_gate(self, request, monkeypatch):
        if request.node.name != 'test_real_websocket_handshake_receive_send_and_disconnect':
            return
        # This upstream protocol test builds a transport without a plugin or Host.
        # Supply only its loopback peer's one permitted write.
        builder = import_module(name + '.runtime.builder').QQRuntimeBuilder
        gate_type = import_module(name + '.services.behavior_policy').BehaviorGate
        original = builder.build
        def build(instance, **kwargs):
            bundle = original(instance, **kwargs)
            gate = gate_type(None, bundle)
            async def rpc(phase, **args):
                if phase == 'prepare':
                    assert args['action'] == 'send_private_msg'
                    assert args['route']['target_id'] == '456'
                return {'allowed': True, 'reference': 'loopback'}
            gate.rpc = rpc
            bundle.transport.behavior_gate = gate
            return bundle
        monkeypatch.setattr(builder, 'build', build)


raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','--basetemp='+str(a.temp.resolve()),str(source/'tests')], plugins=[StandaloneHandshake()]))
