#!/usr/bin/env python3
"""
Automatic scheduler — runs the pipeline on a recurring cycle.
Default: every 25 hours (gives NotebookLM's daily limit time to reset).

Usage:
  python3 scheduler.py              # run in foreground
  nohup python3 scheduler.py &      # run in background
"""

import json
import os
import smtplib
import ssl
import subprocess
import sys
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
STATE_FILE = LOGS_DIR / "scheduler-state.json"
PUBLISHED_FILE = BASE_DIR / "data" / "published.json"

CYCLE_HOURS = int(os.getenv("CYCLE_HOURS", "25"))
EPISODES_PER_DAY = int(os.getenv("EPISODES_PER_DAY", "3"))


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)

    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / "scheduler.log"
    with open(log_file, "a") as f:
        f.write(line + "\n")


def save_state():
    LOGS_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "last_run": datetime.now().isoformat(),
    }))


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def should_wait():
    """Check if we need to wait out remaining time from a previous cycle."""
    state = load_state()
    last_run = state.get("last_run")

    if not last_run:
        return 0

    last = datetime.fromisoformat(last_run)
    next_run = last + timedelta(hours=CYCLE_HOURS)
    now = datetime.now()

    if now < next_run:
        return (next_run - now).total_seconds()

    return 0


def send_summary_email(successes, failures, total):
    """Send a daily summary email if configured."""
    email = os.getenv("GMAIL_ADDRESS", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")

    if not email or not password or os.getenv("ENABLE_EMAIL", "false").lower() != "true":
        return

    podcast_name = os.getenv("PODCAST_NAME", "Podcast Pipeline")
    subject = f"{podcast_name}: {successes}/{total} episodes published"

    body = f"""Daily Pipeline Summary
{'=' * 40}

Published: {successes}/{total}
Failed: {failures}/{total}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Next cycle in {CYCLE_HOURS} hours.
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = email
    msg["To"] = email

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=ctx)
            server.login(email, password)
            server.send_message(msg)
        log("Summary email sent.")
    except Exception as e:
        log(f"Email failed: {e}")


def run_cycle():
    """Run one full pipeline cycle."""
    log(f"Starting cycle — {EPISODES_PER_DAY} episodes")

    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "run.py"), "--batch", "--limit", str(EPISODES_PER_DAY)],
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
    )

    # Count results from published.json
    successes = 0
    failures = 0
    if PUBLISHED_FILE.exists():
        published = json.loads(PUBLISHED_FILE.read_text())
        # Count today's episodes
        today = datetime.now().date().isoformat()
        for ep in published:
            pub_date = ep.get("published_at", "")[:10]
            if pub_date == today:
                if ep.get("status") == "published":
                    successes += 1
                else:
                    failures += 1

    log(f"Cycle complete: {successes} published, {failures} failed")

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    send_summary_email(successes, failures, EPISODES_PER_DAY)
    save_state()


def main():
    log(f"Scheduler started — {CYCLE_HOURS}h cycles, {EPISODES_PER_DAY} episodes/cycle")

    # Save PID
    LOGS_DIR.mkdir(exist_ok=True)
    (LOGS_DIR / "scheduler.pid").write_text(str(os.getpid()))

    while True:
        # Check if we need to wait from a previous run
        wait_secs = should_wait()
        if wait_secs > 0:
            hours = wait_secs / 3600
            log(f"Waiting {hours:.1f}h until next cycle...")
            time.sleep(wait_secs)

        run_cycle()

        # Sleep until next cycle
        log(f"Sleeping {CYCLE_HOURS} hours...")
        time.sleep(CYCLE_HOURS * 3600)


if __name__ == "__main__":
    main()
