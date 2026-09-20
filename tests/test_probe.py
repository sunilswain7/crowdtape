"""
Runs the probe end-to-end against a stubbed transport.

This exists because the probe shipped with a NameError: the parameter sweep referenced
`lines` and `DOCS` from a position above where either was defined. It compiled fine -
a NameError is a runtime event - and the only thing that caught it was a failed CI run
and a wasted round trip with the user. A script that is only ever exercised by spending
real credits in CI is a script nobody tests, so this drives every branch offline:
plan-blocked, path-absent, bad-params, the sweep firing, and the reports being written.
"""
import json, os, pathlib, sys, tempfile, types, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SWEEP_PATHS = ("/v1/dex/holders/count", "/v4/dex/spot-pairs/latest",
               "/v5/cryptocurrency/derivatives/market-pairs/list/latest",
               "/v5/real-world-assets/quotes/latest")


def _stub_request(url, headers, timeout=30):
    path = url.split("coinmarketcap.com")[1].split("?")[0]
    query = url.split("?")[1] if "?" in url else ""
    def body(**kw): return json.dumps(kw).encode()

    if "totally-made-up" in path or "/v6/" in path:      # controls
        return 200, body(status={"error_code": 500,
                                 "error_message": "The system is busy, please try again later!"})
    if any(k in path for k in ("trending", "community", "content")):
        return 403, body(status={"error_code": 1006,
                                 "error_message": "Your API Key subscription plan doesn't support this endpoint."})
    if path in SWEEP_PATHS:
        if "network_slug" in query or "convert=USD" in query or "id=1" in query:
            return 200, body(status={"credit_count": 1}, data=[{"id": 1, "holders": 4211}])
        return 400, body(status={"error_code": 1002,
                                 "error_message": '"network_slug" or "network_id" is required.'})
    if path == "/v1/key/info":
        return 200, body(status={"credit_count": 0}, data={
            "plan": {"credit_limit_monthly": 15000, "rate_limit_minute": 50},
            "usage": {"current_month": {"credits_used": 818}}})
    return 200, body(status={"credit_count": 1}, data=[{"id": 1, "symbol": "BTC", "cmc_rank": 1}])


class ProbeRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._net = sys.modules.get("net")
        stub = types.ModuleType("net"); stub.request = _stub_request
        sys.modules["net"] = stub
        self._env = dict(os.environ)
        os.environ.update(CMC_API_KEY="stub",
                          PROBE_DOCS_DIR=self.tmp.name,
                          PROBE_OUT_DIR=self.tmp.name)

    def tearDown(self):
        os.environ.clear(); os.environ.update(self._env)
        if self._net is None: sys.modules.pop("net", None)
        else: sys.modules["net"] = self._net
        self.tmp.cleanup()

    def _run(self):
        src = (ROOT / "scripts" / "probe.py").read_text().replace("time.sleep(0.25)", "pass")
        ns = {"__file__": str(ROOT / "scripts" / "probe.py"), "__name__": "__main__"}
        from io import StringIO
        held, sys.stdout = sys.stdout, StringIO()
        try:
            exec(compile(src, "probe.py", "exec"), ns)
            return sys.stdout.getvalue()
        finally:
            sys.stdout = held

    def test_runs_to_completion_and_writes_both_reports(self):
        out = self._run()
        d = pathlib.Path(self.tmp.name)
        self.assertTrue((d / "endpoint-access.md").exists())
        self.assertTrue((d / "payload-shapes.md").exists())
        self.assertIn("Wrote docs/", out)

    def test_reports_the_plan_from_the_credit_ceiling(self):
        """/v1/key/info carries no tier name; 15,000 credits is the only tell."""
        self.assertIn("Basic (free)", self._run())

    def test_the_sweep_fires_and_is_published(self):
        self._run()
        table = (pathlib.Path(self.tmp.name) / "endpoint-access.md").read_text()
        self.assertIn("## Parameter sweep", table)
        self.assertIn("network_slug", table, "the rejected parameters must be shown")

    def test_a_nonexistent_path_is_not_recorded_as_working(self):
        """CMC answers HTTP 200 for paths that do not exist. The controls catch it."""
        out = self._run()
        self.assertNotIn("CONTROLS FAILED", out)
        self.assertIn("PATH-ABSENT", out)

    def test_the_error_message_survives_into_the_table(self):
        self._run()
        table = (pathlib.Path(self.tmp.name) / "endpoint-access.md").read_text()
        self.assertIn("subscription plan", table,
                      "omitting the message throws away the whole diagnostic")


if __name__ == "__main__":
    unittest.main()
