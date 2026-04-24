# OpenClaw Visual Dashboard (.EXE Builder)

Advanced desktop control center for OpenClaw with live telemetry, event intelligence, and Windows EXE packaging.

## Core Features

- Live log monitoring with `watchdog` file events
- Structured log classification (INFO/WARN/ERROR)
- Real-time CPU / RAM charts
- OpenClaw process health counter + CPU usage
- OpenClaw Core integration (`/api/core/state` + `/api/core/command`)
- Browser connectivity status detection
- Task extraction from logs
- Autonomous agent graph (Planner, Browser, Vision, Verifier, Recovery)
- Real-time AI activity feed + decision timeline
- Command center actions:
  - Export Logs
  - Clear Timeline
  - Restart Browser
  - Emergency Stop
- Export snapshots to `exports/`
- Windows `.exe` build support via `pyinstaller`

## Folder Structure

```text
openclaw-dashboard/
├── dashboard.py
├── requirements.txt
├── logs/
│   └── openclaw.log
├── exports/
└── assets/
```

## 1) Install Requirements

```powershell
pip install -r requirements.txt
```

## 2) Run Dashboard

```powershell
python dashboard.py
```

### Core Integration Settings

Set these environment variables before running to connect the dashboard to the OpenClaw system core:

```powershell
$env:OPENCLAW_CORE_URL = "http://127.0.0.1:8765"
$env:OPENCLAW_CORE_TOKEN = "your-token-if-required"
```

Expected core endpoints:

- `GET /api/core/state` returning JSON such as:
  - `mode` (e.g., `autonomous`, `manual`)
  - `browser_connected` (boolean)
  - `active_task` (string)
- `POST /api/core/command` with payload:
  - `command` (`restart_browser`, `emergency_stop`, etc.)
  - `source`
  - `timestamp`

## 3) Build EXE

```powershell
pyinstaller --onefile --windowed dashboard.py
```

Output:

```text
/dist/dashboard.exe
```

## Optional EXE Optimization

```powershell
pyinstaller --onefile --windowed --icon=icon.ico --noconsole dashboard.py
```

## Advanced Roadmap (Enterprise)

- Live browser preview stream panel
- OCR overlay + confidence panel
- Click heatmaps and mouse trajectory playback
- Persistent SQLite/PostgreSQL event storage
- Plugin architecture (`plugins/`)
- Remote web monitoring backend (Flask + WebSocket)
- Predictive failure scoring for agent actions
