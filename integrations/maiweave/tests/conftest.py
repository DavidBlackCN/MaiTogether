"""使用组装后的原始插件领域代码；所有外部服务为替身。"""
import importlib.util
import os
from pathlib import Path
import sys

SOURCE = Path(os.environ['MAIWEAVE_SOURCE']).resolve()
sys.path.insert(0, str(SOURCE / 'tests'))
spec = importlib.util.spec_from_file_location('maiweave', SOURCE / '__init__.py', submodule_search_locations=[str(SOURCE)])
package = importlib.util.module_from_spec(spec)
sys.modules['maiweave'] = package
spec.loader.exec_module(package)
from test_plugin import plugin
