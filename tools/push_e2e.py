"""Production end-to-end web push test (item 424): a real Mozilla autopush subscription, headless.

  python3 tools/push_e2e.py setup  <team_a> <team_b>   register with autopush (production VAPID public key) and
                                                        subscribe through https://tifo.elyoxe.com/api/tifo/push/sub
  python3 tools/push_e2e.py setup  <team> p<player> …   «تابع اللاعب»: teams and players (p<id>) on one device, every
                                                        player alert switched on
  python3 tools/push_e2e.py listen <until-UTC-ISO> [--stop-on-end]
                                                        stay connected (reconnects with the same uaid), decrypt
                                                        every notification into received.jsonl, ack it
  python3 tools/push_e2e.py teardown                    DELETE the subscription at the API, unregister the channel
State (keys, uaid, endpoint) in $PUSH_E2E_DIR (default /tmp/push424). Needs websockets, cryptography, http_ece
(PYTHONPATH may point at a pip --target dir). Never uses the VAPID private key.
"""
import asyncio, base64, json, os, sys, time, urllib.request, uuid

DIR = os.environ.get("PUSH_E2E_DIR", "/tmp/push424")
API = "https://tifo.elyoxe.com/api/tifo/push/sub"
WS = "wss://push.services.mozilla.com/"
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _state(upd=None):
    p = os.path.join(DIR, "state.json")
    s = json.load(open(p)) if os.path.exists(p) else {}
    if upd:
        s.update(upd)
        os.makedirs(DIR, exist_ok=True)
        json.dump(s, open(p + ".tmp", "w"), indent=1)
        os.replace(p + ".tmp", p)
    return s


def log(*a):
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(os.path.join(DIR, "log.txt"), "a") as f:
        f.write(line + "\n")


def api(method, body):
    req = urllib.request.Request(API, method=method, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "user-agent": "tifo-push-e2e/1 (hello@elyoxe.com)",
                                          "origin": "https://tifo.elyoxe.com"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return f"{e.code} {e.read()[:200]!r}"


def targets(args):
    """["102122", "p1659961"] -> ([102122], [1659961]): a «p» prefix is a player (player follow, 2026-10-09)."""
    return [int(a) for a in args if a.isdigit()], [int(a[1:]) for a in args if a[:1] == "p" and a[1:].isdigit()]


PLAYER_EVENTS = ["soon", "start11", "squad_out", "subin", "subout", "goal", "assist", "card", "pen", "end", "potm", "video"]


async def setup(teams, players=()):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    import websockets
    key = json.load(urllib.request.urlopen("https://tifo.elyoxe.com/api/tifo/push/key", timeout=20))["publicKey"]
    priv = ec.generate_private_key(ec.SECP256R1())
    auth = os.urandom(16)
    ch = str(uuid.uuid4())
    async with websockets.connect(WS, subprotocols=["push-notification"]) as ws:
        await ws.send(json.dumps({"messageType": "hello", "use_webpush": True}))
        hello = json.loads(await ws.recv())
        await ws.send(json.dumps({"messageType": "register", "channelID": ch, "key": key}))
        reg = json.loads(await ws.recv())
    pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    p256 = b64(priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    s = _state({"uaid": hello["uaid"], "channel": ch, "endpoint": reg["pushEndpoint"], "ua_pem": pem, "auth": b64(auth),
                "p256dh": p256, "teams": teams, "players": list(players), "created": time.time()})
    sub = {"endpoint": s["endpoint"], "keys": {"p256dh": p256, "auth": s["auth"]}}
    st = api("POST", {"teams": teams, "events": ["start", "goal", "end"], "subscription": sub}) if teams else None
    sp = [api("POST", {"player": pid, "events": PLAYER_EVENTS, "cc": "AE", "subscription": sub}) for pid in players]
    log("setup: registered", reg.get("status"), s["endpoint"].split("/")[2], "teams", teams, "->", st, "players", list(players), "->", sp)


async def listen(until, stop_on_end):
    import websockets, http_ece
    from cryptography.hazmat.primitives import serialization
    s = _state()
    priv = serialization.load_pem_private_key(s["ua_pem"].encode(), None)
    auth = unb64(s["auth"])
    deadline = time.mktime(time.strptime(until, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    got_end = False
    while time.time() < deadline and not (stop_on_end and got_end):
        try:
            async with websockets.connect(WS, subprotocols=["push-notification"], ping_interval=60) as ws:
                await ws.send(json.dumps({"messageType": "hello", "use_webpush": True, "uaid": s["uaid"], "channelIDs": [s["channel"]]}))
                h = json.loads(await ws.recv())
                if h.get("uaid") != s["uaid"]:
                    log("WARNING: autopush gave a new uaid", h.get("uaid"))
                log("connected, status", h.get("status"))
                while time.time() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=max(1, min(300, deadline - time.time())))
                    except asyncio.TimeoutError:
                        continue
                    m = json.loads(raw)
                    if m.get("messageType") != "notification":
                        if m.get("messageType") == "ping":
                            await ws.send("{}")
                        continue
                    try:
                        body = json.loads(http_ece.decrypt(unb64(m["data"]), private_key=priv, auth_secret=auth, version="aes128gcm"))
                    except Exception as e:
                        body = {"decrypt_error": f"{type(e).__name__}: {e}"}
                    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": m.get("version"), "payload": body}
                    with open(os.path.join(DIR, "received.jsonl"), "a") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    log("RECEIVED", json.dumps(body, ensure_ascii=False))
                    await ws.send(json.dumps({"messageType": "ack", "updates": [{"channelID": m["channelID"], "version": m["version"]}]}))
                    if str(body.get("title", "")).startswith("انتهت"):
                        got_end = True
                        if stop_on_end:
                            break
        except Exception as e:
            log("connection dropped:", type(e).__name__, str(e)[:120], "- reconnecting in 10 s")
            await asyncio.sleep(10)
    log("listen: done", "end received" if got_end else "deadline reached")


async def teardown():
    import websockets
    s = _state()
    st = api("DELETE", {"teams": s["teams"], "endpoint": s["endpoint"]}) if s.get("teams") else None
    st = [st] + [api("DELETE", {"player": pid, "endpoint": s["endpoint"]}) for pid in s.get("players") or []]
    try:
        async with websockets.connect(WS, subprotocols=["push-notification"]) as ws:
            await ws.send(json.dumps({"messageType": "hello", "use_webpush": True, "uaid": s["uaid"], "channelIDs": [s["channel"]]}))
            await ws.recv()
            await ws.send(json.dumps({"messageType": "unregister", "channelID": s["channel"]}))
            u = json.loads(await ws.recv()).get("status")
    except Exception as e:
        u = f"{type(e).__name__}: {e}"
    log("teardown: API DELETE ->", st, "; autopush unregister ->", u)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "setup":
        asyncio.run(setup(*targets(sys.argv[2:])))
    elif cmd == "listen":
        asyncio.run(listen(sys.argv[2], "--stop-on-end" in sys.argv))
    elif cmd == "teardown":
        asyncio.run(teardown())
