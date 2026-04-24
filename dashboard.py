import os
import queue
import shutil
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import psutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "openclaw.log"
EXPORT_DIR = Path("exports")
HISTORY_POINTS = 60
TIMELINE_POINTS = 120

AGENTS = [
    "Planner Agent",
    "Browser Agent",
    "Vision Agent",
    "Verifier Agent",
    "Recovery Agent",
]

STATUS_COLORS = {
    "ACTIVE": "#00C853",
    "RUNNING": "#42A5F5",
    "SCANNING": "#AB47BC",
    "WAITING": "#FFB300",
    "IDLE": "#90A4AE",
    "ERROR": "#F44336",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LogEventHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_modified(self, event):
        if Path(event.src_path).resolve() == LOG_FILE.resolve():
            self.callback()


class OpenClawDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OpenClaw Visual Monitor")
        self.geometry("1500x950")
        self.minsize(1200, 800)

        self.cpu_history = deque(maxlen=HISTORY_POINTS)
        self.ram_history = deque(maxlen=HISTORY_POINTS)
        self.error_timeline = deque([0] * TIMELINE_POINTS, maxlen=TIMELINE_POINTS)

        self.error_count = 0
        self.browser_status = "Disconnected"
        self.task_count = 0

        self.ui_queue = queue.Queue()
        self.agent_labels = {}
        self.observer = None
        self.log_handle = None

        self._ensure_paths()
        self.build_ui()
        self._load_recent_logs()

        threading.Thread(target=self.collect_metrics, daemon=True).start()
        self.start_log_observer()

        self.after(100, self.process_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _ensure_paths(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE.touch(exist_ok=True)

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        root = ctk.CTkFrame(self)
        root.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=2)
        root.grid_rowconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=2)

        self.status_frame = ctk.CTkFrame(root)
        self.status_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))

        self.graph_frame = ctk.CTkFrame(root)
        self.graph_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))

        self.log_frame = ctk.CTkFrame(root)
        self.log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))

        self.build_status_panel()
        self.build_graphs()
        self.build_logs()

    def build_status_panel(self):
        title = ctk.CTkLabel(
            self.status_frame,
            text="OpenClaw System Status",
            font=("Arial", 24, "bold"),
        )
        title.pack(pady=(14, 10))

        self.cpu_label = ctk.CTkLabel(self.status_frame, text="CPU: 0%", font=("Arial", 18))
        self.cpu_label.pack(pady=4)

        self.ram_label = ctk.CTkLabel(self.status_frame, text="RAM: 0%", font=("Arial", 18))
        self.ram_label.pack(pady=4)

        self.browser_label = ctk.CTkLabel(
            self.status_frame,
            text="Browser: Disconnected",
            font=("Arial", 18),
        )
        self.browser_label.pack(pady=4)

        self.error_label = ctk.CTkLabel(
            self.status_frame,
            text="Errors: 0",
            font=("Arial", 18),
        )
        self.error_label.pack(pady=4)

        self.task_label = ctk.CTkLabel(
            self.status_frame,
            text="Tasks: 0",
            font=("Arial", 18),
        )
        self.task_label.pack(pady=4)

        agent_title = ctk.CTkLabel(
            self.status_frame,
            text="Agent Activity",
            font=("Arial", 18, "bold"),
        )
        agent_title.pack(pady=(10, 4))

        for agent in AGENTS:
            label = ctk.CTkLabel(
                self.status_frame,
                text=f"{agent}: IDLE",
                text_color=STATUS_COLORS["IDLE"],
                font=("Arial", 15),
            )
            label.pack(anchor="w", padx=20, pady=1)
            self.agent_labels[agent] = label

        button_frame = ctk.CTkFrame(self.status_frame)
        button_frame.pack(fill="x", padx=14, pady=(12, 12))

        self.export_button = ctk.CTkButton(button_frame, text="Export Logs", command=self.export_logs)
        self.export_button.pack(fill="x", pady=3)

        self.restart_button = ctk.CTkButton(
            button_frame,
            text="Restart Browser",
            command=lambda: self.command_action("Restart Browser"),
        )
        self.restart_button.pack(fill="x", pady=3)

        self.stop_button = ctk.CTkButton(
            button_frame,
            text="Emergency Stop",
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            command=lambda: self.command_action("Emergency Stop"),
        )
        self.stop_button.pack(fill="x", pady=3)

    def build_graphs(self):
        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax1 = self.fig.add_subplot(311)
        self.ax2 = self.fig.add_subplot(312)
        self.ax3 = self.fig.add_subplot(313)

        self.fig.tight_layout(pad=2.5)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def build_logs(self):
        header = ctk.CTkFrame(self.log_frame)
        header.pack(fill="x", padx=10, pady=(8, 4))

        title = ctk.CTkLabel(header, text="Live OpenClaw Logs & Timeline", font=("Arial", 22, "bold"))
        title.pack(side="left")

        self.timeline_box = ctk.CTkTextbox(self.log_frame, height=90)
        self.timeline_box.pack(fill="x", padx=10, pady=(4, 4))
        self.timeline_box.insert("end", "[timeline] Waiting for events...\n")
        self.timeline_box.configure(state="disabled")

        self.log_box = ctk.CTkTextbox(self.log_frame, height=260)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def collect_metrics(self):
        while True:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            self.ui_queue.put(("metrics", cpu, ram))

    def process_ui_queue(self):
        while not self.ui_queue.empty():
            event = self.ui_queue.get_nowait()
            event_type = event[0]

            if event_type == "metrics":
                _, cpu, ram = event
                self.cpu_history.append(cpu)
                self.ram_history.append(ram)
                self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")
                self.ram_label.configure(text=f"RAM: {ram:.1f}%")
                self.update_graphs()

            if event_type == "log":
                _, line = event
                self.process_log_line(line)

        self.after(100, self.process_ui_queue)

    def update_graphs(self):
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()

        self.ax1.plot(list(self.cpu_history), color="#42A5F5", linewidth=1.8)
        self.ax1.set_ylim(0, 100)
        self.ax1.set_title("CPU Usage %")

        self.ax2.plot(list(self.ram_history), color="#66BB6A", linewidth=1.8)
        self.ax2.set_ylim(0, 100)
        self.ax2.set_title("RAM Usage %")

        self.ax3.plot(list(self.error_timeline), color="#EF5350", linewidth=1.4)
        self.ax3.set_title("Errors / Tick")

        self.fig.tight_layout(pad=2.0)
        self.canvas.draw_idle()

    def _load_recent_logs(self):
        with LOG_FILE.open("r", encoding="utf-8", errors="ignore") as file:
            lines = file.readlines()[-100:]

        for line in lines:
            self.log_box.insert("end", line)

        self.log_box.see("end")

    def start_log_observer(self):
        self.log_handle = LOG_FILE.open("r", encoding="utf-8", errors="ignore")
        self.log_handle.seek(0, os.SEEK_END)

        event_handler = LogEventHandler(self.read_new_log_lines)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(LOG_DIR), recursive=False)
        self.observer.start()

    def read_new_log_lines(self):
        while True:
            line = self.log_handle.readline()
            if not line:
                break
            self.ui_queue.put(("log", line))

    def process_log_line(self, line):
        self.log_box.insert("end", line)
        self.log_box.see("end")

        lower = line.lower()
        tick_errors = 0

        if "error" in lower or "failed" in lower:
            self.error_count += 1
            tick_errors = 1
            self.error_label.configure(text=f"Errors: {self.error_count}")

        self.error_timeline.append(tick_errors)

        if "browser started" in lower or "browser connected" in lower:
            self.browser_status = "Connected"
            self.browser_label.configure(text="Browser: Connected")
        if "browser stopped" in lower or "browser disconnected" in lower:
            self.browser_status = "Disconnected"
            self.browser_label.configure(text="Browser: Disconnected")

        if "task" in lower:
            self.task_count += 1
            self.task_label.configure(text=f"Tasks: {self.task_count}")
            self.append_timeline(f"Task event: {line.strip()[:110]}")

        self.update_agent_statuses(lower)

    def update_agent_statuses(self, lower_line):
        updates = {
            "planner": ("Planner Agent", "ACTIVE"),
            "browser": ("Browser Agent", "RUNNING"),
            "vision": ("Vision Agent", "SCANNING"),
            "verify": ("Verifier Agent", "WAITING"),
            "recovery": ("Recovery Agent", "ACTIVE"),
            "error": ("Recovery Agent", "ERROR"),
        }

        for keyword, (agent, status) in updates.items():
            if keyword in lower_line:
                self.set_agent_status(agent, status)

    def set_agent_status(self, agent, status):
        color = STATUS_COLORS.get(status, "#FFFFFF")
        self.agent_labels[agent].configure(text=f"{agent}: {status}", text_color=color)

    def append_timeline(self, event):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.timeline_box.configure(state="normal")
        self.timeline_box.insert("end", f"{timestamp} {event}\n")
        self.timeline_box.see("end")
        self.timeline_box.configure(state="disabled")

    def command_action(self, command_name):
        self.append_timeline(f"Command executed: {command_name}")
        self.log_box.insert("end", f"[control] {command_name}\n")
        self.log_box.see("end")

    def export_logs(self):
        timestamp = int(time.time())
        export_file = EXPORT_DIR / f"openclaw_logs_{timestamp}.txt"
        shutil.copy2(LOG_FILE, export_file)
        self.log_box.insert("end", f"\n[+] Logs exported to {export_file}\n")
        self.append_timeline(f"Logs exported: {export_file.name}")
        self.log_box.see("end")

    def on_close(self):
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
        if self.log_handle:
            self.log_handle.close()
        self.destroy()


if __name__ == "__main__":
    app = OpenClawDashboard()
    app.mainloop()
