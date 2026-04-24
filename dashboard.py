import os
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import psutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "openclaw.log"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class OpenClawDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OpenClaw Visual Monitor")
        self.geometry("1500x950")
        self.minsize(1200, 800)

        self.cpu_history = deque(maxlen=120)
        self.ram_history = deque(maxlen=120)
        self.timeline_events = deque(maxlen=300)
        self.event_queue = queue.Queue()

        self.error_count = 0
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

        self.running = True
        threading.Thread(target=self.update_metrics_worker, daemon=True).start()
        threading.Thread(target=self.monitor_logs_worker, daemon=True).start()
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
        self.build_graphs()
        self.build_agent_panel()
        self.build_logs()
        self.build_timeline()

    def build_status_panel(self):
        ctk.CTkLabel(
            self.status_frame,
            text="OpenClaw System Status",
            font=("Arial", 24, "bold"),
        ).pack(pady=20)

        self.cpu_label = ctk.CTkLabel(self.status_frame, text="CPU: 0%", font=("Arial", 18))
        self.cpu_label.pack(pady=10)

        self.ram_label = ctk.CTkLabel(self.status_frame, text="RAM: 0%", font=("Arial", 18))
        self.ram_label.pack(pady=10)

        self.browser_label = ctk.CTkLabel(
            self.status_frame,
            text="Browser: Disconnected",
            font=("Arial", 18),
        )
        self.browser_label.pack(pady=10)

        self.error_label = ctk.CTkLabel(
            self.status_frame,
            text="Errors: 0",
            font=("Arial", 18),
        )
        self.error_label.pack(pady=10)

        self.task_label = ctk.CTkLabel(
            self.status_frame,
            text="Task: Idle",
            font=("Arial", 18),
            wraplength=350,
            justify="left",
        )
        self.task_label.pack(pady=10)

        controls = ctk.CTkFrame(self.status_frame)
        controls.pack(pady=15, padx=10, fill="x")
        controls.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(controls, text="Export Logs", command=self.export_logs).grid(
            row=0, column=0, padx=6, pady=6, sticky="ew"
        )
        ctk.CTkButton(controls, text="Clear Timeline", command=self.clear_timeline).grid(
            row=0, column=1, padx=6, pady=6, sticky="ew"
        )
        ctk.CTkButton(controls, text="Restart Browser", command=self.restart_browser).grid(
            row=1, column=0, padx=6, pady=6, sticky="ew"
        )
        ctk.CTkButton(controls, text="Emergency Stop", command=self.emergency_stop).grid(
            row=1, column=1, padx=6, pady=6, sticky="ew"
        )

    def build_graphs(self):
        self.fig = Figure(figsize=(7, 5), dpi=100)

        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def build_agent_panel(self):
        ctk.CTkLabel(
            self.agent_frame,
            text="Autonomous Agent Graph",
            font=("Arial", 22, "bold"),
        ).pack(pady=10)

        self.agent_labels = {}
        for name in self.agent_state:
            label = ctk.CTkLabel(self.agent_frame, text=f"{name}: IDLE", font=("Arial", 16))
            label.pack(anchor="w", padx=14, pady=4)
            self.agent_labels[name] = label

        ctk.CTkLabel(
            self.agent_frame,
            text="Real-Time Activity Map",
            font=("Arial", 18, "bold"),
        ).pack(pady=(20, 8))

        self.activity_box = ctk.CTkTextbox(self.agent_frame, height=220)
        self.activity_box.pack(fill="both", expand=True, padx=10, pady=10)

    def build_logs(self):
        ctk.CTkLabel(
            self.log_frame,
            text="Live OpenClaw Logs",
            font=("Arial", 22, "bold"),
        ).pack(pady=10)

        self.log_box = ctk.CTkTextbox(self.log_frame, height=300)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

    def build_timeline(self):
        ctk.CTkLabel(
            self.timeline_frame,
            text="AI Decision Timeline",
            font=("Arial", 22, "bold"),
        ).pack(pady=10)

        self.timeline_box = ctk.CTkTextbox(self.timeline_frame)
        self.timeline_box.pack(fill="both", expand=True, padx=10, pady=10)

    def update_metrics_worker(self):
        while self.running:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            self.event_queue.put(("metrics", cpu, ram))

    def monitor_logs_worker(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE.touch(exist_ok=True)

        with LOG_FILE.open("r", encoding="utf-8", errors="ignore") as file:
            file.seek(0, os.SEEK_END)
            while self.running:
                line = file.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                self.event_queue.put(("log", line.rstrip("\n")))

    def process_events(self):
        while not self.event_queue.empty():
            event = self.event_queue.get_nowait()

            if event[0] == "metrics":
                self.handle_metrics(event[1], event[2])
            elif event[0] == "log":
                self.process_log_line(event[1])

        if self.running:
            self.after(100, self.process_events)

    def handle_metrics(self, cpu, ram):
        self.cpu_history.append(cpu)
        self.ram_history.append(ram)

        self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")
        self.ram_label.configure(text=f"RAM: {ram:.1f}%")

        self.update_graphs()

    def update_graphs(self):
        self.ax1.clear()
        self.ax2.clear()

        self.ax1.plot(list(self.cpu_history), color="#5DADE2")
        self.ax1.set_ylim(0, 100)
        self.ax1.set_title("CPU Usage")

        self.ax2.plot(list(self.ram_history), color="#58D68D")
        self.ax2.set_ylim(0, 100)
        self.ax2.set_title("RAM Usage")

        self.fig.tight_layout(pad=1.5)
        self.canvas.draw_idle()

    def process_log_line(self, line):
        if not line:
            return

        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")

        lower = line.lower()
        timestamp = datetime.now().strftime("%H:%M:%S")

        if "error" in lower or "failed" in lower:
            self.error_count += 1
            self.error_label.configure(text=f"Errors: {self.error_count}")
            self.add_timeline_event(timestamp, f"ERROR: {line}")
            self.update_agent("Recovery Agent", "RUNNING")

        if "browser started" in lower or "browser connected" in lower:
            self.browser_status = "Connected"
            self.browser_label.configure(text="Browser: Connected")
            self.add_timeline_event(timestamp, "Browser connected")
            self.update_agent("Browser Agent", "RUNNING")

        if "browser disconnected" in lower:
            self.browser_status = "Disconnected"
            self.browser_label.configure(text="Browser: Disconnected")
            self.add_timeline_event(timestamp, "Browser disconnected")
            self.update_agent("Browser Agent", "IDLE")

        if "task" in lower:
            self.current_task = line[:80]
            self.task_label.configure(text=f"Task: {self.current_task}")
            self.add_timeline_event(timestamp, f"Task update: {self.current_task}")
            self.update_agent("Planner Agent", "ACTIVE")

        if "vision" in lower or "ocr" in lower:
            self.update_agent("Vision Agent", "SCANNING")

        if "verify" in lower or "validated" in lower:
            self.update_agent("Verifier Agent", "WAITING")

        self.activity_box.insert("end", f"[{timestamp}] {line}\n")
        self.activity_box.see("end")

    def update_agent(self, agent_name, status):
        self.agent_state[agent_name] = status
        label = self.agent_labels.get(agent_name)
        if label:
            label.configure(text=f"{agent_name}: {status}")

    def add_timeline_event(self, timestamp, message):
        event = f"{timestamp}  {message}"
        self.timeline_events.append(event)
        self.timeline_box.insert("end", event + "\n")
        self.timeline_box.see("end")

    def clear_timeline(self):
        self.timeline_events.clear()
        self.timeline_box.delete("1.0", "end")

    def restart_browser(self):
        self.add_timeline_event(datetime.now().strftime("%H:%M:%S"), "Command: Restart Browser")
        self.update_agent("Browser Agent", "RUNNING")

    def emergency_stop(self):
        self.add_timeline_event(datetime.now().strftime("%H:%M:%S"), "Command: Emergency Stop")
        for name in self.agent_state:
            self.update_agent(name, "IDLE")

    def export_logs(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = BASE_DIR / f"exported_logs_{timestamp}.txt"

        if LOG_FILE.exists():
            export_name.write_text(LOG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
            self.log_box.insert("end", f"\n[+] Logs exported to {export_name.name}\n")
            self.log_box.see("end")

    def on_close(self):
        self.running = False
        self.destroy()


if __name__ == "__main__":
    app = OpenClawDashboard()
    app.mainloop()
