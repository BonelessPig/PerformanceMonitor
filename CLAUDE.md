# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this is

A Windows-only Python service that collects system metrics once a second and
serves them as JSON on `http://127.0.0.1:<port>/performance` for Wallpaper
Engine web wallpapers. All of the logic lives in
`performance_monitor_service.py`. It ships as a PyInstaller-built
`PerformanceMonitor.exe`. There are no tests, no linter config, and no
`requirements.txt`.

## Commands

Dependencies (Python 3.11+):
`python -m pip install psutil pywin32 pyinstaller setuptools`

- **Build the exe:** run `build_script.bat` **as Administrator**. It installs
  the packages, then runs `pyinstaller --clean performance_monitor.spec`. The
  output is a one-folder build at
  `dist\PerformanceMonitor\PerformanceMonitor.exe`, meant to be distributed as a
  zipped folder. Building directly with
  `pyinstaller --clean performance_monitor.spec` also works.
- **Run from source (dev mode):** `python performance_monitor_service.py` with
  no arguments builds the service object and calls `main()` directly, without
  the Service Control Manager. Press Ctrl+C to stop it. This calls
  `stop_workers()`, the same shutdown `SvcStop` uses.
- **Source with arguments:**
  `python performance_monitor_service.py install|start|stop|remove|debug` goes
  through `win32serviceutil.HandleCommandLine` (standard pywin32 behavior, needs
  admin).
- **Frozen exe:** with no arguments it self-elevates through UAC, removes any
  old service, installs the new one, and starts it. `install` / `start` / `stop`
  / `remove` are handled explicitly. `--run-service` is the argument the
  installed service is registered with; it enters `StartServiceCtrlDispatcher`.
- **Check a running instance:** `GET /performance` and `GET /status`. Logs are
  in `%ProgramData%\PerformanceMonitor\performance_monitor.log`.

## Architecture

`PerformanceMonitorService` (a pywin32 `ServiceFramework`) runs two daemon
threads from `main()`:

1. `update_performance_loop`: every second calls `get_performance_data()` and
   **writes the result to `%ProgramData%\PerformanceMonitor\performance.json`**.
2. `run_http_server`: a `ThreadingHTTPServer` bound to `127.0.0.1` only.
   `/performance` **reads that JSON file back from disk** (not
   `self.performance_data`), or returns `get_default_data()` if the file doesn't
   exist. CORS allows `null`/missing origins and `localhost`/`127.0.0.1`
   origins.

The main thread blocks on `hWaitStop` until `SvcStop` sets it.

Data sources, each toggled by `config.json` → `collect`:
- **psutil backend**: CPU, per-core CPU, RAM, network rate (computed from the
  delta against the previous sample), per-drive disk usage as `<letter>_disk`
  keys, and NVIDIA GPU stats via `nvidia-smi` (resolved once at import time with
  `shutil.which`).
- **HWiNFO backend**: reads the HWiNFO "Gadget" registry values
  (`SOFTWARE\HWiNFO64\VSB`, indexed values `Sensor<i>`, `Label<i>`, `Value<i>`,
  `ValueRaw<i>`, `Color<i>`) until a label is missing. It tries
  `HKEY_USERS\<user_sid>` first when `user_sid` is set, then falls back to
  `HKEY_LOCAL_MACHINE`. The service runs in Session 0 as SYSTEM, so
  `HKEY_CURRENT_USER` is not the interactive user's hive. That is why the SID
  option exists.

Config is read once, at service construction, from
`%ProgramData%\PerformanceMonitor\config.json` (the repo's `config.json` is the
user-facing template). Config changes require a service restart.

## Gotchas

- **The JSON shape is part of a public contract.** Third-party wallpapers
  consume it, and README.md documents the keys. Keep key names stable and update
  the README when the shape changes. Key details: `hwinfo` is a list of sensor
  dicts (`null` when disabled), `psutil` is `null` when disabled, and network
  speeds are in kilobits/s.
- **The monitor loop depends on `self.running`.** `SvcDoRun` sets it in service
  mode, and the dev-mode path in `main()` sets it explicitly. Any new entry
  point that calls `service.main()` must set it too, or no data is collected.
- **Outside the SCM, construct with `dev_mode=True`.** pywin32's
  `ServiceFramework.__init__` raises "The service name is not hosted by this
  process" unless the Service Control Manager launched the process, so dev mode
  skips it. Don't call `ReportServiceStatus` in that mode.
- **Some log levels are deliberate.** Normal operation logs at INFO. The startup
  and config messages use `logger.warning` on purpose, so they stand out in the
  log.
- **New imports may need PyInstaller hints.** Add any new runtime import that
  PyInstaller might miss (especially pywin32 modules) to `hiddenimports` in
  `performance_monitor.spec`.
- **Releases bump the version in several places:** `version_info.txt`
  (`filevers`, `prodvers`, `FileVersion`, `ProductVersion`) and the folder name.
- The uninstaller (`uninstaller.bat`) mentioned in the README is distributed
  with releases. It is not in this repo.
