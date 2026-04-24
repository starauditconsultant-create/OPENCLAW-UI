# OpenClaw Visual Dashboard (.EXE Builder)

A live desktop monitoring dashboard for OpenClaw with:

- Live log monitoring with watchdog-based updates
- Agent activity tracking panel
- CPU / RAM real-time graphs
- Browser status indicator
- Task execution timeline
- Error counter + error trend graph
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
├── exports/
└── assets/
```

## Step 1 — Install Requirements

```powershell
pip install customtkinter matplotlib psutil watchdog pyinstaller
```

Or:

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

## Included "Advanced" UX Features

- **Autonomous Agent Graph**: Planner / Browser / Vision / Verifier / Recovery live state labels.
- **Interactive Command Center**: `Restart Browser` and `Emergency Stop` controls (UI event stubs).
- **AI Decision Timeline**: Timestamped timeline panel for task + command + export events.
- **System Health Analytics**: Continuous CPU/RAM charting plus error trend plotting.

## Next Suggested Upgrades

- Live browser screenshot stream panel (`PIL.ImageTk`).
- OCR event feed and confidence panel.
- WebSocket/Flask remote dashboard mode.
- Database-backed session/action/error logging.
- Plugin architecture for integrations (Telegram, booking, trading, etc.).
