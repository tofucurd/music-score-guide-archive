"""Final full-movement tempo charts, poster and two-level navigation."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from xml.sax.saxutils import escape

import cairo
import gi
import numpy as np

gi.require_version('Rsvg','2.0')
from gi.repository import Rsvg

PROJECT=Path(__file__).resolve().parents[1]
ROOT=Path.cwd()
DATA=PROJECT/'data'
AUDIO=ROOT/'audio'
OUT=ROOT/'output/定稿'
TMP=ROOT/'tmp'
TMP.mkdir(exist_ok=True)
os.environ['TMPDIR']=str(TMP)
VENDOR=PROJECT.parents[2]/'vendor/score-sync-video'
FONT=TMP/'video-fonts'
FONT.mkdir(exist_ok=True)
for name in ('SourceHanSerifSC-Light.otf','SourceHanSerifSC-Regular.otf'):
    link = FONT/name
    try:
        link.symlink_to(VENDOR/'assets/fonts'/name)
    except FileExistsError:
        if link.resolve() != (VENDOR/'assets/fonts'/name).resolve():
            raise ValueError(f'Unexpected font at {link}')
conf=TMP/'fonts.conf'
contents=f'<fontconfig><include>/etc/fonts/fonts.conf</include><dir>{escape(str(FONT))}</dir><cachedir>{escape(str(TMP))}/font-cache</cachedir></fontconfig>'
if not conf.exists() or conf.read_text()!=contents:
    private=conf.with_name(f'fonts-{os.getpid()}.conf')
    private.write_text(contents)
    private.replace(conf)
os.environ['FONTCONFIG_FILE']=str(conf)
sys.path.insert(0,str(VENDOR/'scripts/score_sync'))
from navigation import build_navigation, navigation_states, render_navigation

PAPER='#faf8f1'
INK='#253c41'
SOFT='#59696b'
GRID='#dad9cf'
BLUE='#277d9f'
TEAL='#146658'
OCHRE='#986112'
RED='#b33344'
FONT_NAME='Source Han Serif SC'
SETTINGS = json.loads((DATA / 'video-settings.json').read_text())
MOVEMENT = SETTINGS['movement']
LABEL = SETTINGS['label']
ABS_TICKS = SETTINGS['absolute_ticks']
REL_TICKS = SETTINGS['relative_ticks']
BAR_TICKS = SETTINGS['bar_ticks']
LAST_BAR = SETTINGS['last_bar']
WINDOW_LABEL = SETTINGS['window_label']
WIDTH,HEIGHT,FPS,RATE=3840,2160,60,44100
SCALE=WIDTH/1920
L,R=135,1847
BOXES=((243,501,ABS_TICKS[0],ABS_TICKS[-1]),(616,802,REL_TICKS[0],REL_TICKS[-1]))
SEC_TITLE=(204,574)
DOMAIN = tuple(SETTINGS['domain'])
POSTER_SECONDS=3
TRACK_NAMES=('富特文格勒','滕斯泰特','移植')
POSTER_COPY=(
    ('由于主播前面做了几期曲谱同步的视频，开发了对齐乐谱的工具，于是便有了一个整活的想法。',
     '既然主播都能做曲谱同步了，那么每份演绎的速度，主播也就掌握了。'),
    ('那么能否通过这样的速度匹配，让一份录音直接匹配到另外一份演绎的速度上去？',
     '这样子尤其可以应用在历史录音上面，虽然说这不能叫历史录音修复。'),
    ('所以主播就抱着整活的想法，把滕斯泰特 1992 年的贝九演绎，直接调到了富特文格勒 1942 年',
     '著名的“旋律贝九”的速度上。因为即使是 Pristine 修复的“旋律贝九”，它的音质依然非常渣，',
     '几乎是不可能日常听的状态。'),
    ('再次声明，本视频仅供整活娱乐，无任何意义，无任何实际价值，不要上纲上线，谢谢。',),
)


def text(x,y,value,size=24,color=INK,anchor='start',extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" {extra}>{escape(str(value))}</text>'


def line(x1,y1,x2,y2,color,weight=1,dash=''):
    dash=f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{color}" stroke-width="{weight}"{dash}/>'


def svg_surface(fragment,view,width,height):
    doc=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{view}" font-family="{FONT_NAME}">{fragment}</svg>'
    handle=Rsvg.Handle.new_from_data(doc.encode())
    canvas=cairo.ImageSurface(cairo.FORMAT_RGB24,width,height)
    box=Rsvg.Rectangle();box.x=0.;box.y=0.;box.height=height;box.width=width
    handle.render_document(cairo.Context(canvas),box)
    return canvas


def load():
    read=lambda name:np.genfromtxt(DATA/name,delimiter=',',names=True,dtype=None,encoding='utf8')
    ref=read('reference.csv')
    obs=read('learned-beat-fingerprints.csv')
    q=ref['q']
    if not np.array_equal(q,obs['q']):raise ValueError('The three tracks must use identical score positions')
    seconds=np.array([ref['reference_s'],obs['original_donor_s'],obs['measured_render_s']])
    if np.any(np.diff(seconds,axis=1)<=0):raise ValueError('Beat readings must be strictly ordered')
    receipt=json.loads((DATA/'receipt.json').read_text())
    prepared = json.loads((AUDIO / 'receipt.json').read_text())
    if not (prepared['expected_sha256'] == receipt['sha256'] == SETTINGS['master']
            and prepared['samplerate'] == receipt['samplerate'] == RATE
            and prepared['frames'] == receipt['frames'] and prepared['channels'] == 2
            and prepared['label'] == receipt['label'] == LABEL):
        raise ValueError('The prepared audio does not belong to this edition')
    with (AUDIO / 'transplant.flac').open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != prepared['sha256']:
            raise ValueError('Master audio does not match its preparation receipt')
    # Slide a centred four-quarter window inward at the boundaries, retaining
    # the full width and using exactly the same score endpoints on all tracks.
    lo=np.clip(q-2,q[0],q[-1]-4)
    bpm=np.array([240/(np.interp(lo+4,q,s)-np.interp(lo,q,s)) for s in seconds])
    curves=np.stack([bpm,bpm-bpm[0]])
    for series,(_,_,low,high) in zip(curves,BOXES):
        if series.min()<low or series.max()>high:raise ValueError(f'Clipped axis: {series.min()} {series.max()}')
    nav=build_navigation(json.loads((DATA/'structure.json').read_text())['sections'],
                         lambda x:np.interp(x,q,seconds[2]),receipt['frames'],RATE)
    return q,obs['bar'],seconds,curves,nav


def curve(x,y,color,weight,dash=''):
    points=' '.join(f'{u:.2f},{v:.2f}' for u,v in zip(x,y))
    pattern=f' stroke-dasharray="{dash}"' if dash else ''
    return f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{weight}" stroke-linecap="round" stroke-linejoin="round"{pattern}/>'


def abscissa(bar,domain):
    return L+(R-L)*(bar-domain[0])/(domain[1]-domain[0])


def ordinate(value,box):
    top,bottom,low,high=box
    return bottom-(value-low)/(high-low)*(bottom-top)


def img_chart(bars,curves):
    out=[f'<rect width="1920" height="1080" fill="{PAPER}"/>',
         text(74,77,'贝多芬　第九交响曲　'+MOVEMENT,47),
         line(74,104,1847,104,'#b8bdb4',1)]
    for name,x,color,width,dash in zip(TRACK_NAMES,(74,500,935),(TEAL,OCHRE,RED),(5,3,3.2),('','','8 6')):
        out.extend([line(x,142,x+49,142,color,width,dash),text(x+61,150,name,25)])
    for k,(box,ticks) in enumerate(zip(BOXES,(ABS_TICKS,REL_TICKS))):
        top,bottom,low,high=box
        out.extend([text(74,SEC_TITLE[k],'绝对速度' if not k else '相对速度',36),
                    text(257,SEC_TITLE[k],'四分音符 / 分钟（BPM）' if not k else
                         '与富特文格勒之差（Δ BPM）　正值较快，负值较慢',22,SOFT)])
        for v in ticks:
            y=ordinate(v,box)
            out.extend([line(L,y,R,y,GRID,1.2),text(L-19,y+7,f'{v:+}' if k and v else v,22,SOFT,'end')])
        for n in BAR_TICKS:
            x=abscissa(n,DOMAIN)
            out.append(line(x,top,x,bottom,'#e5e4dc',1,'3 6'))
            if k:out.append(text(x,837,str(n),22,SOFT,'middle'))
        x=abscissa(bars,DOMAIN)
        for index,col,w,dash in [(1,OCHRE,3,''),(0,TEAL,5.2,''),(2,RED,3,'8 5')]:
            out.append(curve(x,ordinate(curves[k,index],box),col,w,dash))
    out.extend([text(L,880,'小节',22,SOFT),text(R,880,WINDOW_LABEL,21,SOFT,'end'),
                line(74,906,1847,906,'#b8bdb4',1)])
    return svg_surface(''.join(out),'0 0 1920 1080',WIDTH,HEIGHT)


def poster(bars,curves):
    out=[f'<rect width="1920" height="1080" fill="{PAPER}"/>',
         text(110,70,'LUDWIG VAN BEETHOVEN',21,SOFT,extra='letter-spacing="4"'),
         text(104,173,'贝多芬',76,'#262924'),text(102,290,'第九交响曲',103,'#262924'),
         text(109,386,'速度移植',60,'#287D9F'),text(490,358,MOVEMENT,32,INK),
         text(490,397,LABEL,24,SOFT),
         text(1495,104,'SYMPHONY',20,'#287D9F','middle','letter-spacing="4"'),
         text(1495,350,'IX',270,'#287D9F','middle','font-weight="300"')]
    y=473
    for paragraph in POSTER_COPY:
        for row in paragraph:
            out.append(text(110,y,row,31,INK))
            y+=44
        y+=22
    x=110+(bars-bars[0])/(bars[-1]-bars[0])*1698
    for i,col,w,d in [(1,OCHRE,2,''),(0,TEAL,2.6,''),(2,RED,1.9,'6 4')]:
        out.append(curve(x,974-(curves[0,i]-ABS_TICKS[0])*(63.7/(ABS_TICKS[-1]-ABS_TICKS[0])),col,w,d))
    out.extend([line(110,993,1808,993,'#CBCBC1',1),
                text(110,1036,'WILHELM FURTWÄNGLER   /   1942',18,SOFT,extra='letter-spacing="2"'),
                text(1808,1036,'KLAUS TENNSTEDT   /   1992',18,SOFT,'end','letter-spacing="2"')])
    return svg_surface(''.join(out),'0 0 1920 1080',WIDTH,HEIGHT)


def rgb(c):
    return tuple(int(c[i:i+2],16)/255 for i in (1,3,5))


def dynamic_text(ctx,x,y,s,size,color,align='right'):
    ctx.select_font_face(FONT_NAME,cairo.FONT_SLANT_NORMAL,cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    width=ctx.text_extents(s).x_advance
    ctx.set_source_rgb(*rgb(color));ctx.move_to(x-width if align=='right' else x,y);ctx.show_text(s)


def nav_surface(rows):
    layers=[dict(r,ticks=[]) for r in rows]
    return svg_surface(render_navigation(layers),'0 1834 3840 326',WIDTH,326)


def frame(base,surface,nav,bars,seconds,curves,domain,t,cache):
    ctx=cairo.Context(surface);ctx.set_source_surface(base);ctx.paint()
    sample=round(t*RATE)
    bar=np.interp(t,seconds[2],bars)
    x=abscissa(bar,domain)
    ctx.save();ctx.scale(SCALE,SCALE)
    dynamic_text(ctx,1847,76,f'第 {min(LAST_BAR,int(bar))} 小节　　{int(t)//60:02d}:{int(t)%60:02d}',34,INK)
    for k,box in enumerate(BOXES):
        vals=[np.interp(bar,bars,seq) for seq in curves[k]]
        for col,v,name,stop in zip((TEAL,OCHRE,RED),vals,TRACK_NAMES,(1395,1640,1847)):
            if abs(v)<.05:v=0.
            n=f'{v:+.1f}' if k and v else f'{v:.1f}'
            dynamic_text(ctx,stop,SEC_TITLE[k],f'{name}  {n}',24,col)
        if t>=seconds[2,0]:
            top,bottom,_,_=box
            for stroke,w in [(PAPER,4.1),(BLUE,1.9)]:
                ctx.set_source_rgb(*rgb(stroke));ctx.set_line_width(w)
                ctx.move_to(x,top-3);ctx.line_to(x,bottom+3);ctx.stroke()
            for idx,radius in [(0,5.4),(1,4.5),(2,3.1)]:
                ctx.set_source_rgb(*rgb((TEAL,OCHRE,RED)[idx]));ctx.arc(x,ordinate(vals[idx],box),radius,0,math.tau);ctx.fill()
    ctx.restore()
    rows=navigation_states(nav,sample,window=round(.6*RATE))
    key=tuple((layer['active']['id'],round(layer['alpha'],6)) for row in rows for layer in row['layers'])
    if cache.get('key')!=key:
        cache.update(key=key,img=nav_surface(rows))
    ctx.set_source_surface(cache['img'],0,1834);ctx.paint()
    for j,row in enumerate(rows):
        y=(1848,2000)[j]+102
        for tick in row['ticks']:
            pos=144+3552*tick['progress'];ctx.set_source_rgba(*rgb(BLUE),tick['alpha'])
            ctx.set_line_width(6);ctx.move_to(pos,y-15);ctx.line_to(pos,y+25);ctx.stroke()
    surface.flush()
