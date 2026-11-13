"""Finestra principale di Ingeniotec Vox."""

import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QActionGroup, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSpinBox,
                               QStackedWidget, QSystemTrayIcon, QToolButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from .. import REPO_URL, __version__
from . import nomi, runner, supporto
from .runner import ERRORS, PHASES, Runner
from .theme import THEMES, apply_style, col, qcol, saved_theme

VIDEO_FILTER = "Video (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;Tutti i file (*)"
STATI = {"completato": "Completato", "in corso": "Interrotto", "interrotto": "Interrotto",
         "limite": "In attesa (limite Claude)", "errore": "Errore"}


def asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "assets" / name


def default_out() -> Path:
    return Path.home() / "Documents" / "Ingeniotec Vox"


def fmt_elapsed(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class FileField(QWidget):
    """Casella di testo con pulsante «Scegli…» (file o cartella)."""
    changed = Signal(str)

    def __init__(self, title: str, filt: str = "", folder: bool = False, placeholder: str = ""):
        super().__init__()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self.changed)
        btn = QPushButton("Scegli…")
        btn.clicked.connect(self._pick)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)
        self.title, self.filt, self.folder = title, filt, folder

    def _pick(self) -> None:
        start = self.edit.text() or str(Path.home())
        if self.folder:
            p = QFileDialog.getExistingDirectory(self, self.title, start)
        else:
            p, _ = QFileDialog.getOpenFileName(self, self.title, str(Path(start).parent), self.filt)
        if p:
            self.edit.setText(str(Path(p)))

    def text(self) -> str:
        return self.edit.text().strip().strip('"')

    def setText(self, t: str) -> None:
        self.edit.setText(t)


class MainWindow(QMainWindow):
    checks_ready = Signal(list)
    update_ready = Signal(object, bool)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("Ingeniotec", "Vox")
        self.setWindowTitle(f"Ingeniotec Vox {__version__}")
        self.setWindowIcon(QIcon(str(asset("vox.ico"))))
        self.setAcceptDrops(True)
        self.runner: Runner | None = None
        self.job_dir: Path | None = None
        self.env_ok = False
        self.last_checks: list | None = None
        self.out_path = Path(self.settings.value("out", str(default_out())))
        self.tray: QSystemTrayIcon | None = None

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._header())
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.stack.addWidget(self._home_page())
        self.stack.addWidget(self._run_page())

        self.checks_ready.connect(self._show_checks)
        self.update_ready.connect(self._show_update)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.resize(980, 860)
        self._mode_changed()
        self.refresh_jobs()
        self.run_checks()
        self.check_updates(quiet=True)

    # ------------------------------------------------------------------ intestazione
    def _header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("header")
        bar.setFixedHeight(64)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 18, 0)
        logo = QLabel()
        pix = QPixmap(str(asset("logo_wordmark.png")))
        logo.setPixmap(pix.scaledToHeight(64, Qt.SmoothTransformation))
        lay.addWidget(logo)
        lay.addStretch(1)
        name = QLabel(f"<span style='font-size:20pt;font-weight:600'>Vox</span>"
                      f"<span style='font-size:9pt'>&nbsp;&nbsp;versione {__version__}</span>")
        name.setObjectName("headerText")
        lay.addWidget(name)
        lay.addSpacing(16)
        lay.addWidget(self._settings_button())
        return bar

    def _settings_button(self) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("headerButton")
        btn.setText("Impostazioni ▾")
        btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(btn)
        theme_menu = menu.addMenu("Tema")
        group = QActionGroup(theme_menu)
        current = saved_theme()
        for key, label in THEMES.items():
            act = theme_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == current)
            act.triggered.connect(lambda _=False, k=key: self.set_theme(k))
            group.addAction(act)
        menu.addAction("Cartella dei risultati…", self.choose_out)
        menu.addSeparator()
        menu.addAction("Segnala un problema…", self.report_problem)
        menu.addAction("Controlla aggiornamenti", lambda: self.check_updates(quiet=False))
        menu.addAction("Codice sorgente su GitHub", lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        menu.addSeparator()
        menu.addAction(f"Versione {__version__}", self.show_about)
        btn.setMenu(menu)
        return btn

    def set_theme(self, key: str) -> None:
        self.settings.setValue("tema", key)
        from PySide6.QtWidgets import QApplication
        old = {n: col(n) for n in ("muted", "ok", "error", "warn")}
        apply_style(QApplication.instance(), key)
        for lab in (self.status, self.run_title):   # testi già scritti con i colori del tema di prima
            text = lab.text()
            for n, c in old.items():
                text = text.replace(f"color:{c}", f"color:{col(n)}")
            lab.setText(text)
        if self.last_checks is not None:
            self._show_checks(self.last_checks)
        marks = {"✔": "ok", "▶": "text", "✖": "error"}
        for i in range(self.phase_list.count()):
            it = self.phase_list.item(i)
            it.setForeground(qcol(marks.get(it.text()[:1], "muted")))

    def show_about(self) -> None:
        from PySide6 import __version__ as qt_version
        from .main import data_dir
        QMessageBox.about(
            self, "Ingeniotec Vox",
            f"<b>Ingeniotec Vox</b> versione {__version__}<br><br>"
            f"Dispense e report da registrazioni video.<br>"
            f"Codice sorgente: <a href='{REPO_URL}'>{REPO_URL}</a><br><br>"
            f"<span style='color:{col('muted')}'>Python {sys.version.split()[0]} · PySide6 {qt_version}<br>"
            f"Programma: {runner.app_dir()}<br>Registro errori: {data_dir() / 'vox_gui.log'}</span>")

    # ------------------------------------------------------------------ supporto
    def report_problem(self) -> None:
        from .main import data_dir
        d = self.job_dir if (self.job_dir and self.stack.currentIndex() == 1) else self._selected_dir()
        job_log = d / "_lavoro" / "vox.log" if d else None
        context = ""
        if d:
            rec = runner.read_record(d) or {}
            context = f"lavoro {rec.get('tipo', '?')}, esito «{rec.get('esito', '?')}»"
            if rec.get("messaggio"):
                context += f": {rec['messaggio'][:200]}"
        if QMessageBox.question(
                self, "Segnala un problema",
                "Si apre GitHub con la segnalazione già compilata (versione ed errori del log). "
                "Serve un account GitHub: scrivi cosa stavi facendo, controlla che non ci siano dati "
                "riservati e premi «Create».\n\nAprire la pagina?") != QMessageBox.Yes:
            return
        QDesktopServices.openUrl(QUrl(supporto.issue_url(job_log, data_dir() / "vox_gui.log",
                                                         supporto.anonymize(context))))

    def check_updates(self, quiet: bool) -> None:
        def work():
            try:
                self.update_ready.emit(supporto.latest_release(), quiet)
            except Exception:
                self.update_ready.emit(False, quiet)
        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, info, quiet: bool) -> None:
        if info:
            self.update_banner.setText(
                f"<b>È disponibile la versione {info['versione']}</b> (questa è la {__version__}). "
                "Il nuovo setup è nella cartella di rete aziendale dei programmi: installalo sopra, "
                f"lavori e impostazioni restano. <a href='{info['url']}'>Novità</a>")
            self.update_banner.show()
            if not quiet:
                QDesktopServices.openUrl(QUrl(info["url"]))
        elif not quiet:
            if info is False:
                QMessageBox.warning(self, "Aggiornamenti", "Non riesco a contattare GitHub: "
                                    "controlla la connessione e riprova.")
            else:
                QMessageBox.information(self, "Aggiornamenti", f"Hai già l'ultima versione ({__version__}).")

    def notify_end(self, code: int, kind: str, elapsed: str) -> None:
        """Notifica di Windows e icona lampeggiante se la finestra non è in primo piano."""
        if kind == "annullato" or self.isActiveWindow():
            return
        from PySide6.QtWidgets import QApplication
        QApplication.alert(self)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self.tray is None:
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray.setToolTip("Ingeniotec Vox")
            self.tray.messageClicked.connect(self._bring_to_front)
            self.tray.activated.connect(lambda *_: self._bring_to_front())
        self.tray.show()
        what = "Il report" if self.rec["tipo"] == "call" else "La dispensa"
        if code == 0:
            self.tray.showMessage("Lavoro finito", f"{what} è pronto ({elapsed}).",
                                  QSystemTrayIcon.Information, 15000)
        else:
            self.tray.showMessage("Lavoro interrotto", ERRORS.get(kind, ERRORS["altro"])[:200],
                                  QSystemTrayIcon.Warning, 15000)

    def _bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self.tray:
            self.tray.hide()

    # ------------------------------------------------------------------ pagina iniziale
    def _home_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 14, 18, 14)

        # avviso di nuova versione (nascosto finché GitHub non ne indica una)
        self.update_banner = QLabel()
        self.update_banner.setObjectName("banner")
        self.update_banner.setTextFormat(Qt.RichText)
        self.update_banner.setOpenExternalLinks(True)
        self.update_banner.hide()
        lay.addWidget(self.update_banner)

        # controllo del PC
        self.env_box = QGroupBox("Controllo del PC")
        el = QVBoxLayout(self.env_box)
        self.env_label = QLabel("Controllo in corso…")
        self.env_label.setWordWrap(True)
        self.env_label.setTextFormat(Qt.RichText)
        el.addWidget(self.env_label)
        eb = QHBoxLayout()
        self.login_btn = QPushButton("Installa e collega Claude")
        self.login_btn.clicked.connect(self._claude_login)
        self.login_btn.hide()
        recheck = QPushButton("Ricontrolla")
        recheck.clicked.connect(self.run_checks)
        eb.addWidget(self.login_btn)
        eb.addStretch(1)
        eb.addWidget(recheck)
        el.addLayout(eb)
        lay.addWidget(self.env_box)

        # nuovo lavoro
        box = QGroupBox("Nuovo lavoro")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignRight)
        modes = QHBoxLayout()
        self.rb_call = QRadioButton("Report di una call")
        self.rb_lesson = QRadioButton("Dispense di una lezione")
        self.rb_call.setChecked(self.settings.value("modo", "call") == "call")
        self.rb_lesson.setChecked(not self.rb_call.isChecked())
        g = QButtonGroup(self)
        g.addButton(self.rb_call)
        g.addButton(self.rb_lesson)
        g.buttonToggled.connect(lambda *_: self._mode_changed())
        modes.addWidget(self.rb_call)
        modes.addWidget(self.rb_lesson)
        modes.addStretch(1)
        form.addRow("Cosa produrre:", modes)
        self.video = FileField("Scegli la registrazione", VIDEO_FILTER,
                               placeholder="Trascina qui il video o premi «Scegli…»")
        self.video.changed.connect(lambda *_: self._validate())
        form.addRow("Registrazione:", self.video)

        # opzioni call
        self.call_opts = QWidget()
        cl = QHBoxLayout(self.call_opts)
        cl.setContentsMargins(0, 0, 0, 0)
        self.cb_transcript = QCheckBox("Trascrizione completa in appendice all'allegato")
        cl.addWidget(self.cb_transcript)
        form.addRow("", self.call_opts)

        # opzioni lezione
        self.lesson_opts = QWidget()
        ll = QFormLayout(self.lesson_opts)
        ll.setContentsMargins(0, 0, 0, 0)
        self.profile = QComboBox()
        self.profile.addItem("Corso con esame (peso per l'esame, prova pratica, guida)", "esame")
        self.profile.addItem("Lezione generica (corso, webinar, presentazione)", "generico")
        self.profile.setCurrentIndex(int(self.settings.value("profilo_idx", 0)))
        self.profile.currentIndexChanged.connect(lambda *_: self._mode_changed())
        ll.addRow("Tipo di lezione:", self.profile)
        self.course = QLineEdit(self.settings.value("corso", ""))
        self.course.setPlaceholderText("es. Certificazione BIM")
        self.course.textChanged.connect(lambda *_: self._validate())
        ll.addRow("Corso:", self.course)
        self.number = QSpinBox()
        self.number.setRange(0, 99)
        self.number.setSpecialValueText("–")
        self.number.valueChanged.connect(lambda *_: self._validate())
        ll.addRow("Numero della lezione:", self.number)
        self.teacher = QLineEdit()
        self.teacher.setPlaceholderText("facoltativo: se vuoto si ricava dalla lezione")
        ll.addRow("Docente:", self.teacher)
        self.guide = FileField("Guida all'esame da aggiornare", "Documento Word (*.docx)",
                               placeholder="facoltativo: «00 - Guida all'esame….docx» del corso")
        self.guide.setText(self.settings.value("guida", ""))
        self.guide.changed.connect(lambda *_: self._validate())
        self.guide_row_label = QLabel("Guida all'esame:")
        ll.addRow(self.guide_row_label, self.guide)
        form.addRow(self.lesson_opts)

        start_row = QHBoxLayout()
        self.hint = QLabel()
        self.hint.setObjectName("hint")
        self.start_btn = QPushButton("Avvia")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start_new)
        start_row.addWidget(self.hint, 1)
        start_row.addWidget(self.start_btn)
        form.addRow(start_row)
        lay.addWidget(box)

        # lavori recenti
        jb = QGroupBox("Lavori recenti")
        jl = QVBoxLayout(jb)
        self.out_label = QLabel()
        self.out_label.setObjectName("muted")
        self.out_label.setWordWrap(True)
        jl.addWidget(self.out_label)
        self.jobs = QTreeWidget()
        self.jobs.setHeaderLabels(["Lavoro", "Tipo", "Ultimo aggiornamento", "Stato"])
        self.jobs.setRootIsDecorated(False)
        self.jobs.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.jobs.itemSelectionChanged.connect(self._job_selected)
        self.jobs.itemDoubleClicked.connect(lambda *_: self._open_job_folder())
        jl.addWidget(self.jobs)
        row = QHBoxLayout()
        self.btn_open = QPushButton("Apri cartella")
        self.btn_open.clicked.connect(self._open_job_folder)
        self.btn_resume = QPushButton("Riprendi")
        self.btn_resume.clicked.connect(self._resume_selected)
        self.btn_names = QPushButton("Correggi nomi…")
        self.btn_names.clicked.connect(lambda: self.correct_names(self._selected_dir()))
        self.btn_redo = QPushButton("Rifai da capo")
        self.btn_redo.clicked.connect(self._redo_selected)
        for b in (self.btn_open, self.btn_resume, self.btn_names, self.btn_redo):
            row.addWidget(b)
        row.addStretch(1)
        jl.addLayout(row)
        lay.addWidget(jb, 1)
        self._job_selected()
        return page

    def _mode_changed(self) -> None:
        call = self.rb_call.isChecked()
        self.call_opts.setVisible(call)
        self.lesson_opts.setVisible(not call)
        exam = self.profile.currentData() == "esame"
        self.guide.setVisible(exam)
        self.guide_row_label.setVisible(exam)
        self._validate()

    def _validate(self) -> bool:
        msg = ""
        v = self.video.text()
        if not v:
            msg = "Scegli la registrazione."
        elif not Path(v).is_file():
            msg = "Il file della registrazione non esiste."
        elif self.rb_lesson.isChecked() and self.profile.currentData() == "esame":
            if not self.course.text().strip() or not self.number.value():
                msg = "Per un corso con esame servono il corso e il numero della lezione."
            elif self.guide.text() and not Path(self.guide.text()).is_file():
                msg = "Il file della guida non esiste."
        if not msg and not self.env_ok:
            msg = "Il PC non è pronto: vedi «Controllo del PC»."
        self.hint.setText(msg)
        self.start_btn.setEnabled(not msg)
        return not msg

    # ------------------------------------------------------------------ controllo del PC
    def run_checks(self) -> None:
        self.env_label.setText("Controllo in corso…")
        self.env_ok = False
        self._validate()

        def work():
            from ..core import env_check
            try:
                res = env_check.run_all(self.out_root())
            except Exception as exc:  # non deve mai bloccare la finestra
                res = [env_check.Check("Controllo", False, f"Controllo non riuscito: {exc}")]
            self.checks_ready.emit(res)
        threading.Thread(target=work, daemon=True).start()

    def _show_checks(self, checks: list) -> None:
        self.last_checks = checks
        rows = []
        for ch in checks:
            mark = f"<span style='color:{col('ok')}'>✔</span>" if ch.ok else (
                f"<span style='color:{col('error')}'>✖</span>" if ch.blocking
                else f"<span style='color:{col('warn')}'>!</span>")
            rows.append(f"{mark}&nbsp; <b>{ch.name}</b>: {ch.message}")
        self.env_label.setText("<br>".join(rows))
        self.env_ok = all(ch.ok or not ch.blocking for ch in checks)
        claude_bad = any(ch.name == "Claude Code" and not ch.ok for ch in checks)
        self.login_btn.setVisible(claude_bad)
        self.env_box.setTitle("Controllo del PC" + ("" if self.env_ok else " – da sistemare"))
        self._validate()

    def _claude_login(self) -> None:
        from ..core.env_check import SETUP_SCRIPT
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(SETUP_SCRIPT)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        QMessageBox.information(self, "Installa e collega Claude",
                                "Si è aperta una finestra blu: se serve installa Claude Code, poi "
                                "apre il browser per accedere con "
                                "l'account aziendale, poi chiudila e premi «Ricontrolla».")

    # ------------------------------------------------------------------ lavori recenti
    def out_root(self) -> Path:
        return self.out_path

    def set_out(self, path) -> None:
        self.out_path = Path(path)
        self.settings.setValue("out", str(self.out_path))
        self.refresh_jobs()

    def choose_out(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Cartella dei risultati", str(self.out_root()))
        if p:
            self.set_out(Path(p))
            self.run_checks()   # lo spazio libero dipende dal disco scelto

    def refresh_jobs(self) -> None:
        self.out_label.setText(f"I risultati vanno in {self.out_root()} "
                               "(si cambia da Impostazioni → Cartella dei risultati).")
        self.jobs.clear()
        for d, rec in runner.recent_jobs(self.out_root()):
            when = rec.get("aggiornato", "").replace("T", " ")[:16]
            stato = STATI.get(rec.get("esito", ""), rec.get("esito", ""))
            it = QTreeWidgetItem([d.name, "Call" if rec["tipo"] == "call" else "Lezione", when, stato])
            it.setData(0, Qt.UserRole, str(d))
            it.setToolTip(0, rec.get("video", ""))
            if rec.get("messaggio"):
                it.setToolTip(3, rec["messaggio"])
            self.jobs.addTopLevelItem(it)
        for c in (1, 2, 3):
            self.jobs.resizeColumnToContents(c)
        self._job_selected()

    def _selected_dir(self) -> Path | None:
        it = self.jobs.currentItem()
        return Path(it.data(0, Qt.UserRole)) if it else None

    def _job_selected(self) -> None:
        d = self._selected_dir()
        rec = runner.read_record(d) if d else None
        self.btn_open.setEnabled(bool(d))
        self.btn_resume.setEnabled(bool(rec) and rec.get("esito") != "completato")
        self.btn_redo.setEnabled(bool(rec))
        self.btn_names.setEnabled(bool(rec) and rec["tipo"] == "call" and nomi.available(d))

    def _open_job_folder(self) -> None:
        d = self._selected_dir()
        if d:
            runner.open_path(d)

    def _check_video(self, rec: dict) -> bool:
        if Path(rec["video"]).is_file():
            return True
        QMessageBox.warning(self, "Registrazione non trovata",
                            f"Il video di questo lavoro non è più al suo posto:\n{rec['video']}\n\n"
                            "Rimettilo dov'era (o in una cartella con lo stesso percorso) e riprova.")
        return False

    def _resume_selected(self) -> None:
        d = self._selected_dir()
        rec = runner.read_record(d) if d else None
        if rec and self._check_video(rec):
            self.launch(d, rec, runner.job_args(rec, d))

    def _redo_selected(self) -> None:
        d = self._selected_dir()
        rec = runner.read_record(d) if d else None
        if not rec or not self._check_video(rec):
            return
        if QMessageBox.question(self, "Rifai da capo",
                                "Rifare tutto il lavoro, trascrizione compresa? I documenti attuali "
                                "verranno sostituiti.") == QMessageBox.Yes:
            self.launch(d, rec, runner.job_args(rec, d, redo="trascrizione"))

    def correct_names(self, d: Path | None) -> None:
        if not d or not nomi.available(d):
            return
        dlg = nomi.NamesDialog(d, self)
        if dlg.exec():
            rec = runner.read_record(d)
            if rec and self._check_video(rec):
                self.launch(d, rec, runner.job_args(rec, d, redo="blocchi"))

    # ------------------------------------------------------------------ avvio
    def _new_record(self) -> tuple[Path, dict]:
        """Cartella e parametri del nuovo lavoro, come li sceglierebbe la riga di comando."""
        from .. import pipeline_call
        video = Path(self.video.text()).resolve()
        meta = pipeline_call.call_meta(video)
        if self.rb_call.isChecked():
            name = pipeline_call.default_name(video)
            rec = {"tipo": "call", "video": str(video),
                   "opzioni": {"trascrizione": self.cb_transcript.isChecked()}}
        else:
            n = self.number.value() or None
            name = f"L{n}_{meta['iso']}" if n else f"Lezione_{meta['iso']}"
            exam = self.profile.currentData() == "esame"
            rec = {"tipo": "lezione", "video": str(video),
                   "opzioni": {"profilo": self.profile.currentData(), "corso": self.course.text().strip(),
                               "numero": n, "docente": self.teacher.text().strip() or None,
                               "guida": self.guide.text() if exam and self.guide.text() else None}}
        return self.out_root() / name, rec

    def start_new(self) -> None:
        if not self._validate():
            return
        d, rec = self._new_record()
        self.settings.setValue("modo", "call" if self.rb_call.isChecked() else "lezione")
        self.settings.setValue("corso", self.course.text().strip())
        self.settings.setValue("profilo_idx", self.profile.currentIndex())
        self.settings.setValue("guida", self.guide.text())
        redo = None
        old = runner.read_record(d)
        if old:
            same = Path(old.get("video", "")) == Path(rec["video"])
            box = QMessageBox(self)
            box.setWindowTitle("Lavoro già presente")
            box.setIcon(QMessageBox.Question)
            if same:
                box.setText(f"Questa registrazione è già stata elaborata in «{d.name}» "
                            f"({STATI.get(old.get('esito'), old.get('esito'))}).")
                box.setInformativeText("«Continua» riusa le fasi già fatte (rapido); «Rifai da capo» "
                                       "ripete tutto, trascrizione compresa.")
            else:
                box.setText(f"Esiste già un lavoro «{d.name}» con un'altra registrazione.")
                box.setInformativeText("«Rifai da capo» lo sostituisce con questa.")
            cont = box.addButton("Continua", QMessageBox.AcceptRole) if same else None
            again = box.addButton("Rifai da capo", QMessageBox.DestructiveRole)
            box.addButton("Annulla", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is again:
                redo = "trascrizione"
            elif cont is None or box.clickedButton() is not cont:
                return
        self.launch(d, rec, runner.job_args(rec, d, redo=redo))

    # ------------------------------------------------------------------ pagina di avanzamento
    def _run_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 14, 18, 14)
        self.run_title = QLabel()
        self.run_title.setObjectName("runTitle")
        self.run_title.setWordWrap(True)
        lay.addWidget(self.run_title)
        mid = QHBoxLayout()
        self.phase_list = QListWidget()
        self.phase_list.setFixedWidth(330)
        self.phase_list.setMinimumHeight(410)
        self.phase_list.setObjectName("phases")
        mid.addWidget(self.phase_list)
        right = QVBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("status")
        self.status.setTextFormat(Qt.RichText)
        right.addWidget(self.status)
        right.addWidget(QLabel("Fase in corso"))
        self.bar_phase = QProgressBar()
        right.addWidget(self.bar_phase)
        right.addWidget(QLabel("Totale (stima)"))
        self.bar_total = QProgressBar()
        right.addWidget(self.bar_total)
        self.elapsed = QLabel()
        right.addWidget(self.elapsed)
        right.addStretch(1)
        mid.addLayout(right, 1)
        lay.addLayout(mid)
        self.details_btn = QPushButton("Mostra dettagli")
        self.details_btn.setCheckable(True)
        self.details_btn.setMinimumWidth(150)
        self.details_btn.toggled.connect(self._toggle_details)
        lay.addWidget(self.details_btn, 0, Qt.AlignLeft)
        self.logview = QPlainTextEdit()
        self.logview.setReadOnly(True)
        self.logview.setMaximumBlockCount(5000)
        self.logview.hide()
        lay.addWidget(self.logview, 1)
        buttons = QHBoxLayout()
        self.btn_cancel = QPushButton("Annulla")
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_main = QPushButton("Apri il report")
        self.btn_main.setObjectName("primary")
        self.btn_main.clicked.connect(self._open_main)
        self.btn_folder = QPushButton("Apri cartella")
        self.btn_folder.clicked.connect(lambda: runner.open_path(self.job_dir))
        self.btn_fix = QPushButton("Correggi nomi…")
        self.btn_fix.clicked.connect(lambda: self.correct_names(self.job_dir))
        self.btn_log = QPushButton("Apri log")
        self.btn_log.clicked.connect(lambda: runner.open_path(self.job_dir / "_lavoro" / "vox.log"))
        self.btn_retry = QPushButton("Riprendi")
        self.btn_retry.clicked.connect(lambda: self.launch(self.job_dir, self.rec,
                                                           runner.job_args(self.rec, self.job_dir)))
        self.btn_report = QPushButton("Segnala un problema…")
        self.btn_report.clicked.connect(self.report_problem)
        self.btn_back = QPushButton("Torna all'inizio")
        self.btn_back.clicked.connect(self.go_home)
        for b in (self.btn_cancel, self.btn_main, self.btn_folder, self.btn_fix, self.btn_log,
                  self.btn_retry, self.btn_report):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_back)
        lay.addLayout(buttons)
        return page

    def _toggle_details(self, on: bool) -> None:
        self.logview.setVisible(on)
        self.details_btn.setText("Nascondi dettagli" if on else "Mostra dettagli")

    def launch(self, d: Path, rec: dict, args: list[str]) -> None:
        if self.runner and self.runner.running():
            return
        self.job_dir, self.rec = d, rec
        kind = rec["tipo"]
        phases = dict(PHASES[kind])
        if kind == "lezione" and not rec.get("opzioni", {}).get("guida"):
            phases.pop("guida")
        self.phases = phases
        self.done_phases: set[str] = set()
        self.cur_phase, self.cur_frac = None, 0.0
        self.files: list[str] = []
        self.phase_list.clear()
        for key, (label, _) in phases.items():
            it = QListWidgetItem(f"○   {label}")
            it.setData(Qt.UserRole, key)
            self.phase_list.addItem(it)
        what = "Report di call" if kind == "call" else "Dispense della lezione"
        self.run_title.setText(f"<b>{what}</b> – {Path(rec['video']).name}<br>"
                               f"<span style='color:{col('muted')}'>Risultati in {d}</span>")
        self.status.setText("Avvio…")
        self.logview.clear()
        self.bar_phase.setValue(0)
        self.bar_total.setValue(0)
        self._set_running(True)
        self.stack.setCurrentIndex(1)
        self.t0 = time.time()
        self.timer.start(1000)
        self._tick()
        self.runner = Runner(args, self)
        self.runner.line.connect(self._on_line)
        self.runner.phase.connect(self._on_phase)
        self.runner.phase_progress.connect(self._on_progress)
        self.runner.files.connect(lambda f: setattr(self, "files", f))
        self.runner.finished.connect(self._on_finished)
        runner.keep_awake(True)
        self.runner.start()

    def _set_running(self, on: bool) -> None:
        self.btn_cancel.setVisible(on)
        self.btn_back.setVisible(not on)
        for b in (self.btn_main, self.btn_folder, self.btn_fix, self.btn_log, self.btn_retry,
                  self.btn_report):
            b.setVisible(False)

    def _on_line(self, text: str) -> None:
        self.logview.appendPlainText(text)
        if text.strip() and self.cur_phase:
            label = self.phases.get(self.cur_phase, (self.cur_phase,))[0]
            self.status.setText(f"<b>{label}</b><br><span style='color:{col('muted')}'>{text.strip()[:160]}</span>")

    def _on_phase(self, key: str) -> None:
        if key not in self.phases:
            return
        keys = list(self.phases)
        for k in keys[:keys.index(key)]:
            self.done_phases.add(k)
        self.cur_phase, self.cur_frac = key, 0.0
        self.bar_phase.setValue(0)
        self.bar_phase.setRange(0, 0)   # indeterminata finché non arriva un avanzamento
        self._paint_phases()

    def _on_progress(self, f: float) -> None:
        self.cur_frac = max(0.0, min(f, 1.0))
        self.bar_phase.setRange(0, 100)
        self.bar_phase.setValue(int(self.cur_frac * 100))
        self._update_total()

    def _paint_phases(self) -> None:
        for i in range(self.phase_list.count()):
            it = self.phase_list.item(i)
            key = it.data(Qt.UserRole)
            label = self.phases[key][0]
            if key in self.done_phases:
                it.setText(f"✔   {label}")
                it.setForeground(qcol('ok'))
            elif key == self.cur_phase:
                it.setText(f"▶   {label}")
                it.setForeground(qcol('text'))
                font = it.font(); font.setBold(True); it.setFont(font)
                continue
            else:
                it.setText(f"○   {label}")
                it.setForeground(qcol('muted'))
            font = it.font(); font.setBold(False); it.setFont(font)
        self._update_total()

    def _update_total(self) -> None:
        total = sum(w for _, w in self.phases.values())
        done = sum(self.phases[k][1] for k in self.done_phases)
        if self.cur_phase in self.phases and self.cur_phase not in self.done_phases:
            done += self.phases[self.cur_phase][1] * self.cur_frac
        self.bar_total.setValue(int(100 * done / total))

    def _tick(self) -> None:
        if self.runner is None or self.runner.running():
            self.elapsed.setText(f"Tempo trascorso: {fmt_elapsed(time.time() - self.t0)}")

    def cancel(self) -> None:
        if self.runner and self.runner.running():
            if QMessageBox.question(self, "Annulla", "Interrompere il lavoro? Le fasi già concluse "
                                    "restano salvate e si può riprendere più tardi.") == QMessageBox.Yes:
                self.status.setText("Interruzione in corso…")
                self.runner.cancel()

    def _on_finished(self, code: int, kind: str, msg: str) -> None:
        self.timer.stop()
        runner.keep_awake(False)
        self._set_running(False)
        self.bar_phase.setRange(0, 100)
        elapsed = fmt_elapsed(time.time() - self.t0)
        if code == 0:
            self.done_phases = set(self.phases)
            self.cur_phase = None
            self._paint_phases()
            self.bar_phase.setValue(100)
            self.bar_total.setValue(100)
            self.status.setText(f"<b style='color:{col('ok')}'>Fatto in {elapsed}.</b><br>"
                                "I documenti (Word e PDF) sono nella cartella dei risultati.")
            self.btn_main.setText("Apri il report" if self.rec["tipo"] == "call" else "Apri la dispensa")
            self.btn_main.setVisible(bool(self._main_pdf()))
            self.btn_folder.setVisible(True)
            self.btn_fix.setVisible(self.rec["tipo"] == "call" and nomi.available(self.job_dir))
        else:
            if kind == "annullato":
                runner.write_record(self.job_dir, esito="interrotto", messaggio="Annullato dall'utente.")
                text = "<b>Lavoro annullato.</b> Le fasi già concluse sono salvate: «Riprendi» continua da lì."
            else:
                text = f"<b style='color:{col('error')}'>Lavoro interrotto.</b><br>{ERRORS.get(kind, ERRORS['altro'])}"
                if msg:
                    text += f"<br><span style='color:{col('muted')}'>Dettaglio: {msg[:400]}</span>"
            if self.cur_phase in self.phases:
                it = self.phase_list.item(list(self.phases).index(self.cur_phase))
                it.setText(f"✖   {self.phases[self.cur_phase][0]}")
                it.setForeground(qcol('error'))
            self.status.setText(text)
            self.btn_retry.setVisible(kind != "ambiente")
            self.btn_log.setVisible((self.job_dir / "_lavoro" / "vox.log").is_file())
            self.btn_folder.setVisible(self.job_dir.is_dir())
            self.btn_report.setVisible(kind != "annullato")
        self.refresh_jobs()
        self.notify_end(code, kind, elapsed)
        if kind == "limite" and self.runner.credits:
            self._ask_credits(msg)

    def _ask_credits(self, msg: str) -> None:
        """Fermo al limite del piano: aspettare che si azzeri o continuare a pagamento."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Limite d'uso di Claude")
        box.setText(msg)
        box.setInformativeText(
            "Puoi aspettare che il limite si azzeri e poi premere «Riprendi»: non costa nulla.\n\n"
            "Oppure continuare subito: da qui in poi il lavoro consuma i crediti a pagamento "
            "dell'account Claude (uso extra), addebitati in più rispetto all'abbonamento. "
            "Vox non può sapere in anticipo quanto costerà.")
        wait = box.addButton("Aspetta", QMessageBox.RejectRole)
        go = box.addButton("Continua a pagamento", QMessageBox.DestructiveRole)
        box.setDefaultButton(wait)
        box.setEscapeButton(wait)
        box.exec()
        if box.clickedButton() is go:
            self.launch(self.job_dir, self.rec, runner.job_args(self.rec, self.job_dir, credits=True))

    def _main_pdf(self) -> Path | None:
        pdfs = [Path(f) for f in self.files if f.lower().endswith(".pdf")]
        if not pdfs:
            rec = runner.read_record(self.job_dir) or {}
            pdfs = [Path(f) for f in rec.get("file", []) if f.lower().endswith(".pdf")]
        return pdfs[0] if pdfs else None

    def _open_main(self) -> None:
        p = self._main_pdf()
        if p and p.is_file():
            runner.open_path(p)

    def go_home(self) -> None:
        self.stack.setCurrentIndex(0)
        self.refresh_jobs()

    # ------------------------------------------------------------------ trascina e rilascia
    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls() and self.stack.currentIndex() == 0:
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            p = Path(urls[0])
            if p.suffix.lower() == ".docx" and self.rb_lesson.isChecked():
                self.guide.setText(str(p))
            else:
                self.video.setText(str(p))

    def closeEvent(self, e) -> None:
        if self.runner and self.runner.running():
            if QMessageBox.question(self, "Chiudi Vox", "C'è un lavoro in corso: chiudendo si interrompe "
                                    "(si può riprendere più tardi). Chiudere?") != QMessageBox.Yes:
                e.ignore()
                return
            self.runner.cancel()
            self.runner.proc.waitForFinished(5000)
            runner.write_record(self.job_dir, esito="interrotto", messaggio="Vox chiuso durante il lavoro.")
            runner.keep_awake(False)
        e.accept()


__all__ = ["MainWindow", "apply_style"]
