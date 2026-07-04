"""
game_editor_page.py

The per-game option builder: organized checklists for every category in
options_catalog.py, a reorderable prefix chain (order matters -- prefix
tokens are nested wrappers, leftmost = outermost), free-form "advanced"
fields for anything not in the catalog, and a live preview of exactly
what gamecmd will run.

Existing profiles are edited non-destructively: whatever env_vars /
prefix / suffix a profile already has is loaded verbatim into the
"Custom / Advanced" fields (never silently reverse-engineered into
checkbox guesses), so nothing you already tuned by hand can be lost or
misinterpreted. The checklists are there to layer additional, well-known
options on top.
"""

import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from ..command_builder import (SelectedOption, build_fields, render_preview,  # noqa: E402
                                steam_launch_option_line)
from ..models import Profile, slugify  # noqa: E402
from ..options_catalog import CATALOG, find_option  # noqa: E402

_KEY_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class _OptionRow:
    __slots__ = ("option", "check", "entry", "catalog_index")

    def __init__(self, option, check, entry, catalog_index):
        self.option = option
        self.check = check
        self.entry = entry
        self.catalog_index = catalog_index


class GameEditorPage(Adw.NavigationPage):
    def __init__(self, window, profile_key):
        self.is_new = profile_key is None
        super().__init__(title=profile_key or "New Game")
        self.window = window
        self.original_key = profile_key

        existing = window.games_file.get_profile(profile_key) if profile_key else None

        self.option_rows = {}
        self.prefix_order = []

        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        save_button = Gtk.Button(label="Save")
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", self._on_save_clicked)
        header.pack_end(save_button)

        self.toast_overlay = Adw.ToastOverlay()
        toolbar_view.set_content(self.toast_overlay)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.toast_overlay.set_child(scroller)

        clamp = Adw.Clamp(maximum_size=760, tightening_threshold=560)
        scroller.set_child(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                         margin_top=24, margin_bottom=32, margin_start=12, margin_end=12)
        clamp.set_child(outer)

        # --- Profile identity -----------------------------------------
        identity_group = Adw.PreferencesGroup(
            title="Profile",
            description="This key is what you'll type in Steam's launch options: "
                         "gamecmd <key> %command%",
        )
        self.key_row = Adw.EntryRow(title="Profile key")
        self.key_row.set_text(profile_key or "")
        self.key_row.connect("changed", lambda _e: self._update_preview())
        identity_group.add(self.key_row)
        outer.append(identity_group)

        # --- Catalog categories -----------------------------------------
        catalog_index = 0
        for category in CATALOG:
            group = Adw.PreferencesGroup()
            expander = Adw.ExpanderRow(title=category.title, subtitle=category.subtitle)
            group.add(expander)
            for opt in category.options:
                row, check, entry = self._build_option_row(opt)
                expander.add_row(row)
                self.option_rows[opt.id] = _OptionRow(opt, check, entry, catalog_index)
                catalog_index += 1
            outer.append(group)

        # --- Prefix ordering --------------------------------------------
        self.prefix_order_group = Adw.PreferencesGroup(
            title="Prefix order",
            description="Prefix commands wrap each other left-to-right (leftmost runs "
                         "outermost). Reorder the ones you've enabled above.",
        )
        self.prefix_order_listbox = Gtk.ListBox(css_classes=["boxed-list"],
                                                 selection_mode=Gtk.SelectionMode.NONE)
        self.prefix_order_group.add(self.prefix_order_listbox)
        outer.append(self.prefix_order_group)

        # --- Advanced / custom -------------------------------------------
        advanced_group = Adw.PreferencesGroup(
            title="Custom / Advanced",
            description="Anything already in this profile, or anything not covered by "
                         "the checklists above -- edited as raw text and appended after "
                         "the checked options.",
        )
        self.custom_env_row = Adw.EntryRow(title="Extra env_vars")
        self.custom_prefix_row = Adw.EntryRow(title="Extra prefix")
        self.custom_suffix_row = Adw.EntryRow(title="Extra suffix")
        if existing:
            self.custom_env_row.set_text(existing.env_vars)
            self.custom_prefix_row.set_text(existing.prefix)
            self.custom_suffix_row.set_text(existing.suffix)
        for row in (self.custom_env_row, self.custom_prefix_row, self.custom_suffix_row):
            row.connect("changed", lambda _e: self._update_preview())
            advanced_group.add(row)
        outer.append(advanced_group)

        # --- Live preview -------------------------------------------------
        preview_group = Adw.PreferencesGroup(title="Live preview")

        self.steam_line_row = Adw.ActionRow(title="Steam launch options")
        self.steam_line_label = Gtk.Label(css_classes=["monospace", "dim-label"],
                                           selectable=True, xalign=0)
        self.steam_line_row.add_suffix(self.steam_line_label)
        copy_launch_btn = Gtk.Button(icon_name="edit-copy-symbolic",
                                     tooltip_text="Copy", valign=Gtk.Align.CENTER)
        copy_launch_btn.add_css_class("flat")
        copy_launch_btn.connect("clicked", self._on_copy_launch_line)
        self.steam_line_row.add_suffix(copy_launch_btn)
        preview_group.add(self.steam_line_row)

        preview_frame = Gtk.Frame(margin_top=6)
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                               margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
        self.preview_label = Gtk.Label(css_classes=["monospace"], selectable=True,
                                        wrap=True, xalign=0, justify=Gtk.Justification.LEFT)
        preview_box.append(self.preview_label)
        preview_frame.set_child(preview_box)
        preview_group.add(preview_frame)

        outer.append(preview_group)

        self._update_preview()

    # -- row construction --------------------------------------------------

    def _build_option_row(self, opt):
        row = Adw.ActionRow(title=opt.label, subtitle=opt.description)

        check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
        row.add_prefix(check)
        row.set_activatable_widget(check)

        entry = Gtk.Entry(text=opt.default, valign=Gtk.Align.CENTER, sensitive=False,
                           width_chars=28, hexpand=False)
        row.add_suffix(entry)

        if opt.warning:
            warn_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            warn_icon.set_tooltip_text(opt.warning)
            warn_icon.add_css_class("warning")
            row.add_suffix(warn_icon)

        check.connect("toggled", self._on_option_toggled, opt, entry)
        entry.connect("changed", lambda _e: self._update_preview())

        return row, check, entry

    # -- prefix ordering -----------------------------------------------

    def _on_option_toggled(self, check, opt, entry):
        entry.set_sensitive(check.get_active())
        if opt.target == "prefix":
            if check.get_active():
                if opt.id not in self.prefix_order:
                    self.prefix_order.append(opt.id)
            else:
                if opt.id in self.prefix_order:
                    self.prefix_order.remove(opt.id)
            self._rebuild_prefix_order_box()
        self._update_preview()

    def _rebuild_prefix_order_box(self):
        while True:
            row = self.prefix_order_listbox.get_row_at_index(0)
            if row is None:
                break
            self.prefix_order_listbox.remove(row)

        for opt_id in self.prefix_order:
            opt = find_option(opt_id)
            list_row = Gtk.ListBoxRow(activatable=False)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                            margin_top=6, margin_bottom=6, margin_start=10, margin_end=10)
            hbox.append(Gtk.Label(label=opt.label, hexpand=True, xalign=0))
            up_btn = Gtk.Button(icon_name="go-up-symbolic", valign=Gtk.Align.CENTER)
            up_btn.add_css_class("flat")
            up_btn.connect("clicked", self._move_prefix, opt_id, -1)
            down_btn = Gtk.Button(icon_name="go-down-symbolic", valign=Gtk.Align.CENTER)
            down_btn.add_css_class("flat")
            down_btn.connect("clicked", self._move_prefix, opt_id, 1)
            hbox.append(up_btn)
            hbox.append(down_btn)
            list_row.set_child(hbox)
            self.prefix_order_listbox.append(list_row)

    def _move_prefix(self, _button, opt_id, direction):
        idx = self.prefix_order.index(opt_id)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.prefix_order):
            self.prefix_order[idx], self.prefix_order[new_idx] = (
                self.prefix_order[new_idx], self.prefix_order[idx],
            )
            self._rebuild_prefix_order_box()
            self._update_preview()

    # -- preview -------------------------------------------------------

    def _gather_selected(self):
        selected = []
        for option_id, row in self.option_rows.items():
            opt = row.option
            enabled = row.check.get_active()
            value = row.entry.get_text()
            if opt.target == "prefix":
                order = (self.prefix_order.index(option_id)
                         if option_id in self.prefix_order else 9999)
            else:
                order = row.catalog_index
            selected.append(SelectedOption(option_id=option_id, target=opt.target,
                                            enabled=enabled, value=value, order=order))
        return selected

    def _current_key(self) -> str:
        return self.key_row.get_text().strip()

    def _build_fields(self):
        selected = self._gather_selected()
        return build_fields(
            selected,
            custom_env=self.custom_env_row.get_text(),
            custom_prefix=self.custom_prefix_row.get_text(),
            custom_suffix=self.custom_suffix_row.get_text(),
        )

    def _update_preview(self):
        env_vars, prefix, suffix = self._build_fields()
        key = self._current_key() or "<profile>"
        self.steam_line_label.set_label(steam_launch_option_line(key))
        preview = render_preview(env_vars, prefix, suffix,
                                  game_cmd="/path/to/game_binary")
        self.preview_label.set_label(preview)

    def _on_copy_launch_line(self, _button):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.steam_line_label.get_label())
        self.toast_overlay.add_toast(Adw.Toast(title="Copied launch option", timeout=2))

    # -- save ------------------------------------------------------------

    def _on_save_clicked(self, _button):
        key = self._current_key()
        if not key:
            self.toast_overlay.add_toast(Adw.Toast(title="Give this profile a key first", timeout=3))
            return
        if not _KEY_RE.match(key):
            suggestion = slugify(key)
            self.toast_overlay.add_toast(Adw.Toast(
                title=f"Key can only contain letters, numbers, _ and - (try “{suggestion}”)",
                timeout=4))
            return

        games_file = self.window.games_file
        key_changed = key != self.original_key
        if key_changed and games_file.key_exists(key):
            self.toast_overlay.add_toast(Adw.Toast(title=f"“{key}” already exists", timeout=3))
            return

        env_vars, prefix, suffix = self._build_fields()
        profile = Profile(key=key, env_vars=env_vars, prefix=prefix, suffix=suffix)

        if self.original_key and key_changed:
            games_file.rename_profile(self.original_key, key)
        games_file.upsert_profile(profile)
        games_file.save()

        self.window.close_editor(saved=True, key=key)
