"""Encode the approved whole-movement view and mux the unaltered 02 master."""
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
import hashlib
import json
from math import ceil
import os
from pathlib import Path
import subprocess

import av
import cairo
import numpy as np

import tempo_video as scene

OUT=scene.OUT
MASTER=scene.AUDIO/'transplant.flac'
TITLE='贝多芬第九交响曲第一乐章速度移植'
FFMPEG=os.environ.get('FFMPEG','ffmpeg')


def prepare():
    global base, live, source, converter, bars, seconds, curves, nav, cover, cache
    _,bars,seconds,curves,nav=scene.load()
    base=scene.img_chart(bars,curves)
    cover=scene.poster(bars,curves)
    live=cairo.ImageSurface(cairo.FORMAT_RGB24,scene.WIDTH,scene.HEIGHT)
    source=av.VideoFrame.from_numpy_buffer(
        np.frombuffer(live.get_data(),dtype=np.uint8).reshape(scene.HEIGHT,scene.WIDTH,4),format='bgra')
    converter=av.video.reformatter.VideoReformatter()
    cache={}


def yuv(frame):
    return converter.reformat(frame,format='yuv420p',dst_colorspace='ITU709',
                              src_color_range='JPEG',dst_color_range='MPEG')


def encode(job):
    start,end,dest=job
    if start < 0 and not (OUT/'海报.png').exists():
        still_path = OUT/'海报.part.png'
        cover.write_to_png(str(still_path))
        still_path.replace(OUT/'海报.png')
    if dest.exists():
        return
    tmp=dest.with_suffix('.part.mp4')
    with av.open(str(tmp),'w') as out:
        stream=out.add_stream('libx264',rate=scene.FPS)
        stream.width,stream.height=scene.WIDTH,scene.HEIGHT
        stream.pix_fmt='yuv420p'
        stream.codec_context.thread_count=3
        stream.options={'preset':'ultrafast','crf':'15','x264-params':'keyint=120:min-keyint=120:scenecut=0:colorprim=bt709:transfer=bt709:colormatrix=bt709'}
        if start<0:
            surface=np.frombuffer(cover.get_data(),dtype=np.uint8).reshape(scene.HEIGHT,scene.WIDTH,4)
            still=yuv(av.VideoFrame.from_numpy_buffer(surface,format='bgra'))
        for n in range(start,end):
            if start<0:
                video=still
            else:
                scene.frame(base,live,nav,bars,seconds,curves,scene.DOMAIN,n/scene.FPS,cache)
                video=yuv(source)
            video.pts=n-start
            video.time_base=Fraction(1,scene.FPS)
            for packet in stream.encode(video):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    tmp.replace(dest)
    print(dest.name,flush=True)


def main():
    receipt=json.loads((scene.DATA/'receipt.json').read_text())
    digest=hashlib.sha256()
    for p in [Path(__file__),Path(scene.__file__),scene.DATA/'receipt.json',scene.DATA/'reference.csv',
              scene.DATA/'learned-beat-fingerprints.csv',scene.DATA/'structure.json']:
        digest.update(p.read_bytes())
    for name in ('SourceHanSerifSC-Regular.otf','SourceHanSerifSC-Light.otf'):
        digest.update((scene.FONT/name).read_bytes())
    digest.update((scene.VENDOR/'scripts/score_sync/navigation.py').read_bytes())
    work=scene.TMP/('full-'+digest.hexdigest()[:14])
    work.mkdir(exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    frames=ceil(receipt['frames']*scene.FPS/scene.RATE)
    lead=scene.POSTER_SECONDS*scene.FPS
    chunk=20*scene.FPS
    jobs=[(-lead,0,work/'0000.mp4')]+[(i,min(i+chunk,frames),work/f'{n:04}.mp4')
         for n,i in enumerate(range(0,frames,chunk),start=1)]
    with ProcessPoolExecutor(max_workers=int(os.environ.get("TEMPO_WORKERS", "5")),initializer=prepare) as pool:
        list(pool.map(encode,jobs))
    index=work/'join.txt'
    # Specify cumulative duration on a microsecond clock. The concat demuxer's
    # millisecond MP4 duration rounding must never accumulate at music boundaries.
    cumulative=0
    records=[]
    for a,b,p in jobs:
        limit=cumulative+(b-a)
        us=round(limit*1_000_000/scene.FPS)-round(cumulative*1_000_000/scene.FPS)
        records.extend([f"file '{p.name}'",f'duration {us/1_000_000:.6f}'])
        cumulative=limit
    index.write_text('\n'.join(records)+'\n')
    draft=work/'joined.mov'
    subprocess.run([str(FFMPEG),'-v','error','-y','-f','concat','-safe','0','-i',str(index),'-i',str(MASTER),
        '-map','0:v:0','-map','1:a:0','-c:v','copy','-af',f'adelay={scene.POSTER_SECONDS*scene.RATE}S:all=1',
        '-c:a','alac','-sample_fmt','s32p','-video_track_timescale','60000','-metadata','title='+TITLE,
        '-movflags','+faststart',str(draft)],check=True)
    draft.replace(OUT/(TITLE+'.mov'))
    print(TITLE,frames+lead,'frames',flush=True)


if __name__=='__main__':
    main()
