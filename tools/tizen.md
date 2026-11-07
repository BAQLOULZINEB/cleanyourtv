# `tools/tizen.py`: a Samsung Tizen remote client

**This is not the Android TV path, and it does not debloat anything.**

Every list in `examples/` works by connecting over ADB and running `pm disable-user` on
packages. Samsung Tizen sets have no ADB: port 5555 is closed on retail firmware, and no setting
opens it. The launcher in `launcher/` is an Android APK and cannot be installed on Tizen at all.
`docs/devices/samsung-tizen.md` has the measurements behind that.

So what is this? The same page proposes that a realistic Tizen cleanup would be "settings by
remote keys plus DNS, rather than debloat plus a launcher". This tool is the part of that which
was verified to work on a real set: the remote socket on port 8002.

Verified on a Samsung UA50MU7000 (7 Series 50", `17_KANTM_UHD_BASIC`, Tizen, Developer Mode off),
every subcommand run against that set and checked on the screen.

## What works

| Command | What it does | Needs pairing | Verified |
|---|---|---|---|
| `--probe` | Model, OS, firmware, developer mode, over plain HTTP on 8001 | no | yes |
| `--pair` | One "Allow" prompt on the TV, stores a token for later | the prompt | yes, token reused with no second prompt |
| `--apps` | Lists installed apps with their launchable ids | yes | yes, 14 apps returned |
| `--launch <id>` | Launches an app by id | yes | yes, app opened on screen |
| `--key KEY_... ` | Sends remote key presses | yes | yes, `KEY_MENU` opened the settings menu |

```sh
export TV_HOST=192.168.1.50

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

## A clean home screen on Tizen is possible, just not from here

Worth writing down, because "no ADB" is easy to read as "nothing can be done". A *signed Tizen
app* can give a Samsung set an ad-free home screen. [Free My TV](https://github.com/simbasjungles/free-my-tv)
does exactly that and supports Tizen from 2015 on; SHOWCASE.md already cites it for its look.
It is a sideloaded app, not a debloat and not a Home takeover: Samsung's home screen stays, and
the TV is told to start into the app instead. Nothing is rooted or removed.

Installed and confirmed running on the UA50MU7000 (Tizen 3.0) this page's notes come from, so the
route is real on a 2017 set. It needs Developer Mode on (Apps, then `1 2 3 4 5` on the remote,
this computer's IP as Host PC IP, restart), which opens SDB on 26101.

Three things cost hours on Windows, none of them documented where they bite:

- **Developer Mode cannot be switched on over the network.** Smart Hub's `1 2 3 4 5` prompt
  ignores keys from the remote socket, as `Click` and as `Press`/`Release`, while `KEY_MENU` and
  app launches on the same socket work. It wants the physical remote, an on-screen number pad or a
  USB keyboard. So `--key` cannot bootstrap the very mode that the install path needs.
- **Tizen CLI 2.5.25 is broken on JDK 17.** `org.tizen.common.util.CipherUtil` reads
  `com.sun.org.apache.xerces.internal.impl.dv.util.Base64`, which Java 9+ encapsulates, so it
  throws `IllegalAccessError` while handling the certificate password and falls back to prompting
  for it forever. Run it with
  `JAVA_TOOL_OPTIONS=--add-exports=java.xml/com.sun.org.apache.xerces.internal.impl.dv.util=ALL-UNNAMED`.
- **A UTF-8 BOM in a password silently breaks signing.** PowerShell's `Set-Content -Encoding utf8`
  writes one, and the CLI reads those three bytes as part of the password: 25 bytes for a
  22-character password, and a wrong password with no error that says so.

With the JDK flag in place, plain passwords written straight into `profiles.xml` are accepted and
`tizen package -t wgt -s <profile>` signs without prompting. Without the flag the same file throws.
Both pieces are needed, which is what makes this one hard to find: testing either alone says no.

A TV that has gone into deep standby (8001 and 8002 closed, not just idle) answers a Wake-on-LAN
magic packet to the MAC that `--probe` reports, so a sleeping set does not need the remote either.
