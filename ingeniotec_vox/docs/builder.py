"""Motore documento .docx, derivato da `builder.py` del kit dispense.

Stesse regole di impaginazione (box e tabelle brevi non spezzati, intestazione
di tabella ripetuta, frasi che introducono un elenco legate all'elenco), ma
documento creato da zero con lo stile dei report Ingeniotec: A4, Calibri,
titoli blu, logo nell'intestazione, numero di pagina nel piè di pagina.
"""

import re
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Emu, Pt, RGBColor

NAVY = '1F4E78'
TITLE = '17365D'
TEAL = '43818D'          # colore della fascia del logo
ALT = 'EAF1F8'
GREY = '555555'
RED = 'B01E23'
# 'report': report Ingeniotec; 'dispensa': stile delle dispense L5/L9 del kit (titoli e tabelle rossi)
THEMES = {
    'report': dict(accent=NAVY, title=TITLE, h2=NAVY, rule=TEAL, rule_sz=12, alt=ALT,
                   size=10.5, line=1.1, sizes=(20, 14, 12), before=(0, 16, 12), after=(4, 6, 4),
                   margins=(2, 2, 2.2, 1.8), table_size=9.5, cell=(20, 20), image=6120000),
    'dispensa': dict(accent=RED, title=RED, h2='222222', rule='4F81BD', rule_sz=8, alt='F6EDED',
                     size=11, line=1.15, sizes=(24, 16, 13), before=(0, 18, 12), after=(6, 6, 6),
                     margins=(2.2, 2.2, 2.0, 2.0), table_size=10, cell=(0, 40), image=5580000),
}
BOXES = {  # sfondo, bordo, etichetta, spazio prima
    'DA RICORDARE': ('FBF1E6', 'C8102E', 'C8102E', 120),
    'ATTENZIONE': ('FFF8D6', 'B8860B', 'B8860B', 120),
    'VERIFICA FONTI': ('EAF2FB', '2E75B6', '1F4E79', 80),
    'NOTA': ('F2F2F2', '7F7F7F', '595959', 120),
}
TOKEN = re.compile(r'(\*\*.+?\*\*|\*.+?\*)')
TEXT_WIDTH = 9638        # twip: A4 con margini di 2 cm


def assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parents[2] / "assets"


def _el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn('w:' + k), str(v))
    return e


def _field(p, instr):
    """Campo Word (es. PAGE, NUMPAGES) aggiornato all'apertura e in PDF."""
    f = _el('w:fldSimple', instr=instr)
    r = _el('w:r'); t = _el('w:t'); t.text = '1'; r.append(t); f.append(r)
    p._p.append(f)


class Doc:
    def __init__(self, header_text: str = '', footer_text: str = 'Ingeniotec Vox', theme: str = 'report'):
        self.t = THEMES[theme]
        self.d = docx.Document()
        sec = self.d.sections[0]
        sec.page_width, sec.page_height = Cm(21), Cm(29.7)
        sec.left_margin, sec.right_margin, sec.top_margin, sec.bottom_margin = map(Cm, self.t['margins'])
        sec.header_distance = sec.footer_distance = Cm(0.9)
        self._styles()
        self._header(sec, header_text)
        self._footer(sec, footer_text)

    # ---------- impostazione ----------
    def _styles(self):
        st = self.d.styles
        normal = st['Normal']
        t = self.t
        normal.font.name = 'Calibri'; normal.font.size = Pt(t['size'])
        normal.element.rPr.rFonts.set(qn('w:eastAsia'), 'Calibri')
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = t['line']
        for name, size, color, before, after in zip(
                ('Title', 'Heading 1', 'Heading 2'), t['sizes'], (t['title'], t['accent'], t['h2']),
                t['before'], t['after']):
            s = st[name]
            s.font.name = 'Calibri'; s.font.size = Pt(size); s.font.bold = True
            s.font.color.rgb = RGBColor.from_string(color)
            rf = s.element.rPr.find(qn('w:rFonts'))   # via i font del tema: resta Calibri
            for a in ('asciiTheme', 'hAnsiTheme', 'eastAsiaTheme', 'cstheme'):
                rf.attrib.pop(qn('w:' + a), None)
            s.paragraph_format.space_before = Pt(before)
            s.paragraph_format.space_after = Pt(after)
            s.paragraph_format.keep_with_next = True
        title_pPr = st['Title'].element.get_or_add_pPr()
        for old in title_pPr.findall(qn('w:pBdr')):
            title_pPr.remove(old)
        bdr = _el('w:pBdr'); bdr.append(_el('w:bottom', val='single', sz=t['rule_sz'], space=4, color=t['rule']))
        title_pPr.append(bdr)

    def _hf_style(self, name, size):
        """Stile di intestazione/piè di pagina: un solo tabulatore a destra, testo piccolo e grigio
        (anche i campi PAGE/NUMPAGES, che Word riscrive con lo stile del paragrafo)."""
        s = self.d.styles[name]
        s.paragraph_format.tab_stops.clear_all()
        s.paragraph_format.tab_stops.add_tab_stop(Emu(TEXT_WIDTH * 635), WD_TAB_ALIGNMENT.RIGHT)
        s.font.size = Pt(size)
        s.font.color.rgb = RGBColor.from_string(GREY)

    def _header(self, sec, text):
        self._hf_style('Header', 8.5)
        p = sec.header.paragraphs[0]
        logo = assets_dir() / 'logo_wordmark.png'
        if logo.is_file():
            p.add_run().add_picture(str(logo), width=Cm(4.2))
        p.add_run('\t' + text)

    def _footer(self, sec, text):
        self._hf_style('Footer', 8)
        p = sec.footer.paragraphs[0]
        bdr = _el('w:pBdr'); bdr.append(_el('w:top', val='single', sz=4, space=4, color='BFBFBF'))
        p._p.get_or_add_pPr().append(bdr)
        p.add_run(text + '\tPagina ')
        _field(p, 'PAGE'); p.add_run(' di '); _field(p, 'NUMPAGES')

    # ---------- inline ----------
    def runs(self, p, text, size=None, color=None, italic=False, bold=False):
        for part in TOKEN.split(text):
            if not part:
                continue
            b, i = bold, italic
            if part.startswith('**') and part.endswith('**'):
                part, b = part[2:-2], True
            elif part.startswith('*') and part.endswith('*') and len(part) > 2:
                part, i = part[1:-1], True
            r = p.add_run(part)
            if b: r.bold = True
            if i: r.italic = True
            if size: r.font.size = Pt(size)
            if color: r.font.color.rgb = RGBColor.from_string(color)
        return p

    def _spacing(self, p, before=None, after=None):
        pPr = p._p.get_or_add_pPr()
        sp = pPr.find(qn('w:spacing'))
        if sp is None:
            sp = _el('w:spacing'); pPr.append(sp)
        if before is not None: sp.set(qn('w:before'), str(before))
        if after is not None: sp.set(qn('w:after'), str(after))

    def hyperlink(self, p, text, url):
        rid = self.d.part.relate_to(url, RT.HYPERLINK, is_external=True)
        h = _el('w:hyperlink'); h.set(qn('r:id'), rid)
        r = _el('w:r'); rPr = _el('w:rPr')
        rPr.append(_el('w:color', val='0563C1')); rPr.append(_el('w:u', val='single'))
        r.append(rPr); t = _el('w:t'); t.text = text; t.set(qn('xml:space'), 'preserve')
        r.append(t); h.append(r); p._p.append(h)

    # ---------- blocchi ----------
    def title(self, text):
        self.d.add_paragraph(text, style='Title')

    def subtitle(self, text):
        p = self.d.add_paragraph()
        self.runs(p, text, size=10, color=GREY, italic=True)

    def h1(self, text):
        self.d.add_paragraph(text, style='Heading 1')

    def h2(self, text):
        self.d.add_paragraph(text, style='Heading 2')

    def para(self, text):
        p = self.d.add_paragraph(); self.runs(p, text)
        if text.rstrip().endswith(':'):   # le frasi che introducono una tabella o un elenco restano con esso
            p._p.get_or_add_pPr().insert(0, _el('w:keepNext'))
        return p

    def blank(self):
        self.d.add_paragraph()

    def page_break(self):
        self.d.add_page_break()

    def bullet(self, text):
        p = self.d.add_paragraph(style='List Bullet'); self._spacing(p, after=40)
        self.runs(p, text)

    def bullets(self, items):
        for n, t in enumerate(items, 1):
            self.bullet(t)
            if n < len(items) and len(items) <= 12:   # elenchi brevi non si spezzano
                self.d.paragraphs[-1]._p.get_or_add_pPr().insert(0, _el('w:keepNext'))

    def steps(self, items):
        for n, t in enumerate(items, 1):
            p = self.d.add_paragraph(); self._spacing(p, after=40)
            ind = _el('w:ind', left=539, hanging=340); p._p.get_or_add_pPr().append(ind)
            if n < len(items) and len(items) <= 8:   # i passaggi restano insieme
                p._p.get_or_add_pPr().insert(0, _el('w:keepNext'))
            r = p.add_run(f'{n}.  '); r.bold = True; r.font.color.rgb = RGBColor.from_string(self.t['accent'])
            self.runs(p, t)

    def box(self, kind, text, sources=None, container=None):
        fill, border, label_col, before = BOXES[kind]
        p = (container or self.d).add_paragraph()
        pPr = p._p.get_or_add_pPr()
        pPr.append(_el('w:shd', val='clear', color='auto', fill=fill))
        bdr = _el('w:pBdr'); bdr.append(_el('w:left', val='single', sz=24, space=8, color=border)); pPr.append(bdr)
        pPr.append(_el('w:spacing', before=before, after=160))
        pPr.append(_el('w:ind', left=170))
        if container is None:
            pPr.insert(0, _el('w:keepLines'))   # il box non si spezza tra due pagine
        sz = 8 if container is not None else None
        r = p.add_run(kind + '  '); r.bold = True; r.font.color.rgb = RGBColor.from_string(label_col)
        if sz: r.font.size = Pt(sz)
        self.runs(p, text, size=sz)
        if sources:
            r = p.add_run('  Fonti: ' if len(sources) > 1 else '  Fonte: ')
            r.bold = True; r.font.color.rgb = RGBColor.from_string(label_col)
            for k, (label, url) in enumerate(sources):
                if k: p.add_run(' · ')
                if url: self.hyperlink(p, label, url)
                else: p.add_run(label)
        return p

    def remember(self, t, **k): return self.box('DA RICORDARE', t, **k)
    def warn(self, t, **k): return self.box('ATTENZIONE', t, **k)
    def verify(self, t, sources=None, **k): return self.box('VERIFICA FONTI', t, sources, **k)
    def note(self, t, **k): return self.box('NOTA', t, **k)

    def table(self, header, rows, widths, bold_first=False, notes=None, size=None):
        """rows: liste di stringhe; widths in twip (somma ≤ TEXT_WIDTH);
        notes: {(r,c): (testo, fonti)} box VERIFICA FONTI nella cella"""
        size = size or self.t['table_size']
        t = self.d.add_table(rows=1 + len(rows), cols=len(header))
        t.style = self.d.styles['Table Grid']
        tblPr = t._tbl.tblPr
        tblPr.append(_el('w:jc', val='center'))
        tblPr.append(_el('w:tblLayout', type='fixed'))
        borders = _el('w:tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            borders.append(_el('w:' + side, val='single', sz=4, space=0, color='BFBFBF'))
        tblPr.append(borders)
        grid = t._tbl.tblGrid
        for gc, w in zip(grid.findall(qn('w:gridCol')), widths):
            gc.set(qn('w:w'), str(w))
        for ri, row in enumerate([header] + rows):
            trPr = t.rows[ri]._tr.get_or_add_trPr()
            trPr.append(_el('w:cantSplit'))
            if ri == 0:
                trPr.append(_el('w:tblHeader'))
            for ci, txt in enumerate(row):
                cell = t.rows[ri].cells[ci]
                tcPr = cell._tc.get_or_add_tcPr()
                tcPr.append(_el('w:tcW', type='dxa', w=widths[ci]))
                fill = self.t['accent'] if ri == 0 else (self.t['alt'] if ri % 2 == 0 else None)
                if fill: tcPr.append(_el('w:shd', val='clear', color='auto', fill=fill))
                p = cell.paragraphs[0]; self._spacing(p, *self.t['cell'])
                # tabelle brevi (fino a 8 righe) restano intere sulla stessa pagina;
                # le lunghe non lasciano meno di 3 righe a inizio o a fine pagina
                if ri < len(rows) and (ri <= 3 or ri >= len(rows) - 2 or len(rows) <= 8):
                    p._p.get_or_add_pPr().insert(0, _el('w:keepNext'))
                if ri == 0:
                    self.runs(p, txt, size=size, color='FFFFFF', bold=True)
                else:
                    self.runs(p, txt, size=size, bold=(bold_first and ci == 0))
                if notes and ri > 0 and (ri - 1, ci) in notes:
                    nt, ns = notes[(ri - 1, ci)]
                    self.verify(nt, ns, container=cell)
        self.d.add_paragraph().paragraph_format.space_after = Pt(2)
        return t

    def image(self, path, caption, width_emu=None, max_height_emu=None):
        """Immagine centrata con didascalia; le schermate molto alte si riducono a `max_height_emu`."""
        width_emu = width_emu or self.t['image']
        if max_height_emu:
            from PIL import Image
            with Image.open(path) as im:
                ratio = im.height / im.width
            width_emu = min(width_emu, int(max_height_emu / ratio))
        p = self.d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pPr = p._p.get_or_add_pPr(); pPr.insert(0, _el('w:keepNext'))
        self._spacing(p, before=120, after=40)
        p.add_run().add_picture(str(path), width=Emu(width_emu))
        c = self.d.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.runs(c, caption, size=9, color=GREY, italic=True)

    def question(self, n, q, a):
        """Domanda di autoverifica con risposta rientrata (come nel kit)."""
        p = self.d.add_paragraph(); pPr = p._p.get_or_add_pPr()
        pPr.append(_el('w:keepNext')); pPr.append(_el('w:spacing', before=120, after=40))
        r = p.add_run(f'{n}. '); r.bold = True; r.font.color.rgb = RGBColor.from_string(self.t['accent'])
        self.runs(p, q, bold=True)
        p = self.d.add_paragraph(); p._p.get_or_add_pPr().append(_el('w:ind', left=720))
        self.runs(p, 'Risposta: ' + a, italic=True, color=GREY)

    def save(self, path):
        self.d.core_properties.title = ''
        self.d.core_properties.author = 'Ingeniotec Vox'
        self.d.save(str(path))
