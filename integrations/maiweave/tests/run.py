"""Run the adaptation and affected upstream tests without external connections."""
from pathlib import Path
import argparse
import importlib.util
import os
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    spec = importlib.util.spec_from_file_location('weave_build', Path(__file__).parents[1] / 'build.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    build.verify(source)
    output.mkdir(parents=True, exist_ok=False)
    def audit(event, values):
        if event == 'socket.connect' and (not isinstance(values[1], tuple)
                or values[1][0] not in ('127.0.0.1', '::1')):
            raise PermissionError('EXTERNAL_NETWORK_DENIED')
    sys.addaudithook(audit)
    sys.dont_write_bytecode = True
    os.environ['MAIWEAVE_SOURCE'] = str(source)
    sys.path.insert(0, str(Path(__file__).parent))
    import pytest
    names = ('test_life_status.py', 'test_nap_quiet.py', 'test_sleep_policy.py',
             'test_webui.py', 'test_reading_rhythm.py')
    return pytest.main([str(Path(__file__).with_name('test_integration.py')),
        *[str(source / 'tests' / name) for name in names], '-q', '-p', 'upstream_fixture',
        '-p', 'no:cacheprovider', '-o', 'asyncio_mode=auto',
        '-o', 'asyncio_default_fixture_loop_scope=function',
        '--basetemp=' + str(output / 'tmp'), '--junitxml=' + str(output / 'results.xml')])


if __name__ == '__main__':
    raise SystemExit(main())
