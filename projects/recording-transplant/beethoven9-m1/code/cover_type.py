from xml.sax.saxutils import escape
from fontTools.pens.svgPathPen import SVGPathPen

INK = "#211f1b"

class Paper:
    def __init__(self, fonts):
        self.fonts = fonts
        self.defs = {}
        self.body = []

    def text(self, x, y, words, size, color=INK, weight='Regular', tracking=0, anchor='start'):
        font, cmap, glyphs = self.fonts[weight]
        units = font['head'].unitsPerEm
        runs = []
        advance = 0
        for letter in words:
            name = cmap[ord(letter)]
            key = f'letter-{weight}-{ord(letter):x}'
            if key not in self.defs:
                pen = SVGPathPen(glyphs)
                glyphs[name].draw(pen)
                self.defs[key] = f'<path id="{key}" d="{pen.getCommands()}"/>'
            runs.append(f'<use xlink:href="#{key}" x="{advance:.3f}"/>')
            advance += font['hmtx'][name][0] + tracking*units/size
        width = advance*size/units-tracking
        x -= width*{'start':0,'middle':.5,'end':1}[anchor]
        self.body.append(f'<g aria-label="{escape(words)}" fill="{color}" transform="translate({x:.3f},{y}) scale({size/units},{-size/units})">{"".join(runs)}</g>')

        return width

    def line(self,x,y,right,bottom,color,width=1,dash=None):
        pattern=f' stroke-dasharray="{dash}"' if dash else ''
        self.body.append(f'<path d="M{x:.2f} {y:.2f} L{right:.2f} {bottom:.2f}" stroke="{color}" stroke-width="{width}" fill="none"{pattern}/>')
