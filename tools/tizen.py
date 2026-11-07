#!/usr/bin/env python3
"""Minimal Samsung Tizen remote client for a Samsung Smart TV over Wi-Fi.

This is NOT the Android TV path. Tizen sets have no ADB, so there is no
`pm disable-user` and no launcher install here. See docs/devices/samsung-tizen.md.
What this does is the half that works: pair once, then read the TV, list its
installed apps and launch one by id, or send remote keys.

    export TV_HOST=192.168.1.7

    tools/tizen.py --probe              # model, OS, developer mode
    tools/tizen.py --pair               # accept the prompt on the TV, stores a token
    tools/tizen.py --apps               # installed apps with their ids
    tools/tizen.py --launch 11101200001 # launch an app by id
    tools/tizen.py --key KEY_MENU KEY_DOWN

The token is written next to this file as .tizen-token-<host> and reused, so the
TV only prompts once. Delete that file to force a new prompt.

Keys are not a scripting interface. The TV offers no screen capture, so a key
sequence is open-loop guesswork: menu row order differs by year, region and
firmware. Send keys with someone watching the screen, one step at a time.
"""

import argparse
import asyncio
import base64
import json
import os
import pathlib
import ssl
import sys
import urllib.request

CLIENT_NAME = "CleanYourTV"
HERE = pathlib.Path(__file__).resolve().parent


def die(msg, code=1):
    print(f"tizen.py: {msg}", file=sys.stderr)
    raise SystemExit(code)


def host_from_env_or_args(explicit):
    host = explicit or os.environ.get("TV_HOST", "").strip()
    if not host:
        die("set TV_HOST to the TV's IP address, or pass --host")
    return host.replace("http://", "").replace("https://", "").strip("/")


def token_path(host):
    return HERE / f".tizen-token-{host.replace(':', '_')}"


def ssl_ctx():
    # The TV presents a self-signed certificate. This connection is to a device
    # on the local network, named by the user, and carries no credentials.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def probe(host):
    """Read /api/v2/ over plain HTTP. No pairing needed, nothing is changed."""
    url = f"http://{host}:8001/api/v2/"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            info = json.loads(r.read().decode())
    except Exception as e:
        die(f"no answer from {url} ({e}). Same network? TV awake?")
    d = info.get("device", {})
    fields = [
        ("Model name", d.get("modelName")),
        ("Model string", d.get("model")),
        ("OS", d.get("OS")),
        ("Firmware", d.get("firmwareVersion")),
        ("Developer mode", d.get("developerMode")),
        ("Token auth", d.get("TokenAuthSupport")),
        ("Network", d.get("networkType")),
        ("Resolution", d.get("resolution")),
    ]
    width = max(len(k) for k, _ in fields)
    for k, v in fields:
        print(f"{k:<{width}}  {v}")
    if str(d.get("OS", "")).lower() == "tizen":
        print()
        print("Tizen: no ADB, so this repo's debloat lists and launcher do not apply.")
        print("See docs/devices/samsung-tizen.md and cleanyour.tv/not-android.")
    return info


async def _connect(host, token, first_time=False):
    import websockets

    name = base64.b64encode(CLIENT_NAME.encode()).decode()
    url = f"wss://{host}:8002/api/v2/channels/samsung.remote.control?name={name}"
    if token:
        url += f"&token={token}"
    if first_time:
        print("Accept the prompt on the TV screen.", flush=True)
    ws = await websockets.connect(
        url, ssl=ssl_ctx(), open_timeout=60, ping_interval=None, max_size=None
    )
    hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
    if hello.get("event") != "ms.channel.connect":
        await ws.close()
        die(f"TV refused the connection: {json.dumps(hello)[:200]}")
    new = (hello.get("data") or {}).get("token")
    return ws, new


def load_token(host):
    p = token_path(host)
    return p.read_text().strip() if p.exists() else ""


def save_token(host, token):
    if not token:
        return
    p = token_path(host)
    p.write_text(token)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    print(f"token stored in {p.name}")


async def cmd_pair(host):
    token = load_token(host)
    ws, new = await _connect(host, token, first_time=not token)
    await ws.close()
    save_token(host, new)
    print("paired" if (new or token) else "connected without a token")


async def cmd_apps(host):
    ws, new = await _connect(host, load_token(host))
    save_token(host, new)
    try:
        await ws.send(json.dumps({
            "method": "ms.channel.emit",
            "params": {"event": "ed.installedApp.get", "to": "host"},
        }))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if msg.get("event") == "ed.installedApp.get":
                apps = (msg.get("data") or {}).get("data", [])
                if not apps:
                    print("the TV returned an empty app list")
                    return
                width = max(len(str(a.get("appId", ""))) for a in apps)
                for a in sorted(apps, key=lambda a: (a.get("name") or "").lower()):
                    print(f"{str(a.get('appId')):<{width}}  {a.get('name')}")
                print(f"\n{len(apps)} apps. Launch one with --launch <id>.")
                return
    except asyncio.TimeoutError:
        die("the TV did not return an app list")
    finally:
        await ws.close()


async def cmd_launch(host, app_id):
    ws, new = await _connect(host, load_token(host))
    save_token(host, new)
    try:
        await ws.send(json.dumps({
            "method": "ms.channel.emit",
            "params": {
                "event": "ed.apps.launch",
                "to": "host",
                "data": {"action_type": "DEEP_LINK", "appId": app_id},
            },
        }))
        await asyncio.sleep(1.5)
        print(f"launch sent for {app_id}; check the TV")
    finally:
        await ws.close()


async def cmd_keys(host, keys, delay):
    ws, new = await _connect(host, load_token(host))
    save_token(host, new)
    try:
        for k in keys:
            if not k.startswith("KEY_"):
                die(f"not a key name: {k} (they look like KEY_MENU, KEY_DOWN)")
            await ws.send(json.dumps({
                "method": "ms.remote.control",
                "params": {
                    "Cmd": "Click",
                    "DataOfCmd": k,
                    "Option": "false",
                    "TypeOfRemote": "SendRemoteKey",
                },
            }))
            print(f"sent {k}", flush=True)
            await asyncio.sleep(delay)
    finally:
        await ws.close()


def main():
    ap = argparse.ArgumentParser(
        description="Samsung Tizen remote client (no ADB, no debloat).",
        epilog="TV_HOST=<ip> is read from the environment if --host is not given.",
    )
    ap.add_argument("--host", help="TV IP address")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--probe", action="store_true", help="read model and OS, no pairing")
    g.add_argument("--pair", action="store_true", help="pair and store a token")
    g.add_argument("--apps", action="store_true", help="list installed apps and ids")
    g.add_argument("--launch", metavar="APPID", help="launch an app by id")
    g.add_argument("--key", nargs="+", metavar="KEY", help="send remote keys")
    ap.add_argument("--delay", type=float, default=0.9, help="seconds between keys")
    args = ap.parse_args()

    host = host_from_env_or_args(args.host)

    if args.probe:
        probe(host)
        return

    try:
        import websockets  # noqa: F401
    except ImportError:
        die("needs the websockets package: pip install websockets")

    if args.pair:
        asyncio.run(cmd_pair(host))
    elif args.apps:
        asyncio.run(cmd_apps(host))
    elif args.launch:
        asyncio.run(cmd_launch(host, args.launch))
    elif args.key:
        asyncio.run(cmd_keys(host, args.key, args.delay))


if __name__ == "__main__":
    main()
