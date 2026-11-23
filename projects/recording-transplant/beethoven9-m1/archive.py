"""Rebuild the released Beethoven IX/I tempo transplant from its original recordings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parent
WORK = PROJECT.parents[2] / 'workspaces/recording-transplant/beethoven9-m1'
CODE = PROJECT / 'code'
DATA = PROJECT / 'data'


def read(path):
    return json.loads(path.read_text())


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def recordings(directory):
    paths = {}
    for entry in read(PROJECT / 'sources.json')['external_files']:
        path = directory.resolve() / entry['path']
        if not path.is_file() or sha256(path) != entry['sha256']:
            raise SystemExit(f"Missing or different {entry['role']} recording: {path}")
        paths[entry['role']] = path
    return paths


def prepare_audio(sources):
    dest = WORK / 'audio'
    frozen = read(DATA / 'receipt.json')
    if not dest.exists():
        with tempfile.TemporaryDirectory(dir=WORK) as stage:
            out = Path(stage) / 'audio'
            subprocess.run([
                sys.executable, str(CODE / 'export_one_shot.py'),
                '--source', str(sources['donor']), '--reference', str(sources['reference']),
                '--source-sha256', frozen['source_sha256'], '--clock', str(DATA / 'command.csv'),
                '--out', str(out)
            ], check=True)
            if sha256(out / 'engine-keyframes.txt') != frozen['engine_map_sha256']:
                raise ValueError('Engine keyframes differ from the release')
            out.rename(dest)
    master = dest / 'transplant.flac'
    actual = sha256(master)
    if actual != read(dest / 'receipt.json')['sha256']:
        raise ValueError('Local master does not match the generated receipt')
    if actual == frozen['sha256']:
        print('Rebuilt master matches the released FLAC.')
    else:
        command = [os.environ.get('FFMPEG', 'ffmpeg'), '-v', 'error', '-i', str(master),
                   '-map', '0:a:0', '-f', 's24le', '-c:a', 'pcm_s24le', '-']
        with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
            checksum = hashlib.file_digest(proc.stdout, 'sha256').hexdigest()
            if proc.wait():
                raise RuntimeError('Could not decode the rebuilt master')
        if checksum == read(DATA / 'release.json')['pcm_s24le_sha256']:
            print('Decoded PCM matches the released master.')
        else:
            print('PCM differs from the release. Compare the Rubber Band build and numerical environment.', file=sys.stderr)
    print(master)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['show-inputs','restore','prepare-audio','refit','render','covers'])
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 8), default=5)
    args = parser.parse_args()
    if args.action == 'show-inputs':
        print((PROJECT / 'sources.json').read_text())
        return
    WORK.mkdir(parents=True, exist_ok=True)
    if args.action == 'restore':
        print(WORK)
    elif args.action in ('prepare-audio','refit'):
        if args.sources is None:
            parser.error('This action requires --sources')
        files = recordings(args.sources)
        if args.action == 'prepare-audio':
            prepare_audio(files)
        else:
            subprocess.run([sys.executable, str(PROJECT / 'clock/fit.py'),
                            '--source', str(files['donor']), '--reference', str(files['reference']),
                            '--initial', str(DATA / 'initial.csv'), '--out', str(WORK / 'refit')], check=True)
    elif args.action == 'covers':
        subprocess.run([sys.executable, str(CODE / 'cover.py')], cwd=WORK, check=True)
    else:
        if not (WORK / 'audio/receipt.json').is_file():
            parser.error('Run prepare-audio before render')
        subprocess.run([sys.executable, str(CODE / 'finish_tempo_video.py')], cwd=WORK,
                       env={**os.environ, 'TEMPO_WORKERS': str(args.workers)}, check=True)


if __name__ == '__main__':
    main()
