"""Build the full combination, behavior only, or sleep only into a new directory."""
from pathlib import Path
import argparse
from assembly import CONTROL, PROFILES, assemble, build_pair, git, hashes, normalize

# Used by the workspace delivery tool.
def build(source, kind, target):
    return assemble(source, kind, target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-source', type=Path, required=True)
    parser.add_argument('--adapter-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=PROFILES, default='full')
    args = parser.parse_args()
    result = build_pair(args.host_source, args.adapter_source, args.output, profile=args.profile)
    for kind, files in result['files'].items():
        print(f'{kind}/{args.profile}: {len(files)} files verified')

if __name__ == '__main__':
    main()
