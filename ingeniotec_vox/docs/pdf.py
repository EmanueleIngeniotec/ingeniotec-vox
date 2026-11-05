"""Esportazione .docx → PDF con Word (COM), in un'istanza dedicata.

`DispatchEx` apre un Word separato da quello eventualmente in uso dall'utente,
così chiuderlo non tocca i suoi documenti.
"""

from pathlib import Path

WD_FORMAT_PDF = 17


class PdfError(RuntimeError):
    pass


def export(docx_paths: list[Path], layout: bool = False, log=print,
           pdf_dir: Path | None = None) -> list[Path]:
    """PDF accanto a ogni .docx (o in `pdf_dir`). Con `layout` Word controlla prima
    l'impaginazione, corregge i blocchi spezzati e salva il .docx corretto."""
    import pythoncom
    import win32com.client

    from .impaginazione import check_and_fix

    pythoncom.CoInitialize()
    word = None
    out = []
    try:
        try:
            word = win32com.client.DispatchEx("Word.Application")
        except Exception as exc:
            raise PdfError("Impossibile avviare Microsoft Word per creare il PDF.") from exc
        word.Visible = False
        word.DisplayAlerts = 0
        for src in docx_paths:
            src = Path(src).resolve()
            # percorso assoluto: Word risolve quelli relativi rispetto alla propria cartella
            dst = (Path(pdf_dir).resolve() / src.name if pdf_dir else src).with_suffix(".pdf")
            doc = word.Documents.Open(str(src), ReadOnly=not layout, AddToRecentFiles=False)
            try:
                doc.Fields.Update()
                if layout:
                    log(f"  impaginazione di {src.name} …")
                    rep = check_and_fix(doc, log)
                    if rep["correzioni"]:
                        doc.Save()
                    log(f"  {src.name}: {len(rep['correzioni'])} correzioni, "
                        f"{len(rep['problemi'])} problemi rimasti")
                doc.SaveAs2(str(dst), FileFormat=WD_FORMAT_PDF)
            finally:
                doc.Close(SaveChanges=0)
            out.append(dst)
    finally:
        if word is not None:
            word.Quit(SaveChanges=0)
        pythoncom.CoUninitialize()
    return out


def page_count(pdf: Path) -> int:
    import pymupdf
    with pymupdf.open(str(pdf)) as d:
        return d.page_count


def contact_sheet(pdf: Path, dst: Path, dpi: int = 45) -> Path:
    """Pagine del PDF in fogli 4×2 per il controllo visivo dell'impaginazione."""
    import io

    import pymupdf
    from PIL import Image

    with pymupdf.open(str(pdf)) as doc:
        ims = [Image.open(io.BytesIO(p.get_pixmap(dpi=dpi).tobytes("png"))) for p in doc]
    w, h = ims[0].size
    rows = (len(ims) + 3) // 4
    sheet = Image.new("RGB", (4 * w + 30, rows * (h + 6) + 6), "grey")
    for j, im in enumerate(ims):
        sheet.paste(im, (6 + (j % 4) * (w + 6), 6 + (j // 4) * (h + 6)))
    sheet.save(dst)
    return dst
