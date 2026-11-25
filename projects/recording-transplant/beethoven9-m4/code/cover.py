"""Typeset the fourth-movement sequel in the established conductor series."""
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
OUTPUT = Path.cwd() / 'output/定稿/封面'
ART = PROJECT / 'cover/conductors.png'
TITLE = "滕斯泰特又遭夺舍LPO狂轰500BPM？！"


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


def headline(paper, left, baseline, wide):
    scale = 1.19 if wide else 1.03
    paper.body.append(f'<g transform="translate({left-1},{baseline}) rotate(-3) skewX(-6) scale({scale},1)">')
    size = 229 if wide else 211
    for x,y,color in [(4,5,"#e6ab70"),(0,0,RED)]:
        paper.text(x, y, "夺舍", size, color, "Heavy", tracking=-9)
    paper.body.append("</g>")


def deck(paper, width, wide):
    rect(paper, 0, 715, width, 185, BLACK)
    # 500 has the largest cap height in the banner. Maintain one baseline
    # across the mixed Chinese and Latin line and optically tighten the punctuation.
    runs = [
        ("LPO狂轰", 96 if wide else 83, CREAM, -1.5),
        ("500", 145 if wide else 130, GOLD, -6.5),
        ("BPM", 91 if wide else 78, GOLD, -2.5),
        ("？！", 91 if wide else 80, GOLD, -14),
    ]
    font,cmap,_ = paper.fonts["Heavy"]
    em = font["head"].unitsPerEm
    widths = [sum(font["hmtx"][cmap[ord(c)]][0] for c in word)*size/em + (len(word)-1)*tracking
              for word,size,color,tracking in runs]
    gaps = [20 if wide else 14, 5, 7, 0]
    x = (width - sum(widths) - sum(gaps))/2
    for (word,size,color,tracking),advance,gap in zip(runs,widths,gaps):
        paper.text(x, 850, word, size, color, "Heavy",tracking=tracking)
        x += advance+gap


def render(width, art, fonts):
    wide = width == 1600
    l = 69 if wide else 48
    p = Paper(fonts)
    rect(p,0,0,width,900,CREAM)
    em=30 if wide else 26
    stop=l+p.text(l,89,"贝多芬第九交响曲",em,TEAL,"Medium")+18
    p.line(stop,66,stop,89,TEAL,1.4)
    p.text(stop+18,89,"第四乐章速度移植",em,TEAL,"Medium")
    square=764 if wide else 627
    image_x=width-square-(20 if wide else 15)
    image_y=34 if wide else 98
    p.body.append(f'<image x="{image_x}" y="{image_y}" width="{square}" height="{square}" preserveAspectRatio="xMidYMin meet" xlink:href="data:image/png;base64,{art}"/>')
    p.text(l,279 if wide else 278,"滕斯泰特又遭",108 if wide else 87,BLACK,"Heavy",tracking=-3)
    headline(p,l,554 if wide else 543,wide)
    p.line(l,649,l+36,649,TEAL,4)
    p.text(l+50,660,"富特文格勒的速度 × 滕斯泰特的录音",30 if wide else 25,TEAL,"Medium")
    deck(p,width,wide)
    xml=(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{width*24//10}" height="2160" viewBox="0 0 {width} 900"><title>{TITLE}</title>'
         f'<defs>{"".join(p.defs.values())}</defs>{"".join(p.body)}</svg>')
    ratio="16x9" if wide else "4x3"
    stem=OUTPUT/f"滕斯泰特又遭夺舍-{ratio}"
    subprocess.run(["rsvg-convert","-o",str(stem.with_suffix(".png"))],input=xml.encode(),check=True)
    subprocess.run(["magick",str(stem.with_suffix(".png")),"-colorspace","sRGB","-sampling-factor","4:4:4",
                    "-quality","94",str(stem.with_suffix(".jpg"))],check=True)


if __name__=="__main__":
    OUTPUT.mkdir(exist_ok=True,parents=True)
    art=b64encode(ART.read_bytes()).decode("ascii")
    fonts=typefaces()
    for width in (1600,1200):
        render(width,art,fonts)
