# OpenClaw Visual Dashboard (.EXE Builder)

This project provides a live graphical monitoring dashboard for OpenClaw.

## Features

- Live log monitoring
- AI activity map + decision timeline
- CPU/RAM live graphs
- Browser status indicator
- Task execution indicator
- Error counter + desktop alerts
- System health analytics (top processes)
- Interactive command center buttons
- Auto-refresh dashboard
- Export logs
- Windows `.exe` build support

## Folder Structure

```text
openclaw-dashboard/
├── dashboard.py
├── requirements.txt
├── logs/
│   └── openclaw.log
└── assets/
```

## Step 1 — Install Requirements

```powershell
pip install -r requirements.txt
```

## Step 2 — Run Dashboard

```powershell
python dashboard.py
```

## Step 3 — Build EXE

```powershell
pyinstaller --onefile --windowed dashboard.py
```

EXE output:

```text
/dist/dashboard.exe
```

## Optional EXE Optimization

```powershell
pyinstaller --onefile --windowed --icon=icon.ico dashboard.py
```

You can add `--noconsole` for cleaner GUI-only packaging.

## Implemented Advanced Capabilities

- **Real-Time AI Activity Map**: agent status panel + rolling decision timeline.
- **Autonomous Agent Graph**: planner/browser/vision/verifier/recovery states.
- **Interactive Command Center**: restart/pause/stop/retry dashboard controls.
- **System Health Analytics**: top CPU processes with memory usage.
- **Live Notifications**: desktop alerts (via `plyer`) for failures.
