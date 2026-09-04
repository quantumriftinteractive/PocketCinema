"""Small Tk control panel; desktop behavior remains in the non-GUI modules."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .capabilities import detect_tool, probe_stremio_service
from .config import ConfigurationError, DesktopSettings, load_settings, save_settings, user_data_root, validate_settings
from .lifecycle import PCServerLifecycle


def configure_tk_theme(root):
    """Keep Apple Tcl/Tk 8.5 controls visible under modern macOS dark mode."""
    version = tuple(int(part) for part in root.tk.call("info", "patchlevel").split("."))
    if sys.platform != "darwin" or version >= (8, 6):
        return
    style = ttk.Style(root)
    style.theme_use("clam")
    background = "#f2f2f2"
    foreground = "#202124"
    style.configure(".", background=background, foreground=foreground)
    style.configure("TFrame", background=background)
    style.configure("TLabel", background=background, foreground=foreground)
    style.configure("TButton", background=background, foreground=foreground, padding=6)
    style.configure("TEntry", fieldbackground="#ffffff", foreground=foreground)
    root.configure(background=background)


class PocketCinemaDesktop:
    def __init__(self, root):
        self.root = root
        self.data_root = user_data_root()
        try:
            settings = load_settings(self.data_root)
        except ConfigurationError as exc:
            settings = DesktopSettings()
            self.startup_warning = str(exc)
        else:
            self.startup_warning = ""
        self.lifecycle = PCServerLifecycle(self.data_root)
        self.values = {key: tk.StringVar(value=str(value)) for key, value in asdict(settings).items() if key != "schema_version"}
        self.status = tk.StringVar(value="PCServer is stopped.")
        self.endpoint = tk.StringVar(value="Miyoo endpoint: not running")
        self.service = tk.StringVar(value="Stremio Service: not checked")
        self.tools = tk.StringVar(value="Media tools: checking…")
        self._build()
        self.refresh_capabilities()
        self.poll()
        if self.startup_warning:
            messagebox.showwarning("PocketCinema Server", self.startup_warning)

    def _build(self):
        self.root.title("PocketCinema Server")
        configure_tk_theme(self.root)
        icon = Path(__file__).resolve().parents[2] / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png"
        try:
            self.root.iconphoto(True, tk.PhotoImage(file=str(icon)))
        except tk.TclError:
            pass
        self.root.minsize(720, 530)
        outer = ttk.Frame(self.root, padding=14)
        outer.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        row = 0
        for title, fields in (
            ("Server", (("PCServer name", "server_name"), ("Listen address", "listen_address"), ("Port", "listen_port"), ("Device-facing address", "advertised_address"), ("Network label", "network_name"))),
            ("Stremio Service", (("Endpoint", "stremio_service_url"),)),
            ("Media tools", (("FFmpeg path (optional)", "ffmpeg_path"), ("FFprobe path (optional)", "ffprobe_path"))),
        ):
            ttk.Label(outer, text=title, font=("TkDefaultFont", 12, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(10 if row else 0, 3))
            row += 1
            for label, name in fields:
                ttk.Label(outer, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
                ttk.Entry(outer, textvariable=self.values[name]).grid(row=row, column=1, sticky="ew", pady=2)
                if name in {"ffmpeg_path", "ffprobe_path"}:
                    ttk.Button(outer, text="Choose…", command=lambda key=name: self.choose_tool(key)).grid(row=row, column=2, padx=(8, 0))
                row += 1
        controls = ttk.Frame(outer)
        controls.grid(row=row, column=0, columnspan=3, sticky="w", pady=(12, 5))
        ttk.Button(controls, text="Save settings", command=self.save).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(controls, text="Check Stremio", command=self.check_service).grid(row=0, column=1, padx=6)
        ttk.Button(controls, text="Start server", command=self.start).grid(row=0, column=2, padx=6)
        ttk.Button(controls, text="Stop server", command=self.stop).grid(row=0, column=3, padx=6)
        ttk.Button(controls, text="Restart", command=self.restart).grid(row=0, column=4, padx=6)
        ttk.Button(controls, text="Copy Miyoo address", command=self.copy_endpoint).grid(row=0, column=5, padx=6)
        row += 1
        for variable in (self.status, self.endpoint, self.service, self.tools):
            ttk.Label(outer, textvariable=variable, wraplength=670).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
            row += 1
        ttk.Label(outer, text="Sanitized server log", font=("TkDefaultFont", 12, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 3))
        row += 1
        self.log = tk.Text(
            outer, height=9, width=86, state="disabled", wrap="word",
            background="#ffffff", foreground="#202124", insertbackground="#202124",
        )
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew")
        outer.rowconfigure(row, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def settings(self):
        return DesktopSettings(**{key: value.get() for key, value in self.values.items()})

    def choose_tool(self, name):
        selected = filedialog.askopenfilename(title="Choose " + name.replace("_", " "))
        if selected:
            self.values[name].set(selected)
            self.refresh_capabilities()

    def save(self):
        try:
            saved = save_settings(self.settings(), self.data_root)
        except (ConfigurationError, OSError) as exc:
            messagebox.showerror("Settings not saved", str(exc))
            return None
        self.status.set("Settings saved.")
        self.apply(saved)
        return saved

    def apply(self, settings):
        for key, value in asdict(settings).items():
            if key in self.values:
                self.values[key].set(str(value))
        self.refresh_capabilities()

    def refresh_capabilities(self):
        ffmpeg = detect_tool("ffmpeg", self.values["ffmpeg_path"].get())
        ffprobe = detect_tool("ffprobe", self.values["ffprobe_path"].get())
        self.tools.set(f"FFmpeg: {'available' if ffmpeg.available else 'missing'} | FFprobe: {'available' if ffprobe.available else 'missing'}")

    def check_service(self):
        url = self.values["stremio_service_url"].get()
        self.service.set("Stremio Service: checking…")
        def worker():
            status = probe_stremio_service(url)
            self.root.after(0, lambda: self.service.set("Stremio Service: " + status.message))
        threading.Thread(target=worker, daemon=True).start()

    def start(self):
        try:
            settings = validate_settings(self.settings())
        except ConfigurationError as exc:
            messagebox.showerror("Server cannot start", str(exc))
            return
        self.status.set("Starting PCServer…")
        def worker():
            result = self.lifecycle.start(settings)
            self.root.after(0, lambda: self.show_lifecycle(result))
        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        def worker():
            result = self.lifecycle.stop()
            self.root.after(0, lambda: self.show_lifecycle(result))
        threading.Thread(target=worker, daemon=True).start()

    def restart(self):
        self.stop()
        self.root.after(200, self.start)

    def copy_endpoint(self):
        endpoint = self.lifecycle.status().endpoint
        if endpoint:
            self.root.clipboard_clear()
            self.root.clipboard_append(endpoint)
            self.status.set("Miyoo endpoint copied to the clipboard.")

    def show_lifecycle(self, result):
        self.status.set(f"{result.state}: {result.message}")
        self.endpoint.set("Miyoo endpoint: " + (result.endpoint if result.endpoint else "not running"))

    def poll(self):
        self.show_lifecycle(self.lifecycle.status())
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", "\n".join(self.lifecycle.logs))
        self.log.configure(state="disabled")
        self.root.after(700, self.poll)

    def close(self):
        self.lifecycle.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    PocketCinemaDesktop(root)
    root.mainloop()
