#!/usr/bin/env python3
"""Replay final frozen frames; never realign or re-engrave the archived work."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from fractions import Fraction
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = REPO / 'workspaces' / HERE.name


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def safe(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def restore():
    for row in read(HERE/'inventory.json')['files']:
        target = safe(WORK, row['path'])
        source = safe(HERE, row['archive_path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if row['compressed']:
            with gzip.open(source, 'rb') as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(source, target)
        if digest(target) != row['sha256']:
            raise ValueError('Archived input differs: '+row['path'])
    print(WORK)


def prepared():
    if not (WORK/'render/template.json').is_file():
        raise SystemExit('Run restore first.')


def prepare_audio(external):
    prepared()
    sources = read(HERE/'sources.json')
    row = next(r for r in sources['external_files'] if r['kind'] == 'audio')
    source = safe(external, row['path'])
    if digest(source) != row['sha256']:
        raise ValueError('Recording/edition differs from the frozen clock')
    out = WORK/'output'; out.mkdir(parents=True, exist_ok=True)
    target = out/'audio-with-lead-in.wav'; receipt = out/'audio-receipt.json'
    binding = digest(HERE/'sources.json')
    if target.exists():
        if receipt.exists() and read(receipt)['source_binding'] == binding and read(receipt)['sha256'] == digest(target):
            print(target); return
        raise ValueError('Existing audio has no matching receipt; preserve/move it before rebuilding')
    original = WORK/'.score-sync/m1/audio.wav'
    original.parent.mkdir(parents=True, exist_ok=True)
    command = list(sources['audio']['recipe']['argv'])
    command[command.index('-i')+1] = str(source); command[-1] = str(original)
    subprocess.run(command, check=True, cwd=WORK)
    spec = importlib.util.spec_from_file_location('archived_entrance', WORK/'render/entrance.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    lead = sources['lead_in']
    result = module.sampled_noise_prefix(original, target, duration_seconds=lead['duration_seconds'],
        seed_seconds=lead['seed_original_seconds'], crossfade_seconds=lead['loop_crossfade_seconds'],
        edge_fade_seconds=lead['edge_fade_seconds'], gain=lead['gain'])
    for key in ['sample_rate','channels','bits','prefix_samples','source_samples','output_samples','original_decoded_int32_sha256']:
        if result[key] != lead[key]:
            raise ValueError('Audio preparation differs: '+key)
    write(receipt, {'source_binding':binding, 'sha256':digest(target), 'pcm':result})
    print(target)


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_chapters','-of','json',str(path)]))


def render(workers):
    prepared()
    audio = WORK/'output/audio-with-lead-in.wav'
    audio_receipt = WORK/'output/audio-receipt.json'
    if not audio.exists() or not audio_receipt.exists():
        raise SystemExit('Run prepare-audio with the external recording first.')
    if read(audio_receipt)['sha256'] != digest(audio):
        raise ValueError('Prepared audio changed')
    template = read(WORK/'render/template.json')
    jobs = read(WORK/'render/chunks.json')
    environment = read(HERE/'environment.json')
    total, fps = environment['video']['frames'], environment['video']['fps']
    out = WORK/'output/reproduced'; chunks = out/'chunks'; specs = out/'specs'
    for directory in (out,chunks,specs): directory.mkdir(parents=True, exist_ok=True)
    # Bind resumed chunks to actual restored render inputs, not just a revision label.
    inputs = [WORK/'render/template.json', WORK/'render/frames.jsonl', WORK/'render/chunks.json',
              WORK/'render/video.mjs', *sorted((WORK/'render/layers').glob('*.mjs')), Path(__file__)]
    binding = hashlib.sha256(''.join(digest(p) for p in inputs).encode()).hexdigest()
    final = out/'Beethoven-Grosse-Fuge-Op133-4K60.mov'
    if final.exists():
        raise ValueError('Final already exists; preserve it before making another version')

    def one(row, frames):
        target = chunks/(row['id']+'.mov'); receipt = target.with_suffix('.json')
        if target.exists():
            r = read(receipt) if receipt.exists() else {}
            if (r.get('binding') == binding and r.get('frames') == row['frames']
                    and r.get('sha256') == digest(target)):
                return target
            raise ValueError('Existing chunk has no matching snapshot receipt: '+row['id'])
        scene = specs/(row['id']+'.json')
        spec = {**template, 'frames':frames, 'start_seconds':row['start_frame']/fps,
                'duration':row['frames']/fps, 'silent':True, 'final':True, 'encoder':'hevc_nvenc'}
        write(scene, spec)
        partial = target.with_suffix('.partial.mov')
        subprocess.run(['node',str(WORK/'render/video.mjs'),'--spec',str(scene),
                        '--output',str(partial),'--mode','video'],check=True,cwd=WORK)
        info = probe(partial)
        v = next(s for s in info['streams'] if s['codec_type']=='video')
        if (v['width'],v['height'],v['codec_name'],v['pix_fmt'],int(v['nb_frames'])) != (3840,2160,'hevc','yuv444p10le',row['frames']):
            raise ValueError('Rendered chunk format/frame count differs')
        partial.replace(target)
        write(receipt, {'binding':binding,'frames':row['frames'],'sha256':digest(target)})
        scene.unlink()
        print('Completed',row['id'],flush=True)
        return target

    # Only active workers have temporary full scenes; completed scene JSON is removed.
    # The frame stream is read once, so absolute animation states never restart per chunk.
    count = 0; active = set(); last_launch = 0.
    with (WORK/'render/frames.jsonl').open() as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        for row in jobs:
            while len(active) >= workers:
                done, active = wait(active, return_when=FIRST_COMPLETED)
                for future in done: future.result()
            if shutil.disk_usage(WORK).free < 4*2**30:
                raise RuntimeError('Keep at least 4 GiB disk free for active chunks and final mux')
            # On Linux, wait for current workers if memory falls below the original admission floor.
            meminfo = Path('/proc/meminfo')
            while active and meminfo.exists():
                available = next(int(line.split()[1])*1024 for line in meminfo.read_text().splitlines() if line.startswith('MemAvailable:'))
                if available >= 6*2**30: break
                done, active = wait(active, timeout=2, return_when=FIRST_COMPLETED)
                for future in done: future.result()
            pause = 2-(time.monotonic()-last_launch)
            if active and pause > 0: time.sleep(pause)
            frames = [json.loads(next(stream)) for _ in range(row['frames'])]
            if row['start_frame'] != count: raise ValueError('Non-contiguous frozen frame stream')
            count += len(frames)
            active.add(pool.submit(one,row,frames)); last_launch=time.monotonic()
        for future in active: future.result()
        if count != total or stream.read().strip():
            raise ValueError('Frozen frame count differs')
    listing = out/'concat.ffconcat'
    listing.write_text(''.join("file 'chunks/"+row['id']+".mov'\n" for row in jobs))
    rate, samples = environment['audio']['sample_rate'], environment['audio']['samples']
    metadata = out/'chapters.ffmetadata'
    metadata.write_text(f';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/{rate}\nSTART=0\nEND={samples}\ntitle=大赋格 Op.133\n')
    partial = final.with_suffix('.partial.mov')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-threads','2','-f','concat','-safe','0',
        '-i',str(listing),'-i',str(audio),'-i',str(metadata),'-map','0:v:0','-map','1:a:0','-map_chapters','2',
        '-c:v','copy','-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24','-movflags','+faststart',str(partial)],check=True,cwd=WORK)
    info=probe(partial);v=next(s for s in info['streams'] if s['codec_type']=='video');a=next(s for s in info['streams'] if s['codec_type']=='audio')
    if int(v['nb_frames']) != total or int(a['duration_ts'])*Fraction(a['time_base']) != Fraction(samples,rate):
        raise ValueError('Final frame/sample counts differ')
    partial.replace(final)
    write(out/'delivery-receipt.json',{'binding':binding,'frames':total,'audio_samples':samples,'bytes':final.stat().st_size})
    (out/'B站章节.txt').write_text('00:00 大赋格 Op.133\n')
    print(final)


def covers():
    prepared()
    out = WORK/'output/covers'; out.mkdir(parents=True,exist_ok=True)
    for aspect in ('16x9','4x3'):
        target=out/f'cover-{aspect}.svg'
        if target.exists(): raise ValueError('Cover already exists; preserve it before making another version')
        subprocess.run(['node',str(WORK/'render/cover.mjs'),'--spec',str(WORK/f'render/cover-{aspect}.json'),
                        '--output',str(target),'--mode','cover'],check=True,cwd=WORK)
    print(out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['restore','show-inputs','prepare-audio','render','covers'])
    parser.add_argument('--sources',type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,8),default=1)
    args=parser.parse_args()
    if args.action=='show-inputs':print((HERE/'sources.json').read_text())
    elif args.action=='restore':restore()
    elif args.action=='prepare-audio':
        if args.sources is None:parser.error('--sources is required')
        prepare_audio(args.sources.resolve())
    elif args.action=='render':render(args.workers)
    elif args.action=='covers':covers()


if __name__=='__main__': main()
