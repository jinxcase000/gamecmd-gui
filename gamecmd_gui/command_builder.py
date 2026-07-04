"""
command_builder.py

Turns a set of selected catalog options + custom freeform text into the
three strings gamecmd's games.yaml expects (env_vars, prefix, suffix),
and renders a live preview of exactly what gamecmd will execute --
mirroring the real script's `eval env $ENV_STRING $PREFIX_CMD "$@" $SUFFIX_ARGS`.
"""

from dataclasses import dataclass, field


@dataclass
class SelectedOption:
    """One catalog option as currently configured in the editor."""
    option_id: str
    target: str          # "env" | "prefix" | "suffix"
    enabled: bool
    value: str            # current (possibly user-edited) text
    order: int = 0         # position within its target list (for prefix/suffix ordering)


def join_field(selected: list, target: str, custom_extra: str = "") -> str:
    """Join all enabled options for one target, in order, plus any custom text."""
    items = [s for s in selected if s.target == target and s.enabled]
    items.sort(key=lambda s: s.order)
    parts = [s.value.strip() for s in items if s.value.strip()]
    if custom_extra and custom_extra.strip():
        parts.append(custom_extra.strip())
    return " ".join(parts)


def build_fields(selected: list, custom_env: str = "", custom_prefix: str = "",
                  custom_suffix: str = "") -> tuple:
    """Returns (env_vars, prefix, suffix) strings ready to write to games.yaml."""
    env_vars = join_field(selected, "env", custom_env)
    prefix = join_field(selected, "prefix", custom_prefix)
    suffix = join_field(selected, "suffix", custom_suffix)
    return env_vars, prefix, suffix


def render_preview(env_vars: str, prefix: str, suffix: str,
                    game_cmd: str = "/path/to/game_binary") -> str:
    """
    Renders the actual command gamecmd will eval, e.g.:
        env DXVK_ASYNC=1 mangohud gamemoderun /path/to/game_binary -novid
    Mirrors gamecmd's own GAMECMD_DEBUG=1 output logic.
    """
    parts = ["env"]
    if env_vars:
        parts.append(env_vars)
    if prefix:
        parts.append(prefix)
    parts.append(game_cmd)
    if suffix:
        parts.append(suffix)
    return " ".join(p for p in parts if p)


def render_debug_lines(env_vars: str, prefix: str, suffix: str) -> str:
    """Mirrors the exact three lines gamecmd prints under GAMECMD_DEBUG=1."""
    return (
        f"ENV: {env_vars}\n"
        f"PREFIX: {prefix}\n"
        f"SUFFIX: {suffix}"
    )


def steam_launch_option_line(profile_key: str) -> str:
    return f"gamecmd {profile_key} %command%"
