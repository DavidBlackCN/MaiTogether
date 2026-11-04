"""Run unmodified upstream tests with their expected import package name."""
from pathlib import Path
from types import ModuleType
import argparse
import sys
import pytest

p=argparse.ArgumentParser();p.add_argument('--adapter',type=Path,required=True);p.add_argument('--temp',type=Path,required=True)
a=p.parse_args();source=a.adapter.resolve()
package=ModuleType('plugins');package.__path__=[str(source.parent)];sys.modules['plugins']=package
name='plugins.MaiBot-SnowLuma-Adapter-main'
package=ModuleType(name);package.__path__=[str(source)];sys.modules[name]=package
raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','--basetemp='+str(a.temp.resolve()),str(source/'tests')]))
