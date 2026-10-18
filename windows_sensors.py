#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hardware sensors read through built-in Windows APIs.

Nothing here needs extra software or a kernel driver:
- GPU temperature, fan speed, power and VRAM size come from the D3DKMT
  display API in gdi32, the same source Task Manager uses. Works for any
  GPU brand whose driver reports it.
- GPU usage, VRAM in use and the current CPU clock come from Windows
  performance counters (PDH).
- SSD temperatures come from the storage driver's temperature query. Hard
  drives are skipped so polling never wakes a sleeping disk.

Every reader fails soft: a missing source gives empty values, never an
exception.
"""

import ctypes
import logging
import time
from ctypes import wintypes

import pywintypes
import win32pdh

logger = logging.getLogger("PerformanceMonitor")

BYTES_PER_GB = 1024 ** 3
TENTHS = 10.0
PERCENT_MAX = 100.0

# ===== GPU: D3DKMT (gdi32) =====

STATUS_SUCCESS = 0
KMTQAITYPE_GETSEGMENTSIZE = 3
KMTQAITYPE_ADAPTERREGISTRYINFO = 8
KMTQAITYPE_ADAPTERPERFDATA = 62
KMTQAITYPE_ADAPTERPERFDATA_CAPS = 63
MAX_PATH_CHARS = 260
# Adapter LUIDs change after a driver reload, so cap the per-adapter cache.
MAX_CACHED_ADAPTERS = 16


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _AdapterInfo(ctypes.Structure):
    _fields_ = [
        ("hAdapter", ctypes.c_uint),
        ("AdapterLuid", _Luid),
        ("NumOfSources", wintypes.ULONG),
        ("bPrecisePresentRegionsPreferred", wintypes.BOOL),
    ]


class _EnumAdapters2(ctypes.Structure):
    _fields_ = [
        ("NumAdapters", wintypes.ULONG),
        ("pAdapters", ctypes.POINTER(_AdapterInfo)),
    ]


class _QueryAdapterInfo(ctypes.Structure):
    _fields_ = [
        ("hAdapter", ctypes.c_uint),
        ("Type", ctypes.c_int),
        ("pPrivateDriverData", ctypes.c_void_p),
        ("PrivateDriverDataSize", ctypes.c_uint),
    ]


class _CloseAdapter(ctypes.Structure):
    _fields_ = [("hAdapter", ctypes.c_uint)]


class _SegmentSizeInfo(ctypes.Structure):
    _fields_ = [
        ("DedicatedVideoMemorySize", ctypes.c_uint64),
        ("DedicatedSystemMemorySize", ctypes.c_uint64),
        ("SharedSystemMemorySize", ctypes.c_uint64),
    ]


class _AdapterRegistryInfo(ctypes.Structure):
    _fields_ = [
        ("AdapterString", ctypes.c_wchar * MAX_PATH_CHARS),
        ("BiosString", ctypes.c_wchar * MAX_PATH_CHARS),
        ("DacType", ctypes.c_wchar * MAX_PATH_CHARS),
        ("ChipType", ctypes.c_wchar * MAX_PATH_CHARS),
    ]


class _AdapterPerfData(ctypes.Structure):
    # Temperature is in tenths of a degree C. Power is in tenths of a
    # percent of the card's power limit.
    _fields_ = [
        ("PhysicalAdapterIndex", ctypes.c_uint32),
        ("MemoryFrequency", ctypes.c_uint64),
        ("MaxMemoryFrequency", ctypes.c_uint64),
        ("MaxMemoryFrequencyOC", ctypes.c_uint64),
        ("MemoryBandwidth", ctypes.c_uint64),
        ("PCIEBandwidth", ctypes.c_uint64),
        ("FanRPM", wintypes.ULONG),
        ("Power", wintypes.ULONG),
        ("Temperature", wintypes.ULONG),
        ("PowerStateOverride", ctypes.c_ubyte),
    ]


class _AdapterPerfDataCaps(ctypes.Structure):
    _fields_ = [
        ("PhysicalAdapterIndex", ctypes.c_uint32),
        ("MaxMemoryBandwidth", ctypes.c_uint64),
        ("MaxPCIEBandwidth", ctypes.c_uint64),
        ("MaxFanRPM", wintypes.ULONG),
        ("TemperatureMax", wintypes.ULONG),
        ("TemperatureWarning", wintypes.ULONG),
    ]


def _luid_key(luid):
    """Format a LUID like counter instance names do (lowercased)."""
    high = luid.HighPart & 0xFFFFFFFF
    return f"luid_0x{high:08x}_0x{luid.LowPart:08x}"


class _GpuAdapters:
    """Reads per-adapter GPU data from the D3DKMT display API."""

    def __init__(self):
        self._static = {}
        try:
            self._gdi32 = ctypes.WinDLL("gdi32")
            for name in ("D3DKMTEnumAdapters2", "D3DKMTQueryAdapterInfo",
                         "D3DKMTCloseAdapter"):
                getattr(self._gdi32, name).restype = ctypes.c_long
        except (OSError, AttributeError) as e:
            logger.debug(f"D3DKMT unavailable: {e}")
            self._gdi32 = None

    def read(self):
        """Return a list of dicts: luid, name, temp, fan_rpm, power,
        vram_total. Adapters with no data at all are left out."""
        if self._gdi32 is None:
            return []
        adapters = self._enumerate()
        try:
            results = [self._read_adapter(info) for info in adapters]
        finally:
            for info in adapters:
                self._gdi32.D3DKMTCloseAdapter(
                    ctypes.byref(_CloseAdapter(info.hAdapter))
                )
        return [r for r in results if r is not None]

    def _enumerate(self):
        request = _EnumAdapters2()
        if self._gdi32.D3DKMTEnumAdapters2(
                ctypes.byref(request)) != STATUS_SUCCESS:
            return []
        buffer = (_AdapterInfo * request.NumAdapters)()
        request.pAdapters = buffer
        # Fails if an adapter appeared in between; the next tick retries.
        if self._gdi32.D3DKMTEnumAdapters2(
                ctypes.byref(request)) != STATUS_SUCCESS:
            return []
        return list(buffer[:request.NumAdapters])

    def _query(self, handle, query_type, out):
        request = _QueryAdapterInfo(
            handle,
            query_type,
            ctypes.cast(ctypes.byref(out), ctypes.c_void_p),
            ctypes.sizeof(out),
        )
        status = self._gdi32.D3DKMTQueryAdapterInfo(ctypes.byref(request))
        return status == STATUS_SUCCESS

    def _read_static(self, handle):
        """Name, VRAM size and fan support never change for an adapter."""
        registry = _AdapterRegistryInfo()
        segments = _SegmentSizeInfo()
        caps = _AdapterPerfDataCaps()
        has_name = self._query(
            handle, KMTQAITYPE_ADAPTERREGISTRYINFO, registry
        )
        has_segments = self._query(
            handle, KMTQAITYPE_GETSEGMENTSIZE, segments
        )
        has_caps = self._query(
            handle, KMTQAITYPE_ADAPTERPERFDATA_CAPS, caps
        )
        return {
            "name": registry.AdapterString.strip() if has_name else None,
            "vram_total": (
                segments.DedicatedVideoMemorySize if has_segments else 0
            ),
            "has_fan": has_caps and caps.MaxFanRPM > 0,
        }

    def _read_adapter(self, info):
        luid = _luid_key(info.AdapterLuid)
        static = self._static.get(luid)
        if static is None:
            if len(self._static) >= MAX_CACHED_ADAPTERS:
                self._static.clear()
            static = self._read_static(info.hAdapter)
            self._static[luid] = static

        perf = _AdapterPerfData()
        has_perf = self._query(
            info.hAdapter, KMTQAITYPE_ADAPTERPERFDATA, perf
        )
        # Software adapters (e.g. Microsoft Basic Render) have neither.
        if not has_perf and static["vram_total"] == 0:
            return None

        return {
            "luid": luid,
            "name": static["name"],
            "temp": (
                perf.Temperature / TENTHS
                if has_perf and perf.Temperature else None
            ),
            "fan_rpm": (
                int(perf.FanRPM) if has_perf and static["has_fan"] else None
            ),
            "power": (
                perf.Power / TENTHS if has_perf and perf.Power else None
            ),
            "vram_total": static["vram_total"],
        }


# ===== GPU usage, VRAM in use, CPU clock: performance counters =====

COUNTER_PATHS = {
    "gpu_engine": r"\GPU Engine(*)\Utilization Percentage",
    "gpu_memory": r"\GPU Adapter Memory(*)\Dedicated Usage",
    "cpu_perf": r"\Processor Information(_Total)\% Processor Performance",
    "cpu_freq": r"\Processor Information(_Total)\Processor Frequency",
}
MHZ_PER_GHZ = 1000.0


def _luid_from_instance(instance):
    """'pid_1_luid_0x0_0x1A_phys_0_eng_0_engtype_3D' -> 'luid_0x0_0x1A'."""
    start = instance.find("luid_")
    end = instance.find("_phys_", start)
    if start < 0 or end < 0:
        return None
    return instance[start:end].lower()


def _gpu_usage_by_luid(engine_values):
    """Task Manager's method: add up every process per engine type, then
    take the busiest engine type as the GPU's usage."""
    per_engine = {}
    for instance, value in engine_values.items():
        luid = _luid_from_instance(instance)
        engine = instance.rpartition("_engtype_")[2]
        if luid is None:
            continue
        key = (luid, engine)
        per_engine[key] = per_engine.get(key, 0.0) + value

    usage = {}
    for (luid, _engine), value in per_engine.items():
        usage[luid] = max(usage.get(luid, 0.0), min(value, PERCENT_MAX))
    return usage


class _PerfCounters:
    """One PDH query sampled once per tick. Rate counters need two samples,
    so values read as missing on the very first tick."""

    def __init__(self):
        self._query = None
        self._counters = {}
        try:
            self._query = win32pdh.OpenQuery()
        except pywintypes.error as e:
            logger.debug(f"PDH unavailable: {e}")
            return
        for key, path in COUNTER_PATHS.items():
            try:
                self._counters[key] = win32pdh.AddEnglishCounter(
                    self._query, path
                )
            except pywintypes.error as e:
                logger.debug(f"Counter unavailable ({path}): {e}")

    def collect(self):
        """Take a sample. Returns False if no data could be collected."""
        if self._query is None:
            return False
        try:
            win32pdh.CollectQueryData(self._query)
            return True
        except pywintypes.error as e:
            logger.debug(f"PDH collect failed: {e}")
            return False

    def array(self, key, fmt=win32pdh.PDH_FMT_DOUBLE):
        """Return {instance: value} for a wildcard counter, or {}."""
        counter = self._counters.get(key)
        if counter is None:
            return {}
        try:
            return win32pdh.GetFormattedCounterArray(counter, fmt)
        except pywintypes.error:
            return {}

    def value(self, key):
        """Return a single counter's value, or None."""
        counter = self._counters.get(key)
        if counter is None:
            return None
        try:
            _type, value = win32pdh.GetFormattedCounterValue(
                counter, win32pdh.PDH_FMT_DOUBLE
            )
            return value
        except pywintypes.error:
            return None

    def cpu_freq_ghz(self):
        """Current average CPU clock: nominal speed x % performance."""
        nominal_mhz = self.value("cpu_freq")
        perf_percent = self.value("cpu_perf")
        if not nominal_mhz or perf_percent is None:
            return None
        return nominal_mhz * perf_percent / PERCENT_MAX / MHZ_PER_GHZ


# ===== SSD temperatures: storage temperature query =====

IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
STORAGE_DEVICE_PROPERTY = 0
STORAGE_SEEK_PENALTY_PROPERTY = 7
STORAGE_DEVICE_TEMPERATURE_PROPERTY = 52
PROPERTY_STANDARD_QUERY = 0
# Windows numbers physical drives from 0; 16 covers any normal desktop.
MAX_PHYSICAL_DRIVES = 16
DISK_POLL_SECONDS = 10.0
DESCRIPTOR_BUFFER_BYTES = 1024
# Byte offsets inside the descriptors Windows returns.
PRODUCT_ID_OFFSET_POS = 16
SEEK_PENALTY_FLAG_POS = 8
TEMP_INFO_COUNT_POS = 12
TEMP_INFO_FIRST_POS = 24
TEMP_INFO_TEMP_POS = 2
FILE_SHARE_READ_WRITE = 0x3
OPEN_EXISTING = 3
NO_ACCESS = 0


class _StoragePropertyQuery(ctypes.Structure):
    _fields_ = [
        ("PropertyId", ctypes.c_int),
        ("QueryType", ctypes.c_int),
        ("AdditionalParameters", ctypes.c_ubyte * 4),
    ]


def _int_at(raw, pos, size, signed=False):
    if pos + size > len(raw):
        return None
    return int.from_bytes(raw[pos:pos + size], "little", signed=signed)


class _DiskTemps:
    """Polls SSD temperatures every DISK_POLL_SECONDS and caches them."""

    def __init__(self):
        self._cached = []
        self._last_poll = None
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateFileW.restype = wintypes.HANDLE
            k32.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                wintypes.HANDLE,
            ]
            k32.DeviceIoControl.restype = wintypes.BOOL
            k32.DeviceIoControl.argtypes = [
                wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
            ]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            self._k32 = k32
        except (OSError, AttributeError) as e:
            logger.debug(f"Disk temperature query unavailable: {e}")
            self._k32 = None

    def read(self):
        """Return [{disk, name, temp}], refreshed at most every
        DISK_POLL_SECONDS."""
        if self._k32 is None:
            return []
        now = time.monotonic()
        if (self._last_poll is not None
                and now - self._last_poll < DISK_POLL_SECONDS):
            return self._cached
        self._last_poll = now
        self._cached = [
            entry for entry in map(self._read_drive,
                                   range(MAX_PHYSICAL_DRIVES))
            if entry is not None
        ]
        return self._cached

    def _query(self, handle, property_id):
        buffer = ctypes.create_string_buffer(DESCRIPTOR_BUFFER_BYTES)
        returned = wintypes.DWORD()
        request = _StoragePropertyQuery(property_id, PROPERTY_STANDARD_QUERY)
        ok = self._k32.DeviceIoControl(
            handle, IOCTL_STORAGE_QUERY_PROPERTY,
            ctypes.byref(request), ctypes.sizeof(request),
            buffer, DESCRIPTOR_BUFFER_BYTES, ctypes.byref(returned), None,
        )
        return buffer.raw[:returned.value] if ok else None

    def _read_drive(self, number):
        # Opening with no access rights is enough for these queries and
        # does not need admin.
        handle = self._k32.CreateFileW(
            rf"\\.\PhysicalDrive{number}", NO_ACCESS, FILE_SHARE_READ_WRITE,
            None, OPEN_EXISTING, 0, None,
        )
        if handle is None or handle == wintypes.HANDLE(-1).value:
            return None
        try:
            # Only SSDs: asking a hard drive could spin it up from sleep.
            seek = self._query(handle, STORAGE_SEEK_PENALTY_PROPERTY)
            if _int_at(seek or b"", SEEK_PENALTY_FLAG_POS, 1) != 0:
                return None
            temp = self._read_temp(handle)
            if temp is None:
                return None
            return {
                "disk": number,
                "name": self._read_name(handle),
                "temp": temp,
            }
        finally:
            self._k32.CloseHandle(handle)

    def _read_temp(self, handle):
        raw = self._query(handle, STORAGE_DEVICE_TEMPERATURE_PROPERTY)
        if not raw or not _int_at(raw, TEMP_INFO_COUNT_POS, 2):
            return None
        # The first entry is the drive's overall (composite) temperature.
        return _int_at(
            raw, TEMP_INFO_FIRST_POS + TEMP_INFO_TEMP_POS, 2, signed=True
        )

    def _read_name(self, handle):
        raw = self._query(handle, STORAGE_DEVICE_PROPERTY)
        offset = _int_at(raw or b"", PRODUCT_ID_OFFSET_POS, 4)
        if not offset or offset >= len(raw):
            return None
        end = raw.find(b"\0", offset)
        name = raw[offset:end if end >= 0 else len(raw)]
        return name.decode("ascii", errors="replace").strip() or None


# ===== Public interface =====


class WindowsSensors:
    """Collects the built-in Windows sensors. Call read() once per second
    from a single thread."""

    def __init__(self):
        self._gpus = _GpuAdapters()
        self._counters = _PerfCounters()
        self._disks = _DiskTemps()

    def read(self):
        """Return {"gpus": [...], "cpu_freq_ghz": float|None,
        "disk_temps": [...]}. GPUs are sorted biggest VRAM first."""
        result = {"gpus": [], "cpu_freq_ghz": None, "disk_temps": []}
        try:
            has_counters = self._counters.collect()
            result["gpus"] = self._read_gpus(has_counters)
            if has_counters:
                freq = self._counters.cpu_freq_ghz()
                result["cpu_freq_ghz"] = (
                    round(freq, 2) if freq is not None else None
                )
            result["disk_temps"] = self._disks.read()
        except Exception as e:
            logger.debug(f"Windows sensor read failed: {e}")
        return result

    def _read_gpus(self, has_counters):
        usage, vram_used = {}, {}
        has_usage = False
        if has_counters:
            engines = self._counters.array("gpu_engine")
            # Empty on the first tick, before the counter has two samples.
            has_usage = bool(engines)
            usage = _gpu_usage_by_luid(engines)
            for instance, used in self._counters.array(
                    "gpu_memory", win32pdh.PDH_FMT_LARGE).items():
                luid = _luid_from_instance(instance)
                if luid is not None:
                    vram_used[luid] = vram_used.get(luid, 0) + used

        gpus = []
        adapters = sorted(
            self._gpus.read(), key=lambda a: a["vram_total"], reverse=True
        )
        for adapter in adapters:
            luid = adapter["luid"]
            used = vram_used.get(luid)
            total = adapter["vram_total"]
            gpus.append({
                "name": adapter["name"],
                "usage": (
                    round(usage.get(luid, 0.0), 1) if has_usage else None
                ),
                "temp": _round(adapter["temp"]),
                "fan_rpm": adapter["fan_rpm"],
                "power": _round(adapter["power"]),
                "vram_used_gb": (
                    round(used / BYTES_PER_GB, 1)
                    if used is not None else None
                ),
                "vram_total_gb": (
                    round(total / BYTES_PER_GB, 1) if total else None
                ),
            })
        return gpus


def _round(value):
    return round(value, 1) if value is not None else None
