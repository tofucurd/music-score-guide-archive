#!/usr/bin/env python3
"""Replay the final frozen guide; never recompile prose, engrave or realign."""
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = REPO / 'workspaces' / HERE.name


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def safe(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def restore():
    inventory = read(HERE / 'inventory.json')
    for row in inventory['files']:
        target = safe(WORK, row['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        source = safe(HERE, row['archive_path'])
        if row['compressed']:
            with gzip.open(source, 'rb') as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(source, target)
        if digest(target) != row['sha256']:
            raise ValueError('Snapshot differs: ' + row['path'])
    for row in inventory['shared_files']:
        source = safe(REPO, row['repository_path'])
        if digest(source) != row['sha256']:
            raise ValueError('Shared font differs: ' + row['repository_path'])
        target = safe(WORK, row['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    print(WORK)


def prepared_workspace():
    if not (WORK / 'output/production-04/queue/template.json').exists():
        raise SystemExit('Run restore first.')


def prepare_audio(external):
    prepared_workspace()
    sources = read(HERE / 'sources.json')
    row = next(r for r in sources['external_files'] if r['kind'] == 'audio')
    source = safe(external, row['path'])
    if digest(source) != row['sha256']:
        raise ValueError('This is not the archived recording/edition.')
    target = WORK / '.score-sync/m4/audio.wav'
    target.parent.mkdir(parents=True, exist_ok=True)
    command = list(sources['audio']['recipe']['argv'])
    command[command.index('-i') + 1] = str(source)
    command[-1] = str(target)
    subprocess.run(command, check=True, cwd=WORK)
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_streams', '-of', 'json', str(target)]))['streams'][0]
    count = int(Fraction(info['time_base']) * int(info['duration_ts']) * int(info['sample_rate']))
    if (int(info['sample_rate']), info['channels'], int(info.get('bits_per_sample', 0)), count) != (96000, 2, 24, 121351268):
        raise ValueError('Decoded PCM specifications differ from the frozen clock.')
    print(target)


def source_frame(bundle, payload, seconds, visual):
    # Exact final compiler policy; source clock is unchanged.
    frame = visual.frame_state(bundle, seconds)
    for row in payload.get('source_staff_visibility', []):
        a, z = row['from'], row['to']
        fade = row.get('fade', 4)
        u = max(0, min(1, (seconds-a+fade)/fade, (z+fade-seconds)/fade))
        weight = u*u*u*(10+u*(-15+6*u))
        frame['weights'][row['staff']] = max(frame['weights'].get(row['staff'], 0), weight)
    return frame


def render(workers):
    prepared_workspace()
    audio = WORK / '.score-sync/m4/audio.wav'
    if not audio.is_file():
        raise SystemExit('Run prepare-audio first.')
    sys.path[:0] = [str(WORK/'engine/scripts'), str(WORK/'research/02-linkage')]
    from score_sync import visual
    from connection_capacity import retain_routing_components
    template = read(WORK/'output/production-04/queue/template.json')
    template['audio'] = str(audio)
    # The final embedded font subset is already frozen; do not rebuild it.
    original_font_css = visual.font_css
    visual.font_css = lambda _: template['fonts']
    try:
        bundle = visual.bundle(read(WORK/'project-preview.json'), WORK/'research/shared-base/m4')
    finally:
        visual.font_css = original_font_css
    bundle['navigation_data'] = template['navigation_data']
    bundle['sections'] = template['sections']
    out = WORK/'output/reproduced'
    chunks, specs = out/'chunks', out/'specs'
    chunks.mkdir(parents=True, exist_ok=True)
    specs.mkdir(parents=True, exist_ok=True)
    settings = read(HERE/'environment.json')
    total, fps = settings['video']['frames'], settings['video']['fps']
    lock = threading.Lock()
    binding = hashlib.sha256((digest(HERE/'inventory.json')+digest(Path(__file__))).encode()).hexdigest()
    def one(start):
        count = min(1800, total-start)
        target = chunks/f'{start:09d}.mov'
        receipt = target.with_suffix('.json')
        if target.exists():
            if receipt.exists() and read(receipt) == {'snapshot': binding, 'start_frame': start, 'frames': count}:
                return target
            raise ValueError('Existing chunk has a different or missing snapshot receipt: '+str(target))
        with lock:
            spec = copy.deepcopy(template)
            payload = spec['guide_payload']
            retain_routing_components(payload, start/fps, min((start+count)/fps, bundle['duration']))
            spec['frames'] = [source_frame(bundle, payload, (start+i)/fps, visual) for i in range(count)]
            spec.update(start_seconds=start/fps, duration=count/fps, silent=True,
                        final=True, encoder='hevc_nvenc', movie_timescale=96000)
            scene = specs/f'{start:09d}.json'
            write(scene, spec)
            del spec
        partial = target.with_suffix('.partial.mov')
        subprocess.run(['node', str(WORK/'research/vertical-layout-03/render.mjs'),
                        '--spec', str(scene), '--output', str(partial), '--mode', 'video'],
                       check=True, cwd=WORK)
        partial.replace(target)
        write(receipt, {'snapshot': binding, 'start_frame': start, 'frames': count})
        scene.unlink()
        print('Completed', target.name, flush=True)
        return target
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rendered = list(pool.map(one, range(0, total, 1800)))
    listing = out/'concat.ffconcat'
    listing.write_text(''.join("file 'chunks/"+p.name+"'\n" for p in rendered))
    metadata = out/'chapters.ffmetadata'
    metadata.write_text(';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/96000\nSTART=0\nEND=121351268\ntitle=第四乐章　Adagio\n')
    final = out/'马勒第九交响曲第四乐章-导赏最终版-4K60.mov'
    partial = final.with_suffix('.partial.mov')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-threads', '2',
                    '-f', 'concat', '-safe', '0', '-i', str(listing), '-i', str(audio), '-i', str(metadata),
                    '-map', '0:v:0', '-map', '1:a:0', '-map_chapters', '2',
                    '-metadata:c:0', 'title=第四乐章　Adagio', '-c:v', 'copy', '-c:a', 'alac',
                    '-sample_fmt', 's32p', '-bits_per_raw_sample', '24', '-movflags', '+faststart', str(partial)],
                   check=True, cwd=WORK)
    partial.replace(final)
    (out/'B站章节.txt').write_text('00:00 第四乐章 Adagio\n')
    print(final)


def covers():
    prepared_workspace()
    output = WORK/'output/covers'
    output.mkdir(parents=True, exist_ok=True)
    for aspect in ('16x9', '4x3'):
        subprocess.run(['node', str(WORK/'research/covers-01/render.mjs'),
                        '--spec', str(WORK/f'research/covers-01/spec-{aspect}.json'),
                        '--output', str(output/f'马勒第九交响曲第四乐章-导赏封面-{aspect}.svg'),
                        '--mode', 'cover'], check=True, cwd=WORK)
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['restore', 'show-inputs', 'prepare-audio', 'render', 'covers'])
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 6), default=1)
    args = parser.parse_args()
    if args.action == 'show-inputs':
        print((HERE/'sources.json').read_text())
    elif args.action == 'restore':
        restore()
    elif args.action == 'prepare-audio':
        if args.sources is None:
            parser.error('--sources is required')
        prepare_audio(args.sources.resolve())
    elif args.action == 'render':
        render(args.workers)
    elif args.action == 'covers':
        covers()


if __name__ == '__main__':
    main()
