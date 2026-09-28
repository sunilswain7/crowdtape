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
import json, os, subprocess, sys, time, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTERVAL = int(os.environ.get("SNAPSHOT_INTERVAL_S", "600"))
DURATION = int(os.environ.get("LOOP_DURATION_S", str(5 * 3600 + 40 * 60)))
COMMIT_EVERY = int(os.environ.get("COMMIT_EVERY", "3"))
HOLDERS_EVERY = int(os.environ.get("HOLDERS_EVERY", "18"))   # 18 x 10 min = 3 hours


def run(*args: str) -> tuple[int, str]:
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def dispatch(workflow: str) -> bool:
    """Ask GitHub to start a workflow. Returns whether it was accepted.

    `workflow_dispatch` is one of the two events a GITHUB_TOKEN may raise, and unlike the
    schedule it actually fires: measured over ten days, cron delivered this workflow every
    two to six hours against an hourly request, and once went eight and a half hours
    without a run while nothing recorded. Dispatch has never been late.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return False
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
        data=json.dumps({"ref": "main"}).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception as e:
        print(f"   dispatch {workflow} failed: {str(e)[:100]}", flush=True)
        return False


def redeploy() -> None:
    """Ask the pages workflow to run.

    A push made with GITHUB_TOKEN does not trigger workflows - GitHub suppresses it to
    prevent recursion - so the recorder committing site/data every ten minutes never woke
    the deploy, and the published board sat twenty-one hours behind the repository.
    `workflow_dispatch` is one of the two documented exceptions to that rule, so the
    recorder asks for the deploy explicitly instead of relying on the push.
    """
    # A failed deploy request must never take the recorder down with it: the snapshot is
    # the irreplaceable part, the deploy can wait.
    if dispatch("pages.yml"):
        print("   deploy requested", flush=True)


def commit(n: int) -> None:
    # Regenerate the site's data in the same commit as the snapshots that produced it,
    # so the published board is never describing a state the repository cannot show.
    code, out = run(sys.executable, "-m", "engine.report")
    print(f"   report: {out.splitlines()[0] if out else 'failed'}", flush=True)
    run("git", "add", "data/", "site/")
    code, _ = run("git", "diff", "--staged", "--quiet")
    if code == 0:
        print("   nothing new to commit", flush=True)
        return
    run("git", "commit", "-m", f"snapshot x{n} {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}")
    # Another run may have pushed while this one slept; rebase rather than fail.
    run("git", "pull", "--rebase", "--autostash", "origin", "main")
    code, out = run("git", "push", "origin", "HEAD:main")
    print(f"   push {'ok' if code == 0 else 'FAILED: ' + out[:200]}", flush=True)
    if code == 0:
        redeploy()


started = time.time()
taken = since_commit = failures = 0
print(f"looping for {DURATION//60} min, one snapshot every {INTERVAL}s", flush=True)

while time.time() - started < DURATION:
    cycle = time.time()
    # Wallet counts move over hours, and each one costs a credit. Poll them on a slow
    # cycle rather than every snapshot - see recorder/record.py for the arithmetic.
    holders = (taken % HOLDERS_EVERY == 0)
    env = dict(os.environ, CROWDTAPE_HOLDERS="1" if holders else "0")
    p = subprocess.run([sys.executable, "recorder/record.py"], cwd=ROOT,
                       capture_output=True, text=True, env=env)
    code, out = p.returncode, (p.stdout + p.stderr).strip()
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

# Hand off to a successor before exiting. The schedule is a backstop GitHub honours
# erratically - measured over ten days it delivered this workflow every two to six hours
# against an hourly request - so the chain is what actually keeps the recorder alive.
# Each run starts the next, and the workflow's concurrency group makes a duplicate
# harmless.
if dispatch("record.yml"):
    print("   successor dispatched", flush=True)

print(f"\ndone: {taken} snapshots, {failures} failures, "
      f"{(time.time()-started)/60:.0f} min elapsed", flush=True)
