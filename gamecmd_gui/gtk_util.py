"""
gtk_util.py

Small shared helpers for the GTK layer.

Adw.ActionRow/ExpanderRow/PreferencesGroup/StatusPage titles and
subtitles are rendered as Pango markup, not plain text. Any of our own
strings containing "<", ">", or "&" (env var placeholders like
<appid>, or titles like "GameMode & Performance Wrappers") would
otherwise silently fail to display -- GTK logs a markup parse warning
and leaves the label blank rather than falling back to plain text.
Every dynamic string handed to one of those widgets must go through esc().
"""

from gi.repository import GLib

MONOSPACE_CSS = b"""
.gamecmd-mono {
    font-family: monospace;
    font-size: 0.9em;
}
"""


def esc(text) -> str:
    return GLib.markup_escape_text(text or "")
