import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk          # still needed for StringVar, DoubleVar, Treeview
from tkinter import ttk       # Treeview has no CTk equivalent
import os
import re
import shlex
import threading
import platform
from datetime import datetime, timedelta
from contextlib import contextmanager

try:
    import paramiko
except ImportError:
    paramiko = None

try:
    from tkcalendar import DateEntry
    HAS_TKCALENDAR = True
except ImportError:
    HAS_TKCALENDAR = False

try:
    import pywinstyles
    HAS_PYWINSTYLES = True
except ImportError:
    HAS_PYWINSTYLES = False

# ---------------------------------------------------------------------------
# Connection constants
# ---------------------------------------------------------------------------
JUMP_USER = "gstefanakis"
JUMP_HOST = "adinsightscons.hat-analytics.net"
JUMP_PORT = "15930"

REMOTE_USER = "hat"
REMOTE_HOST = "localhost"

BATCHES_PATH = "/var/agenonlineservice/batches"

IS_WINDOWS = platform.system() == "Windows"

# Strict pattern for batch zip filenames:
# YYYYMMDDHHmm_<systemid>_<serial>.zip
ZIP_RE = re.compile(r"^(\d{12})_(\d+)_(\d+)\.zip$")

# ---------------------------------------------------------------------------
# CustomTkinter appearance
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Accent colours used in a few places
GREEN = "#27ae60"
GREEN_HOVER = "#2ecc71"
BLUE = "#2980b9"
BLUE_HOVER = "#3498db"
RED = "#e74c3c"
RED_HOVER = "#c0392b"
LABEL_FG = "#dcdde1"
MUTED_FG = "#7f8c8d"
HEADING_FG = "#f5f6fa"


def _setup_treeview_style():
    """Style the Treeview (which is still a classic ttk widget) so it looks
    at home inside the dark CustomTkinter window."""
    style = ttk.Style()
    style.theme_use("clam")

    dark_bg = "#2b2b2b"
    dark_fg = "#dcdde1"
    sel_bg = "#3498db"
    heading_bg = "#343638"

    style.configure("Dark.Treeview",
                    background=dark_bg,
                    foreground=dark_fg,
                    fieldbackground=dark_bg,
                    font=("Segoe UI", 13),
                    rowheight=32,
                    borderwidth=0)
    style.configure("Dark.Treeview.Heading",
                    background=heading_bg,
                    foreground="#ecf0f1",
                    font=("Segoe UI", 13, "bold"),
                    relief="flat")
    style.map("Dark.Treeview",
              background=[("selected", sel_bg)],
              foreground=[("selected", "white")])
    style.map("Dark.Treeview.Heading",
              background=[("active", "#3e4042")])

    # Scrollbar styling
    style.configure("Dark.Vertical.TScrollbar",
                    background=heading_bg,
                    troughcolor=dark_bg,
                    borderwidth=0,
                    arrowsize=14)
    style.configure("Dark.Horizontal.TScrollbar",
                    background=heading_bg,
                    troughcolor=dark_bg,
                    borderwidth=0,
                    arrowsize=14)


def _enable_paste(root):
    """Bind Ctrl+V / Cmd+V at the *Entry class level* so paste works in every
    tk.Entry widget – including the inner entries that CTkEntry creates.

    Using ``bind_class`` targets the widget that actually has keyboard focus,
    which is more reliable than ``bind_all`` (the latter fires after all
    per-widget handlers and its ``"break"`` return cannot suppress them).
    """
    def _paste(event):
        w = event.widget
        try:
            clip = root.clipboard_get()
        except tk.TclError:
            return
        try:
            if w.selection_present():
                w.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass  # no selection – that's fine
        w.insert(tk.INSERT, clip)
        return "break"

    modifier = "Command" if platform.system() == "Darwin" else "Control"
    root.bind_class("Entry", f"<{modifier}-v>", _paste)
    root.bind_class("Entry", f"<{modifier}-V>", _paste)


# ---------------------------------------------------------------------------
# Password dialog
# ---------------------------------------------------------------------------
class PasswordDialog(ctk.CTkToplevel):
    """Modal dialog asking for relay and local server passwords."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("SSH Authentication")
        self.resizable(False, False)
        self.result = None

        self.configure(fg_color=("#f0f0f0", "#2b2b2b"))

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=24, pady=20)

        # Title
        ctk.CTkLabel(main, text="Enter SSH Passwords",
                     font=ctk.CTkFont("Segoe UI", 16, "bold")).pack(
            pady=(0, 16))

        # Relay server password
        ctk.CTkLabel(main, text="Password for Relay Server:",
                     font=ctk.CTkFont("Segoe UI", 12, "bold")).pack(
            anchor="w")
        ctk.CTkLabel(main,
                     text=f"{JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}",
                     text_color=MUTED_FG,
                     font=ctk.CTkFont("Segoe UI", 10)).pack(anchor="w")
        self.relay_entry = ctk.CTkEntry(main, show="\u25CF", width=340,
                                        font=ctk.CTkFont("Segoe UI", 12))
        self.relay_entry.pack(fill="x", pady=(6, 14))

        # Local server password
        ctk.CTkLabel(main, text="Password for Local Server:",
                     font=ctk.CTkFont("Segoe UI", 12, "bold")).pack(
            anchor="w")
        ctk.CTkLabel(main,
                     text=f"{REMOTE_USER}@{REMOTE_HOST}:<port>",
                     text_color=MUTED_FG,
                     font=ctk.CTkFont("Segoe UI", 10)).pack(anchor="w")
        self.local_entry = ctk.CTkEntry(main, show="\u25CF", width=340,
                                        font=ctk.CTkFont("Segoe UI", 12))
        self.local_entry.pack(fill="x", pady=(6, 20))

        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x")
        ctk.CTkButton(btn_frame, text="Cancel", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self._cancel).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Connect", width=140,
                      fg_color=GREEN, hover_color=GREEN_HOVER,
                      command=self._ok).pack(side="right")

        # Bindings
        self.relay_entry.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() -
                                     self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() -
                                     self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.grab_set()
        self.wait_window()

    def _ok(self):
        relay = self.relay_entry.get()
        local = self.local_entry.get()
        if not relay or not local:
            messagebox.showwarning("Missing Password",
                                   "Both passwords are required.",
                                   parent=self)
            return
        self.result = (relay, local)
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("SCP Tool \u2014 Upload / Download / Batch Search")
        self.root.geometry("940x760")
        self.root.minsize(700, 560)

        # Apply acrylic / mica on Windows if pywinstyles is available
        if IS_WINDOWS and HAS_PYWINSTYLES:
            try:
                pywinstyles.apply_style(self.root, "acrylic")
            except Exception:
                pass  # Silently ignore if not supported on this OS version

        _setup_treeview_style()
        _enable_paste(self.root)

        # -- passwords (stored in memory only) --------------------------------
        self._relay_pw = None
        self._local_pw = None

        # -- shared variables -------------------------------------------------
        self.remote_port = tk.StringVar(value="39022")

        # -- connection bar ---------------------------------------------------
        conn_frame = ctk.CTkFrame(root, corner_radius=10)
        conn_frame.pack(fill="x", padx=12, pady=(10, 4))

        top_row = ctk.CTkFrame(conn_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 2))

        ctk.CTkLabel(top_row, text="Remote Port:",
                     font=ctk.CTkFont("Segoe UI", 12)).pack(
            side="left", padx=(0, 6))
        ctk.CTkEntry(top_row, textvariable=self.remote_port,
                     width=80, font=ctk.CTkFont("Segoe UI", 12)).pack(
            side="left", padx=(0, 12))

        ctk.CTkButton(top_row, text="Login", width=110,
                      command=self._prompt_passwords).pack(
            side="left", padx=(0, 4))
        ctk.CTkButton(top_row, text="Logout", width=90,
                      fg_color="gray40", hover_color="gray50",
                      command=self._logout).pack(
            side="left", padx=(0, 12))

        self._auth_var = tk.StringVar(value="Not authenticated")
        self._auth_label = ctk.CTkLabel(top_row,
                                        textvariable=self._auth_var,
                                        text_color=RED,
                                        font=ctk.CTkFont("Segoe UI", 11))
        self._auth_label.pack(side="left", padx=4)

        info_text = (f"Jump: {JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}  -->  "
                     f"{REMOTE_USER}@{REMOTE_HOST}:<port>")
        ctk.CTkLabel(conn_frame, text=info_text,
                     text_color=MUTED_FG,
                     font=ctk.CTkFont("Segoe UI", 9)).pack(
            anchor="w", padx=14, pady=(0, 8))

        # -- progress bar + status (pack early so they stay at bottom) --------
        bottom = ctk.CTkFrame(root, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 8))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(bottom, variable=self.progress_var,
                                                height=8)
        self.progress_bar.pack(fill="x", pady=(0, 4))
        self.progress_bar.set(0)

        self.status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(bottom, textvariable=self.status_var,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED_FG,
                     anchor="w").pack(fill="x")

        # -- tabview ----------------------------------------------------------
        self.tabview = ctk.CTkTabview(root, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=6)

        self.tabview.add("Upload / Download")
        self.tabview.add("Batch Search")

        self._build_upload_download_tab()
        self._build_batch_search_tab()

        # Clean shutdown when the user closes the window
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -----------------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------------
    def _prompt_passwords(self):
        dlg = PasswordDialog(self.root)
        if dlg.result is not None:
            self._relay_pw, self._local_pw = dlg.result
            self._auth_var.set("Authenticated")
            self._auth_label.configure(text_color=GREEN)

    def _ensure_passwords(self):
        if self._relay_pw and self._local_pw:
            return True
        self._prompt_passwords()
        return bool(self._relay_pw and self._local_pw)

    def _logout(self):
        """Clear stored passwords and update the auth indicator."""
        self._clear_passwords()
        self.status_var.set("Logged out")

    def _clear_passwords(self):
        self._relay_pw = None
        self._local_pw = None
        self.root.after(0, self._update_auth_indicator_disconnected)

    def _update_auth_indicator_disconnected(self):
        self._auth_var.set("Not authenticated")
        self._auth_label.configure(text_color=RED)

    def _on_close(self):
        """Handle window close: clear passwords and destroy the root window.
        Daemon threads are terminated automatically when the main thread exits."""
        self._clear_passwords()
        self.root.destroy()

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
                    (REMOTE_HOST, int(self.remote_port.get())),
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
    # Progress helpers  (CTkProgressBar uses 0..1 range)
    # -----------------------------------------------------------------------
    def _set_progress(self, pct):
        """Set progress bar from a percentage (0-100)."""
        self.progress_bar.set(pct / 100.0)

    # -----------------------------------------------------------------------
    # Tab 1 – Upload / Download
    # -----------------------------------------------------------------------
    def _build_upload_download_tab(self):
        tab = self.tabview.tab("Upload / Download")

        # Remote path section
        pf = ctk.CTkFrame(tab, corner_radius=8)
        pf.pack(fill="x", padx=4, pady=(4, 8))

        ctk.CTkLabel(pf, text="Remote Linux Path",
                     font=ctk.CTkFont("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=12, pady=(8, 2))
        self.remote_path = tk.StringVar(
            value="/home/hat/Downloads/pythonscripts/")
        ctk.CTkEntry(pf, textvariable=self.remote_path,
                     font=ctk.CTkFont("Segoe UI", 12)).pack(
            fill="x", padx=12, pady=(0, 2))
        ctk.CTkLabel(pf,
                     text=("Upload: destination dir ending with /  "
                           "|  Download: full file path"),
                     text_color=MUTED_FG,
                     font=ctk.CTkFont("Segoe UI", 10)).pack(
            anchor="w", padx=12, pady=(0, 8))

        # Upload section
        uf = ctk.CTkFrame(tab, corner_radius=8)
        uf.pack(fill="x", padx=4, pady=(0, 8))

        ctk.CTkLabel(uf, text="Upload",
                     font=ctk.CTkFont("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=12, pady=(8, 4))

        upload_row = ctk.CTkFrame(uf, fg_color="transparent")
        upload_row.pack(fill="x", padx=12, pady=(0, 4))

        self.file_path = tk.StringVar()
        ctk.CTkLabel(upload_row, text="Local File:",
                     font=ctk.CTkFont("Segoe UI", 11), width=80).pack(
            side="left", padx=(0, 6))
        ctk.CTkEntry(upload_row, textvariable=self.file_path,
                     font=ctk.CTkFont("Segoe UI", 11)).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(upload_row, text="Browse",
                      width=110, command=self._browse_file).pack(side="right")

        self._upload_btn = ctk.CTkButton(
            uf, text="UPLOAD", width=180, height=36,
            fg_color=GREEN, hover_color=GREEN_HOVER,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._upload)
        self._upload_btn.pack(pady=(4, 10))

        # Download section
        df = ctk.CTkFrame(tab, corner_radius=8)
        df.pack(fill="x", padx=4, pady=(0, 4))

        ctk.CTkLabel(df, text="Download",
                     font=ctk.CTkFont("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=12, pady=(8, 4))

        dl_row = ctk.CTkFrame(df, fg_color="transparent")
        dl_row.pack(fill="x", padx=12, pady=(0, 4))

        self.local_path = tk.StringVar()
        ctk.CTkLabel(dl_row, text="Save To:",
                     font=ctk.CTkFont("Segoe UI", 11), width=80).pack(
            side="left", padx=(0, 6))
        ctk.CTkEntry(dl_row, textvariable=self.local_path,
                     font=ctk.CTkFont("Segoe UI", 11)).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(dl_row, text="Browse",
                      width=110, command=self._browse_folder).pack(side="right")

        self._download_btn = ctk.CTkButton(
            df, text="DOWNLOAD", width=180, height=36,
            fg_color=BLUE, hover_color=BLUE_HOVER,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._download)
        self._download_btn.pack(pady=(4, 10))

    # -----------------------------------------------------------------------
    # Tab 2 – Batch Search
    # -----------------------------------------------------------------------
    def _build_batch_search_tab(self):
        tab = self.tabview.tab("Batch Search")

        # -- search criteria --------------------------------------------------
        cf = ctk.CTkFrame(tab, corner_radius=8)
        cf.pack(fill="x", padx=4, pady=(4, 6))

        ctk.CTkLabel(cf, text="Search Criteria",
                     font=ctk.CTkFont("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=12, pady=(8, 4))

        # Date / Time rows
        dt_frame = ctk.CTkFrame(cf, fg_color="transparent")
        dt_frame.pack(fill="x", padx=12, pady=(0, 4))

        # FROM row
        from_row = ctk.CTkFrame(dt_frame, fg_color="transparent")
        from_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(from_row, text="From:",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     width=50).pack(side="left")

        if HAS_TKCALENDAR:
            # DateEntry is a tkinter widget – embed in a tk.Frame
            date_holder_from = tk.Frame(from_row, bg="#2b2b2b")
            date_holder_from.pack(side="left", padx=(4, 8))
            self.from_date = DateEntry(date_holder_from, width=11,
                                       date_pattern="dd/MM/yyyy",
                                       font=("Segoe UI", 10))
            self.from_date.pack()
        else:
            self._from_date_var = tk.StringVar(
                value=datetime.now().strftime("%d/%m/%Y"))
            ctk.CTkEntry(from_row, textvariable=self._from_date_var,
                         width=100,
                         font=ctk.CTkFont("Segoe UI", 11)).pack(
                side="left", padx=(4, 8))

        self._from_hour_var = tk.StringVar(value="00")
        ctk.CTkEntry(from_row, textvariable=self._from_hour_var,
                     width=42, font=ctk.CTkFont("Segoe UI", 11),
                     justify="center").pack(side="left")
        ctk.CTkLabel(from_row, text=":", width=10).pack(side="left")
        self._from_min_var = tk.StringVar(value="00")
        ctk.CTkEntry(from_row, textvariable=self._from_min_var,
                     width=42, font=ctk.CTkFont("Segoe UI", 11),
                     justify="center").pack(side="left")

        # TO row
        to_row = ctk.CTkFrame(dt_frame, fg_color="transparent")
        to_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(to_row, text="To:",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     width=50).pack(side="left")

        if HAS_TKCALENDAR:
            date_holder_to = tk.Frame(to_row, bg="#2b2b2b")
            date_holder_to.pack(side="left", padx=(4, 8))
            self.to_date = DateEntry(date_holder_to, width=11,
                                     date_pattern="dd/MM/yyyy",
                                     font=("Segoe UI", 10))
            self.to_date.pack()
        else:
            self._to_date_var = tk.StringVar(
                value=datetime.now().strftime("%d/%m/%Y"))
            ctk.CTkEntry(to_row, textvariable=self._to_date_var,
                         width=100,
                         font=ctk.CTkFont("Segoe UI", 11)).pack(
                side="left", padx=(4, 8))

        self._to_hour_var = tk.StringVar(value="23")
        ctk.CTkEntry(to_row, textvariable=self._to_hour_var,
                     width=42, font=ctk.CTkFont("Segoe UI", 11),
                     justify="center").pack(side="left")
        ctk.CTkLabel(to_row, text=":", width=10).pack(side="left")
        self._to_min_var = tk.StringVar(value="59")
        ctk.CTkEntry(to_row, textvariable=self._to_min_var,
                     width=42, font=ctk.CTkFont("Segoe UI", 11),
                     justify="center").pack(side="left")

        ctk.CTkButton(to_row, text="+1 h", width=60,
                      fg_color="gray40", hover_color="gray50",
                      command=self._set_to_plus_one_hour).pack(
            side="left", padx=(12, 0))

        # System IDs
        id_row = ctk.CTkFrame(cf, fg_color="transparent")
        id_row.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(id_row, text="System IDs*:",
                     font=ctk.CTkFont("Segoe UI", 11)).pack(
            side="left", padx=(0, 6))
        self.system_ids_var = tk.StringVar()
        ctk.CTkEntry(id_row, textvariable=self.system_ids_var,
                     font=ctk.CTkFont("Segoe UI", 11)).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(id_row, text="comma-separated",
                     text_color=MUTED_FG,
                     font=ctk.CTkFont("Segoe UI", 10)).pack(side="left")

        # Serial number
        sn_row = ctk.CTkFrame(cf, fg_color="transparent")
        sn_row.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(sn_row, text="Serial Number:",
                     font=ctk.CTkFont("Segoe UI", 11)).pack(
            side="left", padx=(0, 6))
        self.serial_var = tk.StringVar()
        ctk.CTkEntry(sn_row, textvariable=self.serial_var,
                     font=ctk.CTkFont("Segoe UI", 11)).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(sn_row, text="optional", text_color=MUTED_FG,
                     font=ctk.CTkFont("Segoe UI", 10)).pack(side="left")

        # Search button
        btn_row = ctk.CTkFrame(cf, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(2, 10))
        self._search_btn = ctk.CTkButton(
            btn_row, text="Search", width=140,
            fg_color=BLUE, hover_color=BLUE_HOVER,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._do_search)
        self._search_btn.pack(side="left")
        self._result_count_var = tk.StringVar()
        ctk.CTkLabel(btn_row, textvariable=self._result_count_var,
                     font=ctk.CTkFont("Segoe UI", 11, "bold")).pack(
            side="left", padx=14)

        # -- actions bar (packed before results so always visible) -------------
        af = ctk.CTkFrame(tab, fg_color="transparent")
        af.pack(side="bottom", fill="x", padx=4, pady=(4, 2))

        ctk.CTkButton(af, text="Select All", width=90,
                      fg_color="gray40", hover_color="gray50",
                      command=self._select_all).pack(
            side="left", padx=(0, 4))
        ctk.CTkButton(af, text="Deselect All", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self._deselect_all).pack(
            side="left", padx=(0, 12))

        self.dest_var = tk.StringVar()
        ctk.CTkButton(af, text="Destination", width=120,
                      command=self._browse_dest).pack(
            side="left", padx=(0, 4))
        ctk.CTkEntry(af, textvariable=self.dest_var, width=200,
                     font=ctk.CTkFont("Segoe UI", 11)).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        self._dl_sel_btn = ctk.CTkButton(
            af, text="Download Selected", width=170,
            fg_color=GREEN, hover_color=GREEN_HOVER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._download_selected)
        self._dl_sel_btn.pack(side="right")

        # -- results (Treeview – classic ttk widget) --------------------------
        rf = ctk.CTkFrame(tab, corner_radius=8)
        rf.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        ctk.CTkLabel(rf, text="Results",
                     font=ctk.CTkFont("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=12, pady=(8, 2))

        tree_container = tk.Frame(rf, bg="#2b2b2b")
        tree_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("filename", "folder", "datetime", "system_id", "serial",
                "full_path")
        self.tree = ttk.Treeview(tree_container, columns=cols,
                                  show="headings", selectmode="extended",
                                  style="Dark.Treeview")

        for col, label, anc in (("filename", "Filename", "center"),
                                ("folder", "Folder", "center"),
                                ("datetime", "Date / Time", "center"),
                                ("system_id", "System ID", "center"),
                                ("serial", "Serial #", "center"),
                                ("full_path", "Server Path", "w")):
            self.tree.heading(
                col, text=label, anchor=anc,
                command=lambda c=col: self._sort_tree(c))

        self._sort_col = None
        self._sort_asc = True

        self.tree.column("filename", width=220, minwidth=120, anchor="center")
        self.tree.column("folder", width=100, minwidth=60, anchor="center")
        self.tree.column("datetime", width=150, minwidth=100, anchor="center")
        self.tree.column("system_id", width=100, minwidth=60, anchor="center")
        self.tree.column("serial", width=90, minwidth=60, anchor="center")
        self.tree.column("full_path", width=280, minwidth=140, anchor="w")

        vsb = ttk.Scrollbar(tree_container, orient="vertical",
                            command=self.tree.yview,
                            style="Dark.Vertical.TScrollbar")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal",
                            command=self.tree.xview,
                            style="Dark.Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

    # -----------------------------------------------------------------------
    # Upload / Download helpers
    # -----------------------------------------------------------------------
    def _browse_file(self):
        p = filedialog.askopenfilename()
        if p:
            self.file_path.set(p)

    def _browse_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.local_path.set(p)

    def _browse_dest(self):
        p = filedialog.askdirectory()
        if p:
            self.dest_var.set(p)

    def _upload(self):
        local_file = self._normalize_path(self.file_path.get())
        if not local_file:
            messagebox.showerror("Error", "Select a file to upload.")
            return
        if not os.path.isfile(local_file):
            messagebox.showerror("Error", f"File not found:\n{local_file}")
            return
        if not self._ensure_passwords():
            return

        remote_dest = self._normalize_path(self.remote_path.get())
        if not remote_dest:
            messagebox.showerror("Error", "Specify a remote path.")
            return
        if remote_dest.endswith("/"):
            remote_dest += os.path.basename(local_file)

        self._upload_btn.configure(state="disabled")
        self.status_var.set("Connecting for upload...")
        self._set_progress(0)
        self.root.update_idletasks()

        def _worker():
            try:
                with self._open_connection() as ssh:
                    sftp = ssh.open_sftp()
                    try:
                        # Verify remote directory exists
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
                            pct = (transferred / total * 100
                                   if total > 0 else 0)
                            self.root.after(0, lambda p=pct: (
                                self._set_progress(p),
                                self.status_var.set(
                                    f"Uploading... {p:.0f}%")))

                        sftp.put(local_file, remote_dest, callback=_cb)
                    finally:
                        sftp.close()

                self.root.after(0, lambda: (
                    messagebox.showinfo(
                        "Success",
                        f"Uploaded to:\n{remote_dest}"),
                    self.status_var.set("Upload complete"),
                    self._set_progress(100)))

            except ConnectionError as exc:
                self._clear_passwords()
                self.root.after(0, lambda: (
                    messagebox.showerror("Connection Error", str(exc)),
                    self.status_var.set("Upload failed"),
                    self._set_progress(0)))
            except Exception as exc:
                self.root.after(0, lambda: (
                    messagebox.showerror("Upload Error", str(exc)),
                    self.status_var.set("Upload failed"),
                    self._set_progress(0)))
            finally:
                self.root.after(
                    0, lambda: self._upload_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _download(self):
        dest_folder = self._normalize_path(self.local_path.get())
        if not dest_folder:
            messagebox.showerror("Error", "Select local destination folder.")
            return
        if not os.path.isdir(dest_folder):
            messagebox.showerror("Error",
                                 f"Local folder not found:\n{dest_folder}")
            return
        remote_src = self._normalize_path(self.remote_path.get())
        if not remote_src:
            messagebox.showerror("Error", "Specify a remote path.")
            return
        if remote_src.endswith("/"):
            messagebox.showerror(
                "Error",
                "Remote path looks like a directory, ends with /.\n"
                "Please specify the full path to the file to download.")
            return
        if not self._ensure_passwords():
            return

        fname = os.path.basename(remote_src)
        if not fname:
            messagebox.showerror(
                "Error",
                "Cannot determine filename from the remote path.")
            return
        local_file = os.path.join(dest_folder, fname)

        self._download_btn.configure(state="disabled")
        self.status_var.set("Connecting for download...")
        self._set_progress(0)
        self.root.update_idletasks()

        def _worker():
            try:
                with self._open_connection() as ssh:
                    sftp = ssh.open_sftp()
                    try:
                        try:
                            sftp.stat(remote_src)
                        except FileNotFoundError:
                            raise IOError(
                                f"Remote file not found:\n{remote_src}")

                        def _cb(transferred, total):
                            pct = (transferred / total * 100
                                   if total > 0 else 0)
                            self.root.after(0, lambda p=pct: (
                                self._set_progress(p),
                                self.status_var.set(
                                    f"Downloading... {p:.0f}%")))

                        sftp.get(remote_src, local_file, callback=_cb)
                    finally:
                        sftp.close()

                self.root.after(0, lambda: (
                    messagebox.showinfo(
                        "Success",
                        f"Downloaded to:\n{local_file}"),
                    self.status_var.set("Download complete"),
                    self._set_progress(100)))

            except ConnectionError as exc:
                self._clear_passwords()
                self.root.after(0, lambda: (
                    messagebox.showerror("Connection Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self._set_progress(0)))
            except Exception as exc:
                self.root.after(0, lambda: (
                    messagebox.showerror("Download Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self._set_progress(0)))
            finally:
                self.root.after(
                    0, lambda: self._download_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    # -----------------------------------------------------------------------
    # Date / time helpers
    # -----------------------------------------------------------------------
    def _get_from_dt(self):
        if HAS_TKCALENDAR:
            d = self.from_date.get_date()
        else:
            d = datetime.strptime(self._from_date_var.get(),
                                  "%d/%m/%Y").date()
        return datetime(d.year, d.month, d.day,
                        int(self._from_hour_var.get()),
                        int(self._from_min_var.get()))

    def _get_to_dt(self):
        if HAS_TKCALENDAR:
            d = self.to_date.get_date()
        else:
            d = datetime.strptime(self._to_date_var.get(),
                                  "%d/%m/%Y").date()
        return datetime(d.year, d.month, d.day,
                        int(self._to_hour_var.get()),
                        int(self._to_min_var.get()))

    def _set_to_plus_one_hour(self):
        try:
            target = self._get_from_dt() + timedelta(hours=1)
        except (ValueError, AttributeError):
            return
        if HAS_TKCALENDAR:
            self.to_date.set_date(target.date())
        else:
            self._to_date_var.set(target.strftime("%d/%m/%Y"))
        self._to_hour_var.set(f"{target.hour:02d}")
        self._to_min_var.set(f"{target.minute:02d}")

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
        raw_ids = self.system_ids_var.get().strip()
        if not raw_ids:
            messagebox.showerror("Error", "System ID is required.")
            return

        sys_ids = {s.strip() for s in raw_ids.split(",") if s.strip()}
        serial_filter = self.serial_var.get().strip() or None

        try:
            from_dt = self._get_from_dt()
            to_dt = self._get_to_dt()
        except ValueError:
            messagebox.showerror("Error",
                                 "Invalid date or time.\n"
                                 "Use dd/mm/yyyy for dates.")
            return

        if from_dt > to_dt:
            messagebox.showerror("Error",
                                 "'From' must be earlier than 'To'.")
            return

        if not self._ensure_passwords():
            return

        self._search_btn.configure(state="disabled")
        self.status_var.set("Connecting via SSH...")
        self._set_progress(0)
        self.root.update_idletasks()

        def _worker():
            try:
                with self._open_connection() as ssh:
                    self.root.after(
                        0, lambda: self.status_var.set(
                            "Searching for zip files..."))

                    find_cmd = (
                        f"find {shlex.quote(BATCHES_PATH)} "
                        f"-type f -name '*.zip' 2>/dev/null"
                    )
                    out, err, code = self._ssh_exec(ssh, find_cmd, timeout=60)

                    if code != 0 and not out.strip():
                        self.root.after(0, lambda: messagebox.showerror(
                            "SSH Error", err or "Command failed."))
                        return

                    lines = [l for l in out.strip().splitlines() if l.strip()]

                    matches = []
                    for line in lines:
                        info = self._parse_zip(line)
                        if info is None:
                            continue
                        if info["system_id"] not in sys_ids:
                            continue
                        if serial_filter and info["serial"] != serial_filter:
                            continue
                        if not (from_dt <= info["dt"] <= to_dt):
                            continue
                        matches.append(info)

                    matches.sort(key=lambda x: (x["dt"], x["system_id"]))
                    self.root.after(0, self._show_results, matches)

            except ConnectionError as exc:
                self._clear_passwords()
                self.root.after(0, lambda: messagebox.showerror(
                    "Connection Error", str(exc)))
                self.root.after(
                    0, lambda: self.status_var.set("Search failed"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", str(exc)))
                self.root.after(
                    0, lambda: self.status_var.set("Search failed"))
            finally:
                self.root.after(
                    0, lambda: self._search_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_results(self, matches):
        for child in self.tree.get_children():
            self.tree.delete(child)
        for m in matches:
            self.tree.insert("", "end", values=(
                m["filename"],
                m["folder"],
                m["dt"].strftime("%d/%m/%Y %H:%M"),
                m["system_id"],
                m["serial"],
                m["full_path"],
            ))
        n = len(matches)
        self._result_count_var.set(f"{n} file{'s' if n != 1 else ''} found")
        self.status_var.set("Search complete")

    # -----------------------------------------------------------------------
    # Selection helpers
    # -----------------------------------------------------------------------
    def _select_all(self):
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children)

    def _deselect_all(self):
        self.tree.selection_remove(*self.tree.get_children())

    # -----------------------------------------------------------------------
    # Column sorting
    # -----------------------------------------------------------------------
    def _sort_tree(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        rows = [(self.tree.set(iid, col), iid) for iid in
                self.tree.get_children()]

        if col in ("system_id", "serial"):
            def key_fn(item):
                try:
                    return int(item[0])
                except ValueError:
                    return item[0]
        elif col == "datetime":
            def key_fn(item):
                try:
                    return datetime.strptime(item[0], "%d/%m/%Y %H:%M")
                except ValueError:
                    return item[0]
        else:
            def key_fn(item):
                return item[0].lower()

        rows.sort(key=key_fn, reverse=not self._sort_asc)

        for idx, (_val, iid) in enumerate(rows):
            self.tree.move(iid, "", idx)

        arrow = " ^" if self._sort_asc else " v"
        col_labels = {
            "filename": ("Filename", "center"),
            "folder": ("Folder", "center"),
            "datetime": ("Date / Time", "center"),
            "system_id": ("System ID", "center"),
            "serial": ("Serial #", "center"),
            "full_path": ("Server Path", "w"),
        }
        for c, (label, anc) in col_labels.items():
            suffix = arrow if c == col else ""
            self.tree.heading(c, text=label + suffix, anchor=anc)

    # -----------------------------------------------------------------------
    # Download selected files
    # -----------------------------------------------------------------------
    def _download_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "No files selected.")
            return

        dest = self._normalize_path(self.dest_var.get())
        if not dest:
            messagebox.showerror("Error",
                                 "Choose a local destination folder first.")
            return

        paths = []
        for iid in selected:
            vals = self.tree.item(iid, "values")
            full_path = vals[5]
            if not full_path.startswith(BATCHES_PATH):
                continue
            paths.append(full_path)

        if not paths:
            messagebox.showerror("Error",
                                 "No valid server paths in selection.")
            return

        if not self._ensure_passwords():
            return

        self._dl_sel_btn.configure(state="disabled")
        self.status_var.set(
            f"Preparing download of {len(paths)} file(s)...")
        self._set_progress(0)
        self.root.update_idletasks()

        def _worker():
            try:
                with self._open_connection() as ssh:
                    sftp = ssh.open_sftp()
                    try:
                        total = len(paths)
                        for idx, remote_path in enumerate(paths, 1):
                            fname = os.path.basename(remote_path)
                            local_file = os.path.join(dest, fname)

                            base, ext = os.path.splitext(fname)
                            counter = 1
                            while os.path.exists(local_file):
                                local_file = os.path.join(
                                    dest, f"{base}_{counter}{ext}")
                                counter += 1

                            self.root.after(0, lambda i=idx, t=total,
                                            f=fname: (
                                self.status_var.set(
                                    f"Downloading {i}/{t}: {f}"),
                                self._set_progress(
                                    (i - 1) / t * 100)))

                            sftp.get(remote_path, local_file)

                        self.root.after(0, lambda: self._set_progress(100))
                    finally:
                        sftp.close()

                self.root.after(0, lambda: (
                    messagebox.showinfo(
                        "Success",
                        f"Downloaded {len(paths)} file(s) to:\n{dest}"),
                    self.status_var.set("Download complete"),
                    self._set_progress(100)))

            except ConnectionError as exc:
                self._clear_passwords()
                self.root.after(0, lambda: (
                    messagebox.showerror("Connection Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self._set_progress(0)))
            except Exception as exc:
                self.root.after(0, lambda: (
                    messagebox.showerror("Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self._set_progress(0)))
            finally:
                self.root.after(
                    0, lambda: self._dl_sel_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if paramiko is None:
        _r = ctk.CTk()
        _r.withdraw()
        messagebox.showerror(
            "Missing Dependency",
            "The 'paramiko' library is required.\n\n"
            "Install it with:\n  pip install paramiko")
        _r.destroy()
        raise SystemExit(1)

    root = ctk.CTk()
    App(root)
    root.mainloop()
