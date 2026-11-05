"""Tema della finestra: chiaro, scuro o come Windows (Impostazioni → Tema).

I colori usati nel codice (testo secondario, ok, errore, avviso…) passano da `col()`, così
cambiano insieme al tema. Il tema scelto è in QSettings («tema»: chiaro / scuro / sistema).
"""

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette

TEAL = "#43818D"
THEMES = {"chiaro": "Chiaro", "scuro": "Scuro", "sistema": "Come Windows"}

COLORS = {
    "chiaro": {"muted": "#808080", "ok": "#2e7d32", "error": "#c62828", "warn": "#ef6c00",
               "hint": "#8a5a00", "border": "#c9d6d9", "accent": TEAL, "accent_hover": "#356a74",
               "accent_off": "#a9c3c8", "text": "#000000", "banner": "#e3f0f2"},
    "scuro": {"muted": "#9aa4a6", "ok": "#81c784", "error": "#ef7a7a", "warn": "#ffb74d",
              "hint": "#e0b860", "border": "#46555a", "accent": "#4f97a5", "accent_hover": "#5fa9b7",
              "accent_off": "#3b5459", "text": "#e6e6e6", "banner": "#25393d"},
}

_current = "chiaro"


def saved_theme() -> str:
    t = QSettings("Ingeniotec", "Vox").value("tema", "chiaro")
    return t if t in THEMES else "chiaro"


def windows_dark() -> bool:
    """Impostazione di Windows «modalità app» (Qt la sovrascrive appena forziamo un tema)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def resolve(theme: str) -> str:
    """«sistema» → chiaro o scuro secondo Windows."""
    if theme != "sistema":
        return theme
    return "scuro" if windows_dark() else "chiaro"


def col(name: str) -> str:
    return COLORS[_current][name]


def qcol(name: str) -> QColor:
    return QColor(col(name))


def _dark_palette() -> QPalette:
    p = QPalette()
    base, window, text = QColor("#1f2426"), QColor("#2a3033"), QColor("#e6e6e6")
    disabled = QColor("#7d8689")
    for role, c in [(QPalette.Window, window), (QPalette.WindowText, text), (QPalette.Base, base),
                    (QPalette.AlternateBase, QColor("#262c2f")), (QPalette.ToolTipBase, window),
                    (QPalette.ToolTipText, text), (QPalette.Text, text), (QPalette.Button, QColor("#353c40")),
                    (QPalette.ButtonText, text), (QPalette.BrightText, QColor("#ff6b6b")),
                    (QPalette.Link, QColor("#7cc4d1")), (QPalette.LinkVisited, QColor("#a99ad6")),
                    (QPalette.Highlight, QColor(COLORS["scuro"]["accent"])),
                    (QPalette.HighlightedText, QColor("#ffffff")), (QPalette.PlaceholderText, disabled),
                    (QPalette.Light, QColor("#4a5256")), (QPalette.Midlight, QColor("#3d4448")),
                    (QPalette.Mid, QColor("#30363a")), (QPalette.Dark, QColor("#181c1e")),
                    (QPalette.Shadow, QColor("#000000"))]:
        p.setColor(role, c)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, disabled)
    return p


def stylesheet() -> str:
    c = COLORS[_current]
    return f"""
QFrame#header {{ background: {TEAL}; }}
QLabel#headerText {{ color: white; }}
QToolButton#headerButton {{ color: white; background: transparent; border: 1px solid rgba(255,255,255,0.55);
    border-radius: 4px; padding: 4px 10px; font-size: 10pt; }}
QToolButton#headerButton:hover {{ background: rgba(255,255,255,0.15); }}
QToolButton#headerButton::menu-indicator {{ image: none; }}
QGroupBox {{ font-weight: 600; border: 1px solid {c['border']}; border-radius: 6px; margin-top: 12px; padding: 10px 8px 8px 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {c['accent']}; }}
QPushButton {{ padding: 5px 12px; }}
QPushButton#primary {{ background: {c['accent']}; color: white; font-weight: 600; padding: 7px 26px; border-radius: 4px; border: none; }}
QPushButton#primary:disabled {{ background: {c['accent_off']}; color: {'#d8e4e6' if _current == 'scuro' else 'white'}; }}
QPushButton#primary:hover {{ background: {c['accent_hover']}; }}
QLabel#hint {{ color: {c['hint']}; }}
QLabel#muted {{ color: {c['muted']}; }}
QLabel#banner {{ background: {c['banner']}; border: 1px solid {c['accent']}; border-radius: 4px; padding: 8px 10px; }}
QLabel#runTitle {{ font-size: 11pt; }}
QListWidget#phases {{ font-size: 10pt; border: 1px solid {c['border']}; }}
QListWidget#phases::item {{ padding: 6px 4px; }}
QProgressBar {{ border: 1px solid {c['border']}; border-radius: 4px; text-align: center; height: 18px; }}
QProgressBar::chunk {{ background: {c['accent']}; }}
"""


def apply_style(app, theme: str | None = None) -> str:
    """Applica il tema (quello salvato se non indicato) e restituisce chiaro/scuro effettivo.
    Fusion con palette esplicita: con il tema di Windows i colori non si leggevano."""
    global _current
    theme = theme or saved_theme()
    _current = resolve(theme)
    try:  # senza questo Fusion segue Windows e mescola i due temi
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark if _current == "scuro" else Qt.ColorScheme.Light)
    except AttributeError:
        pass
    app.setStyle("Fusion")
    app.setPalette(_dark_palette() if _current == "scuro" else app.style().standardPalette())
    app.setStyleSheet(stylesheet())
    return _current
