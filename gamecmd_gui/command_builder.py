"""
command_builder.py

Turns a set of selected catalog options + custom freeform text into the
three strings gamecmd's games.yaml expects (env_vars, prefix, suffix),
and renders a live preview of exactly what gamecmd will execute --
mirroring the real script's `eval env $ENV_STRING $PREFIX_CMD "$@" $SUFFIX_ARGS`.

Gamescope is a special case: its own flags must sit between the literal
"gamescope" token and a closing "--", so options tagged
group="gamescope_block" (see options_catalog.py) never get concatenated
loose into the prefix chain -- they're assembled into one atomic
"gamescope <flags...> --" block wherever the gamescope_enable option
sits in the overall prefix order.
"""

import re
from dataclasses import dataclass

from .options_catalog import (GAMESCOPE_BLOCK_GROUP, GAMESCOPE_CATEGORY_ID,
                               GAMESCOPE_MASTER_ID)


@dataclass
class SelectedOption:
    """One catalog option as currently configured in the editor."""
    option_id: str
    target: str          # "env" | "prefix" | "suffix"
    enabled: bool
    value: str            # current, fully-resolved text (already template-formatted)
    order: int = 0         # position within its target list (for prefix/suffix ordering)
    group: str = ""        # "" or "gamescope_block"


# ---------------------------------------------------------------------------
# Forward direction: build the final strings from selected options
# ---------------------------------------------------------------------------

def join_field(selected: list, target: str, custom_extra: str = "") -> str:
    """Join all enabled, ungrouped options for one target, in order, plus custom text."""
    items = [s for s in selected if s.target == target and s.enabled and not s.group]
    items.sort(key=lambda s: s.order)
    parts = [s.value.strip() for s in items if s.value.strip()]
    if custom_extra and custom_extra.strip():
        parts.append(custom_extra.strip())
    return " ".join(parts)


def join_prefix_field(selected: list, custom_extra: str = "", gamescope_extra: str = "") -> str:
    """
    Like join_field, but for "prefix": any option in the gamescope block group
    is folded into a single "gamescope <flags...> --" segment positioned at
    gamescope_enable's slot, rather than being concatenated independently.
    If gamescope_enable itself isn't checked, block members are ignored
    entirely (they have no effect without the wrapper).
    """
    ungrouped = [s for s in selected if s.target == "prefix" and not s.group]
    block_members = [s for s in selected
                      if s.target == "prefix" and s.group == GAMESCOPE_BLOCK_GROUP]

    ungrouped.sort(key=lambda s: s.order)
    block_members.sort(key=lambda s: s.order)

    parts = []
    for s in ungrouped:
        if not s.enabled:
            continue
        if s.option_id == GAMESCOPE_MASTER_ID:
            flag_values = [b.value.strip() for b in block_members if b.enabled and b.value.strip()]
            if gamescope_extra and gamescope_extra.strip():
                flag_values.append(gamescope_extra.strip())
            block = "gamescope" + (" " + " ".join(flag_values) if flag_values else "") + " --"
            parts.append(block)
        elif s.value.strip():
            parts.append(s.value.strip())

    if custom_extra and custom_extra.strip():
        parts.append(custom_extra.strip())
    return " ".join(parts)


def build_fields(selected: list, custom_env: str = "", custom_prefix: str = "",
                  custom_suffix: str = "", gamescope_extra: str = "") -> tuple:
    """Returns (env_vars, prefix, suffix) strings ready to write to games.yaml."""
    env_vars = join_field(selected, "env", custom_env)
    prefix = join_prefix_field(selected, custom_prefix, gamescope_extra)
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


# ---------------------------------------------------------------------------
# Reverse direction: recognize catalog options inside an existing profile
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def template_regex(template: str, input_fields: tuple) -> str:
    """
    Turns an option's `default` (a literal, or a str.format() template when
    `input` is set) into a regex that matches that option's value wherever
    it appears in a larger string, on whitespace boundaries.

    Field kinds are told apart by duck-typing rather than isinstance, so
    this stays agnostic to the actual dataclasses in options_catalog.py:
      - has `choices` -> ChoiceField: alternation of the fixed values
      - has `min`     -> NumberField: digits only
      - otherwise     -> TextField: any run of non-whitespace, so a path or
                         connector name round-trips even when the user has
                         edited it away from the default
    """
    field_map = {f.name: f for f in input_fields}
    pattern_parts = []
    pos = 0
    for m in _PLACEHOLDER_RE.finditer(template):
        pattern_parts.append(re.escape(template[pos:m.start()]))
        name = m.group(1)
        f = field_map.get(name)
        if f is not None and hasattr(f, "choices"):
            alts = "|".join(re.escape(c[0]) for c in f.choices)
            pattern_parts.append(f"(?P<{name}>{alts})")
        elif f is not None and hasattr(f, "min"):
            pattern_parts.append(f"(?P<{name}>\\d+)")
        else:
            pattern_parts.append(f"(?P<{name}>\\S+)")
        pos = m.end()
    pattern_parts.append(re.escape(template[pos:]))
    return r"(?<!\S)" + "".join(pattern_parts) + r"(?!\S)"


def _span_match(field_value: str, options: list) -> tuple:
    """
    Conservative substring matcher used for "prefix"/"suffix" fields: tries
    each option's template_regex against the whole string, claiming the
    first non-overlapping match found. Returns (matches, leftover) where
    matches is a list of (option_id, matched_text, start_index) and leftover
    is whatever text no option claimed (whitespace-normalized).
    """
    claimed = []  # list of (start, end)

    def overlaps(a_start, a_end):
        return any(not (a_end <= b_start or a_start >= b_end) for b_start, b_end in claimed)

    matches = []
    for opt in options:
        regex = template_regex(opt.default, opt.input)
        for m in re.finditer(regex, field_value, re.IGNORECASE):
            if not overlaps(m.start(), m.end()):
                claimed.append((m.start(), m.end()))
                matches.append((opt.id, m.group(0), m.start()))
                break

    claimed.sort()
    leftover_chars = []
    pos = 0
    for start, end in claimed:
        leftover_chars.append(field_value[pos:start])
        pos = end
    leftover_chars.append(field_value[pos:])
    leftover = " ".join("".join(leftover_chars).split())
    return matches, leftover


def _env_match(field_value: str, options: list) -> tuple:
    """
    KEY-anchored matcher for "env" fields: matches by the KEY portion(s)
    before '=' so an edited value (DXVK_HUD=full vs. the catalog default
    DXVK_HUD=fps) is still recognized, with its actual current value
    preserved. Options with multiple KEY=VALUE tokens in their template
    (e.g. the FSR4 pair) require every key to be present.
    """
    tokens = field_value.split()
    claimed = [False] * len(tokens)
    matches = []
    for opt in options:
        keys_needed = [part.split("=", 1)[0] for part in opt.default.split() if "=" in part]
        if not keys_needed:
            continue
        found_indices, found_values, ok = [], [], True
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
    leftover = " ".join(tok for tok, c in zip(tokens, claimed) if not c)
    return matches, leftover


_GAMESCOPE_SPAN_RE = re.compile(r"(?<!\S)gamescope\b(.*?)(?<!\S)--(?!\S)", re.DOTALL)


def detect_matches(field_value: str, target: str, catalog: list) -> tuple:
    """
    Reverse-match a raw games.yaml field (env_vars/prefix/suffix) against the
    options catalog, so an existing profile lights up the checkboxes it
    already matches instead of dumping everything into "Custom / Advanced".

    Returns (matches, leftover, gamescope_extra):
      matches         -- list of (option_id, matched_value_string, start_index)
      leftover        -- remaining text no option claimed, space-joined
      gamescope_extra -- (prefix only) text found *inside* a gamescope ... --
                          span that no gamescope option claimed -- kept
                          separate so it isn't misplaced outside the block
    """
    field_value = field_value or ""

    if target == "env":
        options = [opt for cat in catalog for opt in cat.options if opt.target == "env"]
        matches, leftover = _env_match(field_value, options)
        return matches, leftover, ""

    if target == "suffix":
        options = [opt for cat in catalog for opt in cat.options if opt.target == "suffix"]
        matches, leftover = _span_match(field_value, options)
        return matches, leftover, ""

    # target == "prefix"
    gamescope_opts = [opt for opt in
                       next((c.options for c in catalog if c.id == GAMESCOPE_CATEGORY_ID), ())
                       if opt.target == "prefix" and opt.id != GAMESCOPE_MASTER_ID]
    other_opts = [opt for cat in catalog for opt in cat.options
                  if opt.target == "prefix" and cat.id != GAMESCOPE_CATEGORY_ID]

    span = _GAMESCOPE_SPAN_RE.search(field_value)
    matches = []
    gamescope_extra = ""
    outer_value = field_value
    if span:
        inner = span.group(1)
        matches.append((GAMESCOPE_MASTER_ID, "gamescope", span.start()))
        sub_matches, gamescope_extra = _span_match(inner, gamescope_opts)
        matches.extend(sub_matches)
        outer_value = field_value[:span.start()] + " " + field_value[span.end():]

    other_matches, other_leftover = _span_match(outer_value, other_opts)
    matches.extend(other_matches)
    return matches, other_leftover, gamescope_extra
