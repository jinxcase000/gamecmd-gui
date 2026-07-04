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


def detect_matches(field_value: str, target: str, catalog: list) -> tuple:
    """
    Reverse-match a raw games.yaml field (env_vars/prefix/suffix) against the
    options catalog, so an existing profile lights up the checkboxes it
    already matches instead of dumping everything into "Custom / Advanced".

    Matching is conservative on purpose: for "env" options it matches by
    KEY (before the '='), so an edited value (e.g. DXVK_HUD=full instead of
    the catalog default DXVK_HUD=fps) is still detected and its *actual*
    value is preserved. For "prefix"/"suffix" it requires an exact,
    contiguous run of tokens matching the catalog default -- if you edited
    a multi-token default (e.g. changed the numbers in a resolution flag),
    it simply won't auto-check that one and the raw tokens fall through to
    the leftover text instead. Nothing is ever guessed incorrectly; unmatched
    tokens are always preserved verbatim.

    Returns (matches, leftover) where:
      matches  -- list of (option_id, matched_value_string, start_token_index)
      leftover -- remaining tokens (whatever no option claimed), space-joined
    """
    tokens = (field_value or "").split()
    claimed = [False] * len(tokens)
    matches = []

    options = [opt for cat in catalog for opt in cat.options if opt.target == target]

    if target == "env":
        for opt in options:
            keys_needed = [part.split("=", 1)[0] for part in opt.default.split() if "=" in part]
            if not keys_needed:
                continue
            found_indices = []
            found_values = []
            ok = True
            for key in keys_needed:
                idx = next((i for i, tok in enumerate(tokens)
                            if not claimed[i] and tok.split("=", 1)[0] == key), None)
                if idx is None:
                    ok = False
                    break
                found_indices.append(idx)
                found_values.append(tokens[idx])
            if ok:
                for i in found_indices:
                    claimed[i] = True
                matches.append((opt.id, " ".join(found_values), min(found_indices)))
    else:
        for opt in options:
            needle = opt.default.split()
            n = len(needle)
            if n == 0:
                continue
            for i in range(len(tokens) - n + 1):
                if all(not claimed[i + j] for j in range(n)) and \
                        all(tokens[i + j] == needle[j] for j in range(n)):
                    for j in range(n):
                        claimed[i + j] = True
                    matches.append((opt.id, " ".join(needle), i))
                    break

    leftover = " ".join(tok for tok, c in zip(tokens, claimed) if not c)
    return matches, leftover
