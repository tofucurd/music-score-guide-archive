"""Typeset both front pages using one original cartoon and the released tempo curve."""
from base64 import b64encode
from pathlib import Path
import subprocess
from fontTools.ttLib import TTFont

from cover_type import Paper

PROJECT = Path(__file__).resolve().parents[1]
FONTS = PROJECT.parents[2]/'vendor/score-sync-video/assets/fonts'


CREAM='#f6edcf'
BLACK='#211f1b'
RED='#c73724'
TEAL='#205e56'
GOLD='#ffcf59'
OUT=Path.cwd()/'output/定稿/双人肖像封面'


def typefaces():
    files={'Medium':FONTS/'SourceHanSerifSC-Medium.otf',
           'Heavy':PROJECT/'cover/PosterHeavy.otf'}
    fonts={}
    for style,path in files.items():
        font=TTFont(path)
        fonts[style]=(font,font.getBestCmap(),font.getGlyphSet())
    return fonts


def rect(p,x,y,w,h,fill):
    p.body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>')


def compose(width,fonts,art):
    wide=width==1600
    l = 69 if wide else 49
    p=Paper(fonts)
    rect(p,0,0,width,900,CREAM)
    em = 30 if wide else 26
    split = l + p.text(l,91,'贝多芬第九交响曲',em,TEAL,'Medium') + 18
    p.line(split,68,split,91,TEAL,1.4)
    p.text(split+18,91,'第一乐章速度移植',em,TEAL,'Medium')
    side = 817 if wide else 659
    ax = width - side - (23 if wide else -4)
    ay = 51 if wide else 121
    p.body.append(f'<image x="{ax}" y="{ay}" width="{side}" height="{side}" xlink:href="data:image/png;base64,{art}"/>')

    # The two headline lines end above the red punchline, which is wider
    # and tilted independently, like an overprinted newspaper wood type.
    p.text(l,289 if wide else 299,'滕斯泰特惨遭',103 if wide else 84,BLACK,'Heavy',tracking=-3)
    sx=1.34 if wide else 1.13
    size=228 if wide else 222
    headline_baseline = 577
    p.body.append(f'<g transform="translate({l-2},{headline_baseline}) rotate(-3) skewX(-7) scale({sx},1)">')
    p.text(3,4,'夺舍',size,'#e6ab70','Heavy',tracking=-11)
    p.text(0,0,'夺舍',size,RED,'Heavy',tracking=-11)
    p.body.append('</g>')
    credit_y = 679
    p.line(l,credit_y-12,l+36,credit_y-12,TEAL,4)
    p.text(l+51,credit_y,'富特文格勒的速度 × 滕斯泰特的录音',31 if wide else 25,TEAL,'Medium')

    footer_y=751
    rect(p,0,footer_y,width,900-footer_y,BLACK)
    decksize=88 if wide else 76
    # Both phrases share a baseline and form a single readable question.
    first='LPO竟然奏出'
    second='旋律贝九？'
    def extent(text):
        font,cmap,_=fonts['Heavy']
        return sum(font['hmtx'][cmap[ord(c)]][0] for c in text)*decksize/font['head'].unitsPerEm
    text_x=(width-extent(first+second))/2
    pos=p.text(text_x,858,first,decksize,CREAM,'Heavy')
    p.text(text_x+pos,858,second,decksize,GOLD,'Heavy')
    suffix='16x9' if wide else '4x3'
    title='滕斯泰特惨遭夺舍，LPO竟然奏出旋律贝九？'
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{int(width*2.4)}" height="2160" viewBox="0 0 {width} 900"><title>{title}</title><defs>{"".join(p.defs.values())}</defs>{"".join(p.body)}</svg>'
    png = OUT/f'滕斯泰特惨遭夺舍-{suffix}.png'
    png.parent.mkdir(exist_ok=True,parents=True)
    subprocess.run(['rsvg-convert','-o',str(png)],input=svg.encode(),check=True)
    subprocess.run(['magick',str(png),'-colorspace','sRGB','-sampling-factor','4:4:4','-quality','93',str(png.with_suffix('.jpg'))],check=True)


if __name__=='__main__':
    illustration=b64encode((PROJECT/'cover/conductors.png').read_bytes()).decode('ascii')
    fonts=typefaces()
    for width in (1600,1200):
        compose(width,fonts,illustration)
