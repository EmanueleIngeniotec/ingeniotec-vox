"""Aggiornamento della guida all'esame (es. «00 - Guida all'esame e glossario») dopo una lezione.

La guida è un documento curato a mano: Vox non la ricrea ma la modifica. Claude
riceve la guida descritta con un id per paragrafo (P…) e tabella (T…) e propone
operazioni puntuali; qui si applicano copiando paragrafi, righe e tabelle esistenti,
così le aggiunte hanno lo stesso stile del resto. Porting di `update_00_lib.py` e
`fix00_layout.py` del kit.
"""

import copy
import re
import shutil
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TOKEN = re.compile(r'(\*\*.+?\*\*)')
KEEP_ROWS = 16      # tabelle fino a 15 righe più l'intestazione restano intere (criteri del kit)


class GuideError(RuntimeError):
    pass


def backup_path(guide: Path, numero: int) -> Path:
    return guide.parent / "_versioni_precedenti" / f"{guide.stem} (prima della L{numero}).docx"


def source_for(guide: Path, numero: int) -> Path:
    """Versione della guida da cui partire: la copia «prima della L<n>» se c'è già
    (il lavoro si può rifare senza aggiungere due volte le stesse righe), altrimenti
    la guida, salvandone prima la copia."""
    bk = backup_path(guide, numero)
    if not bk.is_file():
        bk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(guide, bk)
    return bk


def _items(d) -> dict:
    """id → elemento XML: P1, P2… paragrafi con testo, T0, T1… tabelle, in ordine di documento."""
    out, np, nt = {}, 0, 0
    for el in d.element.body:
        if el.tag == qn('w:p') and ''.join(t.text or '' for t in el.iter(qn('w:t'))).strip():
            np += 1; out[f"P{np}"] = el
        elif el.tag == qn('w:tbl'):
            out[f"T{nt}"] = el; nt += 1
    return out


def _text(el) -> str:
    return ''.join(t.text or '' for t in el.iter(qn('w:t')))


def _style(d, p_el) -> str:
    s = p_el.find(qn('w:pPr') + '/' + qn('w:pStyle'))
    if s is None:
        return 'Normal'
    sid = s.get(qn('w:val'))
    for st in d.styles:
        if st.style_id == sid:
            return st.name
    return sid


def describe(path: Path) -> str:
    """La guida come testo per Claude: ogni paragrafo e tabella con il suo id e lo stile."""
    d = docx.Document(str(path))
    lines = []
    for k, el in _items(d).items():
        if k[0] == 'P':
            lines.append(f"{k} [{_style(d, el)}] {_text(el)}")
        else:
            rows = el.findall(qn('w:tr'))
            lines.append(f"{k} tabella di {len(rows)} righe:")
            for i, tr in enumerate(rows):
                cells = [_text(tc).strip() for tc in tr.findall(qn('w:tc'))]
                lines.append(f"  r{i}: " + " | ".join(cells))
    return "\n".join(lines)


def _set_text(p_el, text: str) -> None:
    """Sostituisce il testo del paragrafo mantenendo il formato del primo run; **grassetto**."""
    first = p_el.find(qn('w:r'))
    rpr = first.find(qn('w:rPr')) if first is not None else None
    for r in list(p_el):
        if r.tag in (qn('w:r'), qn('w:hyperlink'), qn('w:fldSimple')):
            p_el.remove(r)
    for part in TOKEN.split(text):
        if not part:
            continue
        bold = part.startswith('**') and part.endswith('**')
        if bold:
            part = part[2:-2]
        r = OxmlElement('w:r')
        new_rpr = copy.deepcopy(rpr) if rpr is not None else OxmlElement('w:rPr')
        for b in new_rpr.findall(qn('w:b')):
            new_rpr.remove(b)
        if bold:
            new_rpr.insert(0, OxmlElement('w:b'))
        if len(new_rpr):
            r.append(new_rpr)
        t = OxmlElement('w:t'); t.text = part; t.set(qn('xml:space'), 'preserve')
        r.append(t); p_el.append(r)


def _set_cell(tc, text: str) -> None:
    ps = tc.findall(qn('w:p'))
    for extra in ps[1:]:
        tc.remove(extra)
    for extra in tc.findall(qn('w:tbl')):
        tc.remove(extra)
    _set_text(ps[0], text)


def _fill_row(tr, cells: list[str]) -> None:
    tcs = tr.findall(qn('w:tc'))
    cells = (list(cells) + [''] * len(tcs))[:len(tcs)]
    for tc, txt in zip(tcs, cells):
        _set_cell(tc, txt)


def _restripe(tbl) -> None:
    """Righe alternate: dopo un inserimento le righe pari riprendono lo sfondo delle pari."""
    rows = tbl.findall(qn('w:tr'))
    shades = {}
    for i, tr in enumerate(rows[1:], 1):
        shd = tr.find('.//' + qn('w:tcPr') + '/' + qn('w:shd'))
        shades.setdefault(i % 2, copy.deepcopy(shd) if shd is not None else None)
    for i, tr in enumerate(rows[1:], 1):
        for tc in tr.findall(qn('w:tc')):
            tcPr = tc.find(qn('w:tcPr'))
            if tcPr is None:
                tcPr = OxmlElement('w:tcPr'); tc.insert(0, tcPr)
            for s in tcPr.findall(qn('w:shd')):
                tcPr.remove(s)
            if shades.get(i % 2) is not None:
                tcPr.append(copy.deepcopy(shades[i % 2]))


def apply(src: Path, ops: list[dict], dst: Path, log=print) -> int:
    """Applica le operazioni proposte da Claude; quelle con riferimenti sbagliati si saltano."""
    d = docx.Document(str(src))
    items = _items(d)
    rows = {k: el.findall(qn('w:tr')) for k, el in items.items() if k[0] == 'T'}
    after = {}          # ultimo elemento inserito dopo un'ancora: inserimenti multipli in ordine
    done = 0

    def insert_after(anchor, els):
        cur = after.get(id(anchor), anchor)
        for el in els:
            cur.addnext(el); cur = el
        after[id(anchor)] = cur

    for op in ops:
        kind, ref = op.get('op'), op.get('dove', '')
        el = items.get(ref)
        try:
            if el is None:
                raise GuideError(f"riferimento {ref!r} inesistente")
            if kind == 'aggiungi_riga':
                tr = rows[ref][op['riga']]
                new = copy.deepcopy(rows[ref][max(op['riga'], 1)] if len(rows[ref]) > 1 else tr)
                _fill_row(new, op['celle'])
                insert_after(tr, [new])
                _restripe(el)
            elif kind == 'modifica_cella':
                tc = rows[ref][op['riga']].findall(qn('w:tc'))[op['colonna']]
                _set_cell(tc, op['testo'])
            elif kind == 'riscrivi_paragrafo':
                if el.tag != qn('w:p'):
                    raise GuideError(f"{ref} non è un paragrafo")
                _set_text(el, op['testo'])
            elif kind == 'nuovo_punto':
                if el.tag != qn('w:p'):
                    raise GuideError(f"{ref} non è un paragrafo")
                new = copy.deepcopy(el)
                _set_text(new, op['testo'])
                insert_after(el, [new])
            elif kind == 'nuova_tabella':
                if el.tag != qn('w:tbl'):
                    raise GuideError(f"{ref} non è una tabella")
                head = el.getprevious()
                while head is not None and head.tag == qn('w:p') and not _text(head).strip():
                    head = head.getprevious()
                if head is None or head.tag != qn('w:p'):
                    raise GuideError(f"la tabella {ref} non ha un titolo da copiare")
                new_head = copy.deepcopy(head); _set_text(new_head, op['titolo'])
                tbl = copy.deepcopy(el)
                old = tbl.findall(qn('w:tr'))
                _fill_row(old[0], op['intestazione'])
                templates = old[1:3] or old[:1]
                for tr in old[1:]:
                    tbl.remove(tr)
                for i, cells in enumerate(op['righe']):
                    tr = copy.deepcopy(templates[i % len(templates)])
                    _fill_row(tr, cells); tbl.append(tr)
                spacer = el.getnext()
                tail = [copy.deepcopy(spacer)] if spacer is not None and spacer.tag == qn('w:p') \
                    and not _text(spacer).strip() else []
                anchor = spacer if tail else el
                insert_after(anchor, [new_head, tbl, *tail])
            else:
                raise GuideError(f"operazione {kind!r} sconosciuta")
            done += 1
        except (GuideError, KeyError, IndexError) as exc:
            log(f"    guida: operazione saltata ({kind} {ref}): {exc}")
    keep_tables(d)
    d.save(str(dst))
    return done


def _add(parent, tag, first=False):
    if parent.find(qn(tag)) is None:
        e = OxmlElement(tag)
        parent.insert(0, e) if first else parent.append(e)


def keep_tables(d) -> None:
    """Righe mai spezzate, intestazione ripetuta, tabelle brevi intere; titolo e nota
    introduttiva restano con la tabella (da `fix00_layout.py`)."""
    for t in d.tables:
        n = len(t.rows)
        for ri, r in enumerate(t.rows):
            trPr = r._tr.get_or_add_trPr()
            _add(trPr, 'w:cantSplit')
            if ri == 0:
                _add(trPr, 'w:tblHeader')
            if ri < n - 1 and (n <= KEEP_ROWS or ri <= 3 or ri >= n - 3):
                for c in r.cells:
                    for p in c.paragraphs:
                        _add(p._p.get_or_add_pPr(), 'w:keepNext', first=True)
        prev = t._tbl.getprevious()
        for _ in range(3):
            if prev is None or prev.tag != qn('w:p'):
                break
            _add(prev.get_or_add_pPr(), 'w:keepNext', first=True)
            sty = prev.find(qn('w:pPr') + '/' + qn('w:pStyle'))
            if sty is not None and sty.get(qn('w:val')).lower().startswith(('heading', 'titolo')):
                break
            prev = prev.getprevious()
