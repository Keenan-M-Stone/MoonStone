from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional


try:
    import psutil  # type: ignore
except Exception as e:  # pragma: no cover
    psutil = None  # type: ignore


try:
    import GPUtil  # type: ignore

    _HAS_GPU = True
except Exception:  # pragma: no cover
    GPUtil = None  # type: ignore
    _HAS_GPU = False


def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _aggregate_process_tree(proc):
    cpu = 0.0
    mem = 0
    try:
        cpu += float(proc.cpu_percent(interval=None))
    except Exception:
        pass
    try:
        mem += int(proc.memory_info().rss)
    except Exception:
        pass

    try:
        children = proc.children(recursive=True)
    except Exception:
        children = []

    for child in children:
        try:
            cpu += float(child.cpu_percent(interval=None))
        except Exception:
            pass
        try:
            mem += int(child.memory_info().rss)
        except Exception:
            pass
    return cpu, mem


class RunResourceSampler:
    def __init__(self, run_id: str, *, interval: float = 0.8, max_samples: int = 200):
        self.run_id = str(run_id)
        self.interval = float(interval)
        self.max_samples = int(max_samples)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._samples: List[Dict[str, Any]] = []
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if psutil is None:
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def samples(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._samples)

    def _append(self, usage: Dict[str, Any]) -> None:
        with self._lock:
            self._samples.append(usage)
            if len(self._samples) > self.max_samples:
                self._samples = self._samples[-self.max_samples :]

    def _run(self) -> None:
        assert psutil is not None
        process = psutil.Process()

        # Prime CPU counters
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass
        try:
            process.cpu_percent(interval=None)
        except Exception:
            pass

        while not self._stop.is_set():
            try:
                usage: Dict[str, Any] = {"timestamp": time.time()}

                try:
                    usage["cpu_system_percent"] = _safe_float(psutil.cpu_percent(interval=None))
                except Exception:
                    usage["cpu_system_percent"] = None

                try:
                    usage["cpu_per_core"] = psutil.cpu_percent(interval=None, percpu=True)
                except Exception:
                    usage["cpu_per_core"] = None

                proc_cpu, proc_mem = _aggregate_process_tree(process)
                usage["proc_cpu_percent"] = _safe_float(proc_cpu)
                usage["proc_memory_rss"] = _safe_int(proc_mem)

                try:
                    vm = psutil.virtual_memory()
                    usage["memory_total"] = _safe_int(getattr(vm, "total", None))
                    usage["memory_available"] = _safe_int(getattr(vm, "available", None))
                except Exception:
                    usage["memory_total"] = None
                    usage["memory_available"] = None

                try:
                    io_counters = psutil.disk_io_counters()
                    usage["disk_read_bytes"] = _safe_int(getattr(io_counters, "read_bytes", None))
                    usage["disk_write_bytes"] = _safe_int(getattr(io_counters, "write_bytes", None))
                except Exception:
                    usage["disk_read_bytes"] = None
                    usage["disk_write_bytes"] = None

                try:
                    net_counters = psutil.net_io_counters()
                    usage["net_bytes_sent"] = _safe_int(getattr(net_counters, "bytes_sent", None))
                    usage["net_bytes_recv"] = _safe_int(getattr(net_counters, "bytes_recv", None))
                except Exception:
                    usage["net_bytes_sent"] = None
                    usage["net_bytes_recv"] = None

                try:
                    usage["threads"] = _safe_int(process.num_threads())
                except Exception:
                    usage["threads"] = None

                try:
                    usage["open_files"] = _safe_int(len(process.open_files()))
                except Exception:
                    usage["open_files"] = None

                if _HAS_GPU and GPUtil is not None:
                    try:
                        gpus = GPUtil.getGPUs()
                        usage["gpus"] = [
                            {
                                "id": g.id,
                                "name": getattr(g, "name", None),
                                "load": getattr(g, "load", None),
                                "memory_total": getattr(g, "memoryTotal", None),
                                "memory_used": getattr(g, "memoryUsed", None),
                                "memory_util": getattr(g, "memoryUtil", None),
                            }
                            for g in gpus
                        ]
                    except Exception:
                        usage["gpus"] = None
                else:
                    usage["gpus"] = None

                self._append(usage)
            except Exception:
                # Never fail the run if sampling fails.
                pass

            try:
                self._stop.wait(self.interval)
            except Exception:
                time.sleep(self.interval)


_RUN_SAMPLERS: Dict[str, RunResourceSampler] = {}
_RUN_SAMPLERS_LOCK = threading.Lock()


def start_run_sampler(run_id: str) -> None:
    with _RUN_SAMPLERS_LOCK:
        sampler = _RUN_SAMPLERS.get(run_id)
        if sampler is None:
            sampler = RunResourceSampler(run_id)
            _RUN_SAMPLERS[run_id] = sampler
        sampler.start()


def stop_run_sampler(run_id: str) -> None:
    with _RUN_SAMPLERS_LOCK:
        sampler = _RUN_SAMPLERS.get(run_id)
        if sampler is None:
            return
        sampler.stop()


def get_run_samples(run_id: str) -> List[Dict[str, Any]]:
    with _RUN_SAMPLERS_LOCK:
        sampler = _RUN_SAMPLERS.get(run_id)
        if sampler is None:
            return []
        return sampler.samples()
