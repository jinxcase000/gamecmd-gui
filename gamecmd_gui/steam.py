"""
steam.py

Finds installed Steam games by reading Steam's own on-disk metadata --
no Steam Web API key or network access required, since gamecmd only
cares about locally installed titles.

Looks in every known Steam install location (native, .steam symlink,
Flatpak) and every library folder registered in libraryfolders.vdf,
then parses each steamapps/appmanifest_*.acf for appid/name/installdir.
"""

from dataclasses import dataclass
from pathlib import Path

from .vdf import parse_vdf

STEAM_ROOT_CANDIDATES = [
    Path.home() / ".local/share/Steam",
    Path.home() / ".steam/steam",
    Path.home() / ".steam/root",
    Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
]

# Non-game housekeeping "apps" Steam installs as regular appmanifests.
# Filtered out of the import list by name prefix (case-insensitive).
NON_GAME_NAME_PREFIXES = (
    "steamworks common redistributables",
    "steam linux runtime",
    "proton ",
    "steamvr",
)


@dataclass
class SteamGame:
    appid: str
    name: str
    installdir: str
    library_path: str


def find_steam_roots() -> list:
    return [p for p in STEAM_ROOT_CANDIDATES if (p / "steamapps").is_dir()]


def find_library_folders(steam_root: Path) -> list:
    """A Steam root always includes its own steamapps/, plus whatever
    additional library folders are registered in libraryfolders.vdf."""
    libs = [steam_root]
    lf = steam_root / "steamapps" / "libraryfolders.vdf"
    if lf.is_file():
        try:
            data = parse_vdf(lf.read_text(errors="ignore"))
            folders = data.get("libraryfolders", {})
            if isinstance(folders, dict):
                for _, val in folders.items():
                    if isinstance(val, dict) and "path" in val:
                        p = Path(val["path"])
                        if p not in libs and (p / "steamapps").is_dir():
                            libs.append(p)
        except Exception:
            pass
    return libs


def _is_real_game(name: str) -> bool:
    lowered = name.strip().lower()
    return not any(lowered.startswith(prefix) for prefix in NON_GAME_NAME_PREFIXES)


def scan_installed_games() -> list:
    """Returns installed Steam games across all detected libraries, sorted by name."""
    games: dict = {}
    for root in find_steam_roots():
        for lib in find_library_folders(root):
            steamapps = lib / "steamapps"
            if not steamapps.is_dir():
                continue
            for manifest in steamapps.glob("appmanifest_*.acf"):
                try:
                    data = parse_vdf(manifest.read_text(errors="ignore"))
                    state = data.get("AppState", {})
                    if not isinstance(state, dict):
                        continue
                    appid = state.get("appid")
                    name = state.get("name")
                    installdir = state.get("installdir", "")
                    if not appid or not name:
                        continue
                    if not _is_real_game(name):
                        continue
                    games[appid] = SteamGame(
                        appid=appid, name=name, installdir=installdir,
                        library_path=str(lib),
                    )
                except Exception:
                    continue
    return sorted(games.values(), key=lambda g: g.name.lower())
