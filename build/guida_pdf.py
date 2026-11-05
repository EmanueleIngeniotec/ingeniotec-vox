"""GUIDA.md -> dist\\installer\\Guida Ingeniotec Vox.pdf (HTML semplice aperto e salvato da Word).

Uso: .venv\\Scripts\\python build\\guida_pdf.py
Converte solo ciò che usa GUIDA.md: titoli, paragrafi, elenchi, tabelle, citazioni, **grassetto**, `codice`.
"""
import html
import re
import sys
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "GUIDA.md"
OUT = ROOT / "dist" / "installer" / "Guida Ingeniotec Vox.pdf"


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def to_html(md: str) -> str:
    out, lst, table = [], None, []

    def flush():
        nonlocal lst, table
        if lst:
            out.append(f"</{lst}>")
            lst = None
        if table:
            rows = [r for r in table if not (re.fullmatch(r"\|[\s|:-]+\|", r) and "-" in r)]
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            head = all(not c for c in cells[0])
            body = cells[1:] if head else cells
            if not head:
                out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells[0]) + "</tr>")
                body = cells[1:]
            else:
                out.append("<table>")
            out.extend(["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body])
            out.append("</table>")
            table = []

    for line in md.splitlines():
        s = line.rstrip()
        if s.startswith("|"):
            if lst:
                out.append(f"</{lst}>")
                lst = None
            table.append(s)
            continue
        if table:
            flush()
        m = re.match(r"(#{1,3}) (.*)", s)
        if m:
            flush()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            continue
        m = re.match(r"(\s*)(\d+\.|-) (.*)", s)
        if m:
            kind = "ol" if m.group(2)[0].isdigit() else "ul"
            if m.group(1) and lst:          # voce annidata: resa come riga rientrata
                out.append(f"<li style='margin-left:18pt;list-style:circle'>{inline(m.group(3))}</li>")
                continue
            if lst != kind:
                flush()
                out.append(f"<{kind}>")
                lst = kind
            out.append(f"<li>{inline(m.group(3))}</li>")
            continue
        flush()
        if s.startswith("> "):
            out.append(f"<p class='nota'>{inline(s[2:])}</p>")
        elif s:
            out.append(f"<p>{inline(s)}</p>")
    flush()
    css = ("body{font-family:Calibri;font-size:11pt} h1{color:#43818D;font-size:18pt} "
           "h2{color:#43818D;font-size:14pt;margin-top:14pt} table{border-collapse:collapse;width:100%} "
           "td,th{border:1px solid #999;padding:3pt;vertical-align:top;font-size:10pt} "
           "th{background:#E6F0F2} code{font-family:Consolas;font-size:9.5pt} "
           ".nota{border-left:3pt solid #43818D;padding-left:6pt;color:#333}")
    return f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(out)}</body></html>"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".html")
    tmp.write_text(to_html(SRC.read_text(encoding="utf-8")), encoding="utf-8")
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(tmp), ReadOnly=True)
        doc.ExportAsFixedFormat(str(OUT), 17)   # wdExportFormatPDF
        doc.Close(False)
    finally:
        word.Quit()
    tmp.unlink()
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
