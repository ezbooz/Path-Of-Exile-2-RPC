<img width="800" height="500" alt="2" src="https://github.com/user-attachments/assets/30d06f66-797b-4c52-9895-344c42ecadff" />

**Languages:** English · [Русский](README.ru.md) · [Українська](README.ua.md)

## ⚙️ Install guide:
1. Install Python 3.11 or higher.
2. Install the package and dev dependencies: `pip install -e ".[dev]"`
3. Run the app: `poe2-rpc run` (or `python -m poe2_rpc run`).
4. Ensure that Discord is running.

Optional config: drop a `config.toml` at `%APPDATA%\poe2-rpc\config.toml` on
Windows (or `~/.config/poe2-rpc/config.toml` on macOS/Linux for dev). Defaults
work without one.

CLI commands: `poe2-rpc run` (continuous monitor), `poe2-rpc once` (single
log-stream pass), `poe2-rpc validate-config --no-discord` (validate settings
+ bundled assets without contacting Discord IPC).

### 🖥️ Run as a background service (Windows tray)

Install the optional tray extras first, then launch the tray icon and
register it with Windows Startup so it boots on login:

```bash
pip install "poe2-rpc[tray]"
poe2-rpc tray              # foreground tray (Status / Open log / Restart / Quit)
poe2-rpc install-autostart # Startup-folder shortcut so it launches on login
poe2-rpc uninstall-autostart
```

Notes:

- The tray runs the orchestrator on a background thread; `Quit` performs an
  orderly shutdown of the log-stream watcher.
- The shortcut points at the running interpreter / packaged `.exe` and passes
  `tray --quiet` so no console window is spawned at login.
- Use `poe2-rpc tray --quiet` from PowerShell if you launch it manually and
  want to suppress the console.

**For convenience, a pre-compiled .exe is available in the releases section.  
Download the latest release here:**  
👉 https://github.com/ezbooz/Path-Of-Exile-2-RPC/releases

## ✅ Features

- Rich Discord presence for **Path of Exile 2**
- Automatically detects character class, ascendancy, zone, and level
- Displays an image for each class
- Detects both the **Steam** (`PathOfExileSteam.exe`) and the **official**
  (`PathOfExile.exe`) clients
- **Owner auto-pin** so the RPC tracks the player who launched the script,
  not whichever party member appears in the log first
- **AFK / DND status** with `[AFK]` suffix and a temporary small-image override
  that restores the prior icon when AFK clears
- Optional **system-tray background service** with a Windows Startup-folder
  shortcut for autostart on login

---

## 🔧 To-Do

- [x] Support for custom images (all classes and ascendancies)
- [x] Launch as background service when game starts (tray + Windows Startup shortcut)
- [x] Add support for the official PoE2 client
- [x] Detect the player who started the script (avoid party conflicts)
- [x] Show AFK status

---


## 🙏 Acknowledgements

- 💾 [adainrivers](https://github.com/adainrivers/poe2-data) — map data and resources  
- 💻 [Miksuu](https://github.com/Miksuu) — code contributions

---

## 📎 License

This project is open-source under the [MIT License](LICENSE).
