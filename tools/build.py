"""Build unified outbound control into a new directory."""
from pathlib import Path
import argparse
from assembly import CONTROL, assemble, build_pair, git, hashes, normalize

# Used by the workspace delivery tool.
def build(source, kind, target):
    return assemble(source, kind, target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-source', type=Path, required=True)
    parser.add_argument('--adapter-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build_pair(args.host_source, args.adapter_source, args.output)
    for kind, files in result['files'].items():
        print(f'{kind}: {len(files)} files verified')

if __name__ == '__main__':
    main()
