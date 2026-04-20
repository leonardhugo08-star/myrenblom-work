"""Nordbloom mockup pipeline orchestrator.

Reads config from env vars (set by run_pipeline.sh sourcing config.env):
    NORDBLOOM_ROOT          absolute path to runtime root
    UPSCAYL_BIN             path to upscayl-bin / realesrgan binary
    UPSCAYL_MODELS_DIR      path to models directory (may be empty)
    UPSCAYL_MODEL_NAME      e.g. "realesrgan-x4plus"
    UPSCAYL_SCALE           int, usually 4
    PHOTOSHOP_APP_NAME      e.g. "Adobe Photoshop 2024"
    BATCH_SIZE              int, posters per PS session
    PS_RESTART_SLEEP        int, seconds between PS quit and restart
    MIN_MOCKUPS_OK          int, threshold to mark poster complete (default 8)
    JPEG_QUALITY            int, for upscale JPEGs

Designed for a Mac Mini 8 GB RAM. After each batch Photoshop is force-quit and
restarted to recover from memory leaks.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil

# Local import (upscale.py sits next to this file)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from upscale import upscale_all  # noqa: E402


# =====================================================================
# Config
# =====================================================================

def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    raw = env(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Config:
    root: Path
    upscayl_bin: str
    upscayl_models_dir: str
    upscayl_model_name: str
    upscayl_scale: int
    photoshop_app_name: str
    batch_size: int
    ps_restart_sleep: int
    min_mockups_ok: int
    jpeg_quality: int
    script_dir: Path

    @classmethod
    def load(cls) -> "Config":
        script_dir = Path(__file__).resolve().parent
        root_s = env("NORDBLOOM_ROOT") or str(Path.home() / "nordbloom_pipeline")
        return cls(
            root=Path(root_s).expanduser(),
            upscayl_bin=env("UPSCAYL_BIN"),
            upscayl_models_dir=env("UPSCAYL_MODELS_DIR"),
            upscayl_model_name=env("UPSCAYL_MODEL_NAME") or "realesrgan-x4plus",
            upscayl_scale=env_int("UPSCAYL_SCALE", 4),
            photoshop_app_name=env("PHOTOSHOP_APP_NAME"),
            batch_size=env_int("BATCH_SIZE", 3),
            ps_restart_sleep=env_int("PS_RESTART_SLEEP", 10),
            min_mockups_ok=env_int("MIN_MOCKUPS_OK", 8),
            jpeg_quality=env_int("JPEG_QUALITY", 95),
            script_dir=script_dir,
        )

    @property
    def posters_dir(self) -> Path:  return self.root / "input" / "posters"
    @property
    def mockups_dir(self) -> Path:  return self.root / "input" / "mockups"
    @property
    def working_dir(self) -> Path:  return self.root / "working"
    @property
    def upscaled_dir(self) -> Path: return self.root / "output" / "upscaled_for_print"
    @property
    def mockups_out(self) -> Path:  return self.root / "output" / "mockups"
    @property
    def logs_dir(self) -> Path:     return self.root / "logs"
    @property
    def state_dir(self) -> Path:    return self.root / "state"
    @property
    def state_file(self) -> Path:   return self.state_dir / "completed.json"
    @property
    def jsx_path(self) -> Path:     return self.script_dir / "generate_mockups.jsx"


# =====================================================================
# Logging
# =====================================================================

def setup_logger(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"

    logger = logging.getLogger("nordbloom")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.info(f"Log file: {log_path}")
    return logger


# =====================================================================
# State management (completed.json)
# =====================================================================

def load_state(state_file: Path) -> dict:
    if not state_file.exists():
        return {"posters": {}, "schema": 1}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {"posters": {}, "schema": 1}


def save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_file)


def mark_poster_complete(state: dict, poster_name: str, info: dict) -> None:
    state.setdefault("posters", {})[poster_name] = {
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        **info,
    }


# =====================================================================
# macOS helpers
# =====================================================================

def osascript(script: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=timeout,
    )


def quit_heavy_apps(logger: logging.Logger) -> None:
    """Best-effort quit of apps that eat RAM."""
    apps = [
        "Google Chrome", "Safari", "Firefox", "Arc", "Brave Browser",
        "Slack", "Discord", "Spotify", "Mail", "Messages",
        "Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint",
        "Preview", "Zoom",
    ]
    for app in apps:
        res = osascript(
            f'if application "{app}" is running then quit application "{app}"',
            timeout=10,
        )
        if res.returncode == 0:
            logger.info(f"[preflight] Quit {app} (if running)")


def system_info() -> dict:
    vm = psutil.virtual_memory()
    du = shutil.disk_usage(str(Path.home()))
    return {
        "total_ram_gb":       round(vm.total / 1024**3, 2),
        "available_ram_gb":   round(vm.available / 1024**3, 2),
        "cpu_count":          psutil.cpu_count(logical=True),
        "disk_free_gb":       round(du.free / 1024**3, 2),
        "python":             sys.version.split()[0],
    }


def find_photoshop_pids() -> list[int]:
    pids = []
    for p in psutil.process_iter(["name", "pid"]):
        try:
            nm = p.info.get("name") or ""
            if "Adobe Photoshop" in nm or nm.lower().startswith("photoshop"):
                pids.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def start_photoshop(app_name: str, logger: logging.Logger, boot_timeout: int = 90) -> None:
    logger.info(f"[ps] Starting Photoshop: {app_name}")
    subprocess.run(["open", "-a", app_name], check=False)

    deadline = time.time() + boot_timeout
    while time.time() < deadline:
        if find_photoshop_pids():
            # Verify osascript can reach it
            r = osascript(
                f'tell application "{app_name}" to return name of it',
                timeout=10,
            )
            if r.returncode == 0:
                logger.info(f"[ps] Photoshop ready after "
                            f"{int(boot_timeout - (deadline - time.time()))}s")
                return
        time.sleep(2)
    raise RuntimeError(f"Photoshop did not become responsive within {boot_timeout}s")


def stop_photoshop(app_name: str, logger: logging.Logger, wait_before_pkill: int = 5) -> None:
    logger.info("[ps] Quitting Photoshop (graceful)")
    osascript(f'tell application "{app_name}" to quit saving no', timeout=15)
    t0 = time.time()
    while time.time() - t0 < wait_before_pkill:
        if not find_photoshop_pids():
            logger.info(f"[ps] Photoshop exited after {time.time() - t0:.1f}s (graceful)")
            return
        time.sleep(0.5)

    logger.info("[ps] Photoshop still alive — pkill")
    subprocess.run(["pkill", "-f", "Adobe Photoshop"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", "Adobe Photoshop"], check=False)
    time.sleep(1)
    if find_photoshop_pids():
        logger.warning("[ps] Photoshop still alive after pkill -9")


# =====================================================================
# RAM sampler
# =====================================================================

class RAMMonitor:
    """Samples Photoshop RSS + system RAM in a background thread.

    Stores peak RSS (across all Photoshop processes summed) and peak overall
    system RAM usage during a batch.
    """

    def __init__(self, sample_interval: float = 2.0):
        self.sample_interval = sample_interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.peak_ps_rss_gb = 0.0
        self.peak_system_used_gb = 0.0
        self.samples = 0
        self.sum_ps_rss_gb = 0.0

    def _run(self):
        while not self._stop.is_set():
            ps_rss = 0
            for p in psutil.process_iter(["name", "memory_info"]):
                try:
                    nm = p.info.get("name") or ""
                    if "Adobe Photoshop" in nm or nm.lower().startswith("photoshop"):
                        mi = p.info.get("memory_info")
                        if mi:
                            ps_rss += mi.rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            ps_rss_gb = ps_rss / 1024**3
            sys_used_gb = psutil.virtual_memory().used / 1024**3

            if ps_rss_gb > self.peak_ps_rss_gb:
                self.peak_ps_rss_gb = ps_rss_gb
            if sys_used_gb > self.peak_system_used_gb:
                self.peak_system_used_gb = sys_used_gb
            self.sum_ps_rss_gb += ps_rss_gb
            self.samples += 1

            self._stop.wait(self.sample_interval)

    def start(self):
        self.peak_ps_rss_gb = 0.0
        self.peak_system_used_gb = 0.0
        self.samples = 0
        self.sum_ps_rss_gb = 0.0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        avg = (self.sum_ps_rss_gb / self.samples) if self.samples else 0.0
        return {
            "peak_ps_rss_gb":      round(self.peak_ps_rss_gb, 2),
            "avg_ps_rss_gb":       round(avg, 2),
            "peak_system_used_gb": round(self.peak_system_used_gb, 2),
            "samples":             self.samples,
        }


# =====================================================================
# Mockup batch execution
# =====================================================================

def build_tasks_for_poster(
    cfg: Config,
    poster_path: Path,
    mockup_paths: list[Path],
) -> list[dict]:
    """Return a list of task dicts for this poster's remaining mockups.

    Skips mockups whose output JPEG already exists on disk (idempotence).
    """
    tasks = []
    poster_name = poster_path.stem
    out_dir = cfg.mockups_out / poster_name
    out_dir.mkdir(parents=True, exist_ok=True)

    for psd in mockup_paths:
        mockup_name = psd.stem
        out_jpg = out_dir / f"{poster_name}_{mockup_name}.jpg"
        if out_jpg.exists() and out_jpg.stat().st_size > 0:
            continue
        tasks.append({
            "psd":          str(psd),
            "poster":       str(poster_path),
            "output":       str(out_jpg),
            "poster_name":  poster_name,
            "mockup_name":  mockup_name,
        })
    return tasks


def run_jsx_batch(
    cfg: Config,
    tasks: list[dict],
    logger: logging.Logger,
) -> list[dict]:
    """Invoke Photoshop with the JSX, pass tasks via current_batch.json,
    read back results. Photoshop must already be running.

    Returns list of per-task result dicts with keys: task, status, error,
    elapsed_ms, so_width, so_height.
    """
    cfg.working_dir.mkdir(parents=True, exist_ok=True)
    batch_file = cfg.working_dir / "current_batch.json"
    results_file = cfg.working_dir / "current_batch_results.json"

    if results_file.exists():
        results_file.unlink()

    payload = {
        "results_path": str(results_file),
        "tasks": tasks,
    }
    batch_file.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    jsx = cfg.jsx_path.resolve()
    # Escape backslashes and quotes in path for AppleScript string literal.
    jsx_esc = str(jsx).replace("\\", "\\\\").replace('"', '\\"')
    applescript = (
        f'tell application "{cfg.photoshop_app_name}" to '
        f'do javascript of file "{jsx_esc}"'
    )

    logger.info(f"[batch] Running JSX over {len(tasks)} task(s) …")
    t0 = time.time()

    # Allow ample time: ~90s per mockup ceiling (posters large, PS slow).
    timeout = max(300, 120 * len(tasks))
    try:
        r = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True, text=True, timeout=timeout,
        )
        rc = r.returncode
        stderr = r.stderr.strip()
        stdout = r.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"[batch] osascript timed out after {timeout}s")
        rc = -1
        stderr = "osascript timeout"
        stdout = ""

    elapsed = time.time() - t0
    logger.info(f"[batch] JSX finished in {elapsed:.1f}s (osascript rc={rc})")
    if stdout:
        logger.info(f"[batch] stdout: {stdout[:500]}")
    if stderr:
        logger.warning(f"[batch] stderr: {stderr[:1000]}")

    # Read results (even if osascript failed — JSX flushes incrementally).
    results = []
    if results_file.exists():
        try:
            results = json.loads(results_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"[batch] Could not parse results JSON: {e}")

    # For tasks not represented in results, synthesize failure entries.
    done_outputs = {r["task"]["output"] for r in results}
    for t in tasks:
        if t["output"] not in done_outputs:
            results.append({
                "task":        t,
                "status":      "failed",
                "error":       f"no result (osascript rc={rc}, stderr={stderr[:200]})",
                "elapsed_ms":  0,
                "so_width":    0,
                "so_height":   0,
            })

    return results


# =====================================================================
# Preflight
# =====================================================================

def preflight(cfg: Config, logger: logging.Logger) -> None:
    logger.info("=" * 70)
    logger.info(f"Nordbloom pipeline — {datetime.now():%Y-%m-%d %H:%M:%S}")
    logger.info("=" * 70)

    info = system_info()
    logger.info(f"[system] Total RAM:     {info['total_ram_gb']} GB")
    logger.info(f"[system] Available RAM: {info['available_ram_gb']} GB")
    logger.info(f"[system] CPU cores:     {info['cpu_count']}")
    logger.info(f"[system] Disk free:     {info['disk_free_gb']} GB")
    logger.info(f"[system] Python:        {info['python']}")
    logger.info(f"[cfg] Root:             {cfg.root}")
    logger.info(f"[cfg] Batch size:       {cfg.batch_size}")
    logger.info(f"[cfg] PS restart sleep: {cfg.ps_restart_sleep}s")
    logger.info(f"[cfg] Min mockups OK:   {cfg.min_mockups_ok}/10")
    logger.info(f"[cfg] Photoshop app:    {cfg.photoshop_app_name!r}")
    logger.info(f"[cfg] Upscayl bin:      {cfg.upscayl_bin!r}")

    missing = []
    if not cfg.posters_dir.exists() or not any(cfg.posters_dir.glob("*.png")):
        missing.append(f"Posters: {cfg.posters_dir} (no *.png found)")
    if not cfg.mockups_dir.exists() or not any(cfg.mockups_dir.glob("*.psd")):
        missing.append(f"Mockups: {cfg.mockups_dir} (no *.psd found)")
    if not cfg.upscayl_bin or not Path(cfg.upscayl_bin).exists():
        missing.append(f"Upscayl binary: {cfg.upscayl_bin!r}")
    if not cfg.photoshop_app_name:
        missing.append("PHOTOSHOP_APP_NAME not set")
    if not cfg.jsx_path.exists():
        missing.append(f"JSX not found: {cfg.jsx_path}")

    if missing:
        logger.error("Preflight failed:")
        for m in missing:
            logger.error(f"  - {m}")
        raise SystemExit(2)

    poster_count = len(list(cfg.posters_dir.glob("*.png")))
    mockup_count = len(list(cfg.mockups_dir.glob("*.psd")))
    logger.info(f"[input] Posters: {poster_count}")
    logger.info(f"[input] Mockups: {mockup_count}")

    quit_heavy_apps(logger)

    # Ensure no stale Photoshop is running so we know PIDs track our session.
    if find_photoshop_pids():
        logger.info("[preflight] Found existing Photoshop — quitting first")
        stop_photoshop(cfg.photoshop_app_name, logger)


# =====================================================================
# Main
# =====================================================================

def chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main() -> int:
    cfg = Config.load()
    logger = setup_logger(cfg.logs_dir)

    # Create runtime dirs (in case setup.sh wasn't run).
    for d in [cfg.posters_dir, cfg.mockups_dir, cfg.working_dir,
              cfg.upscaled_dir, cfg.mockups_out, cfg.state_dir]:
        d.mkdir(parents=True, exist_ok=True)

    preflight(cfg, logger)

    state = load_state(cfg.state_file)
    completed_names = set(state.get("posters", {}).keys())
    logger.info(f"[state] Already completed: {len(completed_names)} poster(s)")
    if completed_names:
        logger.info(f"[state]   {sorted(completed_names)}")

    posters = sorted(p for p in cfg.posters_dir.glob("*.png") if p.is_file())
    mockups = sorted(p for p in cfg.mockups_dir.glob("*.psd") if p.is_file())

    pending_posters = [p for p in posters if p.stem not in completed_names]
    logger.info(f"[state] Pending posters: {len(pending_posters)}")

    run_start = time.time()

    # ----------------------------------------------------------------
    # STEP 1: Upscale
    # ----------------------------------------------------------------
    logger.info("")
    logger.info("### STEP 1: Upscale ###")
    upscale_all(
        posters_dir=cfg.posters_dir,
        output_dir=cfg.upscaled_dir,
        working_dir=cfg.working_dir,
        upscayl_bin=cfg.upscayl_bin,
        models_dir=cfg.upscayl_models_dir or None,
        model_name=cfg.upscayl_model_name,
        scale=cfg.upscayl_scale,
        jpeg_quality=cfg.jpeg_quality,
        logger=logger,
        skip_names=completed_names,
    )

    # ----------------------------------------------------------------
    # STEP 2: Mockups, in batches of BATCH_SIZE posters
    # ----------------------------------------------------------------
    logger.info("")
    logger.info("### STEP 2: Mockups ###")

    total_mockups_ok = 0
    total_mockups_failed = 0
    total_mockups_skipped = 0
    batch_ram_reports: list[dict] = []
    per_poster_status: dict[str, dict] = {}

    batches = list(chunks(pending_posters, cfg.batch_size))
    logger.info(f"[batching] {len(batches)} batch(es) of up to {cfg.batch_size} posters")

    for batch_idx, batch_posters in enumerate(batches, 1):
        logger.info("")
        logger.info(f"--- Batch {batch_idx}/{len(batches)}: "
                    f"{[p.stem for p in batch_posters]} ---")

        # Collect tasks across all posters in this batch.
        all_tasks: list[dict] = []
        per_poster_tasks: dict[str, list[dict]] = {}
        per_poster_prior_done: dict[str, int] = {}
        for poster in batch_posters:
            tasks = build_tasks_for_poster(cfg, poster, mockups)
            per_poster_tasks[poster.stem] = tasks
            # Count how many mockup outputs already exist (counts toward OK).
            out_dir = cfg.mockups_out / poster.stem
            existing = len([
                f for f in out_dir.glob(f"{poster.stem}_*.jpg")
                if f.is_file() and f.stat().st_size > 0
            ])
            per_poster_prior_done[poster.stem] = existing
            logger.info(f"[batch {batch_idx}] {poster.stem}: "
                        f"{existing} existing, {len(tasks)} to generate")
            all_tasks.extend(tasks)
            total_mockups_skipped += existing

        if not all_tasks:
            logger.info(f"[batch {batch_idx}] Nothing to do, all mockups already exist")
            # Still mark posters complete.
            for poster in batch_posters:
                ok_count = per_poster_prior_done[poster.stem]
                per_poster_status[poster.stem] = {
                    "ok": ok_count, "failed": 0, "total": len(mockups),
                }
                if ok_count >= cfg.min_mockups_ok:
                    mark_poster_complete(state, poster.stem, {
                        "mockups_ok": ok_count,
                        "mockups_failed": 0,
                        "mockups_total": len(mockups),
                        "upscale_present": (cfg.upscaled_dir / f"{poster.stem}.jpg").exists(),
                    })
                    save_state(cfg.state_file, state)
            continue

        # Start Photoshop + RAM monitor for this batch.
        monitor = RAMMonitor(sample_interval=2.0)
        monitor.start()

        try:
            start_photoshop(cfg.photoshop_app_name, logger)
        except Exception as e:
            logger.error(f"[batch {batch_idx}] Could not start Photoshop: {e}")
            monitor.stop()
            # Give up on this batch; continue with next one (will try again).
            continue

        t_batch = time.time()
        try:
            results = run_jsx_batch(cfg, all_tasks, logger)
        except Exception as e:
            logger.error(f"[batch {batch_idx}] JSX run crashed: {e}")
            results = []

        batch_elapsed = time.time() - t_batch

        # Tabulate per-poster results.
        poster_ok: dict[str, int] = {p.stem: 0 for p in batch_posters}
        poster_fail: dict[str, int] = {p.stem: 0 for p in batch_posters}
        for r in results:
            pname = r["task"]["poster_name"]
            mname = r["task"]["mockup_name"]
            if r["status"] == "ok":
                poster_ok[pname] = poster_ok.get(pname, 0) + 1
                total_mockups_ok += 1
                logger.info(f"[batch {batch_idx}] OK     {pname} + {mname} "
                            f"({r['elapsed_ms']/1000:.1f}s, "
                            f"SO {r.get('so_width')}x{r.get('so_height')})")
            else:
                poster_fail[pname] = poster_fail.get(pname, 0) + 1
                total_mockups_failed += 1
                logger.warning(f"[batch {batch_idx}] FAILED {pname} + {mname}: "
                               f"{r.get('error','')[:200]}")

        # Stop Photoshop, then stop monitor.
        stop_photoshop(cfg.photoshop_app_name, logger)
        ram = monitor.stop()
        batch_ram_reports.append({**ram, "batch": batch_idx,
                                  "elapsed_s": round(batch_elapsed, 1)})
        logger.info(f"[batch {batch_idx}] Elapsed {batch_elapsed:.1f}s, "
                    f"peak PS RSS {ram['peak_ps_rss_gb']} GB, "
                    f"peak system used {ram['peak_system_used_gb']} GB")

        # Update state per poster.
        for poster in batch_posters:
            prior = per_poster_prior_done[poster.stem]
            ok_now = prior + poster_ok.get(poster.stem, 0)
            failed_now = poster_fail.get(poster.stem, 0)
            per_poster_status[poster.stem] = {
                "ok": ok_now,
                "failed": failed_now,
                "total": len(mockups),
            }
            upscale_ok = (cfg.upscaled_dir / f"{poster.stem}.jpg").exists()

            if ok_now >= cfg.min_mockups_ok and upscale_ok:
                flag = "" if ok_now == len(mockups) else \
                       f" (flag: only {ok_now}/{len(mockups)} mockups OK)"
                logger.info(f"[state] {poster.stem}: complete ({ok_now}/{len(mockups)}"
                            f" mockups OK){flag}")
                mark_poster_complete(state, poster.stem, {
                    "mockups_ok":     ok_now,
                    "mockups_failed": failed_now,
                    "mockups_total":  len(mockups),
                    "upscale_present": upscale_ok,
                })
                save_state(cfg.state_file, state)
            else:
                logger.warning(f"[state] {poster.stem}: NOT marked complete "
                               f"({ok_now}/{len(mockups)} OK, upscale={upscale_ok})"
                               f" — will retry on next run")

        # Sleep between batches to let Photoshop fully release resources.
        if batch_idx < len(batches):
            logger.info(f"[batch] Sleeping {cfg.ps_restart_sleep}s before next batch …")
            time.sleep(cfg.ps_restart_sleep)

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    total_elapsed = time.time() - run_start
    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total elapsed:          {total_elapsed/60:.1f} min")
    logger.info(f"Posters in input:       {len(posters)}")
    logger.info(f"Posters completed:      {len([p for p, s in per_poster_status.items() if s['ok'] >= cfg.min_mockups_ok])}")
    logger.info(f"Mockups generated OK:   {total_mockups_ok}")
    logger.info(f"Mockups failed:         {total_mockups_failed}")
    logger.info(f"Mockups skipped (existed): {total_mockups_skipped}")
    if batch_ram_reports:
        peak = max(r["peak_ps_rss_gb"] for r in batch_ram_reports)
        avg = sum(r["peak_ps_rss_gb"] for r in batch_ram_reports) / len(batch_ram_reports)
        peak_sys = max(r["peak_system_used_gb"] for r in batch_ram_reports)
        logger.info(f"Peak PS RSS across batches: {peak:.2f} GB")
        logger.info(f"Avg PS peak RSS per batch:  {avg:.2f} GB")
        logger.info(f"Peak system used:           {peak_sys:.2f} GB")
        if peak_sys > 7.0:
            logger.warning("Peak system RAM > 7 GB — consider lowering BATCH_SIZE")
        elif peak_sys < 5.0 and cfg.batch_size < 5:
            logger.info("Peak system RAM comfortably low — could try BATCH_SIZE=5")

    logger.info(f"State file: {cfg.state_file}")
    logger.info("Done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by user.\n")
        sys.exit(130)
