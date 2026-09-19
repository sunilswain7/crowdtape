#!/usr/bin/env python3
"""
Keeps snapshotting for the life of a CI job.

`cron: "*/15 * * * *"` does not give you a snapshot every fifteen minutes. Measured on
this repository over nine hours it gave four runs, spaced two to three hours apart:
GitHub queues scheduled workflows on shared capacity and drops them freely. At that
resolution the recorded series is worthless, and resolution is the entire point - nobody
can reconstruct attention or positioning after the fact, because CoinMarketCap keeps
neither.

So the schedule is used only to *start* a job, and the job then holds itself open and
snapshots on its own clock. A run that survives its full duration produces ~34 snapshots
where cron produced one. Overlapping runs are cancelled by the workflow's concurrency
group, so a late trigger costs nothing and a missed one costs only the gap.

Actions minutes are free on public repositories, which is the only reason this is a
reasonable thing to do.

Env:
  SNAPSHOT_INTERVAL_S   default 600  - raise the rate when the plan allows it
  LOOP_DURATION_S       default 5h40 - under the 6h job ceiling
  COMMIT_EVERY          default 3    - snapshots per commit
"""
import os, subprocess, sys, time, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTERVAL = int(os.environ.get("SNAPSHOT_INTERVAL_S", "600"))
DURATION = int(os.environ.get("LOOP_DURATION_S", str(5 * 3600 + 40 * 60)))
COMMIT_EVERY = int(os.environ.get("COMMIT_EVERY", "3"))


def run(*args: str) -> tuple[int, str]:
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def commit(n: int) -> None:
    run("git", "add", "data/")
    code, _ = run("git", "diff", "--staged", "--quiet")
    if code == 0:
        print("   nothing new to commit", flush=True)
        return
    run("git", "commit", "-m", f"snapshot x{n} {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}")
    # Another run may have pushed while this one slept; rebase rather than fail.
    run("git", "pull", "--rebase", "--autostash", "origin", "main")
    code, out = run("git", "push", "origin", "HEAD:main")
    print(f"   push {'ok' if code == 0 else 'FAILED: ' + out[:200]}", flush=True)


started = time.time()
taken = since_commit = failures = 0
print(f"looping for {DURATION//60} min, one snapshot every {INTERVAL}s", flush=True)

while time.time() - started < DURATION:
    cycle = time.time()
    code, out = run(sys.executable, "recorder/record.py")
    if code == 0:
        taken += 1
        since_commit += 1
        print(f"[{taken}] {out.splitlines()[-1] if out else 'ok'}", flush=True)
    else:
        failures += 1
        print(f"[!] snapshot failed: {out[-300:]}", flush=True)
        # A key that has stopped working will not start working by being hammered.
        if failures >= 5 and taken == 0:
            sys.exit("five consecutive failures and nothing recorded - stopping")

    if since_commit >= COMMIT_EVERY:
        commit(since_commit)
        since_commit = 0

    slept = INTERVAL - (time.time() - cycle)
    if slept > 0 and time.time() - started + slept < DURATION:
        time.sleep(slept)
    elif slept > 0:
        break

if since_commit:
    commit(since_commit)
print(f"\ndone: {taken} snapshots, {failures} failures, "
      f"{(time.time()-started)/60:.0f} min elapsed", flush=True)
