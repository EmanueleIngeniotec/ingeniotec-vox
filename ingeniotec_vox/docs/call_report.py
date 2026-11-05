"""Composizione del report di una call: documento snello + allegato di dettaglio."""

from pathlib import Path

from .builder import TEXT_WIDTH, Doc

# quota del parlato attribuita oltre la quale la nota sull'attribuzione non serve
ATTRIBUZIONE_PIENA = 0.9


def secs(hms: str) -> float:
    try:
        parts = [float(x) for x in hms.strip().split(':')]
    except ValueError:
        return 0.0
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def hms(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}"


def duration_text(seconds: float) -> str:
    m = round(seconds / 60)
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def _w(*parts):
    """Larghezze di colonna in twip da proporzioni."""
    tot = sum(parts)
    ws = [TEXT_WIDTH * p // tot for p in parts]
    ws[-1] += TEXT_WIDTH - sum(ws)
    return ws


def _subtitle(meta: dict) -> str:
    bits = [f"Riunione del {meta['data']}"]
    if meta.get('ora'):
        bits[0] += f" alle {meta['ora']}"
    bits.append(f"durata {duration_text(meta['durata'])}")
    if meta.get('piattaforma'):
        bits.append(meta['piattaforma'])
    return ' · '.join(bits)


def _by_min(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda x: secs(x['min']))


def build_report(r: dict, meta: dict, dst: Path, allegato_name: str) -> Path:
    r = {**r, **{k: _by_min(r[k]) for k in ('decisioni', 'azioni', 'punti_aperti')}}
    d = Doc(header_text=f"Report riunione · {meta['data']}")
    d.title(r['titolo'])
    d.subtitle(_subtitle(meta))

    d.h1('Dati della riunione')
    persone = [p['nome'] + (f" ({p['ruolo']})" if p['ruolo'] else '') for p in r['partecipanti']]
    rows = [['Oggetto', r['oggetto']],
            ['Data e ora', meta['data'] + (f", ore {meta['ora']}" if meta.get('ora') else '')],
            ['Durata', duration_text(meta['durata'])],
            ['Partecipanti', ', '.join(persone) or '—'],
            ['Registrazione', meta['video']]]
    d.table(['Voce', 'Dettaglio'], rows, _w(22, 78), bold_first=True)

    d.h1('Sintesi')
    for s in r['sintesi']:
        d.para(s)

    d.h1('Decisioni')
    if r['decisioni']:
        d.table(['#', 'Decisione', 'Min.'],
                [[str(n), x['testo'], x['min']] for n, x in enumerate(r['decisioni'], 1)],
                _w(5, 83, 12))
    else:
        d.para('Nessuna decisione esplicita emersa dalla riunione.')

    d.h1('Azioni')
    if r['azioni']:
        d.table(['#', 'Chi', 'Cosa', 'Entro', 'Min.'],
                [[str(n), x['chi'], x['cosa'], x['quando'] or '—', x['min']]
                 for n, x in enumerate(r['azioni'], 1)],
                _w(5, 20, 51, 12, 12))
    else:
        d.para('Nessuna azione assegnata durante la riunione.')

    d.h1('Punti aperti')
    if r['punti_aperti']:
        d.bullets([f"{x['testo']} *(min. {x['min']})*" for x in r['punti_aperti']])
    else:
        d.para('Nessun punto aperto.')

    d.note(f"Report generato automaticamente da Ingeniotec Vox dalla registrazione della riunione. "
           f"I minuti si riferiscono al video. Argomenti nel dettaglio, interventi per persona, "
           f"schermate e glossario sono nell'allegato *{allegato_name}*.")
    d.save(dst)
    return dst


def build_allegato(r: dict, meta: dict, shots: list[dict], dst: Path,
                   transcript: dict | None = None, copertura: float | None = None) -> Path:
    """`copertura`: quota del parlato attribuita a una persona dalle voci (None: voci non separate)."""
    d = Doc(header_text=f"Allegato al report · {meta['data']}")
    d.title('Allegato – ' + r['titolo'])
    d.subtitle(_subtitle(meta) + ' · dettaglio degli argomenti, interventi e schermate')

    args = r['argomenti']
    by_arg = {i: [] for i in range(len(args))}
    for s in shots:
        idx = next((i for i, a in enumerate(args) if a['titolo'] == s['argomento']), None)
        if idx is None:   # argomento non riconosciuto: si sceglie quello in corso al minuto della schermata
            idx = max((i for i, a in enumerate(args) if secs(a['inizio']) <= s['t']), default=0)
        by_arg[idx].append(s)

    d.h1('Indice degli argomenti')
    d.table(['#', 'Argomento', 'Min. video'],
            [[str(n), a['titolo'], f"{a['inizio']} – {a['fine']}"] for n, a in enumerate(args, 1)],
            _w(5, 73, 22))

    d.h1('Argomenti')
    for n, a in enumerate(args, 1):
        d.h2(f"{n}. {a['titolo']} · min. {a['inizio']}")
        d.para(a['sintesi'])
        if a['punti']:
            d.bullets(a['punti'])
        for s in sorted(by_arg[n - 1], key=lambda s: s['t']):
            d.image(s['path'], f"Min. {hms(s['t'])} – {s['didascalia']}")

    if r['interventi']:
        d.h1('Interventi per persona')
        if copertura is None:
            d.note("L'attribuzione degli interventi è dedotta dal contenuto della conversazione "
                   "(nomi citati, ruoli, riferimenti): può contenere imprecisioni.")
        elif copertura < ATTRIBUZIONE_PIENA:
            d.note(f"Interventi attribuiti riconoscendo le voci e il riquadro evidenziato nel video. "
                   f"Circa il {round((1 - copertura) * 100)}% del parlato non è attribuito a una persona: "
                   f"quei contributi non compaiono in questa sezione.")
        for p in r['interventi']:
            d.h2(p['persona'])
            d.table(['Min.', 'Contributo'], [[c['min'], c['testo']] for c in p['contributi']],
                    _w(12, 88))

    terms = [t for t in r['termini'] if t['termine'].strip()]
    if terms:
        d.h1('Glossario')
        d.table(['Termine', 'Significato'],
                [[t['termine'], t['significato'] or '—'] for t in sorted(terms, key=lambda t: t['termine'].lower())],
                _w(25, 75), bold_first=True)

    if transcript:
        d.page_break()
        d.h1('Trascrizione automatica')
        d.note('Trascrizione automatica (Whisper), non rivista: può contenere errori su nomi e termini tecnici.')
        # paragrafi di circa un minuto: una riga per segmento Whisper raddoppierebbe le pagine
        groups, cur = [], []
        for s in transcript['segments']:
            if cur and (s['start'] - cur[0]['start'] >= 60 or s.get('persona') != cur[0].get('persona')):
                groups.append(cur); cur = []
            cur.append(s)
        if cur:
            groups.append(cur)
        for g in groups:
            p = d.d.add_paragraph(); d._spacing(p, after=60)
            d.runs(p, f"[{hms(g[0]['start'])}] ", size=8, color='7F7F7F', bold=True)
            if g[0].get('persona'):
                d.runs(p, f"{g[0]['persona']}: ", size=8, bold=True)
            d.runs(p, ' '.join(s['text'] for s in g), size=8)
    d.save(dst)
    return dst
