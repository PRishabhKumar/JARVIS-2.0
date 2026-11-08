# User-level autostart (experimental; opt-in)

The generator creates files only. It does not install/register tasks, start audio, or change persistence. Test foreground `jarvis satellite` with your actual microphone and unlocked native keyring before proceeding. Keep a hardware mute available. Autostart also requires the optional audio/wake dependencies and all explicitly installed model assets.

Use a virtual environment installed at a stable absolute path. The generator defaults to the Python running the generator; specify `--python` explicitly if needed. Configuration and model paths are made absolute.

## Windows

Generate XML via `scripts/render_autostart.py --os windows ... --output jarvis-task.xml`. In Task Scheduler use **Import Task**, choose your user, **Run only when user is logged on**, do not choose highest privileges, verify the action and paths, and keep a visible terminal. The XML uses InteractiveToken/LeastPrivilege. Validate Windows microphone access and Credential Manager availability.

Disable/remove: Task Scheduler → the imported task → End, Disable, then Delete. This is not a Windows service. Actual import/logon behavior is untested here.

## macOS

Generate with `--os macos --output local.jarvis.satellite.plist`. Review the plist, microphone/TCC permission, Keychain access and console visibility. After validation, place it in `~/Library/LaunchAgents/local.jarvis.satellite.plist`, then explicitly run:

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.jarvis.satellite.plist
```

Stop/remove:

```sh
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/local.jarvis.satellite.plist
rm ~/Library/LaunchAgents/local.jarvis.satellite.plist
```

The generated launch agent does not currently provide a tray mic indicator or automatically open a terminal; **do not use unattended until that release gap is resolved**. No sudo/system launch daemon is needed.

## Linux

Generate with `--os linux --output jarvis-satellite.service`. It requires a user-session systemd installation, local PortAudio/microphone permissions, and an unlocked desktop keyring. Do not enable system-wide or root service modes. After review, place it in `~/.config/systemd/user/` and explicitly run:

```sh
systemctl --user daemon-reload
systemctl --user enable --now jarvis-satellite.service
```

Stop/remove:

```sh
systemctl --user disable --now jarvis-satellite.service
rm ~/.config/systemd/user/jarvis-satellite.service
systemctl --user daemon-reload
```

Other init systems require their own autostart providers. The template alone is not proof of distro support. The unit does not add a tray mic indicator; use foreground operation during testing. Privacy-sensitive transcriptions may appear on the terminal/system service output even though JARVIS itself does not persist transcripts; disable journal/stdout retention or keep foreground operation until a dedicated service logging/privacy design is completed.
