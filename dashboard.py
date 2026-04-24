import os
import queue
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import customtkinter as ctk
import psutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "openclaw.log"
EXPORT_DIR = BASE_DIR / "exports"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


@dataclass
class LogEvent:
    raw: str
    timestamp: str
    level: str = "INFO"
    task: Optional[str] = None
    agent: Optional[str] = None
    browser_connected: Optional[bool] = None


class LogClassifier:
    LEVEL_PATTERNS = {
        "ERROR": [r"\berror\b", r"\bfailed\b", r"\bexception\b", r"\btraceback\b"],
        "WARN": [r"\bwarn\b", r"\bretry\b", r"\btimeout\b"],
    }

    AGENT_PATTERNS = {
        "Planner Agent": [r"planner", r"plan"],
        "Browser Agent": [r"browser", r"page", r"navigate"],
        "Vision Agent": [r"vision", r"ocr", r"image"],
        "Verifier Agent": [r"verify", r"validated", r"assert"],
        "Recovery Agent": [r"recover", r"rollback", r"retry"],
    }

    TASK_PATTERN = re.compile(r"\btask\b[:\- ]*(.*)", re.IGNORECASE)

    @classmethod
    def classify(cls, line: str) -> LogEvent:
        lower = line.lower()
        level = "INFO"

        for candidate, patterns in cls.LEVEL_PATTERNS.items():
            if any(re.search(pattern, lower) for pattern in patterns):
                level = candidate
                break

        agent = None
        for name, patterns in cls.AGENT_PATTERNS.items():
            if any(re.search(pattern, lower) for pattern in patterns):
                agent = name
                break

        task = None
        match = cls.TASK_PATTERN.search(line)
        if match and match.group(1).strip():
            task = match.group(1).strip()[:120]

        browser_connected = None
        if "browser started" in lower or "browser connected" in lower:
            browser_connected = True
        elif "browser disconnected" in lower or "browser crashed" in lower:
            browser_connected = False

        return LogEvent(
            raw=line,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            task=task,
            agent=agent,
            browser_connected=browser_connected,
        )


class LogTailHandler(FileSystemEventHandler):
    def __init__(self, log_file: Path, callback):
        super().__init__()
        self.log_file = log_file
        self.callback = callback
        self.offset = 0

    def bootstrap(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.touch(exist_ok=True)
        self.offset = self.log_file.stat().st_size

    def on_modified(self, event):
        if Path(event.src_path) != self.log_file:
            return

        with self.log_file.open("r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(self.offset)
            for line in handle:
                line = line.rstrip("\n")
                if line:
                    self.callback(line)
            self.offset = handle.tell()


class OpenClawDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OpenClaw Visual Monitor — Advanced")
        self.geometry("1600x980")
        self.minsize(1280, 820)

        self.running = True
        self.event_queue = queue.Queue()

        self.cpu_history = deque(maxlen=180)
        self.ram_history = deque(maxlen=180)
        self.timeline_events = deque(maxlen=600)
        self.error_count = 0
        self.warning_count = 0

        self.browser_status = "Disconnected"
        self.current_task = "Idle"
        self.agent_state = {
            "Planner Agent": "IDLE",
            "Browser Agent": "IDLE",
            "Vision Agent": "IDLE",
            "Verifier Agent": "IDLE",
            "Recovery Agent": "IDLE",
        }

        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.log_handler = LogTailHandler(LOG_FILE, self.enqueue_log)
        self.log_handler.bootstrap()
        self.observer = Observer()
        self.observer.schedule(self.log_handler, str(LOG_DIR), recursive=False)
        self.observer.start()

        threading.Thread(target=self.metrics_worker, daemon=True).start()
        threading.Thread(target=self.process_health_worker, daemon=True).start()

        self.after(100, self.process_events)

    def build_ui(self):
        self.grid_columnconfigure((0, 1, 2), weight=1, uniform="main")
        self.grid_rowconfigure((0, 1), weight=1)

        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.graph_frame = ctk.CTkFrame(self)
        self.graph_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.agent_frame = ctk.CTkFrame(self)
        self.agent_frame.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        self.timeline_frame = ctk.CTkFrame(self)
        self.timeline_frame.grid(row=1, column=2, sticky="nsew", padx=10, pady=10)

        self.build_status_panel()
        self.build_graph_panel()
        self.build_agent_panel()
        self.build_log_panel()
        self.build_timeline_panel()

    def build_status_panel(self):
        ctk.CTkLabel(self.status_frame, text="System Status", font=("Arial", 24, "bold")).pack(pady=14)

        self.cpu_label = ctk.CTkLabel(self.status_frame, text="CPU: 0.0%", font=("Arial", 18))
        self.cpu_label.pack(pady=6)

        self.ram_label = ctk.CTkLabel(self.status_frame, text="RAM: 0.0%", font=("Arial", 18))
        self.ram_label.pack(pady=6)

        self.process_label = ctk.CTkLabel(self.status_frame, text="OpenClaw Proc: Unknown", font=("Arial", 16))
        self.process_label.pack(pady=6)

        self.browser_label = ctk.CTkLabel(self.status_frame, text="Browser: Disconnected", font=("Arial", 18))
        self.browser_label.pack(pady=6)

        self.error_label = ctk.CTkLabel(self.status_frame, text="Errors: 0", font=("Arial", 18))
        self.error_label.pack(pady=6)

        self.warning_label = ctk.CTkLabel(self.status_frame, text="Warnings: 0", font=("Arial", 18))
        self.warning_label.pack(pady=6)

        self.task_label = ctk.CTkLabel(
            self.status_frame,
            text="Task: Idle",
            font=("Arial", 16),
            wraplength=380,
            justify="left",
        )
        self.task_label.pack(pady=10)

        command_frame = ctk.CTkFrame(self.status_frame)
        command_frame.pack(fill="x", padx=10, pady=10)
        command_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(command_frame, text="Export Logs", command=self.export_logs).grid(
            row=0, column=0, padx=6, pady=6, sticky="ew"
        )
        ctk.CTkButton(command_frame, text="Clear Timeline", command=self.clear_timeline).grid(
            row=0, column=1, padx=6, pady=6, sticky="ew"
        )
        ctk.CTkButton(command_frame, text="Restart Browser", command=self.restart_browser).grid(
            row=1, column=0, padx=6, pady=6, sticky="ew"
        )
        ctk.CTkButton(command_frame, text="Emergency Stop", command=self.emergency_stop).grid(
            row=1, column=1, padx=6, pady=6, sticky="ew"
        )

    def build_graph_panel(self):
        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def build_agent_panel(self):
        ctk.CTkLabel(self.agent_frame, text="Agent Activity", font=("Arial", 22, "bold")).pack(pady=10)

        self.agent_labels = {}
        for agent_name in self.agent_state:
            label = ctk.CTkLabel(self.agent_frame, text=f"{agent_name}: IDLE", font=("Arial", 15))
            label.pack(anchor="w", padx=12, pady=3)
            self.agent_labels[agent_name] = label

        self.activity_box = ctk.CTkTextbox(self.agent_frame, height=220)
        self.activity_box.pack(fill="both", expand=True, padx=10, pady=10)

    def build_log_panel(self):
        ctk.CTkLabel(self.log_frame, text="Live OpenClaw Logs", font=("Arial", 22, "bold")).pack(pady=8)
        self.log_box = ctk.CTkTextbox(self.log_frame, height=320)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

    def build_timeline_panel(self):
        ctk.CTkLabel(self.timeline_frame, text="AI Decision Timeline", font=("Arial", 22, "bold")).pack(pady=8)
        self.timeline_box = ctk.CTkTextbox(self.timeline_frame)
        self.timeline_box.pack(fill="both", expand=True, padx=10, pady=10)

    def enqueue_log(self, line: str):
        self.event_queue.put(("log", line))

    def metrics_worker(self):
        while self.running:
            cpu_percent = psutil.cpu_percent(interval=1)
            ram_percent = psutil.virtual_memory().percent
            self.event_queue.put(("metrics", cpu_percent, ram_percent))

    def process_health_worker(self):
        while self.running:
            openclaw_related = 0
            openclaw_cpu = 0.0
            for proc in psutil.process_iter(attrs=["name", "cmdline", "cpu_percent"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                    if "openclaw" in name or "openclaw" in cmdline:
                        openclaw_related += 1
                        openclaw_cpu += float(proc.info.get("cpu_percent") or 0.0)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            self.event_queue.put(("proc", openclaw_related, openclaw_cpu))
            time.sleep(2)

    def process_events(self):
        while not self.event_queue.empty():
            event = self.event_queue.get_nowait()
            kind = event[0]

            if kind == "metrics":
                self.handle_metrics(event[1], event[2])
            elif kind == "log":
                self.handle_log(event[1])
            elif kind == "proc":
                self.process_label.configure(text=f"OpenClaw Proc: {event[1]} | CPU: {event[2]:.1f}%")

        if self.running:
            self.after(100, self.process_events)

    def handle_metrics(self, cpu: float, ram: float):
        self.cpu_history.append(cpu)
        self.ram_history.append(ram)

        self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")
        self.ram_label.configure(text=f"RAM: {ram:.1f}%")

        self.ax1.clear()
        self.ax2.clear()

        self.ax1.plot(list(self.cpu_history), color="#4aa3ff", linewidth=1.3)
        self.ax1.set_ylim(0, 100)
        self.ax1.set_title("CPU Usage")

        self.ax2.plot(list(self.ram_history), color="#2ecc71", linewidth=1.3)
        self.ax2.set_ylim(0, 100)
        self.ax2.set_title("RAM Usage")

        self.fig.tight_layout(pad=1.4)
        self.canvas.draw_idle()

    def handle_log(self, line: str):
        event = LogClassifier.classify(line)

        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")

        if event.level == "ERROR":
            self.error_count += 1
            self.error_label.configure(text=f"Errors: {self.error_count}")
            self.update_agent("Recovery Agent", "RUNNING")
        elif event.level == "WARN":
            self.warning_count += 1
            self.warning_label.configure(text=f"Warnings: {self.warning_count}")

        if event.browser_connected is not None:
            self.browser_status = "Connected" if event.browser_connected else "Disconnected"
            self.browser_label.configure(text=f"Browser: {self.browser_status}")
            self.update_agent("Browser Agent", "RUNNING" if event.browser_connected else "IDLE")

        if event.task:
            self.current_task = event.task
            self.task_label.configure(text=f"Task: {self.current_task}")
            self.update_agent("Planner Agent", "ACTIVE")

        if event.agent:
            updated_state = {
                "ERROR": "FAIL",
                "WARN": "WAITING",
                "INFO": "RUNNING",
            }.get(event.level, "RUNNING")
            self.update_agent(event.agent, updated_state)

        self.add_timeline_event(event.timestamp, f"{event.level}: {event.raw[:140]}")
        self.activity_box.insert("end", f"[{event.timestamp}] {event.raw}\n")
        self.activity_box.see("end")

    def update_agent(self, agent_name: str, status: str):
        if agent_name not in self.agent_state:
            return

        self.agent_state[agent_name] = status
        label = self.agent_labels[agent_name]
        label.configure(text=f"{agent_name}: {status}")

    def add_timeline_event(self, timestamp: str, description: str):
        event_text = f"{timestamp}  {description}"
        self.timeline_events.append(event_text)
        self.timeline_box.insert("end", event_text + "\n")
        self.timeline_box.see("end")

    def clear_timeline(self):
        self.timeline_events.clear()
        self.timeline_box.delete("1.0", "end")

    def restart_browser(self):
        self.add_timeline_event(datetime.now().strftime("%H:%M:%S"), "Command Center: Restart Browser")
        self.update_agent("Browser Agent", "RUNNING")

    def emergency_stop(self):
        self.add_timeline_event(datetime.now().strftime("%H:%M:%S"), "Command Center: Emergency Stop")
        for agent in self.agent_state:
            self.update_agent(agent, "IDLE")

    def export_logs(self):
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"openclaw_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        target = EXPORT_DIR / filename

        if LOG_FILE.exists():
            target.write_text(LOG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
            self.log_box.insert("end", f"\n[+] Logs exported: {target.relative_to(BASE_DIR)}\n")
            self.log_box.see("end")

    def on_close(self):
        self.running = False

        if hasattr(self, "observer"):
            self.observer.stop()
            self.observer.join(timeout=2)

        self.destroy()


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)

    app = OpenClawDashboard()
    app.mainloop()
