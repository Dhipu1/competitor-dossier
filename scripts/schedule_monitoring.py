"""Sets up a recurring monitoring run via Windows Task Scheduler.

The retainer only works if the monthly brief actually generates itself. On
Linux this would be cron; the Windows equivalent is Task Scheduler, driven
from the command line by schtasks.

By default this only *prepares* the task: it writes a .bat launcher and
prints the exact schtasks command. Registering a scheduled task is a lasting
change to your machine, so it happens only when you pass --install.

Run with:
  .venv\\Scripts\\python scripts\\schedule_monitoring.py clients\\pilot.json
  .venv\\Scripts\\python scripts\\schedule_monitoring.py clients\\pilot.json --days 14 --install
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = ROOT / "jobs"


def write_launcher(config: str, task_name: str) -> Path:
    """A .bat so Task Scheduler has one thing to call, with paths resolved."""
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    log = JOBS_DIR / f"{task_name}.log"

    bat = JOBS_DIR / f"{task_name}.bat"
    bat.write_text(
        "@echo off\r\n"
        f'cd /d "{ROOT}"\r\n'
        f'"{python}" scripts\\monitor_run.py "{config}" >> "{log}" 2>&1\r\n',
        encoding="utf-8",
    )
    return bat


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    config = args[0] if args else "clients/pilot.json"

    if not (ROOT / config).exists():
        sys.exit(f"Client config not found: {config}")

    days = 14
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    client_slug = Path(config).stem
    task_name = f"dossier-monitor-{client_slug}"

    JOBS_DIR.mkdir(exist_ok=True)
    bat = write_launcher(config, task_name)
    print(f"Wrote launcher: {bat}")

    # /SC DAILY with /MO <days> runs every N days, which is how you express a
    # fortnightly cadence to schtasks — it has no native "every 2 weeks".
    command = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", f'"{bat}"',
        "/SC", "DAILY",
        "/MO", str(days),
        "/ST", "03:00",
        "/F",  # replace an existing task of the same name
    ]

    print(f"\nSchedule: every {days} days at 03:00, logging to jobs\\{task_name}.log")
    print("\nCommand:\n  " + " ".join(command))

    if "--install" not in sys.argv:
        print(
            "\nNot installed. Re-run with --install to register it, or copy the"
            "\ncommand above into a terminal yourself."
            f"\n\nRemove later with:  schtasks /Delete /TN {task_name} /F"
        )
        sys.exit(0)

    result = subprocess.run(command)
    if result.returncode != 0:
        sys.exit(
            f"\nschtasks failed (exit {result.returncode}). Creating a task can "
            "require an elevated terminal."
        )
    print(f"\nRegistered '{task_name}'.")
    print(f"  check it:  schtasks /Query /TN {task_name}")
    print(f"  run now:   schtasks /Run /TN {task_name}")
    print(f"  remove:    schtasks /Delete /TN {task_name} /F")
