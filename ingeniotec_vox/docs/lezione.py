"""Composizione delle dispense di una lezione: dispensa e scheda di ripasso.

Struttura e stile delle dispense L5/L9 del kit (titoli e tabelle rossi), con il
logo Ingeniotec nell'intestazione. I contenuti arrivano già risolti dalla pipeline:
le schermate hanno il percorso del ritaglio, le verifiche il testo del box e le fonti.
"""

from pathlib import Path

from .builder import TEXT_WIDTH, Doc
from .call_report import secs

SHOT_MAX_HEIGHT = 3060000   # EMU (8,5 cm): le schermate alte non occupano mezza pagina
CHAR_TWIP = 115             # larghezza media di un carattere a 10 pt, per non spezzare le parole
CELL_PAD = 260              # margini interni della cella


def to_secs(t: str) -> float:
    """Secondi da un minuto del video: h:mm:ss, oppure h:mm come chiesto nei prompt
    (es. 1:47). Un primo numero da 6 in su in una lezione è mm:ss (es. 12:30)."""
    parts = t.strip().split(':')
    if len(parts) == 2 and all(p.isdigit() for p in parts) and int(parts[0]) < 6:
        return int(parts[0]) * 3600 + int(parts[1]) * 60
    return secs(t)


def hm(t) -> str:
    """Minuto del video come h:mm, da secondi o da una stringa."""
    s = int(to_secs(t) if isinstance(t, str) else t)
    return f"{s // 3600}:{s // 60 % 60:02d}"


def auto_widths(header: list[str], rows: list[list[str]]) -> list[int]:
    """Larghezze di colonna in twip proporzionali alla lunghezza tipica del testo,
    mai più strette della parola più lunga della colonna."""
    n = len(header)
    scores, mins = [], []
    for c in range(n):
        texts = [header[c]] + [r[c] for r in rows]
        cells = [len(t) for t in texts[1:]] or [0]
        typical = (sum(cells) / len(cells) + max(cells)) / 2
        scores.append(min(max(typical, len(header[c]) * 0.8, 3), 80))
        word = max((len(w.strip('*')) for t in texts for w in t.split()), default=1)
        mins.append(min(word * CHAR_TWIP + CELL_PAD, TEXT_WIDTH // n))
    ws = [int(TEXT_WIDTH * s / sum(scores)) for s in scores]
    for _ in range(n):   # le colonne sotto il minimo prendono spazio dalle più larghe
        short = [i for i in range(n) if ws[i] < mins[i]]
        if not short:
            break
        need = sum(mins[i] - ws[i] for i in short)
        free = [i for i in range(n) if i not in short]
        spare = sum(ws[i] - mins[i] for i in free)
        if not free or spare <= 0:
            break
        for i in short:
            ws[i] = mins[i]
        for i in free:
            ws[i] -= round(need * (ws[i] - mins[i]) / spare)
    ws[ws.index(max(ws))] += TEXT_WIDTH - sum(ws)
    return ws


def _table(d: Doc, header: list[str], rows: list[list[str]], **kw):
    n = len(header)
    rows = [(list(r) + [''] * n)[:n] for r in rows]
    if rows:
        d.table(header, rows, auto_widths(header, rows), **kw)


def elements(d: Doc, items: list[dict]) -> None:
    """Elementi di contenuto prodotti da Claude (capitoli e scheda)."""
    for e in items:
        k = e['tipo']
        if k == 'paragrafo' and e.get('testo'):
            d.para(e['testo'])
        elif k == 'sottotitolo' and e.get('testo'):
            d.h2(e['testo'] + (f" · min. {hm(e['min'])}" if e.get('min') else ''))
        elif k == 'elenco' and e.get('voci'):
            d.bullets(e['voci'])
        elif k == 'passi' and e.get('voci'):
            d.steps(e['voci'])
        elif k == 'tabella' and e.get('intestazione') and e.get('righe'):
            _table(d, e['intestazione'], e['righe'], bold_first=len(e['intestazione']) > 2)
        elif k == 'ricorda' and e.get('testo'):
            d.remember(e['testo'])
        elif k == 'attenzione' and e.get('testo'):
            d.warn(e['testo'])
        elif k == 'schermata' and e.get('path'):
            d.image(e['path'], f"Schermata della lezione – {e['testo'].rstrip('.')} (min. {hm(e['t'])})",
                    max_height_emu=SHOT_MAX_HEIGHT)
        elif k == 'verifica' and e.get('box'):
            d.verify(e['box']['testo'], [(f['titolo'], f['url']) for f in e['box']['fonti']])


def _lesson(meta: dict) -> str:
    return f"Lezione {meta['numero']}" if meta.get('numero') else "Lezione"


def _header(meta: dict) -> str:
    return ' · '.join(x for x in (meta.get('corso'), _lesson(meta) if meta.get('numero') else '') if x)


def build_dispensa(st: dict, caps: list[dict], meta: dict, dst: Path, exam: bool = True) -> Path:
    """`exam`: corso con esame (peso per l'esame, prova pratica); altrimenti lezione generica."""
    d = Doc(header_text=_header(meta), theme='dispensa')
    d.title(f"{_lesson(meta)} – {st['titolo']}" if meta.get('numero') else st['titolo'])
    bits = ['Dispensa di studio', f"lezione del {meta['data']}"]
    if st['docente']:
        bits.append(f"docente {st['docente']}")
    bits.append(f"fonti: registrazione della lezione (circa {round(meta['durata'] / 60)} min) "
                "e schermate della lezione")
    d.subtitle(' · '.join(bits))

    chapters = st['capitoli']
    d.h1('Mappa della lezione')
    _table(d, ['#', 'Argomento', "Peso per l'esame" if exam else 'Importanza'],
           [[str(n), c['titolo'], c['peso']] for n, c in enumerate(chapters, 1)])

    d.h1('Indice del video')
    d.para(f"Video: {meta['video']}. {st['nota_video']}")
    _table(d, ['Min. video', 'Argomento'],
           [[hm(i['min']), i['voce']] for i in sorted(st['indice'], key=lambda i: to_secs(i['min']))])
    d.remember(st['ricorda'])

    for n, (c, body) in enumerate(zip(chapters, caps), 1):
        d.h1(f"{n}. {c['titolo']} · min. {hm(c['inizio'])}")
        elements(d, body['elementi'])

    questions = [(q, n) for n, b in enumerate(caps, 1) for q in b['domande_aula']]
    if questions:
        d.h1('Domande fatte in aula' if exam else 'Domande dei partecipanti')
        _table(d, ['Min.', 'Domanda di un partecipante', 'Risposta del docente'],
               [[hm(q['min']), q['domanda'], q['risposta']] for q, _ in questions])

    todo = [(t, n) for n, b in enumerate(caps, 1) for t in b.get('saper_fare', [])] if exam else []
    if todo:
        d.h1('Cosa saper fare per la prova pratica')
        _table(d, ['Attività', 'Riferimento'], [[t, f'§{n}'] for t, n in todo])

    d.h1('Domande di autoverifica')
    for i, (q, _) in enumerate(((q, n) for n, b in enumerate(caps, 1) for q in b['autoverifica']), 1):
        d.question(i, q['domanda'], q['risposta'])

    d.note("Dispensa generata automaticamente da Ingeniotec Vox dalla registrazione della lezione: "
           "testi, schermate e verifiche delle fonti non sono stati rivisti da una persona. "
           "I minuti si riferiscono al video.")
    d.save(dst)
    return dst


def build_scheda(sc: dict, st: dict, meta: dict, dispensa_name: str, dst: Path, exam: bool = True) -> Path:
    d = Doc(header_text=_header(meta), theme='dispensa')
    d.title(f"Scheda di ripasso – {_lesson(meta)}" if meta.get('numero') else "Scheda di ripasso")
    when = f"{_lesson(meta)} ({meta['data']})" if meta.get('numero') else f"Lezione del {meta['data']}"
    bits = [meta.get('corso'), when, st['titolo'], f"per i dettagli vedi *{dispensa_name}*"]
    d.subtitle(' · '.join(b for b in bits if b))
    d.h1('In una frase')
    d.para(sc['in_una_frase'])
    for s in sc['sezioni']:
        d.h1(s['titolo'])
        elements(d, s['elementi'])
    if sc.get('crocette'):
        d.h1('Crocette: risposte secche')
        _table(d, ['Domanda', 'Risposta'], [[c['domanda'], c['risposta']] for c in sc['crocette']])
    if sc['trabocchetti']:
        d.h1('Trabocchetti tipici' if exam else 'Errori da evitare')
        d.bullets(sc['trabocchetti'])
    d.save(dst)
    return dst
