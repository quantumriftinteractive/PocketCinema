"""Small Tk control panel; desktop behavior remains in the non-GUI modules."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .capabilities import detect_tool, preferred_local_address, probe_stremio_service
from .config import (
    ConfigurationError,
    DesktopSettings,
    load_settings,
    pocketcinema_url,
    resolve_network_settings,
    save_settings,
    user_data_root,
    validate_settings,
)
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


LISTEN_LABELS = {
    "Automatic / Local network": "automatic",
    "All interfaces": "all_interfaces",
    "Custom address": "custom",
}


class PocketCinemaDesktop:
    def __init__(self, root):
        self.root = root
        self.data_root = user_data_root()
        try:
            settings = load_settings(self.data_root)
        except ConfigurationError as exc:
            settings, self.startup_warning = DesktopSettings(), str(exc)
        else:
            self.startup_warning = ""
        self.lifecycle = PCServerLifecycle(self.data_root)
        self.values = {
            key: tk.StringVar(value=str(value))
            for key, value in asdict(settings).items()
            if key != "schema_version"
        }
        self.listen_choice = tk.StringVar(value=self._listen_label(settings.listen_mode))
        self.server_state = tk.StringVar(value="Stopped")
        self.server_detail = tk.StringVar(value="")
        self.device_url = tk.StringVar(value="Not available")
        self.listen_detail = tk.StringVar(value="")
        self.service_state = tk.StringVar(value="Not checked")
        self.tool_ffmpeg = tk.StringVar(value="Checking…")
        self.tool_ffprobe = tk.StringVar(value="Checking…")
        self._effective_settings = None
        self._build()
        self.refresh_capabilities()
        self.refresh_network_summary()
        self.poll()
        if self.startup_warning:
            messagebox.showwarning("PocketCinema Server", self.startup_warning)

    @staticmethod
    def _listen_label(mode):
        return next(label for label, value in LISTEN_LABELS.items() if value == mode)

    def _build(self):
        self.root.title("PocketCinema Server")
        configure_tk_theme(self.root)
        icon = Path(__file__).resolve().parents[2] / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png"
        try:
            self.root.iconphoto(True, tk.PhotoImage(file=str(icon)))
        except tk.TclError:
            pass
        self.root.minsize(760, 650)
        outer = ttk.Frame(self.root, padding=18)
        outer.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(18, weight=1)

        row = 0
        ttk.Label(outer, text="Server", font=("TkDefaultFont", 15, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        row += 1
        self._field(outer, row, "Server name", "server_name")
        row += 1
        ttk.Label(outer, text="Listen on").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        self.listen_selector = ttk.Combobox(
            outer, textvariable=self.listen_choice, values=tuple(LISTEN_LABELS), state="readonly"
        )
        self.listen_selector.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        self.listen_selector.bind("<<ComboboxSelected>>", self.on_listen_mode_changed)
        row += 1
        self.listen_status_label = ttk.Label(outer, textvariable=self.listen_detail, wraplength=620)
        self.listen_status_label.grid(row=row, column=1, columnspan=2, sticky="w", pady=(0, 3))
        row += 1
        self.custom_listen_label = ttk.Label(outer, text="Custom listen address")
        self.custom_listen_entry = ttk.Entry(outer, textvariable=self.values["listen_address"])
        self.custom_listen_label.grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        self.custom_listen_entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        self.custom_listen_row = row
        row += 1
        self._field(outer, row, "Port", "listen_port")
        row += 1
        ttk.Label(outer, text="PocketCinema address").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        self.address_display = ttk.Entry(outer, textvariable=self.device_url, state="readonly")
        self.address_display.grid(row=row, column=1, sticky="ew", pady=3)
        self.copy_button = ttk.Button(outer, text="Copy address", command=self.copy_endpoint)
        self.copy_button.grid(row=row, column=2, padx=(8, 0), pady=3)
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        ttk.Label(outer, text="Stremio Service", font=("TkDefaultFont", 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w"
        )
        row += 1
        ttk.Label(outer, text="PocketCinema Server uses this endpoint to talk to Stremio Service.", wraplength=660).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 5)
        )
        row += 1
        self._field(outer, row, "Endpoint", "stremio_service_url", button=("Check connection", self.check_service))
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        ttk.Label(outer, text="Media tools", font=("TkDefaultFont", 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w"
        )
        row += 1
        ttk.Label(outer, text="FFmpeg").grid(row=row, column=0, sticky="w")
        ttk.Label(outer, textvariable=self.tool_ffmpeg).grid(row=row, column=1, columnspan=2, sticky="w")
        row += 1
        ttk.Label(outer, text="FFprobe").grid(row=row, column=0, sticky="w")
        ttk.Label(outer, textvariable=self.tool_ffprobe).grid(row=row, column=1, columnspan=2, sticky="w")
        row += 1
        self.advanced_button = ttk.Button(outer, text="Advanced settings…", command=self.open_advanced)
        self.advanced_button.grid(row=row, column=0, columnspan=3, sticky="w", pady=(5, 2))
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        actions = ttk.Frame(outer)
        actions.grid(row=row, column=0, columnspan=3, sticky="w")
        self.save_button = ttk.Button(actions, text="Save settings", command=self.save)
        self.save_button.grid(row=0, column=0, padx=(0, 8))
        self.start_button = ttk.Button(actions, text="Start server", command=self.start)
        self.start_button.grid(row=0, column=1, padx=8)
        self.stop_button = ttk.Button(actions, text="Stop server", command=self.stop)
        self.stop_button.grid(row=0, column=2, padx=8)
        self.restart_button = ttk.Button(actions, text="Restart", command=self.restart)
        self.restart_button.grid(row=0, column=3, padx=8)
        row += 1

        ttk.Label(outer, text="Status", font=("TkDefaultFont", 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(12, 2)
        )
        row += 1
        self._status_row(outer, row, "PocketCinema Server", self.server_state)
        row += 1
        self._status_row(outer, row, "PocketCinema address", self.device_url)
        row += 1
        self._status_row(outer, row, "Stremio Service", self.service_state)
        row += 1
        if self.server_detail.get():
            ttk.Label(outer, textvariable=self.server_detail, wraplength=660).grid(
                row=row, column=0, columnspan=3, sticky="w"
            )
            row += 1
        ttk.Label(outer, text="Sanitized server log", font=("TkDefaultFont", 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(12, 4)
        )
        row += 1
        self.log = tk.Text(
            outer, height=7, state="disabled", wrap="word", background="#17181a",
            foreground="#e6e6e6", insertbackground="#e6e6e6", relief="flat",
        )
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew")
        outer.rowconfigure(row, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.on_listen_mode_changed()

    @staticmethod
    def _status_row(parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=1)
        ttk.Label(parent, textvariable=variable, wraplength=620).grid(row=row, column=1, columnspan=2, sticky="w", pady=1)

    def _field(self, parent, row, label, name, button=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        ttk.Entry(parent, textvariable=self.values[name]).grid(row=row, column=1, sticky="ew", pady=3)
        if button:
            text, command = button
            ttk.Button(parent, text=text, command=command).grid(row=row, column=2, padx=(8, 0), pady=3)

    def settings(self):
        values = {key: value.get() for key, value in self.values.items()}
        values["listen_mode"] = LISTEN_LABELS[self.listen_choice.get()]
        return DesktopSettings(**values)

    def effective_settings(self):
        return resolve_network_settings(self.settings(), preferred_local_address())

    def on_listen_mode_changed(self, event=None):
        custom = LISTEN_LABELS[self.listen_choice.get()] == "custom"
        if custom:
            self.custom_listen_label.grid()
            self.custom_listen_entry.grid()
        else:
            self.custom_listen_label.grid_remove()
            self.custom_listen_entry.grid_remove()
        self.refresh_network_summary()

    def refresh_network_summary(self):
        try:
            settings = self._effective_settings or self.effective_settings()
            address = pocketcinema_url(settings.advertised_address, settings.listen_port)
            self.device_url.set(address)
            if settings.listen_mode == "automatic":
                self.listen_detail.set(f"Automatically uses {settings.listen_address} when the server starts.")
            elif settings.listen_mode == "all_interfaces":
                self.listen_detail.set(f"Listens on all interfaces; PocketCinema uses {settings.advertised_address}.")
            else:
                self.listen_detail.set("Uses the custom address configured below.")
        except ConfigurationError as exc:
            self.device_url.set("Not available")
            self.listen_detail.set(str(exc))

    def choose_tool(self, name):
        selected = filedialog.askopenfilename(title="Choose " + name.replace("_", " "))
        if selected:
            self.values[name].set(selected)
            self.refresh_capabilities()

    def refresh_capabilities(self):
        ffmpeg = detect_tool("ffmpeg", self.values["ffmpeg_path"].get())
        ffprobe = detect_tool("ffprobe", self.values["ffprobe_path"].get())
        self.tool_ffmpeg.set("Available" if ffmpeg.available else "Missing")
        self.tool_ffprobe.set("Available" if ffprobe.available else "Missing")

    def open_advanced(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced settings")
        dialog.transient(self.root)
        dialog.columnconfigure(1, weight=1)
        frame = ttk.Frame(dialog, padding=14)
        frame.grid(sticky="nsew")
        dialog.columnconfigure(0, weight=1)
        manual = tk.BooleanVar(value=self.values["advertised_mode"].get() == "manual")
        ttk.Checkbutton(frame, text="Manually set PocketCinema address", variable=manual).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        self._advanced_field(frame, 1, "PocketCinema address", "advertised_address")
        self._advanced_field(frame, 2, "Network label", "network_name")
        self._advanced_field(frame, 3, "FFmpeg path", "ffmpeg_path", choose=True)
        self._advanced_field(frame, 4, "FFprobe path", "ffprobe_path", choose=True)

        def apply_advanced():
            self.values["advertised_mode"].set("manual" if manual.get() else "automatic")
            self.refresh_capabilities()
            self.refresh_network_summary()
            dialog.destroy()

        ttk.Button(frame, text="Done", command=apply_advanced).grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))

    def _advanced_field(self, parent, row, label, name, choose=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Entry(parent, textvariable=self.values[name], width=48).grid(row=row, column=1, sticky="ew", pady=3)
        if choose:
            ttk.Button(parent, text="Choose…", command=lambda: self.choose_tool(name)).grid(row=row, column=2, padx=(8, 0))

    def save(self):
        try:
            saved = save_settings(self.settings(), self.data_root)
        except (ConfigurationError, OSError) as exc:
            messagebox.showerror("Settings not saved", str(exc))
            return None
        self.apply(saved)
        return saved

    def apply(self, settings):
        for key, value in asdict(settings).items():
            if key in self.values:
                self.values[key].set(str(value))
        self.listen_choice.set(self._listen_label(settings.listen_mode))
        self._effective_settings = None
        self.on_listen_mode_changed()
        self.refresh_capabilities()

    def check_service(self):
        url = self.values["stremio_service_url"].get()
        self.service_state.set("Checking…")

        def worker():
            status = probe_stremio_service(url)
            label = "Connected" if status.reachable else "Unreachable"
            self.root.after(0, lambda: self.service_state.set(label))

        threading.Thread(target=worker, daemon=True).start()

    def _start_with_current_settings(self):
        try:
            settings = self.effective_settings()
        except ConfigurationError as exc:
            self.root.after(0, lambda: messagebox.showerror("Server cannot start", str(exc)))
            return
        self._effective_settings = settings
        result = self.lifecycle.start(settings)
        self.root.after(0, lambda: self.show_lifecycle(result))

    def start(self):
        try:
            validate_settings(self.settings())
        except ConfigurationError as exc:
            messagebox.showerror("Server cannot start", str(exc))
            return
        self.server_state.set("Starting")
        threading.Thread(target=self._start_with_current_settings, daemon=True).start()

    def stop(self):
        self.server_state.set("Stopping")

        def worker():
            result = self.lifecycle.stop()
            self.root.after(0, lambda: self.show_lifecycle(result))

        threading.Thread(target=worker, daemon=True).start()

    def restart(self):
        def worker():
            self.lifecycle.stop()
            self._start_with_current_settings()

        self.server_state.set("Starting")
        threading.Thread(target=worker, daemon=True).start()

    def copy_endpoint(self):
        endpoint = self.device_url.get()
        if endpoint != "Not available":
            self.root.clipboard_clear()
            self.root.clipboard_append(endpoint)

    def show_lifecycle(self, result):
        self.server_state.set(result.state)
        if result.state == "Error":
            self.server_detail.set(result.message)
        else:
            self.server_detail.set("")
        if result.state == "Stopped":
            self._effective_settings = None
        self.refresh_network_summary()
        self.update_actions(result.state)

    def update_actions(self, state):
        running = state in {"Starting", "Running"}
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.restart_button.configure(state="normal" if state == "Running" else "disabled")

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
