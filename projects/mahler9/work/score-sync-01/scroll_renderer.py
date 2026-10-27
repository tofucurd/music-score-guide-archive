"""Fixed blue reading position, native score scrolling beneath it."""
from pathlib import Path
from bisect import bisect_right
import json, math, hashlib, argparse, subprocess, shutil, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import PchipInterpolator
from prepare_data import W,R,load,dump
from core import interval_index, interpolate, source_sample

BG='#faf8f1';BLUE='#287d9f';INK='#263c41';MUTED='#827e72'
WIDTH=3840;HEIGHT=2160;LEFT=380;RIGHT=3730;CURSOR=1344
FONT=R/'work/revision-04/assets/fonts/source-han-official-01/SourceHanSerifSC-Regular.otf'
LABELS={'1.Violine':'第一小提琴','Bassoon':'巴松','Baßklarinette in B':'降B调低音单簧管',
        'Englischhorn':'英国管','Fagott':'巴松','Glsp.':'钟琴','Horn in F':'F调圆号',
        'K.-Fag':'低音巴松','Kl. Tr.':'小鼓','Klar. in Es':'降E调单簧管',
        'Klarinette in A':'A调单簧管','Klarinette in B':'降B调单簧管','Kontra-Fagott':'低音巴松',
        'Posaune':'长号','Trompete in F':'F调小号','Trp. in B':'降B调小号',
        'Violins':'小提琴','Violoncellos':'大提琴','Vl.Solo':'独奏小提琴',
        '三枚 低音钟 Glocken':'三枚低音钟','低音单簧管 降B调 in B':'降B调低音单簧管'}

def clock_curve(clock, axis):
    """Smooth only between measured/shared anchors, preserving each anchor."""
    qa,qb=axis[0][0],axis[-1][0]
    knots={int(s):interpolate(axis,q) for s,q in clock if qa<=q<=qb}
    for q,x in axis:
        # Tail hold remains in original clock, while a score endpoint uses its
        # first time before the decay. q=0 note onset occurs after initial silence.
        s=source_sample(clock,q,onset=q!=clock[-1][1]);knots[s]=x
    keys=sorted(knots);values=[knots[k] for k in keys]
    assert all(b>=a-1e-6 for a,b in zip(values,values[1:])), 'scroll must never move backwards'
    return PchipInterpolator(keys,values,extrapolate=False),[keys[0],keys[-1]]

def make_navigation(nav,sample):
    im=Image.new('RGB',(WIDTH,HEIGHT),BG);d=ImageDraw.Draw(im)
    parents=nav['parents'];parent=next((p for p in parents if p['range'][0]<=sample<p['range'][1]),parents[-1])
    child=next((p for p in parent['children'] if p['range'][0]<=sample<p['range'][1]),parent['children'][-1])
    font=ImageFont.truetype(str(FONT),42);small=ImageFont.truetype(str(FONT),36)
    result=[]
    for top,segments,extent,current in [(1848,parents,nav['range'],parent),(2000,parent['children'],parent['range'],child)]:
        x=144;w=3552; y=top+102
        d.text((x,top),current['label'],fill=INK,font=font)
        for seg in segments:
            a=x+w*(seg['range'][0]-extent[0])/(extent[1]-extent[0]);b=x+w*(seg['range'][1]-extent[0])/(extent[1]-extent[0])
            active=seg['id']==current['id'];color=BLUE if active else '#d3d0c7'
            d.rectangle([round(a),y,round(b-8),y+11],fill=color)
            if not active:
                text=seg['label']
                if d.textlength(text,font=small)>b-a-22:text=seg.get('short_label',text)
                if d.textlength(text,font=small)<=b-a-22:
                    d.text(((a+b)/2,top+72),text,anchor='mm',fill=MUTED,font=small)
        result.append(dict(y=y,extent=extent))
    return im.crop((0,1834,WIDTH,HEIGHT)),result,(parent['id'],child['id'])

class Renderer:
    def __init__(self):
        self.timeline=load(W/'timeline.json')
        self.data={m:load(W/f'data/M{m}/data.json') for m in range(1,5)}
        self.current=None;self.nav_key=None
        self.font=ImageFont.truetype(str(FONT),32)

    def locate(self,frame):
        sample=min(frame*1600,self.timeline['total_samples']-1)
        movement=self.timeline['movements'][interval_index([m['global_range'][0] for m in self.timeline['movements']],sample)]
        m=movement['movement'];s=sample-movement['global_range'][0];data=self.data[m]
        sec=data['sections'][interval_index([x['range'][0] for x in data['sections']],s)]
        return data,sec,s

    def prepare(self,data,section):
        p=W/'strip-raster'/section['id']/'page-001.json';self.page=load(p)
        self.tiles={t['x']:Image.open(R/t['path']).convert('RGB').crop((0,50,3840,1830)) for t in self.page['tiles']}
        atlas=Image.open(R/self.page['head_atlas']).convert('RGBA')
        self.heads=[]
        for h in self.page['heads']:
            a,b,w,z=h['atlas'];sprite=atlas.crop((a,b,a+w,b+z));pixels=np.array(sprite)
            pixels[:,:,:3]=[40,125,159];sprite=Image.fromarray(pixels)
            self.heads.append((h,sprite))
        self.heads.sort(key=lambda item:item[0]['box'][0])
        self.head_x=[h['box'][0] for h,sprite in self.heads]
        self.max_head_width=max(h['box'][2] for h,sprite in self.heads)
        self.curve,self.curve_bounds=clock_curve(data['clock'],self.page['axis'])
        self.current=section['id'];self.nav_key=None
        self.paper=Image.new('RGB',(WIDTH,HEIGHT),BG);d=ImageDraw.Draw(self.paper)
        # Extend the original staff lines under the fixed reading column at the
        # beginning and ending; actual engraved staff lines overlay this base.
        for y in self.page['staff_lines']:d.line((LEFT,y,RIGHT,y),fill='#77766e',width=1)
        for label in self.page['labels']:
            text=LABELS.get(label['text'],label['text']);size=min(32,max(21,int(285/max(1,len(text)))));f=ImageFont.truetype(str(FONT),size)
            d.text((LEFT-32,label['y']),text,font=f,anchor='rm',fill=INK)

    def frame(self,frame):
        data,section,s=self.locate(frame)
        if self.current!=section['id']:self.prepare(data,section)
        curve_s=min(max(s,self.curve_bounds[0]),self.curve_bounds[1]);x=float(self.curve(curve_s))
        # Keep subpixel phase in the scroll. A fixed-point fractional translation
        # uses only a two-tap horizontal interpolation, never frame blending.
        offset=x-CURSOR;integer=math.floor(offset);frac=offset-integer
        pic=self.paper.copy()
        strip=Image.new('RGB',(RIGHT-LEFT+2,1780),BG)
        start=integer+LEFT
        for tile_x,tile in self.tiles.items():
            a=max(start,tile_x);b=min(start+strip.width,tile_x+tile.width)
            if b>a:strip.paste(tile.crop((a-tile_x,0,b-tile_x,1780)),(a-start,0))
        if frac:
            # A translation requires just the adjacent pixel columns. This is
            # the same spatial two-tap sampling without a general affine warp.
            strip=Image.blend(strip.crop((0,0,RIGHT-LEFT,1780)),strip.crop((1,0,RIGHT-LEFT+1,1780)),frac)
        else:strip=strip.crop((0,0,RIGHT-LEFT,1780))
        pic.paste(strip,(LEFT,50))
        # Native heads are recolored only at the stationary blue reading zone.
        # Their original geometry stays attached to the moving notation.
        band_left,band_right=CURSOR-8,CURSOR+29
        first=bisect_right(self.head_x,x-8-self.max_head_width)-1
        last=bisect_right(self.head_x,x+29)
        for h,sprite in self.heads[max(0,first):last]:
            hx,hy,w,height=h['box'];sx=hx-offset
            if sx+w<=band_left or sx>=band_right:continue
            sx=hx-integer
            if frac:
                shifted=Image.new('RGBA',(w,height));shifted.paste(sprite.crop((1,0,w,height)),(0,0))
                sprite=Image.blend(sprite,shifted,frac)
            a=max(sx,band_left);b=min(sx+w,band_right)
            if b>a:
                piece=sprite.crop((a-sx,0,b-sx,height));pic.paste(piece,(a,hy),piece)
        nav=self.data[data['movement']]['nav']
        parent=next((p for p in nav['parents'] if p['range'][0]<=s<p['range'][1]),nav['parents'][-1])
        child=next((c for c in parent['children'] if c['range'][0]<=s<c['range'][1]),parent['children'][-1])
        key=(data['movement'],parent['id'],child['id'])
        if key!=self.nav_key:self.nav,self.tracks,_=make_navigation(nav,s);self.nav_key=key
        pic.paste(self.nav,(0,1834));d=ImageDraw.Draw(pic)
        a,b=self.page['cursor_extent'];d.line((CURSOR,a,CURSOR,b),fill=BLUE,width=3)
        for track in self.tracks:
            a,b=track['extent'];px=144+3552*min(1,max(0,(s-a)/(b-a)));d.line((px,track['y']-15,px,track['y']+25),fill=BLUE,width=6)
        return pic

def main():
    p=argparse.ArgumentParser();p.add_argument('--frame',type=int);p.add_argument('--output');p.add_argument('--start',type=int,default=0);p.add_argument('--frames',type=int);p.add_argument('--height',type=int,default=2160)
    args=p.parse_args();r=Renderer();output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    if args.frame is not None:r.frame(args.frame).save(output);return
    assert args.frames and not output.exists()
    width=args.height*16//9;cmd=[shutil.which('ffmpeg'),'-nostdin','-v','error','-n','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{args.height}','-framerate','60','-i','pipe:0',
        '-ss',str(args.start/60),'-i',str(W/'audio/Walter-full-96k24.m4a'),'-t',str(args.frames/60),'-map','0:v:0','-map','1:a:0',
        '-vf','scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p10le',
        '-c:v','libx265','-preset','medium','-crf','23','-maxrate','8000000','-bufsize','16000000','-x265-params','pools=4:frame-threads=2:log-level=error',
        '-pix_fmt','yuv420p10le','-tag:v','hvc1','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv',
        '-video_track_timescale','60000','-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24','-movflags','+faststart',str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE);start=time.monotonic()
    try:
        for frame in range(args.start,args.start+args.frames):
            im=r.frame(frame)
            if args.height!=2160:im=im.resize((width,args.height),Image.Resampling.LANCZOS)
            proc.stdin.write(im.tobytes())
            if (frame-args.start)%120==0:print(frame,round((frame-args.start+1)/(time.monotonic()-start),2),'fps',flush=True)
        proc.stdin.close();assert proc.wait()==0
    finally:
        if proc.poll() is None:proc.terminate();proc.wait()

if __name__=='__main__':main()
