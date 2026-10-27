"""Generate two standalone SVG covers from the final video's native score assets."""
from pathlib import Path
import base64
import json
from fontTools import subset

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'output/score-sync-02/封面'
NATIVE = ROOT / 'work/score-sync-02/canonical/M1'
FONT = ROOT / 'work/revision-04/assets/fonts/source-han-official-01'
OUT.mkdir(parents=True, exist_ok=True)

TEXT = '马勒第九交响曲谱同步瓦尔特指挥哥伦比亚乐团小提琴中大一二三四章呈示部展开再现尾声引入主题群连接尾部GUSTAV MAHLER SYMPHONY NO. 9 BRUNO WALTER COLUMBIA ORCHESTRA I II III IV 0123456789 abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,—'
faces = []
for weight, style in [(300, 'Light'), (400, 'Regular'), (500, 'Medium')]:
    font_dir = HERE / 'fonts' if style == 'Light' else FONT
    font = subset.load_font(str(font_dir / f'SourceHanSerifSC-{style}.otf'), subset.Options())
    sub = subset.Subsetter()
    sub.populate(text=TEXT)
    sub.subset(font)
    dst = HERE / f'CoverSerif-{style}.otf'
    subset.save_font(font, str(dst), subset.Options())
    data = base64.b64encode(dst.read_bytes()).decode()
    faces.append(f'@font-face{{font-family:CoverSerif;font-weight:{weight};src:url(data:font/otf;base64,{data})}}')

source = json.loads((NATIVE / 'source.json').read_text())
data = json.loads((ROOT / source['data']).read_text())
music = ''.join((NATIVE / f'measures/{n:04d}.svg').read_text() for n in range(6, 11))
active = [n['engraver_id'] for n in data['notes'] if n['q'] <= 28 < n['q'] + n['duration']]
active_css = ','.join(f'#m1-{n}' for n in active) + '{color:#C94732;fill:#C94732;}'

def text(x, y, value, size, weight=400, fill='#282B29', spacing=0, anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" letter-spacing="{spacing}" text-anchor="{anchor}">{value}</text>'

def build(width, height, tag):
    wide = width == 3840
    margin = 220 if wide else 170
    main_size = 267 if wide else 224
    number_x = 3000 if wide else 2220
    score_x = 480 if wide else 425
    score_right = width - margin
    world_left, world_right = 21816, 41097
    scale = (score_right - score_x) / (world_right - world_left)
    # Both layouts retain the full same phrase; no stretching or cropping between ratios.
    row_y = [1350, 1570, 1790]
    parts = [(51, '第二小提琴'), (53, '中提琴'), (55, '大提琴')]
    clips = ''.join(f'<clipPath id="row-{n}"><rect x="{score_x}" y="{y-150}" width="{score_right-score_x}" height="295"/></clipPath>' for (n, _), y in zip(parts, row_y))
    defs = (NATIVE / 'defs.svg').read_text()
    css = ''.join(faces) + '''
      text{font-family:CoverSerif,serif} .engraving{color:#333633;fill:currentColor}
      .engraving path,.engraving ellipse,.engraving polygon,.engraving polyline,.engraving rect{stroke:currentColor}
      .engraving .staff > path{color:#767B76}
      .engraving .dir,.engraving .dynam{font-style:italic}
      .engraving .mNum,.engraving .dir{display:none}
    ''' + active_css
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<title>马勒第九交响曲，瓦尔特指挥，曲谱同步</title>',
         f'<style>{css}</style>', defs,
         f'<defs>{clips}<g id="score-phrase" class="engraving">{music}</g></defs>',
         f'<rect width="{width}" height="{height}" fill="#faf8f1"/>']
    p.append(text(margin, 210, 'GUSTAV MAHLER', 43, spacing=9, fill='#59645F'))
    p.append(text(margin-6, 555 if wide else 560, '马勒', 188 if wide else 176, weight=500, spacing=12))
    p.append(text(margin-10, 880 if wide else 858, '第九交响曲', main_size, weight=500, spacing=3))
    p.append(text(margin-3, 1090, '曲谱同步', 144 if wide else 136, weight=500, fill='#287D9F', spacing=10))
    credit_x = 1040 if wide else 940
    p.append(text(credit_x, 1045, '瓦尔特指挥', 65 if wide else 60, spacing=8))
    p.append(text(credit_x, 1138, '哥伦比亚交响乐团', 49 if wide else 46, fill='#626A63', spacing=5))
    p.append(text(number_x, 380 if wide else 450, 'SYMPHONY', 34 if wide else 32, fill='#287D9F', spacing=8, anchor='middle'))
    p.append(text(number_x, 1000, 'IX', 760 if wide else 660, weight=300, fill='#287D9F', spacing=-12 if wide else -10, anchor='middle'))
    for (staff, label), y in zip(parts, row_y):
        center = source['centers'][str(staff)]
        p.append(text(margin, y+13, label, 35 if wide else 31, fill='#737C75'))
        p.append(f'<g clip-path="url(#row-{staff})"><use href="#score-phrase" transform="translate({score_x-world_left*scale} {y-center*scale}) scale({scale})"/></g>')
    playhead = score_x + (30342-world_left)*scale
    p.append(f'<path d="M{playhead} 1218 V1937" stroke="#287D9F" stroke-width="4"/>')
    # The two baseline strokes echo the two structural navigation rails in the film.
    p.append(f'<path d="M{margin} 1960 H{width-margin}" stroke="#CBD2C9" stroke-width="2"/>')
    p.append(f'<path d="M{margin} 1975 H{width-margin}" stroke="#DFE2D9" stroke-width="2"/>')
    p.append(text(margin, 2075, 'BRUNO WALTER', 37, fill='#4E5B53', spacing=5))
    p.append(text(width-margin, 2075, 'COLUMBIA SYMPHONY ORCHESTRA', 33 if wide else 28, fill='#727C74', spacing=3, anchor='end'))
    p.append('</svg>')
    target = OUT / f'马勒第九交响曲-封面-{tag}.svg'
    target.write_text(''.join(p))
    print(target)

build(3840, 2160, '16x9')
build(2880, 2160, '4x3')
