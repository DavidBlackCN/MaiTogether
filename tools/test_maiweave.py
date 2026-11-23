"""Run original upstream contract and sharing tests without external connections."""
from pathlib import Path
import argparse
from community_source import verify_reviewed
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    verify_reviewed(source, 'MaiWeave')
    output.mkdir(parents=True, exist_ok=False)
    def audit(event, values):
        if event == 'socket.connect' and (not isinstance(values[1], tuple)
                or values[1][0] not in ('127.0.0.1', '::1')):
            raise PermissionError('EXTERNAL_NETWORK_DENIED')
    sys.addaudithook(audit)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).parent))
    import pytest
    names = ('test_life_status.py', 'test_nap_quiet.py', 'test_sleep_policy.py',
             'test_webui.py', 'test_reading_rhythm.py', 'test_qzone.py',
             'test_farewell.py', 'test_private_wake.py', 'test_chat_schedule.py',
             'test_proactive_modes.py', 'test_proactive_followup.py', 'test_plugin.py')
    return pytest.main([
        *[str(source / 'tests' / name) for name in names], '-q',
        '-p', 'no:cacheprovider', '-o', 'asyncio_mode=auto',
        '-o', 'asyncio_default_fixture_loop_scope=function',
        '--basetemp=' + str(output / 'tmp'), '--junitxml=' + str(output / 'results.xml')])


if __name__ == '__main__':
    raise SystemExit(main())
