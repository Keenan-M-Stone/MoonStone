#!/usr/bin/env python3

"""Run pytest with both per-test and overall watchdog timeouts.

Why:
- Per-test timeouts catch infinite loops/hangs inside a single test.
- Overall timeout prevents the whole suite from running forever.

Usage:
  python tools/run_tests_watchdog.py
  python tools/run_tests_watchdog.py -k "not gpu" --maxfail=1
  MOONSTONE_TEST_TIMEOUT_S=600 python tools/run_tests_watchdog.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time


def main() -> int:
  overall_timeout_s = int(os.environ.get("MOONSTONE_TEST_TIMEOUT_S", "1200"))
  start = time.time()

  cmd = [sys.executable, "-m", "pytest", *sys.argv[1:]]
  print("Running:", " ".join(cmd))
  print(f"Overall timeout: {overall_timeout_s}s")

  proc = subprocess.Popen(cmd)
  try:
    while True:
      rc = proc.poll()
      if rc is not None:
        return int(rc)
      if (time.time() - start) > overall_timeout_s:
        print("\nERROR: pytest exceeded overall timeout; terminating...", file=sys.stderr)
        proc.terminate()
        try:
          proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
          print("Force killing pytest...", file=sys.stderr)
          proc.kill()
        return 124
      time.sleep(0.5)
  except KeyboardInterrupt:
    proc.terminate()
    return 130


if __name__ == "__main__":
  raise SystemExit(main())
