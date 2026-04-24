import os
import threading
import time
from collections import deque
from datetime import datetime
from queue import Empty, Queue

import customtkinter as ctk
import psutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

try:
    from plyer import notification
except ImportError:  # Optional dependency for desktop notifications.
    notification = None


LOG_FILE = "logs/openclaw.log"
MAX_TIMELINE_ITEMS = 120

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class OpenClawDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OpenClaw Visual Monitor")
        self.geometry("1600x960")
        self.minsize(1280, 800)

        self.cpu_history = deque(maxlen=60)
        self.ram_history = deque(maxlen=60)

        self.error_count = 0
        self.browser_status = "Disconnected"
        self.agent_events = deque(maxlen=MAX_TIMELINE_ITEMS)
        self.agent_states = {
            "Planner Agent": "IDLE",
            "Browser Agent": "DISCONNECTED",
            "Vision Agent": "WAITING",
            "Verifier Agent": "WAITING",
            "Recovery Agent": "IDLE",
        }

        self.event_queue = Queue()

        self.build_ui()

        self.after(200, self.flush_events)

        threading.Thread(target=self.update_metrics, daemon=True).start()
        threading.Thread(target=self.monitor_logs, daemon=True).start()

    def build_ui(self):
        self.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        self.grid_rowconfigure((0, 1), weight=1)

        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.graph_frame = ctk.CTkFrame(self)
        self.graph_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.activity_frame = ctk.CTkFrame(self)
        self.activity_frame.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        self.health_frame = ctk.CTkFrame(self)
        self.health_frame.grid(row=1, column=2, sticky="nsew", padx=10, pady=10)

        self.build_status_panel()
        self.build_graphs()
        self.build_activity_map()
        self.build_logs()
        self.build_health_panel()

    def build_status_panel(self):
        title = ctk.CTkLabel(
            self.status_frame,
            text="OpenClaw System Status",
            font=("Arial", 24, "bold"),
        )
        title.pack(pady=20)

        self.cpu_label = ctk.CTkLabel(self.status_frame, text="CPU: 0%", font=("Arial", 18))
        self.cpu_label.pack(pady=8)

        self.ram_label = ctk.CTkLabel(self.status_frame, text="RAM: 0%", font=("Arial", 18))
        self.ram_label.pack(pady=8)

        self.browser_label = ctk.CTkLabel(
            self.status_frame,
            text="Browser: Disconnected",
            font=("Arial", 18),
        )
        self.browser_label.pack(pady=8)

        self.error_label = ctk.CTkLabel(
            self.status_frame,
            text="Errors: 0",
            font=("Arial", 18),
        )
        self.error_label.pack(pady=8)

        self.task_label = ctk.CTkLabel(
            self.status_frame,
            text="Task: Idle",
            font=("Arial", 18),
        )
        self.task_label.pack(pady=8)

        command_title = ctk.CTkLabel(
            self.status_frame,
            text="Command Center",
            font=("Arial", 20, "bold"),
        )
        command_title.pack(pady=(20, 8))

        commands = [
            ("Restart Browser", "Browser restart requested"),
            ("Pause Agents", "All agents paused"),
            ("Emergency Stop", "Emergency stop executed"),
            ("Force Retry", "Retry workflow triggered"),
        ]
        for label, event in commands:
            button = ctk.CTkButton(
                self.status_frame,
                text=label,
                command=lambda message=event: self.publish_event("command", message),
            )
            button.pack(pady=4, padx=10, fill="x")

        self.export_button = ctk.CTkButton(
            self.status_frame,
            text="Export Logs",
            command=self.export_logs,
        )
        self.export_button.pack(pady=20, padx=10, fill="x")

    def build_graphs(self):
        self.fig = Figure(figsize=(8, 5), dpi=100)

        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def build_activity_map(self):
        title = ctk.CTkLabel(
            self.activity_frame,
            text="AI Activity Map",
            font=("Arial", 22, "bold"),
        )
        title.pack(pady=10)

        self.agent_status_box = ctk.CTkTextbox(self.activity_frame, height=140)
        self.agent_status_box.pack(fill="x", padx=10, pady=8)

        timeline_label = ctk.CTkLabel(
            self.activity_frame,
            text="Decision Timeline",
            font=("Arial", 18, "bold"),
        )
        timeline_label.pack(pady=(10, 4))

        self.timeline_box = ctk.CTkTextbox(self.activity_frame)
        self.timeline_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.refresh_agent_statuses()

    def build_logs(self):
        title = ctk.CTkLabel(
            self.log_frame,
            text="Live OpenClaw Logs",
            font=("Arial", 22, "bold"),
        )
        title.pack(pady=10)

        self.log_box = ctk.CTkTextbox(self.log_frame, height=320)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

    def build_health_panel(self):
        title = ctk.CTkLabel(
            self.health_frame,
            text="System Health Analytics",
            font=("Arial", 22, "bold"),
        )
        title.pack(pady=10)

        subtitle = ctk.CTkLabel(
            self.health_frame,
            text="Top processes by CPU",
            font=("Arial", 16),
        )
        subtitle.pack(pady=(0, 8))

        self.process_box = ctk.CTkTextbox(self.health_frame)
        self.process_box.pack(fill="both", expand=True, padx=10, pady=10)

    def update_metrics(self):
        while True:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent

            self.cpu_history.append(cpu)
            self.ram_history.append(ram)

            proc_rows = self.collect_top_processes()
            self.event_queue.put(
                {
                    "type": "metrics",
                    "cpu": cpu,
                    "ram": ram,
                    "process_rows": proc_rows,
                }
            )

            time.sleep(0.5)

    def collect_top_processes(self):
        rows = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            info = proc.info
            rows.append(
                (
                    info.get("cpu_percent") or 0.0,
                    info.get("memory_percent") or 0.0,
                    info.get("pid") or 0,
                    info.get("name") or "unknown",
                )
            )

        rows.sort(key=lambda value: value[0], reverse=True)
        return rows[:8]

    def update_graphs(self):
        self.ax1.clear()
        self.ax2.clear()

        self.ax1.plot(list(self.cpu_history), color="#4caf50")
        self.ax1.set_title("CPU Usage")
        self.ax1.set_ylim(0, 100)

        self.ax2.plot(list(self.ram_history), color="#42a5f5")
        self.ax2.set_title("RAM Usage")
        self.ax2.set_ylim(0, 100)

        self.fig.tight_layout(pad=1.5)
        self.canvas.draw_idle()

    def monitor_logs(self):
        os.makedirs("logs", exist_ok=True)

        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding="utf-8"):
                pass

        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as file:
            file.seek(0, os.SEEK_END)

            while True:
                line = file.readline()

                if not line:
                    time.sleep(0.2)
                    continue

                self.event_queue.put({"type": "log_line", "line": line.rstrip("\n")})

    def flush_events(self):
        try:
            while True:
                event = self.event_queue.get_nowait()
                if event["type"] == "metrics":
                    self.apply_metrics(event)
                elif event["type"] == "log_line":
                    self.process_log_line(event["line"])
                elif event["type"] == "timeline":
                    self.add_timeline_event(event["message"])
        except Empty:
            pass

        self.after(200, self.flush_events)

    def apply_metrics(self, event):
        cpu = event["cpu"]
        ram = event["ram"]

        self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")
        self.ram_label.configure(text=f"RAM: {ram:.1f}%")

        self.update_graphs()

        process_text = "PID      CPU%   MEM%   NAME\n"
        process_text += "-" * 42 + "\n"
        for cpu_pct, mem_pct, pid, name in event["process_rows"]:
            process_text += f"{pid:<8} {cpu_pct:>5.1f} {mem_pct:>6.1f}   {name}\n"
        self.process_box.delete("1.0", "end")
        self.process_box.insert("end", process_text)

    def process_log_line(self, line):
        self.log_box.insert("end", f"{line}\n")
        self.log_box.see("end")

        lower = line.lower()

        if "error" in lower or "failed" in lower:
            self.error_count += 1
            self.error_label.configure(text=f"Errors: {self.error_count}")
            self.push_notification("OpenClaw Alert", line)

        if "browser started" in lower:
            self.browser_status = "Connected"
            self.browser_label.configure(text="Browser: Connected")
            self.agent_states["Browser Agent"] = "RUNNING"
            self.refresh_agent_statuses()

        if "browser disconnected" in lower or "browser closed" in lower:
            self.browser_status = "Disconnected"
            self.browser_label.configure(text="Browser: Disconnected")
            self.agent_states["Browser Agent"] = "DISCONNECTED"
            self.refresh_agent_statuses()

        if "task" in lower:
            task_text = line[:70]
            self.task_label.configure(text=f"Task: {task_text}")
            self.agent_states["Planner Agent"] = "ACTIVE"
            self.refresh_agent_statuses()

        if "verify" in lower:
            self.agent_states["Verifier Agent"] = "SCANNING"
            self.refresh_agent_statuses()

        if "recover" in lower or "retry" in lower:
            self.agent_states["Recovery Agent"] = "ACTIVE"
            self.refresh_agent_statuses()

        self.add_timeline_event(line)

    def add_timeline_event(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        event = f"{timestamp}  {message}"
        self.agent_events.append(event)

        self.timeline_box.delete("1.0", "end")
        self.timeline_box.insert("end", "\n".join(self.agent_events))
        self.timeline_box.see("end")

    def publish_event(self, source, message):
        self.event_queue.put({"type": "timeline", "message": f"[{source}] {message}"})

    def refresh_agent_statuses(self):
        lines = [f"{name:<16} [{status}]" for name, status in self.agent_states.items()]
        self.agent_status_box.delete("1.0", "end")
        self.agent_status_box.insert("end", "\n".join(lines))

    def push_notification(self, title, message):
        if notification is None:
            return
        notification.notify(
            title=title,
            message=message[:120],
            timeout=4,
        )

    def export_logs(self):
        timestamp = int(time.time())
        export_name = f"exported_logs_{timestamp}.txt"

        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as src:
                with open(export_name, "w", encoding="utf-8") as dst:
                    dst.write(src.read())

            self.publish_event("system", f"Logs exported to {export_name}")


if __name__ == "__main__":
    app = OpenClawDashboard()
    app.mainloop()
