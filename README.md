# OpenClaw Visual Dashboard (.EXE Builder)

A live graphical monitoring dashboard for OpenClaw with real-time metrics, log intelligence, timeline tracking, and Windows executable support.

## Features

- Live log monitoring (`logs/openclaw.log` tailing)
- CPU/RAM live graphs
- Browser status indicator
- Error counter
- Task execution timeline
- Real-time AI activity map
- Autonomous agent status panel
- Interactive command center buttons (restart browser, emergency stop, clear timeline)
- Log export
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

## 1) Install Requirements

```powershell
pip install -r requirements.txt
```

## 2) Run Dashboard

```powershell
python dashboard.py
```

## 3) Build EXE

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

Optional flag:

```powershell
--noconsole
```

## Advanced Feature Roadmap

- Live browser stream panel
- Mouse movement visualizer + click heatmaps
- OCR viewer panel
- Voice command integration
- Database-backed session logging
- Remote web dashboard (Flask + WebSocket)
- Plugin architecture
