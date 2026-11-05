"""Run adaptation and selected upstream tests with external connections blocked."""
from pathlib import Path
import argparse
import importlib.util
import os
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Assembled MaiWork source, including upstream tests')
    parser.add_argument('--output',type=Path,required=True,help='New evidence directory outside the repository')
    args=parser.parse_args()
    source=args.source.resolve();output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    def audit(event,values):
        if event=='socket.connect' and (not isinstance(values[1],tuple) or values[1][0] not in ('127.0.0.1','::1')):
            raise PermissionError('EXTERNAL_NETWORK_DENIED')
    sys.addaudithook(audit);sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('CharTyr_MaiWork',source/'__init__.py',submodule_search_locations=[str(source)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    sys.path.insert(0,str(source/'tests'))
    import pytest
    names=['test_outbox.py','test_outbox_concurrency_release.py','test_approvals.py',
           'test_group_approval_failclosed.py','test_skill_allowed_tools.py','test_store_historical_migrations.py']
    options=[str(Path(__file__).with_name('test_integration.py')),*[str(source/'tests'/name) for name in names],
             '-q','-p','no:cacheprovider','-o','asyncio_default_fixture_loop_scope=function',
             '--basetemp='+str(output/'tmp'),'--junitxml='+str(output/'results.xml')]
    if os.name=='nt':
        # Creating symlinks requires Windows developer mode or a separate privilege.
        options+=['-k','not test_deliver_task_rejects_symlink_pointing_outside']
    return pytest.main(options)


if __name__=='__main__':raise SystemExit(main())
