"""
models.py

Reads and writes the exact same ~/.config/gamecmd/games.yaml file that
the gamecmd bash script reads. Uses ruamel.yaml's round-trip mode so
hand-written comments and formatting survive edits made through the GUI.

Schema (unchanged from upstream gamecmd -- this GUI never adds extra
keys, so the file stays fully compatible with the plain script):

    <profile_key>:
      env_vars: "..."   # optional
      prefix: "..."     # optional
      suffix: "..."     # optional
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

DEFAULT_YAML_PATH = Path.home() / ".config" / "gamecmd" / "games.yaml"

HEADER_COMMENT = (
    "# gamecmd game profiles\n"
    "# Each profile has three optional fields:\n"
    "#   env_vars: environment variables set before launch\n"
    "#   prefix:   commands that run before the game executable\n"
    "#   suffix:   arguments passed after the game executable\n"
)

_FIELDS = ("env_vars", "prefix", "suffix")


def slugify(name: str) -> str:
    """Turn a display name like 'Half-Life 2' into a safe yaml key 'half_life_2'."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "game"


@dataclass
class Profile:
    key: str
    env_vars: str = ""
    prefix: str = ""
    suffix: str = ""

    def is_empty(self) -> bool:
        return not (self.env_vars or self.prefix or self.suffix)


class GamesFile:
    """Loads / saves the gamecmd games.yaml file."""

    def __init__(self, path: Path = None):
        self.path = path or DEFAULT_YAML_PATH
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.width = 4096  # avoid line-wrapping long env_vars strings
        self.yaml.indent(mapping=2, sequence=2, offset=0)
        self._data = CommentedMap()
        self._had_file = False
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            self._had_file = True
            with self.path.open("r") as f:
                data = self.yaml.load(f)
            self._data = data if isinstance(data, CommentedMap) else (data or CommentedMap())
        else:
            self._had_file = False
            self._data = CommentedMap()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w") as f:
            if not self._had_file:
                f.write(HEADER_COMMENT + "\n")
            self.yaml.dump(self._data, f)
        tmp.replace(self.path)
        self._had_file = True

    def list_profiles(self) -> list:
        profiles = []
        for key, val in (self._data or {}).items():
            val = val or {}
            profiles.append(Profile(
                key=str(key),
                env_vars=str(val.get("env_vars", "") or ""),
                prefix=str(val.get("prefix", "") or ""),
                suffix=str(val.get("suffix", "") or ""),
            ))
        return sorted(profiles, key=lambda p: p.key.lower())

    def get_profile(self, key: str):
        if key not in (self._data or {}):
            return None
        val = self._data[key] or {}
        return Profile(
            key=key,
            env_vars=str(val.get("env_vars", "") or ""),
            prefix=str(val.get("prefix", "") or ""),
            suffix=str(val.get("suffix", "") or ""),
        )

    def key_exists(self, key: str) -> bool:
        return key in (self._data or {})

    def upsert_profile(self, profile: Profile) -> None:
        entry = self._data.get(profile.key)
        if not isinstance(entry, CommentedMap):
            entry = CommentedMap()
        for f in _FIELDS:
            value = getattr(profile, f)
            if value:
                entry[f] = value
            elif f in entry:
                del entry[f]
        self._data[profile.key] = entry

    def rename_profile(self, old_key: str, new_key: str) -> None:
        if old_key == new_key or old_key not in self._data:
            return
        entry = self._data.pop(old_key)
        self._data[new_key] = entry

    def delete_profile(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
