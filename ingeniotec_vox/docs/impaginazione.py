"""Controllo e correzione automatica dell'impaginazione, con Word sul documento aperto.

Le regole del builder (box con «keepLines», tabelle brevi e frasi introduttive con
«keepNext») non bastano sempre: Word le ignora quando una catena di blocchi legati
non sta in una pagina. Qui si chiede a Word dove finisce davvero ogni blocco e, se
un blocco che sta in una pagina risulta spezzato, si porta all'inizio della pagina
successiva con «interruzione di pagina prima» sul primo paragrafo della sua catena
(titolo e frase introduttiva restano con il blocco).

Blocchi controllati: box (paragrafi con sfondo fuori dalle tabelle), tabelle che il
documento vuole intere (tutte le righe legate alla successiva), titoli rimasti soli
a fondo pagina, schermate separate dalla didascalia.
"""

WD_PAGE = 3                 # wdActiveEndPageNumber
WD_IN_TABLE = 12            # wdWithInTable
WD_AUTO = -16777216         # wdColorAutomatic: paragrafo senza sfondo
MAX_CHAIN = 3               # paragrafi legati al blocco che si spostano con lui (titolo, frase con «:»)


def _page_at(doc, pos: int) -> int:
    return doc.Range(pos, pos).Information(WD_PAGE)


def _chain_start(para):
    """Primo paragrafo della catena «keepNext» che precede `para` (al massimo MAX_CHAIN)."""
    start = para
    for _ in range(MAX_CHAIN):
        prev = start.Previous()
        if prev is None or not prev.KeepWithNext or prev.Range.Information(WD_IN_TABLE):
            break
        start = prev
    return start


def _blocks(doc) -> list[tuple]:
    """(tipo, descrizione, paragrafo d'inizio, inizio, fine) in ordine di documento."""
    out = []
    for i in range(1, doc.Tables.Count + 1):
        t = doc.Tables(i)
        n = t.Rows.Count
        # intera solo se ogni riga (tranne l'ultima) è legata alla successiva
        if n > 1 and all(t.Rows(r).Range.Paragraphs(1).KeepWithNext for r in range(1, n)):
            first = t.Range.Paragraphs(1)
            out.append(("tabella", f"tabella di {n} righe «{first.Range.Text.strip()[:40]}»",
                        first, t.Range.Start, t.Range.End - 1))
    paras = doc.Paragraphs
    count = paras.Count
    p = paras(1) if count else None
    while p is not None:
        r = p.Range
        nxt = p.Next()
        if not r.Information(WD_IN_TABLE):
            text = r.Text.strip()
            if 1 <= p.OutlineLevel <= 3 and text and nxt is not None:
                out.append(("titolo", f"titolo «{text[:50]}»", p, r.Start, nxt.Range.Start))
            elif r.InlineShapes.Count and nxt is not None:
                out.append(("schermata", f"schermata «{nxt.Range.Text.strip()[:50]}»", p, r.Start,
                            nxt.Range.End - 1))
            elif text and r.ParagraphFormat.Shading.BackgroundPatternColor != WD_AUTO:
                out.append(("box", f"box «{text[:50]}»", p, r.Start, r.End - 1))
        p = nxt
    out.sort(key=lambda b: b[3])
    return out


def check_and_fix(doc, log=print) -> dict:
    """Corregge i blocchi spezzati del documento aperto; restituisce correzioni e problemi rimasti."""
    doc.Repaginate()
    fixed, left = [], []
    for kind, what, para, start, end in _blocks(doc):
        p0, p1 = _page_at(doc, start), _page_at(doc, end)
        if kind == "titolo":
            broken = p0 != p1      # il titolo è a fondo pagina, il testo che segue nella successiva
        else:
            broken = p1 > p0
        if not broken:
            continue
        anchor = _chain_start(para)
        if p1 - p0 > 1 or anchor.Format.PageBreakBefore or _page_at(doc, anchor.Range.Start) != p0:
            left.append(f"pag. {p0}: {what} più lungo di una pagina, resta spezzato")
            continue
        anchor.Format.PageBreakBefore = True
        doc.Repaginate()
        if _page_at(doc, end) != _page_at(doc, start) and kind != "titolo":
            left.append(f"pag. {p0}: {what} spezzato anche su pagina nuova")
        fixed.append(f"pag. {p0}: {what} portato alla pagina successiva")
    for line in fixed + left:
        log("    " + line)
    return {"pagine": doc.ComputeStatistics(2), "correzioni": fixed, "problemi": left}
