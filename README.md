## Performance Monitor for Wallpaper Engine Web Wallpapers

**Performance Monitor** is a lightweight application designed specifically for
[Wallpaper Engine web
wallpapers](https://docs.wallpaperengine.io/en/web/overview.html). It collects
system performance data and serves it locally so that your web wallpapers can
access real-time metrics. When installed, it runs as a Windows service,
operating in the background and automatically starting when the system boots.

### Features

- Collects system performance data every second via **psutil / NVIDIA SMI**
  and/or **[HWiNFO](https://www.hwinfo.com/)**, and runs a local HTTP server so
  the data can be accessed from Wallpaper Engine web wallpapers.
- When using **psutil / NVIDIA SMI**, the following metrics are available:
  - CPU usage and current CPU clock speed
  - GPU usage, temperature, fan speed and power (NVIDIA, AMD and Intel)
  - RAM and VRAM usage
  - Disk usage and SSD temperatures
  - Network upload and download speeds

  No extra software is needed for these. GPU and SSD data come from the same
  built-in Windows sources Task Manager uses.

- When **[HWiNFO](https://www.hwinfo.com/)** is available, all sensors with
  **“Report value in Gadget”** enabled are collected automatically, providing
  more accurate clocks, temperatures, and advanced hardware metrics.

> This method provides the most precise and real-time hardware information and
> is recommended if you require accurate clock speeds or temperature data. Check
> [Data Sources](#data-sources) for more detailed instructions.

![Screenshot](screenshot.jpg?raw=true)

### Supported Wallpapers

- [[sheeta](https://steamcommunity.com/profiles/76561198383102380/)] [TERMINAL
  02][wp-1]
- [[sheeta](https://steamcommunity.com/profiles/76561198383102380/)] [UI toggle
  wallpaper][wp-2]
- [[sheeta](https://steamcommunity.com/profiles/76561198383102380/)] [Widget
  Wallpaper][wp-3]
- [[sheeta](https://steamcommunity.com/profiles/76561198383102380/)] [weather +
  performance monitor widget][wp-4]

[wp-1]: https://steamcommunity.com/sharedfiles/filedetails/?id=3639973107
[wp-2]: https://steamcommunity.com/sharedfiles/filedetails/?id=3115349801
[wp-3]: https://steamcommunity.com/sharedfiles/filedetails/?id=3470738721
[wp-4]: https://steamcommunity.com/sharedfiles/filedetails/?id=3343374776

Only the wallpapers that I am aware of are listed here.

### Installation & Usage

1. Download the latest `PerformanceMonitor.exe` from [Latest
   Release](https://github.com/sheetau/PerformanceMonitor/releases/latest).
2. Run the executable **once with administrator privileges**.
   > This will automatically uninstall any previous versions and register the
   > new service to start at boot.
3. By default, performance data is accessible at:
   http://127.0.0.1:5000/performance

#### Data Sources

- **Default (psutil / NVIDIA SMI)**  
  The application works out of the box using `psutil` and `nvidia-smi` when
  available.  
  This provides CPU, memory, disk, network and GPU metrics, plus GPU
  temperature and fan speed on any GPU whose driver reports them to Windows,
  and SSD temperatures. Hard drives (HDDs) are skipped so they are never woken
  from sleep.

- **Advanced (HWiNFO)**  
  For sensors Windows does not expose on its own (CPU temperature, case and
  CPU fan speeds, voltages, motherboard temperatures, etc.), HWiNFO can be
  used.

  To enable it:
  1. Install and launch **[HWiNFO](https://www.hwinfo.com/)**.
  2. In **Settings**, enable all options starting with **“Minimize …”** and
     **Auto Start** (setting the global polling period to 1000 ms is also
     recommended).
  3. Open **Sensor Settings → HWiNFO Gadget**.
  4. Enable **"Enable reporting to Gadget"**, and enable **“Report value in
     gadget”** for the sensors you want to use.

  Sensors marked this way can be accessed by supported wallpapers by referencing
  their sensor label names or ids.

#### Changing the Port & Data Sources

1. Download [config.json][config].
2. Place it in `%ProgramData%\PerformanceMonitor`.
3. Open `config.json` and edit the following options as needed:
   - **Port**
     - Change the `port` value to use a different local server port.

   - **Data source control**
     - Inside the `collect` section, you can enable or disable data sources:
       - Set `psutil` to `true` or `false`
       - Set `hwinfo` to `true` or `false`
     - This allows you to limit which backend is used to collect performance
       data.
     - You can verify the presence of HWiNFO data by running
       `reg query HKEY_LOCAL_MACHINE\SOFTWARE\HWiNFO64\VSB` in the Command
       Prompt.

   - **HWiNFO registry fallback**
     - If the default command above returns no data, check for user-level data
       by running `reg query HKEY_CURRENT_USER\SOFTWARE\HWiNFO64\VSB`. If data
       is found there, run `whoami /user` in the Command Prompt to obtain your
       SID. By setting this SID to `user_sid` field in `config.json`, the
       service will correctly fallback to that specific registry path.

4. Restart the service by right-clicking **Performance Monitor Service** in
   `services.msc` and selecting **Restart**.

[config]: https://github.com/sheetau/PerformanceMonitor/blob/main/config.json

#### Stopping the Service

1. Press `Win + R` and type `services.msc`.
2. Locate **Performance Monitor Service** in the list.
3. Right-click the service and select **Stop**.

#### Uninstalling

download the uninstaller from [Latest
Release](https://github.com/sheetau/PerformanceMonitor/releases/latest), place
it in the same folder as `PerformanceMonitor.exe`, and run it as Administrator
(This will stop and delete Performance Monitor service, Kill any remaining
`PerformanceMonitor.exe` processes, and Delete `PerformanceMonitor.exe` and
`%ProgramData%\PerformanceMonitor`).

### Security & Privacy

- Built using Python and the Windows / Python standard libraries for a **simple,
  local performance monitoring environment**.
- The tool runs entirely on your machine and **does not send any data over the
  internet** or access external servers.
- Performance statistics are collected locally and served only on `localhost`.
- The default endpoint (`http://127.0.0.1:5000/performance`) is only accessible
  from your own computer.
- Fully open-source, allowing you to inspect and verify the code at any time.

> **Note on Security Warnings:** This executable is not code-signed, and it
> accesses specific registry paths to retrieve HWiNFO sensor data. Because of
> these factors, some antivirus software may flag it as suspicious. Currently,
> we have confirmed detections such as Bkav Pro (W64.AIDetectMalware) and
> SecureAge (Malicious). These are false positives; all other major security
> vendors recognize the software as clean. If you see a warning, click “More
> info” and then “Run anyway” to proceed with the installation.
>
> **Technical Architecture:** Because this tool runs as a standard Windows
> service using legitimate Service APIs, it operates in Session 0. This
> architecture is necessary for proper system integration and automatic startup,
> but it can unfortunately cause some user-level diagnostic tools (like Process
> Explorer or PowerShell's Get-Process) to fail in retrieving standard process
> metadata (e.g., Path, Company). This behavior is an inherent side effect of
> the service architecture, not a result of intentional anti-analysis or
> obfuscation techniques.
>
> It is safe to run. If you are concerned, you can review the source code in the
> GitHub repository or uninstall using `uninstaller.bat`. Please understand this
> is a personal, free project.

### Dependencies and References

- [Python 3.11+](https://www.python.org/)
- [psutil](https://github.com/giampaolo/psutil)
- [HWiNFO](https://www.hwinfo.com/)
- [pywin32](https://github.com/mhammond/pywin32)
- [PyInstaller](https://github.com/pyinstaller/pyinstaller)
- [Windows
  Services](https://docs.microsoft.com/en-us/windows/win32/services/services)
- [Wallpaper Engine](https://www.wallpaperengine.io/en)

### Contributing

- Create wallpapers compatible with this monitor by referring to the [next
  section](#accessing-performance-data-in-your-web-wallpaper).
- Report bugs [here](https://github.com/sheetau/PerformanceMonitor/issues) or in
  [my server](https://discord.gg/2dXs5HwXuW), including the console output or
  the contents of the log file, which is usually located at
  `C:\ProgramData\PerformanceMonitor\performance_monitor.log`.
- If you like my work, please consider:
  - Starring this project on GitHub
  - [![ko-fi][kofi-badge]](https://ko-fi.com/sheeta)
- Stay tuned in [Sheeta's Discord Server](https://discord.gg/2dXs5HwXuW)

[kofi-badge]: https://www.ko-fi.com/img/githubbutton_sm.svg

---

### Accessing Performance Data in Your Web Wallpaper

The Performance Monitor exposes system metrics via a local HTTP server (default:
`http://127.0.0.1:5000/performance`). You can fetch these metrics in your web
wallpaper using standard JavaScript `fetch`.

The data is returned in the following JSON format:

```json
{
    "hwinfo": [
        {
            "color": "16375f",
            "id": 0,
            "label": "Total CPU Usage",
            "sensor": "CPU [#0]: AMD Ryzen 9 9900X",
            "value": "3.1 %",
            "valueraw": "3.1"
        },
        {
            "color": "005c80",
            "id": 1,
            "label": "CPU (Tctl/Tdie)",
            "sensor": "CPU [#0]: AMD Ryzen 9 9900X: Enhanced",
            "value": "53.4 °C",
            "valueraw": "53.4"
        },
        ...
    ],
    "psutil": {
        "cpu": 6.1,
        "memory": 41.3,
		...
    },
    "timestamp": 1767331384.1830423
}
```

- `hwinfo` is an array of sensor objects. It is an empty array when HWiNFO data
  is not found, and `null` when the HWiNFO data source is disabled in
  `config.json`.
- `psutil` is `null` when the psutil data source is disabled in `config.json`.

#### Available psutil / GPU Keys

The following keys are available by default under the `psutil` object:

| Key                   | Description                          | Unit / Format |
| --------------------- | ------------------------------------ | ------------- |
| `cpu`                 | Overall CPU usage percentage         | %             |
| `cpu_percore`         | Per-core CPU usage (if available)    | %             |
| `cpu_freq_ghz`        | Current average CPU clock speed      | GHz           |
| `memory`              | RAM usage percentage                 | %             |
| `memory_gb`           | RAM usage in GB                      | GB            |
| `gpu_usage`           | GPU usage percentage                 | %             |
| `vram_usage`          | GPU memory usage percentage          | %             |
| `vram_gb`             | GPU memory usage in GB               | GB            |
| `gpu_temp`            | GPU temperature                      | °C            |
| `gpus`                | Every GPU's details (see below)      | array         |
| `disk_temps`          | SSD temperatures (see below)         | array         |
| `upload_speed`        | Network upload speed (kilobits/s)    | kbps          |
| `download_speed`      | Network download speed (kilobits/s)  | kbps          |
| `c_disk`, `d_disk`, … | Disk usage as "used GB/total GB"     | GB            |
| `timestamp`           | UNIX timestamp of measurement        | seconds       |

`gpu_usage`, `vram_usage`, `vram_gb` and `gpu_temp` describe one GPU. They
come from `nvidia-smi` on NVIDIA systems. Otherwise they come from Windows,
using the GPU with the most video memory (`gpus[0]`).

Any value the hardware or driver does not report is `null`. `cpu_freq_ghz`
and each GPU's `usage` are also `null` for the first second after the service
starts.

#### GPU List (`gpus`)

One object per GPU, sorted by video memory (largest first), from built-in
Windows sources. Works for NVIDIA, AMD and Intel GPUs.

| Key             | Description                                 | Unit |
| --------------- | ------------------------------------------- | ---- |
| `name`          | GPU name, e.g. `"NVIDIA GeForce RTX 2080"`  | text |
| `usage`         | GPU usage (same method as Task Manager)     | %    |
| `temp`          | GPU temperature                             | °C   |
| `fan_rpm`       | GPU fan speed                               | RPM  |
| `power`         | Power draw as a percent of the power limit  | %    |
| `vram_used_gb`  | Video memory in use                         | GB   |
| `vram_total_gb` | Total video memory                          | GB   |

```json
"gpus": [
    {
        "name": "NVIDIA GeForce RTX 2080",
        "usage": 43.5, "temp": 44.4, "fan_rpm": 1422, "power": 26.6,
        "vram_used_gb": 2.2, "vram_total_gb": 7.8
    }
]
```

#### SSD Temperatures (`disk_temps`)

One object per SSD that reports a temperature, refreshed every 10 seconds.
Hard drives are skipped. `disk` is the Windows disk number, as shown in Disk
Management.

```json
"disk_temps": [
    { "disk": 0, "name": "WD_BLACK SN850X 4000GB", "temp": 40 }
]
```

#### Handling HWiNFO Data

Since the HWiNFO sensor list is an array and IDs may change depending on your
HWiNFO configuration, it is recommended to map the sensors by their label for
more reliable access. Labels can also be renamed from within HWiNFO.

You can create a lookup map like this:

```js
const hwinfoMap = Object.create(null);
for (const item of Array.isArray(data.hwinfo) ? data.hwinfo : []) {
  hwinfoMap[item.label] = item;
}
```

This allows you to select specific sensors using `hwinfoMap["Label Name"]` and
extract values such as `hwinfoMap["Total CPU Usage"].valueraw`. Each sensor
object provides the following properties:

- **`color`**: The background color hex code assigned to the tray icon in
  HWiNFO.
- **`id`**: The index number assigned by HWiNFO.
- **`label`**: The display name (customizable in HWiNFO).
- **`sensor`**: Technical hardware sensor name.
- **`value`**: Formatted value with units (e.g., `"53.4 °C"`).
- **`valueraw`**: Numeric value only (e.g., `"53.4"`).

#### Example Usage

```javascript
const port = 5000; // Default port

async function fetchPerformance() {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/performance`);
    if (!response.ok) throw new Error("Network response was not ok");

    const data = await response.json();
    const psutil = data.psutil ?? {};

    // Map HWiNFO sensors by label for easy access
    const hwinfo = Object.create(null);
    for (const item of Array.isArray(data.hwinfo) ? data.hwinfo : []) {
      hwinfo[item.label] = item;
    }

    // Prepare log data
    const stats = {
      "CPU Usage": `${psutil.cpu} %`,
      "CPU Temp (HWiNFO)": hwinfo["CPU (Tctl/Tdie)"]?.value ?? "N/A",
      "RAM Usage": `${psutil.memory} %`,
      "GPU Usage": `${psutil.gpu_usage} %`,
      "GPU Temp": hwinfo["GPU Temperature"]?.value ?? `${psutil.gpu_temp} °C`,
      "GPU Fan": `${psutil.gpus?.[0]?.fan_rpm ?? "N/A"} RPM`,
      "CPU Clock": `${psutil.cpu_freq_ghz ?? "N/A"} GHz`,
      Download: `${psutil.download_speed} kbps`,
      Upload: `${psutil.upload_speed} kbps`,
    };

    // Add disk info (any key ending in _disk)
    Object.keys(psutil).forEach((key) => {
      if (key.endsWith("_disk")) {
        stats[`Disk (${key.split("_")[0].toUpperCase()}:)`] = psutil[key];
      }
    });

    // Add SSD temperatures
    for (const drive of psutil.disk_temps ?? []) {
      stats[`SSD Temp (${drive.name})`] = `${drive.temp} °C`;
    }

    console.table(stats);
  } catch (err) {
    console.error("Failed to fetch performance data:", err);
  }
}

// Refresh data every second
setInterval(fetchPerformance, 1000);
```
