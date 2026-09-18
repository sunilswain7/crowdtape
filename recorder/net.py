"""
HTTP with a DNS escape hatch.

Measured on the machine this was written on (an Indian consumer connection), two
separate things were wrong, and only the first is a DNS problem:

  1. The system resolver returns a block-page address for coinmarketcap.com hosts.
     Fixed here by resolving over DoH against 1.1.1.1.
  2. The connection is then reset on the TLS hello - RST injection keyed on the SNI.
     Measured success rate against pro-api: 2 of 16 attempts, spread evenly across all
     four CloudFront edges, so no edge is reliably good and DNS alone does not fix it.

There is no clean client-side fix for (2), so the transport retries across edges until
one slips through. Locally that means a call can take several seconds and occasionally
still fail. From CI, where neither problem exists, the first attempt succeeds and none
of this code runs - which is the real reason the recorder belongs in CI and not on a
developer machine.

TLS is never weakened: only the address lookup is bypassed, and the certificate is
still validated against the real hostname.
"""
import http.client, json, os, socket, ssl, time, urllib.error, urllib.parse, urllib.request

DOH = "https://1.1.1.1/dns-query?name={}&type=A"
PROBE_TIMEOUT = 5          # a hijacked address is a black hole; fail fast and reroute
MAX_ATTEMPTS = int(os.environ.get("CMC_NET_ATTEMPTS", "4"))
# 4 keeps a local run responsive. It is not enough to beat the reset injection
# reliably, and it is not meant to be: the authoritative runs happen in CI, where
# the first attempt succeeds. Raise it with CMC_NET_ATTEMPTS if you must work local.

_cache: dict[str, list[str]] = {}
_direct_ok: dict[str, bool] = {}   # per host: is the system resolver usable at all?


class _Pinned(http.client.HTTPSConnection):
    """Connect to a known-good address while validating the certificate against the
    real hostname."""

    def __init__(self, host, ip, **kw):
        super().__init__(host, **kw)
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _doh(host: str) -> list[str]:
    if host in _cache:
        return _cache[host]
    req = urllib.request.Request(DOH.format(host), headers={"accept": "application/dns-json"})
    try:
        answer = json.loads(urllib.request.urlopen(req, timeout=12).read())
        ips = [a["data"] for a in answer.get("Answer", []) if a.get("type") == 1]
    except Exception:
        ips = []
    _cache[host] = ips
    return ips


def request(url: str, headers: dict, timeout: int = 30) -> tuple[int, bytes]:
    """Returns (http_status, body). Status 0 means every route failed."""
    parts = urllib.parse.urlsplit(url)
    target = parts.path + (f"?{parts.query}" if parts.query else "")

    host = parts.hostname

    # Try the system resolver once per host. A hijacked address does not refuse the
    # connection, it swallows it, so the first attempt gets a short leash - and if it
    # fails we stop paying that cost on every subsequent call.
    if _direct_ok.get(host, True):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(
                    req, timeout=timeout if host in _direct_ok else PROBE_TIMEOUT) as r:
                _direct_ok[host] = True
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            _direct_ok[host] = True      # a real answer, just not a 2xx
            return e.code, e.read()
        except Exception:
            _direct_ok[host] = False     # connection-level - reroute from here on

    ips = _doh(host)
    if not ips:
        return 0, b"could not resolve " + host.encode()

    last = b""
    ctx = ssl.create_default_context()
    for attempt in range(MAX_ATTEMPTS):
        ip = ips[attempt % len(ips)]        # rotate; no edge is reliably better
        try:
            conn = _Pinned(host, ip, timeout=timeout, context=ctx)
            conn.request("GET", target, headers=headers)
            resp = conn.getresponse()
            status, body = resp.status, resp.read()
            conn.close()
            return status, body
        except Exception as e:
            last = f"{type(e).__name__}: {e}".encode()[:120]
            time.sleep(0.3)                    # injected resets come in bursts
    return 0, last
