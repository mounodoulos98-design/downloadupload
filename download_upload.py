import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import sys

JUMP_USER = "gstefanakis"
JUMP_HOST = "adinsightscons.hat-analytics.net"
JUMP_PORT = "15930"

REMOTE_USER = "hat"
REMOTE_HOST = "localhost"

def browse_file():
    file_path.set(filedialog.askopenfilename())

def browse_folder():
    local_path.set(filedialog.askdirectory())

def upload():
    if not file_path.get():
        messagebox.showerror("Error", "Select a file to upload")
        return

    cmd = [
        "scp",
        "-P", remote_port.get(),
        "-J", f"{JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}",
        file_path.get(),
        f"{REMOTE_USER}@{REMOTE_HOST}:{remote_path.get()}"
    ]

    run(cmd)

def download():
    if not local_path.get():
        messagebox.showerror("Error", "Select local destination folder")
        return

    cmd = [
        "scp",
        "-P", remote_port.get(),
        "-J", f"{JUMP_USER}@{JUMP_HOST}:{JUMP_PORT}",
        f"{REMOTE_USER}@{REMOTE_HOST}:{remote_path.get()}",
        local_path.get()
    ]

    run(cmd)

def run(cmd):
    try:
        full_cmd = " ".join(cmd)
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command", full_cmd],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    except Exception as e:
        messagebox.showerror("Error", str(e))


# GUI
root = tk.Tk()
root.title("SCP Upload / Download (Jump Host)")
root.geometry("520x340")

file_path = tk.StringVar()
local_path = tk.StringVar()
remote_port = tk.StringVar(value="39022")
remote_path = tk.StringVar(value="/home/hat/Downloads/pythonscripts/")

tk.Label(root, text="Remote Port").pack()
tk.Entry(root, textvariable=remote_port).pack(fill="x", padx=10)

tk.Label(root, text="Remote Linux Path").pack()
tk.Entry(root, textvariable=remote_path).pack(fill="x", padx=10)

tk.Label(root, text="Upload: Select Local File").pack(pady=(10, 0))
tk.Entry(root, textvariable=file_path).pack(fill="x", padx=10)
tk.Button(root, text="Browse File", command=browse_file).pack()

tk.Button(root, text="UPLOAD", bg="#4CAF50", fg="white", command=upload).pack(pady=10)

tk.Label(root, text="Download: Select Local Folder").pack()
tk.Entry(root, textvariable=local_path).pack(fill="x", padx=10)
tk.Button(root, text="Browse Folder", command=browse_folder).pack()

tk.Button(root, text="DOWNLOAD", bg="#2196F3", fg="white", command=download).pack(pady=10)

root.mainloop()
