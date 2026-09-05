"""Small Tk control panel; desktop behavior remains in the non-GUI modules."""
from __future__ import annotations

from dataclasses import asdict
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .capabilities import device_endpoints, detect_tool, preferred_local_address, probe_stremio_service
from .config import (
    ConfigurationError,
    DesktopSettings,
    derive_device_endpoints,
    load_settings,
    pocketcinema_url,
    presented_device_endpoints,
    resolve_network_settings,
    save_settings,
    user_data_root,
    validate_settings,
)
from .lifecycle import PCServerLifecycle, sanitize_log_line
from .tray import SERVER_ICON, WindowsTray, menu_state, tray_title
from .workers import DesktopWorkers


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


def connection_summary(count):
    """Keep the status row concise; concrete URLs belong in the route list."""
    if count <= 0:
        return "None available"
    return f"{count} available"


class PocketCinemaDesktop:
    def __init__(self, root, instance=None):
        self.root = root
        self.instance = instance
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
        self._operation_lock = threading.Lock()
        self._last_logs = ()
        self._closing = False
        self._busy = False
        self.workers = DesktopWorkers()
        self.tray = None
        self._tray_failed = False
        self._quit_error = None
        self._build()
        for name in ("listen_port", "listen_address", "advertised_address"):
            self.values[name].trace_add("write", self._on_route_setting_changed)
        self.refresh_capabilities()
        self.refresh_network_summary()
        if sys.platform == "win32":
            try:
                self.tray = WindowsTray(
                    lambda action: self.workers.post(lambda: self.tray_action(action)),
                    self.tray_state,
                    lambda: tray_title(self.lifecycle.status().state),
                )
            except Exception:
                self._tray_failed = True
                messagebox.showerror("System tray unavailable",
                    "Install server/requirements-desktop.txt and relaunch. "
                    "The window will stay open; use Quit to exit.")
        self.pump_workers()
        self.poll()
        if self.startup_warning:
            messagebox.showwarning("PocketCinema Server", self.startup_warning)

    @staticmethod
    def _listen_label(mode):
        return next(label for label, value in LISTEN_LABELS.items() if value == mode)

    def _build(self):
        self.root.title("PocketCinema Server")
        configure_tk_theme(self.root)
        icon = SERVER_ICON
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
        ttk.Label(outer, text="PocketCinema connections", font=("TkDefaultFont", 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(7, 3)
        )
        row += 1
        ttk.Label(
            outer,
            text="Use Local on the same network. Use Tailscale / Remote only with the Miyoo's separately configured proxy.",
            wraplength=660,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 4))
        row += 1
        self.connections_frame = ttk.Frame(outer)
        self.connections_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        self.connections_frame.columnconfigure(1, weight=1)
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
        ttk.Button(actions, text="Quit", command=self.quit).grid(row=0, column=4, padx=8)
        row += 1

        ttk.Label(outer, text="Status", font=("TkDefaultFont", 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(12, 2)
        )
        row += 1
        self._status_row(outer, row, "PocketCinema Server", self.server_state)
        row += 1
        self._status_row(outer, row, "PocketCinema connections", self.device_url)
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
        endpoints = device_endpoints()
        return resolve_network_settings(self.settings(), preferred_local_address(endpoints))

    def effective_endpoints(self, settings):
        return derive_device_endpoints(settings, device_endpoints())

    def on_listen_mode_changed(self, event=None):
        custom = LISTEN_LABELS[self.listen_choice.get()] == "custom"
        if custom:
            self.custom_listen_label.grid()
            self.custom_listen_entry.grid()
        else:
            self.custom_listen_label.grid_remove()
            self.custom_listen_entry.grid_remove()
        self.refresh_network_summary()

    def _on_route_setting_changed(self, *_unused):
        if self._effective_settings is None:
            self.refresh_network_summary()

    def refresh_network_summary(self):
        requested_settings = self._effective_settings or self.settings()
        pinned_settings = self._effective_settings

        def worker():
            try:
                routes = device_endpoints()
                settings = pinned_settings or resolve_network_settings(
                    requested_settings, preferred_local_address(routes)
                )
                endpoints = derive_device_endpoints(settings, routes)
                urls = [
                    (endpoint.label, pocketcinema_url(endpoint.address, settings.listen_port))
                    for endpoint in presented_device_endpoints(endpoints)
                ]
                if settings.listen_mode == "automatic":
                    detail = "Automatically serves detected Local network connections only."
                elif settings.listen_mode == "all_interfaces":
                    detail = "Listens once on all current interfaces and keeps Local and Remote routes separate."
                else:
                    detail = "Uses the custom address configured below."
            except ConfigurationError as exc:
                urls, detail = (), str(exc)
            self.workers.post(lambda: self._show_network_summary(urls, detail))

        self.workers.start(worker)

    def _show_network_summary(self, urls, detail):
        self.device_url.set(connection_summary(len(urls)))
        self._render_connections(urls)
        self.listen_detail.set(detail)

    def _render_connections(self, urls):
        for child in self.connections_frame.winfo_children():
            child.destroy()
        if not urls:
            ttk.Label(self.connections_frame, text="No reachable PocketCinema address is available.").grid(
                row=0, column=0, columnspan=3, sticky="w"
            )
            return
        for row, (label, url) in enumerate(urls):
            ttk.Label(self.connections_frame, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=2
            )
            value = ttk.Entry(self.connections_frame)
            value.insert(0, url)
            value.configure(state="readonly")
            value.grid(row=row, column=1, sticky="ew", pady=2)
            ttk.Button(
                self.connections_frame, text="Copy", command=lambda endpoint=url: self.copy_endpoint(endpoint)
            ).grid(row=row, column=2, padx=(8, 0), pady=2)

    def choose_tool(self, name):
        selected = filedialog.askopenfilename(title="Choose " + name.replace("_", " "))
        if selected:
            self.values[name].set(selected)
            self.refresh_capabilities()

    def refresh_capabilities(self):
        ffmpeg_path = self.values["ffmpeg_path"].get()
        ffprobe_path = self.values["ffprobe_path"].get()

        def worker():
            ffmpeg = detect_tool("ffmpeg", ffmpeg_path)
            ffprobe = detect_tool("ffprobe", ffprobe_path)
            self.workers.post(lambda: self._show_capabilities(ffmpeg, ffprobe))

        self.workers.start(worker)

    def _show_capabilities(self, ffmpeg, ffprobe):
        self.tool_ffmpeg.set(self._tool_status_text(ffmpeg))
        self.tool_ffprobe.set(self._tool_status_text(ffprobe))

    @staticmethod
    def _tool_status_text(status):
        if not status.available:
            return "Missing"
        return "Available" if status.source == "manual" else f"Available ({status.source})"

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
            self.workers.post(lambda: self.service_state.set(label))

        self.workers.start(worker)

    def _start_with_settings(self, requested_settings):
        routes = device_endpoints()
        settings = resolve_network_settings(
            requested_settings, preferred_local_address(routes)
        )
        endpoints = derive_device_endpoints(settings, routes)
        result = self.lifecycle.start(settings, [endpoint.address for endpoint in endpoints])
        self.workers.post(lambda: self.show_lifecycle(result, settings))

    def _operation(self, action):
        if self._closing or self._busy:
            return
        state = self.lifecycle.status().state
        if action == "start" and state in {"Starting", "Running", "Stopping"}:
            return
        if action == "restart" and state != "Running":
            return
        settings = None
        if action != "stop":
            try:
                settings = validate_settings(self.settings())
            except ConfigurationError as exc:
                self.show()
                messagebox.showerror("Server cannot start", str(exc))
                return
        self._busy = True
        self.server_state.set("Stopping" if action == "stop" else "Starting")
        self.update_actions(self.server_state.get())

        def worker():
            try:
                with self._operation_lock:
                    if self._closing:
                        return
                    if action in {"stop", "restart"}:
                        result = self.lifecycle.stop()
                        if action == "stop":
                            self.workers.post(lambda: self.show_lifecycle(result))
                    if action != "stop" and not self._closing:
                        self._start_with_settings(settings)
            except Exception as exc:
                detail = sanitize_log_line(str(exc))
                self.workers.post(lambda: self._operation_error(detail))
            finally:
                self.workers.post(self._operation_done)

        self.workers.start(worker)

    def _operation_error(self, detail):
        self.show()
        messagebox.showerror("Server operation failed", detail)

    def _operation_done(self):
        self._busy = False
        self.update_actions(self.lifecycle.status().state)

    def start(self):
        self._operation("start")

    def stop(self):
        self._operation("stop")

    def restart(self):
        self._operation("restart")

    def copy_endpoint(self, endpoint=None):
        if endpoint:
            self.root.clipboard_clear()
            self.root.clipboard_append(endpoint)

    def show_lifecycle(self, result, effective_settings=None, refresh_routes=True):
        if self._closing:
            return
        self.server_state.set(result.state)
        if result.state == "Error":
            self.server_detail.set(result.message)
        else:
            self.server_detail.set("")
        if result.state == "Stopped":
            self._effective_settings = None
        elif effective_settings is not None and result.state == "Running":
            self._effective_settings = effective_settings
        if refresh_routes:
            self.refresh_network_summary()
        self.update_actions(result.state)

    def tray_state(self):
        return menu_state(self.lifecycle.status().state, self._busy, self._closing)

    def tray_action(self, action):
        if self._closing:
            return
        if action == "open":
            self.show()
        elif action == "quit":
            self.quit()
        elif action == "restart":
            self.restart()
        elif action == "toggle":
            label, enabled, _ = self.tray_state()
            if enabled:
                self.stop() if label == "Stop server" else self.start()

    def update_actions(self, state):
        _, enabled, restart = menu_state(state, self._busy, self._closing)
        self.start_button.configure(state="normal" if enabled and state != "Running" else "disabled")
        self.stop_button.configure(state="normal" if enabled and state == "Running" else "disabled")
        self.restart_button.configure(state="normal" if restart else "disabled")
        if self.tray:
            self.tray.update()

    def poll(self):
        if self._closing:
            return
        if self.instance and self.instance.restore_requested():
            self.show()
        if not self._busy:
            self.show_lifecycle(self.lifecycle.status(), refresh_routes=False)
        elif self.tray:
            self.tray.update()
        logs = tuple(self.lifecycle.logs)
        if logs != self._last_logs:
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.insert("1.0", "\n".join(logs))
            self.log.configure(state="disabled")
            self._last_logs = logs
        if self.tray and (self.tray.error or not self.tray.thread.is_alive()) and not self._tray_failed:
            self._tray_failed = True
            self.show()
            messagebox.showerror("System tray unavailable", "The window will stay open; use Quit to exit.")
        self.root.after(700, self.poll)

    def pump_workers(self):
        if self._closing:
            if self.workers.idle():
                if self._quit_error:
                    detail, self._quit_error = self._quit_error, None
                    self.workers.discard()
                    self._closing = False
                    self._busy = False
                    self.show()
                    messagebox.showerror("Quit incomplete", detail)
                    self.poll()
                    self.root.after(50, self.pump_workers)
                    return
                self.root.destroy()
                return
        else:
            self.workers.drain()
            self.workers.idle()
        self.root.after(50, self.pump_workers)

    def show(self):
        if self._closing:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def close(self):
        if self._closing:
            return
        if sys.platform == "win32":
            if self.tray and self.tray.available:
                self.root.withdraw()
            else:
                messagebox.showerror("System tray unavailable", "The window will stay open; use Quit to exit.")
        else:
            self.quit()

    def quit(self):
        if self._closing:
            return
        self._closing = True
        self.server_state.set("Stopping")
        self.update_actions("Stopping")

        def worker():
            try:
                with self._operation_lock:
                    self.lifecycle.stop()
                if self.tray:
                    self.tray.stop()
            except Exception as exc:
                self._quit_error = sanitize_log_line(str(exc)) or "Could not finish shutdown; retry Quit."

        self.workers.start(worker)


def main():
    instance = None
    if sys.platform == "win32":
        from .instance import WindowsInstance
        instance = WindowsInstance(user_data_root())
        if not instance.primary:
            instance.close()
            return
    try:
        root = tk.Tk()
        PocketCinemaDesktop(root, instance=instance)
        root.mainloop()
    finally:
        if instance:
            instance.close()
