import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import re
import shlex
import secrets
import threading
import platform
from datetime import datetime, timedelta

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


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("SCP Tool \u2014 Upload / Download / Batch Search")
        self.root.geometry("860x680")
        self.root.minsize(780, 620)
        self.root.configure(bg=BG)

        _configure_styles()

        # -- shared variables ------------------------------------------------
        self.remote_port = tk.StringVar(value="39022")

        # -- connection bar --------------------------------------------------
        conn = ttk.LabelFrame(root, text="Connection Settings")
        conn.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(conn, text="Remote Port:").grid(row=0, column=0, padx=(8, 4),
                                                   pady=6, sticky="w")
        ttk.Entry(conn, textvariable=self.remote_port, width=12).grid(
            row=0, column=1, padx=(0, 12), pady=6)

        info_text = (f"Jump: {JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}  \u2192  "
                     f"{REMOTE_USER}@{REMOTE_HOST}:<port>")
        ttk.Label(conn, text=info_text, foreground="grey").grid(
            row=0, column=2, padx=8, sticky="w")

        # -- status bar (pack early so it stays at bottom) -------------------
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self.status_var,
                  style="Status.TLabel").pack(side="bottom", fill="x",
                                               padx=12, pady=(0, 8))

        # -- notebook --------------------------------------------------------
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        self._build_upload_download_tab()
        self._build_batch_search_tab()

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

        ttk.Button(uf, text="\u2B06  UPLOAD", style="Green.TButton",
                   command=self._upload).pack(pady=(0, 8))

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

        ttk.Button(df, text="\u2B07  DOWNLOAD", style="Blue.TButton",
                   command=self._download).pack(pady=(0, 8))

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

        self.tree.heading("filename", text="Filename")
        self.tree.heading("folder", text="Folder")
        self.tree.heading("datetime", text="Date / Time")
        self.tree.heading("system_id", text="System ID")
        self.tree.heading("serial", text="Serial #")
        self.tree.heading("full_path", text="Server Path")

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
        ttk.Button(af, text="\u2B07  Download Selected",
                   style="Green.TButton",
                   command=self._download_selected).pack(side="right")

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

    def _run_interactive(self, cmd):
        """Open an SCP / SSH command in a visible console (original behaviour)."""
        try:
            if IS_WINDOWS:
                full_cmd = " ".join(cmd)
                subprocess.Popen(
                    ["powershell", "-NoExit", "-Command", full_cmd],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                # On Linux / macOS open a terminal emulator
                subprocess.Popen(cmd)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _upload(self):
        if not self.file_path.get():
            messagebox.showerror("Error", "Select a file to upload")
            return
        cmd = [
            "scp", "-P", self.remote_port.get(),
            "-J", f"{JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}",
            self.file_path.get(),
            f"{REMOTE_USER}@{REMOTE_HOST}:{self.remote_path.get()}",
        ]
        self._run_interactive(cmd)

    def _download(self):
        if not self.local_path.get():
            messagebox.showerror("Error", "Select local destination folder")
            return
        cmd = [
            "scp", "-P", self.remote_port.get(),
            "-J", f"{JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}",
            f"{REMOTE_USER}@{REMOTE_HOST}:{self.remote_path.get()}",
            self.local_path.get(),
        ]
        self._run_interactive(cmd)

    # -----------------------------------------------------------------------
    # SSH helpers (batch search)
    # -----------------------------------------------------------------------
    def _ssh_command(self, remote_cmd, timeout=60):
        """Run *remote_cmd* on the remote host via the jump host and return
        the completed process.  The command string is passed as a single
        argument to ``ssh`` so the remote shell interprets it."""
        cmd = [
            "ssh",
            "-p", self.remote_port.get(),
            "-J", f"{JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=15",
            f"{REMOTE_USER}@{REMOTE_HOST}",
            "--",
            remote_cmd,
        ]
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)

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

        self._search_btn.state(["disabled"])
        self.status_var.set("Connecting via SSH \u2026")
        self.root.update_idletasks()

        def _worker():
            try:
                find_cmd = (
                    f"find {shlex.quote(BATCHES_PATH)} "
                    f"-type f -name '*.zip' 2>/dev/null"
                )
                result = self._ssh_command(find_cmd, timeout=60)

                if result.returncode != 0 and not result.stdout.strip():
                    self.root.after(0, lambda: messagebox.showerror(
                        "SSH Error", result.stderr or "Connection failed."))
                    return

                lines = [l for l in result.stdout.strip().splitlines()
                         if l.strip()]

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

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: messagebox.showerror(
                    "Timeout", "SSH connection timed out."))
                self.root.after(0,
                                lambda: self.status_var.set("Search timed out"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", str(exc)))
                self.root.after(0,
                                lambda: self.status_var.set("Search failed"))
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

        self.status_var.set(
            f"Preparing download of {len(paths)} file(s) \u2026")
        self.root.update_idletasks()

        def _worker():
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            rand = secrets.token_hex(8)
            remote_zip = f"/tmp/batch_dl_{ts}_{rand}.zip"
            local_zip = os.path.join(dest, f"batch_download_{ts}.zip")
            try:
                # 1. Create zip on the remote server (-j stores without dirs)
                quoted_paths = " ".join(shlex.quote(p) for p in paths)
                zip_cmd = (f"zip -j {shlex.quote(remote_zip)} {quoted_paths}")
                zr = self._ssh_command(zip_cmd, timeout=120)
                if zr.returncode != 0:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error",
                        f"Remote zip failed:\n{zr.stderr or zr.stdout}"))
                    return

                # 2. SCP the zip to local machine
                self.root.after(
                    0, lambda: self.status_var.set("Downloading zip \u2026"))
                scp_cmd = [
                    "scp",
                    "-P", self.remote_port.get(),
                    "-J", f"{JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}",
                    "-o", "StrictHostKeyChecking=no",
                    f"{REMOTE_USER}@{REMOTE_HOST}:{remote_zip}",
                    local_zip,
                ]
                sr = subprocess.run(scp_cmd, capture_output=True, text=True,
                                    timeout=600)
                if sr.returncode != 0:
                    self.root.after(0, lambda: messagebox.showerror(
                        "SCP Error", sr.stderr or "Download failed."))
                    return

                self.root.after(0, lambda: messagebox.showinfo(
                    "Success",
                    f"Downloaded {len(paths)} file(s) to:\n{local_zip}"))
                self.root.after(
                    0, lambda: self.status_var.set("Download complete"))

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: messagebox.showerror(
                    "Timeout", "Download timed out."))
                self.root.after(
                    0, lambda: self.status_var.set("Download timed out"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", str(exc)))
                self.root.after(
                    0, lambda: self.status_var.set("Download failed"))
            finally:
                # 3. Always try to remove the temp zip on the server
                try:
                    self._ssh_command(
                        f"rm -f {shlex.quote(remote_zip)}", timeout=15)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
