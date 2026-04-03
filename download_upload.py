import sys
import os
import re
import shlex
import platform
from datetime import datetime, timedelta
from contextlib import contextmanager

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QComboBox, QDateEdit, QDialog,
    QMessageBox, QFileDialog, QHeaderView, QAbstractItemView, QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor, QPalette

try:
    import paramiko
except ImportError:
    paramiko = None

# ---------------------------------------------------------------------------
# Connection constants
# ---------------------------------------------------------------------------
JUMP_USER = "gstefanakis"
JUMP_HOST = "adinsightscons.hat-analytics.net"
JUMP_PORT = "15930"
JUMP_DISPLAY = "proxy"            # short label shown in the UI

REMOTE_USER = "hat"
REMOTE_HOST = "localhost"

BATCHES_PATH = "/var/agenonlineservice/batches"

IS_WINDOWS = platform.system() == "Windows"

# Strict pattern for batch zip filenames:
# YYYYMMDDHHmm_<systemid>_<serial>.zip
ZIP_RE = re.compile(r"^(\d{12})_(\d+)_(\d+)\.zip$")

# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------
GREEN = "#27ae60"
GREEN_HOVER = "#2ecc71"
BLUE = "#2980b9"
BLUE_HOVER = "#3498db"
RED = "#e74c3c"
LABEL_FG = "#dcdde1"
MUTED_FG = "#7f8c8d"
HEADING_FG = "#f5f6fa"

# ---------------------------------------------------------------------------
# QSS theme stylesheets
# ---------------------------------------------------------------------------
_DARK_QSS = """
QMainWindow, QWidget#central {
    background-color: #2b2b2b;
}
QTabWidget::pane {
    background-color: #343638;
    border: 1px solid #444;
    border-radius: 6px;
}
QTabBar::tab {
    background: #3d3f41;
    color: #dcdde1;
    padding: 6px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #343638;
    color: #f5f6fa;
    font-weight: bold;
}
QFrame#connFrame, QFrame#sectionFrame {
    background-color: #343638;
    border-radius: 10px;
}
QFrame#innerFrame {
    background-color: #3d3f41;
    border-radius: 6px;
}
QLabel {
    color: #dcdde1;
    font-family: 'Segoe UI';
}
QLabel#muted {
    color: #7f8c8d;
}
QLabel#heading {
    color: #f5f6fa;
    font-weight: bold;
}
QLabel#authLabel {
    font-family: 'Segoe UI';
    font-size: 11px;
}
QLineEdit {
    background-color: #3d3f41;
    color: #dcdde1;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px 6px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QLineEdit:focus {
    border: 1px solid #3498db;
}
QPushButton {
    background-color: #2980b9;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3498db;
}
QPushButton:disabled {
    background-color: #555;
    color: #999;
}
QPushButton#gray {
    background-color: #666;
}
QPushButton#gray:hover {
    background-color: #777;
}
QPushButton#green {
    background-color: #27ae60;
}
QPushButton#green:hover {
    background-color: #2ecc71;
}
QProgressBar {
    background-color: #3d3f41;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    font-size: 0px;
}
QProgressBar::chunk {
    background-color: #2980b9;
    border-radius: 4px;
}
QTableWidget {
    background-color: #2b2b2b;
    color: #dcdde1;
    gridline-color: #444;
    border: none;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QTableWidget::item:selected {
    background-color: #3498db;
    color: white;
}
QHeaderView::section {
    background-color: #343638;
    color: #ecf0f1;
    font-family: 'Segoe UI';
    font-size: 13px;
    font-weight: bold;
    border: none;
    padding: 4px;
}
QHeaderView::section:hover {
    background-color: #3e4042;
}
QScrollBar:vertical {
    background: #2b2b2b;
    width: 14px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #343638;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar:horizontal {
    background: #2b2b2b;
    height: 14px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #343638;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0; width: 0;
}
QComboBox {
    background-color: #3d3f41;
    color: #dcdde1;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px 8px;
    font-family: 'Segoe UI';
    font-size: 11px;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #3d3f41;
    color: #dcdde1;
    selection-background-color: #3498db;
}
QDateEdit {
    background-color: #3d3f41;
    color: #dcdde1;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px 6px;
    font-family: 'Segoe UI';
    font-size: 11px;
}
QDateEdit::drop-down {
    border: none;
}
QCalendarWidget {
    background-color: #343638;
    color: #dcdde1;
}
"""

_LIGHT_QSS = """
QMainWindow, QWidget#central {
    background-color: #f0f0f0;
}
QTabWidget::pane {
    background-color: #d6d6d6;
    border: 1px solid #bbb;
    border-radius: 6px;
}
QTabBar::tab {
    background: #c0c0c0;
    color: #1a1a1a;
    padding: 6px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #d6d6d6;
    color: #1a1a1a;
    font-weight: bold;
}
QFrame#connFrame, QFrame#sectionFrame {
    background-color: #d6d6d6;
    border-radius: 10px;
}
QFrame#innerFrame {
    background-color: #c0c0c0;
    border-radius: 6px;
}
QLabel {
    color: #1a1a1a;
    font-family: 'Segoe UI';
}
QLabel#muted {
    color: #7f8c8d;
}
QLabel#heading {
    color: #1a1a1a;
    font-weight: bold;
}
QLabel#authLabel {
    font-family: 'Segoe UI';
    font-size: 11px;
}
QLineEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #aaa;
    border-radius: 4px;
    padding: 4px 6px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QLineEdit:focus {
    border: 1px solid #2980b9;
}
QPushButton {
    background-color: #2980b9;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3498db;
}
QPushButton:disabled {
    background-color: #bbb;
    color: #888;
}
QPushButton#gray {
    background-color: #999;
}
QPushButton#gray:hover {
    background-color: #aaa;
}
QPushButton#green {
    background-color: #27ae60;
}
QPushButton#green:hover {
    background-color: #2ecc71;
}
QProgressBar {
    background-color: #c0c0c0;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    font-size: 0px;
}
QProgressBar::chunk {
    background-color: #2980b9;
    border-radius: 4px;
}
QTableWidget {
    background-color: #f0f0f0;
    color: #1a1a1a;
    gridline-color: #bbb;
    border: none;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QTableWidget::item:selected {
    background-color: #2980b9;
    color: white;
}
QHeaderView::section {
    background-color: #d6d6d6;
    color: #1a1a1a;
    font-family: 'Segoe UI';
    font-size: 13px;
    font-weight: bold;
    border: none;
    padding: 4px;
}
QHeaderView::section:hover {
    background-color: #c0c0c0;
}
QScrollBar:vertical {
    background: #f0f0f0;
    width: 14px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #d6d6d6;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar:horizontal {
    background: #f0f0f0;
    height: 14px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #d6d6d6;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0; width: 0;
}
QComboBox {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #aaa;
    border-radius: 4px;
    padding: 4px 8px;
    font-family: 'Segoe UI';
    font-size: 11px;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1a1a1a;
    selection-background-color: #2980b9;
}
QDateEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #aaa;
    border-radius: 4px;
    padding: 4px 6px;
    font-family: 'Segoe UI';
    font-size: 11px;
}
QDateEdit::drop-down {
    border: none;
}
QCalendarWidget {
    background-color: #d6d6d6;
    color: #1a1a1a;
}
"""


# ---------------------------------------------------------------------------
# Password dialog (QDialog)
# ---------------------------------------------------------------------------
class PasswordDialog(QDialog):
    """Modal dialog asking for relay and local server passwords."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSH Authentication")
        self.setFixedSize(400, 300)
        self.setModal(True)
        self.result = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Enter SSH Passwords")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(12)

        # Relay server password
        relay_label = QLabel("Password for Relay Server:")
        relay_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(relay_label)

        relay_hint = QLabel(JUMP_DISPLAY)
        relay_hint.setObjectName("muted")
        relay_hint.setFont(QFont("Segoe UI", 10))
        layout.addWidget(relay_hint)

        self.relay_entry = QLineEdit()
        self.relay_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.relay_entry.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self.relay_entry)
        layout.addSpacing(10)

        # Local server password
        local_label = QLabel("Password for Local Server:")
        local_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(local_label)

        local_hint = QLabel(f"{REMOTE_USER}@{REMOTE_HOST}:<port>")
        local_hint.setObjectName("muted")
        local_hint.setFont(QFont("Segoe UI", 10))
        layout.addWidget(local_hint)

        self.local_entry = QLineEdit()
        self.local_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.local_entry.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self.local_entry)
        layout.addSpacing(16)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        connect_btn = QPushButton("Connect")
        connect_btn.setObjectName("green")
        connect_btn.setFixedWidth(140)
        connect_btn.clicked.connect(self._ok)
        btn_layout.addWidget(connect_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("gray")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self.relay_entry.setFocus()
        self.relay_entry.returnPressed.connect(
            lambda: self.local_entry.setFocus())
        self.local_entry.returnPressed.connect(self._ok)

    def _ok(self):
        relay = self.relay_entry.text().strip()
        local = self.local_entry.text().strip()
        if not relay or not local:
            QMessageBox.warning(self, "Missing Password",
                                "Both passwords are required.")
            return
        self.result = (relay, local)
        self.accept()


# ---------------------------------------------------------------------------
# Worker threads (QThread subclasses with signals)
# ---------------------------------------------------------------------------
class UploadWorker(QThread):
    progress = pyqtSignal(float)
    status = pyqtSignal(str)
    error = pyqtSignal(str, str)       # (title, message)
    success = pyqtSignal(str)          # message
    clear_passwords = pyqtSignal()
    finished_work = pyqtSignal()

    def __init__(self, app, local_file, remote_dest):
        super().__init__()
        self._app = app
        self._local_file = local_file
        self._remote_dest = remote_dest

    def run(self):
        try:
            with self._app._open_connection() as ssh:
                sftp = ssh.open_sftp()
                try:
                    remote_dest = self._remote_dest
                    if "/" in remote_dest:
                        remote_dir = remote_dest.rsplit("/", 1)[0]
                    else:
                        remote_dir = ""
                    if remote_dir:
                        try:
                            sftp.stat(remote_dir)
                        except FileNotFoundError:
                            raise IOError(
                                f"Remote directory does not exist:\n"
                                f"{remote_dir}\n\n"
                                f"Create it on the server first.")

                    def _cb(transferred, total):
                        pct = transferred / total * 100 if total > 0 else 0
                        self.progress.emit(pct)
                        self.status.emit(f"Uploading... {pct:.0f}%")

                    sftp.put(self._local_file, remote_dest, callback=_cb)
                finally:
                    sftp.close()

            self.progress.emit(100)
            self.success.emit(f"Uploaded to:\n{self._remote_dest}")
            self.status.emit("Upload complete")

        except ConnectionError as exc:
            self.clear_passwords.emit()
            self.error.emit("Connection Error", str(exc))
            self.status.emit("Upload failed")
            self.progress.emit(0)
        except Exception as exc:
            self.error.emit("Upload Error", str(exc))
            self.status.emit("Upload failed")
            self.progress.emit(0)
        finally:
            self.finished_work.emit()


class DownloadWorker(QThread):
    progress = pyqtSignal(float)
    status = pyqtSignal(str)
    error = pyqtSignal(str, str)
    success = pyqtSignal(str)
    clear_passwords = pyqtSignal()
    finished_work = pyqtSignal()

    def __init__(self, app, remote_src, local_file):
        super().__init__()
        self._app = app
        self._remote_src = remote_src
        self._local_file = local_file

    def run(self):
        try:
            with self._app._open_connection() as ssh:
                sftp = ssh.open_sftp()
                try:
                    try:
                        sftp.stat(self._remote_src)
                    except FileNotFoundError:
                        raise IOError(
                            f"Remote file not found:\n{self._remote_src}")

                    def _cb(transferred, total):
                        pct = transferred / total * 100 if total > 0 else 0
                        self.progress.emit(pct)
                        self.status.emit(f"Downloading... {pct:.0f}%")

                    sftp.get(self._remote_src, self._local_file, callback=_cb)
                finally:
                    sftp.close()

            self.progress.emit(100)
            self.success.emit(f"Downloaded to:\n{self._local_file}")
            self.status.emit("Download complete")

        except ConnectionError as exc:
            self.clear_passwords.emit()
            self.error.emit("Connection Error", str(exc))
            self.status.emit("Download failed")
            self.progress.emit(0)
        except Exception as exc:
            self.error.emit("Download Error", str(exc))
            self.status.emit("Download failed")
            self.progress.emit(0)
        finally:
            self.finished_work.emit()


class SearchWorker(QThread):
    progress = pyqtSignal(float)
    status = pyqtSignal(str)
    error = pyqtSignal(str, str)
    results_ready = pyqtSignal(list)
    clear_passwords = pyqtSignal()
    finished_work = pyqtSignal()

    def __init__(self, app, sys_ids, serial_filter, from_dt, to_dt):
        super().__init__()
        self._app = app
        self._sys_ids = sys_ids
        self._serial_filter = serial_filter
        self._from_dt = from_dt
        self._to_dt = to_dt

    def run(self):
        try:
            with self._app._open_connection() as ssh:
                self.status.emit("Searching for zip files...")

                find_cmd = (
                    f"find {shlex.quote(BATCHES_PATH)} "
                    f"-type f -name '*.zip' 2>/dev/null"
                )
                out, err, code = self._app._ssh_exec(
                    ssh, find_cmd, timeout=60)

                if code != 0 and not out.strip():
                    self.error.emit("SSH Error", err or "Command failed.")
                    return

                lines = [ln for ln in out.strip().splitlines() if ln.strip()]

                matches = []
                for line in lines:
                    info = App._parse_zip(line)
                    if info is None:
                        continue
                    if info["system_id"] not in self._sys_ids:
                        continue
                    if (self._serial_filter and
                            info["serial"] != self._serial_filter):
                        continue
                    if not (self._from_dt <= info["dt"] <= self._to_dt):
                        continue
                    matches.append(info)

                matches.sort(key=lambda x: (x["dt"], x["system_id"]))
                self.results_ready.emit(matches)

        except ConnectionError as exc:
            self.clear_passwords.emit()
            self.error.emit("Connection Error", str(exc))
            self.status.emit("Search failed")
        except Exception as exc:
            self.error.emit("Error", str(exc))
            self.status.emit("Search failed")
        finally:
            self.finished_work.emit()


class BatchDownloadWorker(QThread):
    progress = pyqtSignal(float)
    status = pyqtSignal(str)
    error = pyqtSignal(str, str)
    success = pyqtSignal(str)
    clear_passwords = pyqtSignal()
    finished_work = pyqtSignal()

    def __init__(self, app, paths, dest):
        super().__init__()
        self._app = app
        self._paths = paths
        self._dest = dest

    def run(self):
        try:
            with self._app._open_connection() as ssh:
                sftp = ssh.open_sftp()
                try:
                    total = len(self._paths)
                    for idx, remote_path in enumerate(self._paths, 1):
                        fname = os.path.basename(remote_path)
                        local_file = os.path.join(self._dest, fname)

                        base, ext = os.path.splitext(fname)
                        counter = 1
                        while os.path.exists(local_file):
                            local_file = os.path.join(
                                self._dest, f"{base}_{counter}{ext}")
                            counter += 1

                        self.status.emit(
                            f"Downloading {idx}/{total}: {fname}")
                        self.progress.emit((idx - 1) / total * 100)

                        sftp.get(remote_path, local_file)

                    self.progress.emit(100)
                finally:
                    sftp.close()

            self.success.emit(
                f"Downloaded {len(self._paths)} file(s) to:\n{self._dest}")
            self.status.emit("Download complete")

        except ConnectionError as exc:
            self.clear_passwords.emit()
            self.error.emit("Connection Error", str(exc))
            self.status.emit("Download failed")
            self.progress.emit(0)
        except Exception as exc:
            self.error.emit("Error", str(exc))
            self.status.emit("Download failed")
            self.progress.emit(0)
        finally:
            self.finished_work.emit()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCP Tool \u2014 Upload / Download / Batch Search")
        self.resize(940, 760)
        self.setMinimumSize(700, 560)

        self._current_mode = "dark"
        self._active_worker = None

        # -- passwords (stored in memory only) --------------------------------
        self._relay_pw = None
        self._local_pw = None

        # -- central widget ---------------------------------------------------
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 10, 12, 8)
        main_layout.setSpacing(4)

        # -- connection bar ---------------------------------------------------
        conn_frame = QFrame()
        conn_frame.setObjectName("connFrame")
        conn_layout = QVBoxLayout(conn_frame)
        conn_layout.setContentsMargins(12, 10, 12, 8)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        port_label = QLabel("Remote Port:")
        port_label.setFont(QFont("Segoe UI", 12))
        top_row.addWidget(port_label)

        self.remote_port_edit = QLineEdit("39022")
        self.remote_port_edit.setFixedWidth(80)
        self.remote_port_edit.setFont(QFont("Segoe UI", 12))
        top_row.addWidget(self.remote_port_edit)
        top_row.addSpacing(6)

        login_btn = QPushButton("Login")
        login_btn.setFixedWidth(110)
        login_btn.clicked.connect(self._prompt_passwords)
        top_row.addWidget(login_btn)

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("gray")
        logout_btn.setFixedWidth(90)
        logout_btn.clicked.connect(self._logout)
        top_row.addWidget(logout_btn)
        top_row.addSpacing(6)

        self._auth_label = QLabel("Not authenticated")
        self._auth_label.setObjectName("authLabel")
        self._auth_label.setFont(QFont("Segoe UI", 11))
        self._auth_label.setStyleSheet(f"color: {RED};")
        top_row.addWidget(self._auth_label)

        top_row.addStretch()

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Dark", "Light"])
        self._theme_combo.setFixedWidth(90)
        self._theme_combo.currentTextChanged.connect(self._change_theme)
        top_row.addWidget(self._theme_combo)

        conn_layout.addLayout(top_row)

        info_text = (f"Jump: {JUMP_DISPLAY}  -->  "
                     f"{REMOTE_USER}@{REMOTE_HOST}:<port>")
        info_label = QLabel(info_text)
        info_label.setObjectName("muted")
        info_label.setFont(QFont("Segoe UI", 9))
        conn_layout.addWidget(info_label)

        main_layout.addWidget(conn_frame)

        # -- tabview ----------------------------------------------------------
        self.tabview = QTabWidget()
        main_layout.addWidget(self.tabview, stretch=1)

        self._build_upload_download_tab()
        self._build_batch_search_tab()

        # -- progress bar + status at bottom ----------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("muted")
        self.status_label.setFont(QFont("Segoe UI", 10))
        main_layout.addWidget(self.status_label)

        # -- apply dark theme -------------------------------------------------
        self.setStyleSheet(_DARK_QSS)

    # -----------------------------------------------------------------------
    # Theme switching
    # -----------------------------------------------------------------------
    def _change_theme(self, choice):
        mode = choice.lower()
        if mode == self._current_mode:
            return
        self._current_mode = mode
        if mode == "dark":
            self.setStyleSheet(_DARK_QSS)
        else:
            self.setStyleSheet(_LIGHT_QSS)

    # -----------------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------------
    def _prompt_passwords(self):
        dlg = PasswordDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result:
            self._relay_pw, self._local_pw = dlg.result
            self._auth_label.setText("Authenticated")
            self._auth_label.setStyleSheet(f"color: {GREEN};")

    def _ensure_passwords(self):
        if self._relay_pw and self._local_pw:
            return True
        self._prompt_passwords()
        return bool(self._relay_pw and self._local_pw)

    def _logout(self):
        self._clear_passwords()
        self.status_label.setText("Logged out")

    def _clear_passwords(self):
        self._relay_pw = None
        self._local_pw = None
        self._auth_label.setText("Not authenticated")
        self._auth_label.setStyleSheet(f"color: {RED};")

    def closeEvent(self, event):
        self._clear_passwords()
        event.accept()

    # -----------------------------------------------------------------------
    # Path helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _normalize_path(path):
        """Strip surrounding quotes and whitespace from user-entered paths."""
        path = path.strip()
        if len(path) >= 2:
            if (path[0] == '"' and path[-1] == '"') or \
               (path[0] == "'" and path[-1] == "'"):
                path = path[1:-1].strip()
        return path

    # -----------------------------------------------------------------------
    # SSH connection (paramiko)
    # -----------------------------------------------------------------------
    @contextmanager
    def _open_connection(self):
        """Context manager yielding a paramiko SSHClient connected to the
        remote server through the jump host."""
        jump = paramiko.SSHClient()
        jump.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        remote = paramiko.SSHClient()
        remote.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            try:
                jump.connect(
                    JUMP_HOST,
                    port=int(JUMP_PORT),
                    username=JUMP_USER,
                    password=self._relay_pw,
                    timeout=15,
                    banner_timeout=15,
                    allow_agent=False,
                    look_for_keys=False,
                )
            except paramiko.AuthenticationException:
                raise ConnectionError(
                    "Relay server authentication failed.\n"
                    "Please check the relay password.")
            except Exception as exc:
                raise ConnectionError(
                    f"Cannot reach relay server:\n{exc}")

            try:
                transport = jump.get_transport()
                transport.set_keepalive(30)
                channel = transport.open_channel(
                    "direct-tcpip",
                    (REMOTE_HOST, int(self.remote_port_edit.text())),
                    ("127.0.0.1", 0),
                )
            except Exception as exc:
                raise ConnectionError(
                    f"Cannot open tunnel to local server:\n{exc}")

            try:
                remote.connect(
                    REMOTE_HOST,
                    username=REMOTE_USER,
                    password=self._local_pw,
                    sock=channel,
                    timeout=15,
                    banner_timeout=15,
                    allow_agent=False,
                    look_for_keys=False,
                )
            except paramiko.AuthenticationException:
                raise ConnectionError(
                    "Local server authentication failed.\n"
                    "Please check the local server password.")
            except Exception as exc:
                raise ConnectionError(
                    f"Cannot connect to local server:\n{exc}")

            remote_transport = remote.get_transport()
            if remote_transport:
                remote_transport.set_keepalive(30)

            yield remote

        finally:
            try:
                remote.close()
            except Exception:
                pass
            try:
                jump.close()
            except Exception:
                pass

    def _ssh_exec(self, ssh_client, cmd, timeout=60):
        _stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return out, err, code

    # -----------------------------------------------------------------------
    # Progress helpers
    # -----------------------------------------------------------------------
    def _set_progress(self, pct):
        self.progress_bar.setValue(int(pct))

    # -----------------------------------------------------------------------
    # Tab 1 – Upload / Download
    # -----------------------------------------------------------------------
    def _build_upload_download_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Remote path section
        pf = QFrame()
        pf.setObjectName("sectionFrame")
        pf_layout = QVBoxLayout(pf)
        pf_layout.setContentsMargins(12, 8, 12, 8)

        rp_heading = QLabel("Remote Linux Path")
        rp_heading.setObjectName("heading")
        rp_heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        pf_layout.addWidget(rp_heading)

        self.remote_path_edit = QLineEdit(
            "/home/hat/Downloads/pythonscripts/")
        self.remote_path_edit.setFont(QFont("Segoe UI", 12))
        pf_layout.addWidget(self.remote_path_edit)

        rp_hint = QLabel("Upload: destination dir ending with /  "
                         "|  Download: full file path")
        rp_hint.setObjectName("muted")
        rp_hint.setFont(QFont("Segoe UI", 10))
        pf_layout.addWidget(rp_hint)

        layout.addWidget(pf)

        # Upload section
        uf = QFrame()
        uf.setObjectName("sectionFrame")
        uf_layout = QVBoxLayout(uf)
        uf_layout.setContentsMargins(12, 8, 12, 10)

        ul_heading = QLabel("Upload")
        ul_heading.setObjectName("heading")
        ul_heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        uf_layout.addWidget(ul_heading)

        upload_row = QFrame()
        upload_row.setObjectName("innerFrame")
        ur_layout = QHBoxLayout(upload_row)
        ur_layout.setContentsMargins(8, 6, 8, 6)

        ur_layout.addWidget(QLabel("Local File:"))
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setFont(QFont("Segoe UI", 11))
        ur_layout.addWidget(self.file_path_edit, stretch=1)
        browse_file_btn = QPushButton("Browse")
        browse_file_btn.setFixedWidth(110)
        browse_file_btn.clicked.connect(self._browse_file)
        ur_layout.addWidget(browse_file_btn)

        uf_layout.addWidget(upload_row)

        upload_btn_row = QHBoxLayout()
        upload_btn_row.addStretch()
        self._upload_btn = QPushButton("UPLOAD")
        self._upload_btn.setObjectName("green")
        self._upload_btn.setFixedSize(180, 36)
        self._upload_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._upload_btn.clicked.connect(self._upload)
        upload_btn_row.addWidget(self._upload_btn)
        upload_btn_row.addStretch()
        uf_layout.addLayout(upload_btn_row)

        layout.addWidget(uf)

        # Download section
        df = QFrame()
        df.setObjectName("sectionFrame")
        df_layout = QVBoxLayout(df)
        df_layout.setContentsMargins(12, 8, 12, 10)

        dl_heading = QLabel("Download")
        dl_heading.setObjectName("heading")
        dl_heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        df_layout.addWidget(dl_heading)

        dl_row = QFrame()
        dl_row.setObjectName("innerFrame")
        dlr_layout = QHBoxLayout(dl_row)
        dlr_layout.setContentsMargins(8, 6, 8, 6)

        dlr_layout.addWidget(QLabel("Save To:"))
        self.local_path_edit = QLineEdit()
        self.local_path_edit.setFont(QFont("Segoe UI", 11))
        dlr_layout.addWidget(self.local_path_edit, stretch=1)
        browse_folder_btn = QPushButton("Browse")
        browse_folder_btn.setFixedWidth(110)
        browse_folder_btn.clicked.connect(self._browse_folder)
        dlr_layout.addWidget(browse_folder_btn)

        df_layout.addWidget(dl_row)

        dl_btn_row = QHBoxLayout()
        dl_btn_row.addStretch()
        self._download_btn = QPushButton("DOWNLOAD")
        self._download_btn.setFixedSize(180, 36)
        self._download_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._download_btn.clicked.connect(self._download)
        dl_btn_row.addWidget(self._download_btn)
        dl_btn_row.addStretch()
        df_layout.addLayout(dl_btn_row)

        layout.addWidget(df)
        layout.addStretch()

        self.tabview.addTab(tab, "Upload / Download")

    # -----------------------------------------------------------------------
    # Tab 2 – Batch Search
    # -----------------------------------------------------------------------
    def _build_batch_search_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # -- search criteria --------------------------------------------------
        cf = QFrame()
        cf.setObjectName("sectionFrame")
        cf_layout = QVBoxLayout(cf)
        cf_layout.setContentsMargins(12, 8, 12, 10)

        sc_heading = QLabel("Search Criteria")
        sc_heading.setObjectName("heading")
        sc_heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        cf_layout.addWidget(sc_heading)

        # Date / Time - FROM row
        dt_frame = QFrame()
        dt_frame.setObjectName("innerFrame")
        dt_layout = QVBoxLayout(dt_frame)
        dt_layout.setContentsMargins(8, 6, 8, 6)

        from_row = QHBoxLayout()
        from_lbl = QLabel("From:")
        from_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        from_lbl.setFixedWidth(50)
        from_row.addWidget(from_lbl)

        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setDate(QDate.currentDate())
        self.from_date.setFont(QFont("Segoe UI", 11))
        self.from_date.setFixedWidth(120)
        from_row.addWidget(self.from_date)

        self._from_hour_edit = QLineEdit("00")
        self._from_hour_edit.setFixedWidth(42)
        self._from_hour_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._from_hour_edit.setFont(QFont("Segoe UI", 11))
        from_row.addWidget(self._from_hour_edit)
        from_row.addWidget(QLabel(":"))
        self._from_min_edit = QLineEdit("00")
        self._from_min_edit.setFixedWidth(42)
        self._from_min_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._from_min_edit.setFont(QFont("Segoe UI", 11))
        from_row.addWidget(self._from_min_edit)
        from_row.addStretch()

        dt_layout.addLayout(from_row)

        # TO row
        to_row = QHBoxLayout()
        to_lbl = QLabel("To:")
        to_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        to_lbl.setFixedWidth(50)
        to_row.addWidget(to_lbl)

        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setDate(QDate.currentDate())
        self.to_date.setFont(QFont("Segoe UI", 11))
        self.to_date.setFixedWidth(120)
        to_row.addWidget(self.to_date)

        self._to_hour_edit = QLineEdit("23")
        self._to_hour_edit.setFixedWidth(42)
        self._to_hour_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._to_hour_edit.setFont(QFont("Segoe UI", 11))
        to_row.addWidget(self._to_hour_edit)
        to_row.addWidget(QLabel(":"))
        self._to_min_edit = QLineEdit("59")
        self._to_min_edit.setFixedWidth(42)
        self._to_min_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._to_min_edit.setFont(QFont("Segoe UI", 11))
        to_row.addWidget(self._to_min_edit)

        plus1h_btn = QPushButton("+1 h")
        plus1h_btn.setObjectName("gray")
        plus1h_btn.setFixedWidth(60)
        plus1h_btn.clicked.connect(self._set_to_plus_one_hour)
        to_row.addWidget(plus1h_btn)
        to_row.addStretch()

        dt_layout.addLayout(to_row)
        cf_layout.addWidget(dt_frame)

        # System IDs
        id_row_frame = QFrame()
        id_row_frame.setObjectName("innerFrame")
        id_layout = QHBoxLayout(id_row_frame)
        id_layout.setContentsMargins(8, 6, 8, 6)
        id_label = QLabel("System IDs*:")
        id_label.setFont(QFont("Segoe UI", 11))
        id_layout.addWidget(id_label)
        self.system_ids_edit = QLineEdit()
        self.system_ids_edit.setFont(QFont("Segoe UI", 11))
        id_layout.addWidget(self.system_ids_edit, stretch=1)
        id_hint = QLabel("comma-separated")
        id_hint.setObjectName("muted")
        id_hint.setFont(QFont("Segoe UI", 10))
        id_layout.addWidget(id_hint)
        cf_layout.addWidget(id_row_frame)

        # Serial number
        sn_row_frame = QFrame()
        sn_row_frame.setObjectName("innerFrame")
        sn_layout = QHBoxLayout(sn_row_frame)
        sn_layout.setContentsMargins(8, 6, 8, 6)
        sn_label = QLabel("Serial Number:")
        sn_label.setFont(QFont("Segoe UI", 11))
        sn_layout.addWidget(sn_label)
        self.serial_edit = QLineEdit()
        self.serial_edit.setFont(QFont("Segoe UI", 11))
        sn_layout.addWidget(self.serial_edit, stretch=1)
        sn_hint = QLabel("optional")
        sn_hint.setObjectName("muted")
        sn_hint.setFont(QFont("Segoe UI", 10))
        sn_layout.addWidget(sn_hint)
        cf_layout.addWidget(sn_row_frame)

        # Search button row
        btn_row_frame = QFrame()
        btn_row_frame.setObjectName("innerFrame")
        br_layout = QHBoxLayout(btn_row_frame)
        br_layout.setContentsMargins(8, 6, 8, 6)
        self._search_btn = QPushButton("Search")
        self._search_btn.setFixedWidth(140)
        self._search_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._search_btn.clicked.connect(self._do_search)
        br_layout.addWidget(self._search_btn)
        self._result_count_label = QLabel("")
        self._result_count_label.setFont(
            QFont("Segoe UI", 11, QFont.Weight.Bold))
        br_layout.addWidget(self._result_count_label)
        br_layout.addStretch()
        cf_layout.addWidget(btn_row_frame)

        layout.addWidget(cf)

        # -- results (QTableWidget) -------------------------------------------
        rf = QFrame()
        rf.setObjectName("sectionFrame")
        rf_layout = QVBoxLayout(rf)
        rf_layout.setContentsMargins(12, 8, 12, 8)

        res_heading = QLabel("Results")
        res_heading.setObjectName("heading")
        res_heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        rf_layout.addWidget(res_heading)

        self._col_names = ["Filename", "Folder", "Date / Time",
                           "System ID", "Serial #", "Server Path"]
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(self._col_names)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 90)

        rf_layout.addWidget(self.table, stretch=1)
        layout.addWidget(rf, stretch=1)

        # -- actions bar ------------------------------------------------------
        af = QFrame()
        af.setObjectName("connFrame")
        af_layout = QHBoxLayout(af)
        af_layout.setContentsMargins(8, 6, 8, 6)

        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setObjectName("gray")
        sel_all_btn.setFixedWidth(90)
        sel_all_btn.clicked.connect(self._select_all)
        af_layout.addWidget(sel_all_btn)

        desel_btn = QPushButton("Deselect All")
        desel_btn.setObjectName("gray")
        desel_btn.setFixedWidth(100)
        desel_btn.clicked.connect(self._deselect_all)
        af_layout.addWidget(desel_btn)
        af_layout.addSpacing(8)

        dest_btn = QPushButton("Destination")
        dest_btn.setFixedWidth(120)
        dest_btn.clicked.connect(self._browse_dest)
        af_layout.addWidget(dest_btn)

        self.dest_edit = QLineEdit()
        self.dest_edit.setFont(QFont("Segoe UI", 11))
        af_layout.addWidget(self.dest_edit, stretch=1)

        self._dl_sel_btn = QPushButton("Download Selected")
        self._dl_sel_btn.setObjectName("green")
        self._dl_sel_btn.setFixedWidth(170)
        self._dl_sel_btn.setFont(
            QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._dl_sel_btn.clicked.connect(self._download_selected)
        af_layout.addWidget(self._dl_sel_btn)

        layout.addWidget(af)

        self.tabview.addTab(tab, "Batch Search")

    # -----------------------------------------------------------------------
    # Upload / Download helpers
    # -----------------------------------------------------------------------
    def _browse_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select File")
        if p:
            self.file_path_edit.setText(p)

    def _browse_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Select Folder")
        if p:
            self.local_path_edit.setText(p)

    def _browse_dest(self):
        p = QFileDialog.getExistingDirectory(self, "Select Destination")
        if p:
            self.dest_edit.setText(p)

    # -----------------------------------------------------------------------
    # Worker signal helpers
    # -----------------------------------------------------------------------
    def _on_worker_error(self, title, message):
        QMessageBox.critical(self, title, message)

    def _on_worker_success(self, message):
        QMessageBox.information(self, "Success", message)

    # -----------------------------------------------------------------------
    # Upload
    # -----------------------------------------------------------------------
    def _upload(self):
        local_file = self._normalize_path(self.file_path_edit.text())
        if not local_file:
            QMessageBox.critical(self, "Error", "Select a file to upload.")
            return
        if not os.path.isfile(local_file):
            QMessageBox.critical(
                self, "Error", f"File not found:\n{local_file}")
            return
        if not self._ensure_passwords():
            return

        remote_dest = self._normalize_path(self.remote_path_edit.text())
        if not remote_dest:
            QMessageBox.critical(self, "Error", "Specify a remote path.")
            return
        if remote_dest.endswith("/"):
            remote_dest += os.path.basename(local_file)

        self._upload_btn.setEnabled(False)
        self.status_label.setText("Connecting for upload...")
        self._set_progress(0)

        worker = UploadWorker(self, local_file, remote_dest)
        worker.progress.connect(self._set_progress)
        worker.status.connect(self.status_label.setText)
        worker.error.connect(self._on_worker_error)
        worker.success.connect(self._on_worker_success)
        worker.clear_passwords.connect(self._clear_passwords)
        worker.finished_work.connect(
            lambda: self._upload_btn.setEnabled(True))
        self._active_worker = worker
        worker.start()

    # -----------------------------------------------------------------------
    # Download
    # -----------------------------------------------------------------------
    def _download(self):
        dest_folder = self._normalize_path(self.local_path_edit.text())
        if not dest_folder:
            QMessageBox.critical(
                self, "Error", "Select local destination folder.")
            return
        if not os.path.isdir(dest_folder):
            QMessageBox.critical(
                self, "Error", f"Local folder not found:\n{dest_folder}")
            return
        remote_src = self._normalize_path(self.remote_path_edit.text())
        if not remote_src:
            QMessageBox.critical(self, "Error", "Specify a remote path.")
            return
        if remote_src.endswith("/"):
            QMessageBox.critical(
                self, "Error",
                "Remote path looks like a directory, ends with /.\n"
                "Please specify the full path to the file to download.")
            return
        if not self._ensure_passwords():
            return

        fname = os.path.basename(remote_src)
        if not fname:
            QMessageBox.critical(
                self, "Error",
                "Cannot determine filename from the remote path.")
            return
        local_file = os.path.join(dest_folder, fname)

        self._download_btn.setEnabled(False)
        self.status_label.setText("Connecting for download...")
        self._set_progress(0)

        worker = DownloadWorker(self, remote_src, local_file)
        worker.progress.connect(self._set_progress)
        worker.status.connect(self.status_label.setText)
        worker.error.connect(self._on_worker_error)
        worker.success.connect(self._on_worker_success)
        worker.clear_passwords.connect(self._clear_passwords)
        worker.finished_work.connect(
            lambda: self._download_btn.setEnabled(True))
        self._active_worker = worker
        worker.start()

    # -----------------------------------------------------------------------
    # Date / time helpers
    # -----------------------------------------------------------------------
    def _get_from_dt(self):
        d = self.from_date.date()
        return datetime(d.year(), d.month(), d.day(),
                        int(self._from_hour_edit.text()),
                        int(self._from_min_edit.text()))

    def _get_to_dt(self):
        d = self.to_date.date()
        return datetime(d.year(), d.month(), d.day(),
                        int(self._to_hour_edit.text()),
                        int(self._to_min_edit.text()))

    def _set_to_plus_one_hour(self):
        try:
            target = self._get_from_dt() + timedelta(hours=1)
        except (ValueError, AttributeError):
            return
        self.to_date.setDate(QDate(target.year, target.month, target.day))
        self._to_hour_edit.setText(f"{target.hour:02d}")
        self._to_min_edit.setText(f"{target.minute:02d}")

    # -----------------------------------------------------------------------
    # Filename parser
    # -----------------------------------------------------------------------
    @staticmethod
    def _parse_zip(filepath):
        basename = os.path.basename(filepath.strip())
        m = ZIP_RE.match(basename)
        if not m:
            return None
        dt_str, sys_id, serial = m.groups()
        try:
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
        except ValueError:
            return None
        parts = filepath.strip().split("/")
        folder = ""
        for i, p in enumerate(parts):
            if p == "batches" and i + 1 < len(parts) - 1:
                folder = parts[i + 1]
                break
        return {
            "filename": basename,
            "folder": folder,
            "dt": dt,
            "system_id": sys_id,
            "serial": serial,
            "full_path": filepath.strip(),
        }

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------
    def _do_search(self):
        raw_ids = self.system_ids_edit.text().strip()
        if not raw_ids:
            QMessageBox.critical(self, "Error", "System ID is required.")
            return

        sys_ids = {s.strip() for s in raw_ids.split(",") if s.strip()}
        serial_filter = self.serial_edit.text().strip() or None

        try:
            from_dt = self._get_from_dt()
            to_dt = self._get_to_dt()
        except ValueError:
            QMessageBox.critical(
                self, "Error",
                "Invalid date or time.\nUse dd/mm/yyyy for dates.")
            return

        if from_dt > to_dt:
            QMessageBox.critical(
                self, "Error", "'From' must be earlier than 'To'.")
            return

        if not self._ensure_passwords():
            return

        self._search_btn.setEnabled(False)
        self.status_label.setText("Connecting via SSH...")
        self._set_progress(0)

        worker = SearchWorker(self, sys_ids, serial_filter, from_dt, to_dt)
        worker.status.connect(self.status_label.setText)
        worker.error.connect(self._on_worker_error)
        worker.results_ready.connect(self._show_results)
        worker.clear_passwords.connect(self._clear_passwords)
        worker.finished_work.connect(
            lambda: self._search_btn.setEnabled(True))
        self._active_worker = worker
        worker.start()

    def _show_results(self, matches):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for m in matches:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0,
                               QTableWidgetItem(m["filename"]))
            self.table.setItem(row, 1,
                               QTableWidgetItem(m["folder"]))
            self.table.setItem(row, 2,
                               QTableWidgetItem(
                                   m["dt"].strftime("%d/%m/%Y %H:%M")))
            self.table.setItem(row, 3,
                               QTableWidgetItem(m["system_id"]))
            self.table.setItem(row, 4,
                               QTableWidgetItem(m["serial"]))
            self.table.setItem(row, 5,
                               QTableWidgetItem(m["full_path"]))

            for col in range(6):
                item = self.table.item(row, col)
                if col < 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table.setSortingEnabled(True)
        n = len(matches)
        self._result_count_label.setText(
            f"{n} file{'s' if n != 1 else ''} found")
        self.status_label.setText("Search complete")

    # -----------------------------------------------------------------------
    # Selection helpers
    # -----------------------------------------------------------------------
    def _select_all(self):
        self.table.selectAll()

    def _deselect_all(self):
        self.table.clearSelection()

    # -----------------------------------------------------------------------
    # Download selected files
    # -----------------------------------------------------------------------
    def _download_selected(self):
        selected_rows = set()
        for idx in self.table.selectedIndexes():
            selected_rows.add(idx.row())

        if not selected_rows:
            QMessageBox.critical(self, "Error", "No files selected.")
            return

        dest = self._normalize_path(self.dest_edit.text())
        if not dest:
            QMessageBox.critical(
                self, "Error",
                "Choose a local destination folder first.")
            return

        paths = []
        for row in sorted(selected_rows):
            item = self.table.item(row, 5)
            if item is None:
                continue
            full_path = item.text()
            if not full_path.startswith(BATCHES_PATH):
                continue
            paths.append(full_path)

        if not paths:
            QMessageBox.critical(
                self, "Error",
                "No valid server paths in selection.")
            return

        if not self._ensure_passwords():
            return

        self._dl_sel_btn.setEnabled(False)
        self.status_label.setText(
            f"Preparing download of {len(paths)} file(s)...")
        self._set_progress(0)

        worker = BatchDownloadWorker(self, paths, dest)
        worker.progress.connect(self._set_progress)
        worker.status.connect(self.status_label.setText)
        worker.error.connect(self._on_worker_error)
        worker.success.connect(self._on_worker_success)
        worker.clear_passwords.connect(self._clear_passwords)
        worker.finished_work.connect(
            lambda: self._dl_sel_btn.setEnabled(True))
        self._active_worker = worker
        worker.start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    if paramiko is None:
        QMessageBox.critical(
            None, "Missing Dependency",
            "The 'paramiko' library is required.\n\n"
            "Install it with:\n  pip install paramiko")
        sys.exit(1)

    window = App()
    window.show()
    sys.exit(app.exec())
