import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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
# Colours / style helpers
# ---------------------------------------------------------------------------
BG = "#f5f6fa"
ACCENT = "#2c3e50"
GREEN = "#27ae60"
BLUE = "#2980b9"
RED = "#c0392b"
LIGHT = "#ecf0f1"


def _configure_styles():
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, font=("Segoe UI", 10))
    style.configure("TLabelframe", background=BG, font=("Segoe UI", 10, "bold"))
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT)
    style.configure("TEntry", padding=4)
    style.configure("TButton", padding=6, font=("Segoe UI", 10))
    style.configure("TNotebook", background=BG)
    style.configure("TNotebook.Tab", padding=[14, 6], font=("Segoe UI", 10, "bold"))

    style.configure("Green.TButton", foreground="white", background=GREEN,
                     font=("Segoe UI", 10, "bold"))
    style.map("Green.TButton", background=[("active", "#2ecc71")])

    style.configure("Blue.TButton", foreground="white", background=BLUE,
                     font=("Segoe UI", 10, "bold"))
    style.map("Blue.TButton", background=[("active", "#3498db")])

    style.configure("Red.TButton", foreground="white", background=RED,
                     font=("Segoe UI", 10, "bold"))

    style.configure("Status.TLabel", background=LIGHT, font=("Segoe UI", 9),
                     relief="sunken", anchor="w", padding=(6, 3))

    style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
    style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    style.configure("Auth.TLabel", background=BG, font=("Segoe UI", 9))


# ---------------------------------------------------------------------------
# Password dialog
# ---------------------------------------------------------------------------
class PasswordDialog(tk.Toplevel):
    """Modal dialog asking for relay and local server passwords."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("\U0001F512 SSH Authentication")
        self.resizable(False, False)
        self.result = None

        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)

        # Title
        ttk.Label(main, text="Enter SSH Passwords",
                  font=("Segoe UI", 12, "bold"),
                  foreground=ACCENT).pack(pady=(0, 12))

        # Relay server password
        ttk.Label(main, text="Password for Relay Server:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(main, text=f"({JUMP_USER}@{JUMP_HOST}:{JUMP_PORT})",
                  foreground="grey", font=("Segoe UI", 9)).pack(anchor="w")
        self.relay_entry = ttk.Entry(main, show="\u25CF", width=40,
                                     font=("Segoe UI", 10))
        self.relay_entry.pack(fill="x", pady=(4, 12))

        # Local server password
        ttk.Label(main, text="Password for Local Server:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(main, text=f"({REMOTE_USER}@{REMOTE_HOST}:<port>)",
                  foreground="grey", font=("Segoe UI", 9)).pack(anchor="w")
        self.local_entry = ttk.Entry(main, show="\u25CF", width=40,
                                     font=("Segoe UI", 10))
        self.local_entry.pack(fill="x", pady=(4, 16))

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="\u2714  Connect", style="Green.TButton",
                   command=self._ok).pack(side="right")
        ttk.Button(btn_frame, text="Cancel",
                   command=self._cancel).pack(side="right", padx=(0, 8))

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
    def __init__(self, root):
        self.root = root
        self.root.title("SCP Tool \u2014 Upload / Download / Batch Search")
        self.root.geometry("860x720")
        self.root.minsize(780, 660)
        self.root.configure(bg=BG)

        _configure_styles()

        # -- passwords (stored in memory only) --------------------------------
        self._relay_pw = None
        self._local_pw = None

        # -- shared variables ------------------------------------------------
        self.remote_port = tk.StringVar(value="39022")

        # -- connection bar --------------------------------------------------
        conn = ttk.LabelFrame(root, text="Connection Settings")
        conn.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(conn, text="Remote Port:").grid(row=0, column=0, padx=(8, 4),
                                                   pady=6, sticky="w")
        ttk.Entry(conn, textvariable=self.remote_port, width=12).grid(
            row=0, column=1, padx=(0, 12), pady=6)

        ttk.Button(conn, text="\U0001F512 Login",
                   command=self._prompt_passwords).grid(
            row=0, column=2, padx=(0, 8), pady=6)

        self._auth_var = tk.StringVar(value="\u274C Not authenticated")
        self._auth_label = ttk.Label(conn, textvariable=self._auth_var,
                                     style="Auth.TLabel", foreground=RED)
        self._auth_label.grid(row=0, column=3, padx=8, sticky="w")

        info_text = (f"Jump: {JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}  \u2192  "
                     f"{REMOTE_USER}@{REMOTE_HOST}:<port>")
        ttk.Label(conn, text=info_text, foreground="grey").grid(
            row=1, column=0, columnspan=4, padx=8, pady=(0, 4), sticky="w")

        # -- progress bar + status bar (pack early so they stay at bottom) ---
        bottom = ttk.Frame(root)
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 8))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(bottom,
                                            variable=self.progress_var,
                                            maximum=100,
                                            mode="determinate")
        self.progress_bar.pack(fill="x", pady=(0, 2))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self.status_var,
                  style="Status.TLabel").pack(fill="x")

        # -- notebook --------------------------------------------------------
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        self._build_upload_download_tab()
        self._build_batch_search_tab()

    # -----------------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------------
    def _prompt_passwords(self):
        """Show the password dialog and store credentials."""
        dlg = PasswordDialog(self.root)
        if dlg.result is not None:
            self._relay_pw, self._local_pw = dlg.result
            self._auth_var.set("\u2705 Authenticated")
            self._auth_label.configure(foreground=GREEN)

    def _ensure_passwords(self):
        """Make sure passwords are available; prompt if not."""
        if self._relay_pw and self._local_pw:
            return True
        self._prompt_passwords()
        return bool(self._relay_pw and self._local_pw)

    def _clear_passwords(self):
        """Clear stored credentials (e.g. after auth failure)."""
        self._relay_pw = None
        self._local_pw = None
        self.root.after(0, self._update_auth_indicator_disconnected)

    def _update_auth_indicator_disconnected(self):
        self._auth_var.set("\u274C Not authenticated")
        self._auth_label.configure(foreground=RED)

    # -----------------------------------------------------------------------
    # SSH connection (paramiko)
    # -----------------------------------------------------------------------
    @contextmanager
    def _open_connection(self):
        """Context manager yielding a paramiko SSHClient connected to the
        remote server through the jump host.

        Raises ``ConnectionError`` with a user-friendly message on failure.
        """
        jump = paramiko.SSHClient()
        jump.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        remote = paramiko.SSHClient()
        remote.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # 1. Connect to relay / jump host
            try:
                jump.connect(
                    JUMP_HOST,
                    port=int(JUMP_PORT),
                    username=JUMP_USER,
                    password=self._relay_pw,
                    timeout=15,
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

            # 2. Open forwarded channel to the remote host
            try:
                transport = jump.get_transport()
                channel = transport.open_channel(
                    "direct-tcpip",
                    (REMOTE_HOST, int(self.remote_port.get())),
                    ("127.0.0.1", 0),
                )
            except Exception as exc:
                raise ConnectionError(
                    f"Cannot open tunnel to local server:\n{exc}")

            # 3. Connect to the remote host through the tunnel
            try:
                remote.connect(
                    REMOTE_HOST,
                    username=REMOTE_USER,
                    password=self._local_pw,
                    sock=channel,
                    timeout=15,
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
        """Execute *cmd* on the connected *ssh_client* and return
        ``(stdout_str, stderr_str, exit_code)``."""
        _stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return out, err, code

    # -----------------------------------------------------------------------
    # Tab 1 – Upload / Download
    # -----------------------------------------------------------------------
    def _build_upload_download_tab(self):
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="  Upload / Download  ")

        # Remote path
        pf = ttk.LabelFrame(tab, text="Remote Linux Path")
        pf.pack(fill="x", pady=(0, 10))
        self.remote_path = tk.StringVar(
            value="/home/hat/Downloads/pythonscripts/")
        ttk.Entry(pf, textvariable=self.remote_path).pack(
            fill="x", padx=8, pady=6)

        # Upload
        uf = ttk.LabelFrame(tab, text="Upload")
        uf.pack(fill="x", pady=(0, 10))

        self.file_path = tk.StringVar()
        row = ttk.Frame(uf)
        row.pack(fill="x", padx=8, pady=6)
        ttk.Entry(row, textvariable=self.file_path).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row, text="Browse File",
                   command=self._browse_file).pack(side="right")

        self._upload_btn = ttk.Button(uf, text="\u2B06  UPLOAD",
                                      style="Green.TButton",
                                      command=self._upload)
        self._upload_btn.pack(pady=(0, 8))

        # Download
        df = ttk.LabelFrame(tab, text="Download")
        df.pack(fill="x")

        self.local_path = tk.StringVar()
        row2 = ttk.Frame(df)
        row2.pack(fill="x", padx=8, pady=6)
        ttk.Entry(row2, textvariable=self.local_path).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row2, text="Browse Folder",
                   command=self._browse_folder).pack(side="right")

        self._download_btn = ttk.Button(df, text="\u2B07  DOWNLOAD",
                                        style="Blue.TButton",
                                        command=self._download)
        self._download_btn.pack(pady=(0, 8))

    # -----------------------------------------------------------------------
    # Tab 2 – Batch Search
    # -----------------------------------------------------------------------
    def _build_batch_search_tab(self):
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="  Batch Search  ")

        # -- search criteria -------------------------------------------------
        cf = ttk.LabelFrame(tab, text="Search Criteria")
        cf.pack(fill="x", pady=(0, 8))

        # Date / Time row
        dt_frame = ttk.Frame(cf)
        dt_frame.pack(fill="x", padx=8, pady=(8, 4))

        # FROM
        ttk.Label(dt_frame, text="From:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w")
        if HAS_TKCALENDAR:
            self.from_date = DateEntry(dt_frame, width=11,
                                       date_pattern="dd/MM/yyyy",
                                       font=("Segoe UI", 10))
            self.from_date.grid(row=0, column=1, padx=4)
        else:
            self._from_date_var = tk.StringVar(
                value=datetime.now().strftime("%d/%m/%Y"))
            ttk.Entry(dt_frame, textvariable=self._from_date_var,
                      width=11).grid(row=0, column=1, padx=4)

        self.from_hour = ttk.Spinbox(dt_frame, from_=0, to=23, width=3,
                                     format="%02.0f", font=("Segoe UI", 10))
        self.from_hour.set("00")
        self.from_hour.grid(row=0, column=2, padx=(4, 0))
        ttk.Label(dt_frame, text=":").grid(row=0, column=3)
        self.from_min = ttk.Spinbox(dt_frame, from_=0, to=59, width=3,
                                    format="%02.0f", font=("Segoe UI", 10))
        self.from_min.set("00")
        self.from_min.grid(row=0, column=4, padx=(0, 16))

        # TO
        ttk.Label(dt_frame, text="To:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=5, sticky="w")
        if HAS_TKCALENDAR:
            self.to_date = DateEntry(dt_frame, width=11,
                                     date_pattern="dd/MM/yyyy",
                                     font=("Segoe UI", 10))
            self.to_date.grid(row=0, column=6, padx=4)
        else:
            self._to_date_var = tk.StringVar(
                value=datetime.now().strftime("%d/%m/%Y"))
            ttk.Entry(dt_frame, textvariable=self._to_date_var,
                      width=11).grid(row=0, column=6, padx=4)

        self.to_hour = ttk.Spinbox(dt_frame, from_=0, to=23, width=3,
                                   format="%02.0f", font=("Segoe UI", 10))
        self.to_hour.set("23")
        self.to_hour.grid(row=0, column=7, padx=(4, 0))
        ttk.Label(dt_frame, text=":").grid(row=0, column=8)
        self.to_min = ttk.Spinbox(dt_frame, from_=0, to=59, width=3,
                                  format="%02.0f", font=("Segoe UI", 10))
        self.to_min.set("59")
        self.to_min.grid(row=0, column=9, padx=(0, 8))

        # +1 h shortcut
        ttk.Button(dt_frame, text="+1 h",
                   command=self._set_to_plus_one_hour).grid(
            row=0, column=10, padx=4)

        # System IDs
        id_frame = ttk.Frame(cf)
        id_frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(id_frame, text="System ID(s)*:").pack(side="left",
                                                         padx=(0, 4))
        self.system_ids_var = tk.StringVar()
        ttk.Entry(id_frame, textvariable=self.system_ids_var).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(id_frame, text="comma\u2011separated",
                  foreground="grey").pack(side="left")

        # Serial number
        sn_frame = ttk.Frame(cf)
        sn_frame.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Label(sn_frame, text="Serial Number:").pack(side="left",
                                                         padx=(0, 4))
        self.serial_var = tk.StringVar()
        ttk.Entry(sn_frame, textvariable=self.serial_var).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(sn_frame, text="optional", foreground="grey").pack(
            side="left")

        # Search button
        btn_row = ttk.Frame(cf)
        btn_row.pack(fill="x", padx=8, pady=(0, 8))
        self._search_btn = ttk.Button(btn_row, text="\U0001F50D  Search",
                                      style="Blue.TButton",
                                      command=self._do_search)
        self._search_btn.pack(side="left")
        self._result_count_var = tk.StringVar()
        ttk.Label(btn_row, textvariable=self._result_count_var,
                  foreground=ACCENT, font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=12)

        # -- results ---------------------------------------------------------
        rf = ttk.LabelFrame(tab, text="Results")
        rf.pack(fill="both", expand=True, pady=(0, 8))

        cols = ("filename", "folder", "datetime", "system_id", "serial",
                "full_path")
        self.tree = ttk.Treeview(rf, columns=cols, show="headings",
                                 selectmode="extended")

        for col, label in (("filename", "Filename"),
                           ("folder", "Folder"),
                           ("datetime", "Date / Time"),
                           ("system_id", "System ID"),
                           ("serial", "Serial #"),
                           ("full_path", "Server Path")):
            self.tree.heading(
                col, text=label,
                command=lambda c=col: self._sort_tree(c))

        # Track current sort state
        self._sort_col = None
        self._sort_asc = True

        self.tree.column("filename", width=220, minwidth=140)
        self.tree.column("folder", width=90, minwidth=60)
        self.tree.column("datetime", width=120, minwidth=100)
        self.tree.column("system_id", width=80, minwidth=60)
        self.tree.column("serial", width=80, minwidth=60)
        self.tree.column("full_path", width=260, minwidth=160)

        vsb = ttk.Scrollbar(rf, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(rf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0),
                       pady=(6, 0))
        vsb.grid(row=0, column=1, sticky="ns", pady=(6, 0))
        hsb.grid(row=1, column=0, sticky="ew", padx=(8, 0))
        rf.columnconfigure(0, weight=1)
        rf.rowconfigure(0, weight=1)

        # -- actions ---------------------------------------------------------
        af = ttk.Frame(tab)
        af.pack(fill="x")

        ttk.Button(af, text="Select All",
                   command=self._select_all).pack(side="left", padx=(0, 4))
        ttk.Button(af, text="Deselect All",
                   command=self._deselect_all).pack(side="left", padx=(0, 16))

        self.dest_var = tk.StringVar()
        ttk.Button(af, text="\U0001F4C1 Destination",
                   command=self._browse_dest).pack(side="left", padx=(0, 4))
        ttk.Entry(af, textvariable=self.dest_var, width=28).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        self._dl_sel_btn = ttk.Button(af, text="\u2B07  Download Selected",
                                      style="Green.TButton",
                                      command=self._download_selected)
        self._dl_sel_btn.pack(side="right")

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
        local_file = self.file_path.get().strip()
        if not local_file:
            messagebox.showerror("Error", "Select a file to upload.")
            return
        if not os.path.isfile(local_file):
            messagebox.showerror("Error", f"File not found:\n{local_file}")
            return
        if not self._ensure_passwords():
            return

        remote_dest = self.remote_path.get().strip()
        if remote_dest.endswith("/"):
            remote_dest += os.path.basename(local_file)

        self._upload_btn.state(["disabled"])
        self.status_var.set("Connecting for upload \u2026")
        self.progress_var.set(0)
        self.root.update_idletasks()

        def _worker():
            try:
                with self._open_connection() as ssh:
                    sftp = ssh.open_sftp()
                    try:
                        def _cb(transferred, total):
                            pct = (transferred / total * 100
                                   if total > 0 else 0)
                            self.root.after(0, lambda p=pct: (
                                self.progress_var.set(p),
                                self.status_var.set(
                                    f"Uploading\u2026 {p:.0f}%")))

                        sftp.put(local_file, remote_dest, callback=_cb)
                    finally:
                        sftp.close()

                self.root.after(0, lambda: (
                    messagebox.showinfo(
                        "Success",
                        f"Uploaded to:\n{remote_dest}"),
                    self.status_var.set("Upload complete"),
                    self.progress_var.set(100)))

            except ConnectionError as exc:
                self._clear_passwords()
                self.root.after(0, lambda: (
                    messagebox.showerror("Connection Error", str(exc)),
                    self.status_var.set("Upload failed"),
                    self.progress_var.set(0)))
            except Exception as exc:
                self.root.after(0, lambda: (
                    messagebox.showerror("Upload Error", str(exc)),
                    self.status_var.set("Upload failed"),
                    self.progress_var.set(0)))
            finally:
                self.root.after(
                    0, lambda: self._upload_btn.state(["!disabled"]))

        threading.Thread(target=_worker, daemon=True).start()

    def _download(self):
        dest_folder = self.local_path.get().strip()
        if not dest_folder:
            messagebox.showerror("Error", "Select local destination folder.")
            return
        remote_src = self.remote_path.get().strip()
        if not remote_src:
            messagebox.showerror("Error", "Specify a remote path.")
            return
        if not self._ensure_passwords():
            return

        local_file = os.path.join(dest_folder, os.path.basename(remote_src))

        self._download_btn.state(["disabled"])
        self.status_var.set("Connecting for download \u2026")
        self.progress_var.set(0)
        self.root.update_idletasks()

        def _worker():
            try:
                with self._open_connection() as ssh:
                    sftp = ssh.open_sftp()
                    try:
                        def _cb(transferred, total):
                            pct = (transferred / total * 100
                                   if total > 0 else 0)
                            self.root.after(0, lambda p=pct: (
                                self.progress_var.set(p),
                                self.status_var.set(
                                    f"Downloading\u2026 {p:.0f}%")))

                        sftp.get(remote_src, local_file, callback=_cb)
                    finally:
                        sftp.close()

                self.root.after(0, lambda: (
                    messagebox.showinfo(
                        "Success",
                        f"Downloaded to:\n{local_file}"),
                    self.status_var.set("Download complete"),
                    self.progress_var.set(100)))

            except ConnectionError as exc:
                self._clear_passwords()
                self.root.after(0, lambda: (
                    messagebox.showerror("Connection Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self.progress_var.set(0)))
            except Exception as exc:
                self.root.after(0, lambda: (
                    messagebox.showerror("Download Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self.progress_var.set(0)))
            finally:
                self.root.after(
                    0, lambda: self._download_btn.state(["!disabled"]))

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
                        int(self.from_hour.get()), int(self.from_min.get()))

    def _get_to_dt(self):
        if HAS_TKCALENDAR:
            d = self.to_date.get_date()
        else:
            d = datetime.strptime(self._to_date_var.get(),
                                  "%d/%m/%Y").date()
        return datetime(d.year, d.month, d.day,
                        int(self.to_hour.get()), int(self.to_min.get()))

    def _set_to_plus_one_hour(self):
        """Set *To* = *From* + 1 hour (quick shortcut)."""
        try:
            target = self._get_from_dt() + timedelta(hours=1)
        except (ValueError, AttributeError):
            return
        if HAS_TKCALENDAR:
            self.to_date.set_date(target.date())
        else:
            self._to_date_var.set(target.strftime("%d/%m/%Y"))
        self.to_hour.set(f"{target.hour:02d}")
        self.to_min.set(f"{target.minute:02d}")

    # -----------------------------------------------------------------------
    # Filename parser
    # -----------------------------------------------------------------------
    @staticmethod
    def _parse_zip(filepath):
        """Return a dict with parsed info or *None* if the name doesn't
        match the expected pattern."""
        basename = os.path.basename(filepath.strip())
        m = ZIP_RE.match(basename)
        if not m:
            return None
        dt_str, sys_id, serial = m.groups()
        try:
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
        except ValueError:
            return None
        # folder is the first component after "batches/"
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

        self._search_btn.state(["disabled"])
        self.status_var.set("Connecting via SSH \u2026")
        self.progress_var.set(0)
        self.root.update_idletasks()

        def _worker():
            try:
                with self._open_connection() as ssh:
                    self.root.after(
                        0, lambda: self.status_var.set(
                            "Searching for zip files \u2026"))

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
                    0, lambda: self._search_btn.state(["!disabled"]))

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
        """Sort the results Treeview by *col*, toggling direction."""
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        rows = [(self.tree.set(iid, col), iid) for iid in
                self.tree.get_children()]

        # For numeric columns use numeric sort
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

        # Update heading arrows
        arrow = " \u25B2" if self._sort_asc else " \u25BC"
        col_labels = {
            "filename": "Filename",
            "folder": "Folder",
            "datetime": "Date / Time",
            "system_id": "System ID",
            "serial": "Serial #",
            "full_path": "Server Path",
        }
        for c, label in col_labels.items():
            suffix = arrow if c == col else ""
            self.tree.heading(c, text=label + suffix)

    # -----------------------------------------------------------------------
    # Download selected files
    # -----------------------------------------------------------------------
    def _download_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "No files selected.")
            return

        dest = self.dest_var.get().strip()
        if not dest:
            messagebox.showerror("Error",
                                 "Choose a local destination folder first.")
            return

        paths = []
        for iid in selected:
            vals = self.tree.item(iid, "values")
            full_path = vals[5]
            # Safety: only allow paths that look like expected server paths
            if not full_path.startswith(BATCHES_PATH):
                continue
            paths.append(full_path)

        if not paths:
            messagebox.showerror("Error",
                                 "No valid server paths in selection.")
            return

        if not self._ensure_passwords():
            return

        self._dl_sel_btn.state(["disabled"])
        self.status_var.set(
            f"Preparing download of {len(paths)} file(s) \u2026")
        self.progress_var.set(0)
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

                            # Avoid overwriting: add suffix if file exists
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
                                self.progress_var.set(
                                    (i - 1) / t * 100)))

                            sftp.get(remote_path, local_file)

                        self.root.after(0, lambda: self.progress_var.set(100))
                    finally:
                        sftp.close()

                self.root.after(0, lambda: (
                    messagebox.showinfo(
                        "Success",
                        f"Downloaded {len(paths)} file(s) to:\n{dest}"),
                    self.status_var.set("Download complete"),
                    self.progress_var.set(100)))

            except ConnectionError as exc:
                self._clear_passwords()
                self.root.after(0, lambda: (
                    messagebox.showerror("Connection Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self.progress_var.set(0)))
            except Exception as exc:
                self.root.after(0, lambda: (
                    messagebox.showerror("Error", str(exc)),
                    self.status_var.set("Download failed"),
                    self.progress_var.set(0)))
            finally:
                self.root.after(
                    0, lambda: self._dl_sel_btn.state(["!disabled"]))

        threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if paramiko is None:
        _r = tk.Tk()
        _r.withdraw()
        messagebox.showerror(
            "Missing Dependency",
            "The 'paramiko' library is required.\n\n"
            "Install it with:\n  pip install paramiko")
        _r.destroy()
        raise SystemExit(1)

    root = tk.Tk()
    App(root)
    root.mainloop()
