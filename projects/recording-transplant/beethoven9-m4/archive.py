"""Rebuild the released Beethoven IX finale tempo transplant."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT = Path(__file__).resolve().parent
WORK = PROJECT.parents[2] / 'workspaces' / 'recording-transplant' / PROJECT.name
CODE = PROJECT / 'code'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['show-inputs', 'restore', 'prepare-audio', 'refit', 'render', 'covers'])
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 8), default=5)
    args = parser.parse_args()
    if args.action == 'show-inputs':
        print((PROJECT / 'sources.json').read_text(), end='')
        return
    WORK.mkdir(parents=True, exist_ok=True)
    if args.action == 'restore':
        print(WORK)
        return
    if args.action == 'prepare-audio':
        if args.sources is None:
            parser.error('prepare-audio requires --sources')
        command = [CODE / 'prepare_audio.py', '--sources', args.sources.resolve(), '--out', WORK / 'audio']
    elif args.action == 'refit':
        command = [PROJECT / 'clock' / 'fit.py', '--out', WORK / 'refit']
    elif args.action == 'covers':
        command = [CODE / 'cover.py']
    else:
        if not (WORK / 'audio' / 'receipt.json').is_file():
            parser.error('Run prepare-audio before render')
        command = [CODE / 'finish_tempo_video.py']
    subprocess.run([sys.executable, *command], cwd=WORK, check=True,
                   env={**os.environ, 'TEMPO_WORKERS': str(args.workers)})


if __name__ == '__main__':
    main()
