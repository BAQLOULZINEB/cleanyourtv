# `tools/tizen.py`: a Samsung Tizen remote client

**This is not the Android TV path, and it does not debloat anything.**

Every list in `examples/` works by connecting over ADB and running `pm disable-user` on
packages. Samsung Tizen sets have no ADB: port 5555 is closed on retail firmware, and no setting
opens it. The launcher in `launcher/` is an Android APK and cannot be installed on Tizen at all.
`docs/devices/samsung-tizen.md` has the measurements behind that.

So what is this? The same page proposes that a realistic Tizen cleanup would be "settings by
remote keys plus DNS, rather than debloat plus a launcher". This tool is the part of that which
was verified to work on a real set: the remote socket on port 8002.

Verified on a Samsung UA50MU7000 (7 Series 50", `17_KANTM_UHD_BASIC`, Tizen, Developer Mode off).

## What works

| Command | What it does | Needs pairing |
|---|---|---|
| `--probe` | Model, OS, firmware, developer mode, over plain HTTP on 8001 | no |
| `--pair` | One "Allow" prompt on the TV, stores a token for later | the prompt |
| `--apps` | Lists installed apps with their launchable ids | yes |
| `--launch <id>` | Launches an app by id | yes |
| `--key KEY_... ` | Sends remote key presses | yes |

```sh
export TV_HOST=192.168.1.7

tools/tizen.py --probe
tools/tizen.py --pair          # accept the prompt on the TV, once
tools/tizen.py --apps
tools/tizen.py --launch 11101200001
```

The token is written next to the script as `.tizen-token-<host>` and reused, so the TV stops
prompting. Delete that file to force a new prompt. `websockets` is the only dependency
(`pip install websockets`); `--probe` needs nothing but the standard library.

## What does not work, and will not

- **No debloat.** No shell, no package manager, no way to disable a Samsung app from outside.
- **No launcher replacement.** A third-party app cannot take the Home button on Tizen.
- **No screen capture.** There is no capture API on 8001 or 8002.

That last one is the important one, because it decides what the key sender is good for.

## Why `--key` is not an automation interface

Menu position cannot be known from outside. Row order differs by year, region and firmware, the
highlight does not start in a fixed place, and `/api/v2/` reports no UI state. On the test set,
two short sequences aimed at Software Update both landed somewhere else, the second on a Live TV
setup screen, two rows from a channel retune.

So `--key` is for a person sitting in front of the TV, pressing one step at a time and reading the
screen. It is not for a script that walks a menu unattended. Nothing in this tool sends
`KEY_ENTER` on your behalf as part of a sequence you have not checked.

`--launch` is the opposite: an app id is exact, so launching is deterministic and safe to script.

## What this is actually good for

- **Jumping straight to an app**, skipping Smart Hub and the rows it puts in front of you. Bind
  `--launch` to a shortcut on a phone or a keyboard and the ad-heavy home screen stops being the
  thing you look at. The TV's own home is still there; you are just not visiting it.
- **Reading what is installed** on a set you are documenting, without touching it.
- **Driving the privacy menus with a person watching**, which is the real cleanup available on
  Tizen: Support, then Terms & Privacy, where the interest-based ads and viewing-information
  toggles live. Combine with DNS blocking at the router.

For the full CleanYourTV experience on a Samsung set, the honest answer is an Android TV or Google
TV device on an HDMI input. That device is supported by this repo; the TV is not.
