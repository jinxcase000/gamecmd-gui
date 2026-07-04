# gamecmd-gui

A GTK4 + libadwaita GUI for [gamecmd](https://github.com/jinxcase000/gamecmd) --
build per-game Steam launch-option profiles from organized checklists instead
of hand-writing `env_vars` / `prefix` / `suffix` strings.

gamecmd itself is unchanged: this GUI just reads and writes the same
`~/.config/gamecmd/games.yaml` file, so both tools can be used interchangeably
on the same profiles.

---

## Features

- **Games tab** -- every profile in `games.yaml`, with edit / delete / copy
  (copies `gamecmd <profile> %command%` to your clipboard, ready to paste into
  Steam's launch options).
- **Add Game** -- opens a blank profile editor.
- **Import from Steam** -- scans every detected Steam library (native,
  `~/.steam`, and Flatpak installs) by reading `libraryfolders.vdf` and
  `appmanifest_*.acf` directly -- no Steam API key, no network access.
  Multi-select which installed games to add, either blank or with GameMode
  (`gamemoderun`) pre-applied.
- **Organized checklists** covering:
  - Compatibility Layer (Proton) toggles
  - DXVK tuning
  - DLSS / NVIDIA (NVAPI passthrough, shader cache, threaded optimizations)
  - FSR (Wine's built-in FSR 1.0, plus an experimental RADV FSR4 entry)
  - Gamescope (resolution, upscale filters, HDR, frame limiting)
  - MangoHud (overlay contents, FPS limit, per-game config file)
  - GameMode & performance wrappers (GameMode, `prime-run`, vkBasalt, OBS
    Vulkan capture, Bazzite-style `game-performance`)
  - Wine / prefix options (WINEPREFIX, WINEARCH, sync primitives, DLL overrides)
  - Engine-specific suffix flags: Unreal Engine, Unity, Source/GoldSrc, id
    Tech, Godot
  - Every option shows a description; a handful carry an explicit warning
    (e.g. FSR4 support is new and driver-version-dependent) rather than
    pretending they're as settled as the rest.
- Each checked option adds an **editable** value -- checking a box seeds a
  sane default, but you can tweak it before it's added.
- A **Custom / Advanced** section per profile holds anything not in the
  checklists (and, when editing an existing profile, its current settings --
  nothing is silently reinterpreted).
- A **live preview** shows exactly what gamecmd will execute, mirroring its
  own `GAMECMD_DEBUG=1` output, plus the literal Steam launch-option line to
  paste in.

---

## Requirements

- gamecmd itself, installed and with `~/.config/gamecmd/games.yaml` present
  (run `../gamecmd/install.sh` first if you haven't).
- Python 3.10+
- GTK4 + libadwaita (1.4+) with GObject introspection (PyGObject)
- `ruamel.yaml` (installed automatically)

## Installation

    cd gamecmd-gui
    chmod +x install.sh
    ./install.sh

This installs the GTK4/libadwaita system packages for your distro (pacman /
apt / dnf / zypper), then installs gamecmd-gui itself via pip, registering a
`gamecmd-gui` command in `~/.local/bin`.

To run from source without installing:

    ./run.sh

## Usage

1. Launch `gamecmd-gui`.
2. Add games manually, or click **Import from Steam** to pull in your
   installed library.
3. Open a game, check the options you want, tweak the seeded values if
   needed, watch the live preview at the bottom update as you go.
4. Click **Save**, then copy the Steam launch-option line into that game's
   Properties → Launch Options in Steam.

## Notes on option accuracy

The checklists are grounded in currently-documented Proton/DXVK/gamescope/
MangoHud/engine flags. A few areas -- most notably driver-level FSR4 support
via RADV -- are moving fast enough that exact environment variable names can
shift between Mesa releases; those entries carry a warning icon in the UI
rather than being presented as settled fact. Verify anything marked that way
against current upstream docs for your specific driver version before relying
on it.

## License

Unlicense (public domain), matching the parent gamecmd project.
