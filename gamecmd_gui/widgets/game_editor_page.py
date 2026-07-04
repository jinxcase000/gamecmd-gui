"""
game_editor_page.py

The per-game option builder: organized checklists for every category in
options_catalog.py, a reorderable prefix chain (order matters -- prefix
tokens are nested wrappers, leftmost = outermost), free-form "advanced"
fields for anything not in the catalog, and a live preview of exactly
what gamecmd will run.

Options with a real parameter (frame rate, resolution, a fixed set of
named modes) render a spin button or dropdown instead of freeform text,
built from the option's NumberField/ChoiceField metadata -- see
options_catalog.py.

Any option can declare `requires=<other option id>` (see
options_catalog.py) -- its checkbox is disabled, and forced back off if
it was checked, whenever the option it requires isn't itself checked.
This covers both gamescope's own flags (which only mean anything while
"Wrap in gamescope" is checked -- the command_builder additionally
assembles them into one "gamescope <flags> --" block rather than
placing them loose in the prefix chain) and things like a DLSS render
preset requiring its *_OVERRIDE flag to be on.

Existing profiles are matched against the catalog on open: any option
found in the profile's env_vars/prefix/suffix gets its checkbox
pre-checked with the *actual* value found (see
command_builder.detect_matches). Whatever isn't recognized lands in
"Custom / Advanced" (or, for text found inside a gamescope block, a
dedicated "Extra gamescope flags" field) verbatim, so nothing is lost.
"""

import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from ..command_builder import (SelectedOption, build_fields, detect_matches,  # noqa: E402
                                render_preview, steam_launch_option_line,
                                template_regex)
from ..gtk_util import esc  # noqa: E402
from ..models import Profile, slugify  # noqa: E402
from ..options_catalog import (CATALOG, GAMESCOPE_CATEGORY_ID, GAMESCOPE_MASTER_ID,  # noqa: E402
                                ChoiceField, TextField, find_option)

_KEY_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class _OptionRow:
    __slots__ = ("option", "check", "get_value", "catalog_index", "widgets")

    def __init__(self, option, check, get_value, catalog_index, widgets):
        self.option = option
        self.check = check
        self.get_value = get_value
        self.catalog_index = catalog_index
        self.widgets = widgets  # non-check widgets, for sensitivity toggling


def _parse_initial(opt, initial_value):
    """
    Extract {field: value} from a matched value string using the option's
    template. Matching is case-insensitive (DXVK-NVAPI and friends document
    their setting values as case-insensitive) -- ChoiceField values are
    additionally lowercased so they line up with the ids registered on the
    dropdown (all lowercase in options_catalog.py), while NumberField digits
    are unaffected by case.
    """
    if not initial_value or not opt.input:
        return {}
    regex = template_regex(opt.default, opt.input)
    m = re.match(regex, initial_value, re.IGNORECASE)
    if not m:
        return {}
    result = m.groupdict()
    field_map = {f.name: f for f in opt.input}
    for name, value in list(result.items()):
        field = field_map.get(name)
        if field is not None and hasattr(field, "choices"):
            result[name] = value.lower()
    return result


class GameEditorPage(Adw.NavigationPage):
    def __init__(self, window, profile_key):
        self.is_new = profile_key is None
        super().__init__(title=esc(profile_key or "New Game"))
        self.window = window
        self.original_key = profile_key

        existing = window.games_file.get_profile(profile_key) if profile_key else None

        if existing:
            env_matches, env_leftover, _ = detect_matches(existing.env_vars, "env", CATALOG)
            prefix_matches, prefix_leftover, gamescope_extra = detect_matches(
                existing.prefix, "prefix", CATALOG)
            suffix_matches, suffix_leftover, _ = detect_matches(existing.suffix, "suffix", CATALOG)
        else:
            env_matches, prefix_matches, suffix_matches = [], [], []
            env_leftover = prefix_leftover = suffix_leftover = gamescope_extra = ""

        matched_values = {oid: val for (oid, val, _idx) in
                           env_matches + prefix_matches + suffix_matches}
        initial_prefix_order = [
            oid for (oid, _val, _idx) in sorted(prefix_matches, key=lambda t: t[2])
            if not (find_option(oid) and find_option(oid).group)
        ]

        self.option_rows = {}
        self.prefix_order = list(initial_prefix_order)

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
            description=esc("This key is what you'll type in Steam's launch options: "
                             "gamecmd <key> %command%"),
        )
        self.key_row = Adw.EntryRow(title="Profile key")
        self.key_row.set_text(profile_key or "")
        self.key_row.connect("changed", lambda _e: self._update_preview())
        identity_group.add(self.key_row)
        outer.append(identity_group)

        # --- Catalog categories -----------------------------------------
        catalog_index = 0
        self.gamescope_extra_row = None
        for category in CATALOG:
            group_widget = Adw.PreferencesGroup()
            expander = Adw.ExpanderRow(title=esc(category.title), subtitle=esc(category.subtitle))
            group_widget.add(expander)
            for opt in category.options:
                initial_value = matched_values.get(opt.id)
                row, check, get_value, widgets = self._build_option_row(
                    opt, initial_value=initial_value, checked=opt.id in matched_values)
                expander.add_row(row)
                option_row = _OptionRow(opt, check, get_value, catalog_index, widgets)
                self.option_rows[opt.id] = option_row
                catalog_index += 1
            if category.id == GAMESCOPE_CATEGORY_ID:
                self.gamescope_extra_row = Adw.EntryRow(title="Extra gamescope flags (advanced)")
                self.gamescope_extra_row.set_text(gamescope_extra)
                self.gamescope_extra_row.connect("changed", lambda _e: self._update_preview())
                expander.add_row(self.gamescope_extra_row)
                self.gamescope_extra_row.set_sensitive(
                    bool(self.option_rows[GAMESCOPE_MASTER_ID].check.get_active()))
            outer.append(group_widget)

        # Build the requires-> dependents reverse index, then apply initial
        # sensitivity for every option that depends on another one (covers
        # both the gamescope block and things like a DLSS preset requiring
        # its override flag).
        self._dependents = {}
        for option_id, row in self.option_rows.items():
            if row.option.requires:
                self._dependents.setdefault(row.option.requires, []).append(option_id)
        for option_id, row in self.option_rows.items():
            if row.option.requires:
                self._apply_row_sensitivity(option_id)

        # --- Prefix ordering --------------------------------------------
        self.prefix_order_group = Adw.PreferencesGroup(
            title="Prefix order",
            description=esc("Prefix commands wrap each other left-to-right (leftmost runs "
                             "outermost). Reorder the ones you've enabled above. Gamescope's "
                             "own flags aren't listed here -- they're always assembled "
                             "together right after 'gamescope' automatically."),
        )
        self.prefix_order_listbox = Gtk.ListBox(css_classes=["boxed-list"],
                                                 selection_mode=Gtk.SelectionMode.NONE)
        self.prefix_order_group.add(self.prefix_order_listbox)
        outer.append(self.prefix_order_group)
        self._rebuild_prefix_order_box()

        # --- Advanced / custom -------------------------------------------
        advanced_group = Adw.PreferencesGroup(
            title="Custom / Advanced",
            description=esc("Anything not recognized from the checklists above -- edited "
                             "as raw text and appended after the checked options."),
        )
        self.custom_env_row = Adw.EntryRow(title="Extra env_vars")
        self.custom_prefix_row = Adw.EntryRow(title="Extra prefix")
        self.custom_suffix_row = Adw.EntryRow(title="Extra suffix")
        self.custom_env_row.set_text(env_leftover)
        self.custom_prefix_row.set_text(prefix_leftover)
        self.custom_suffix_row.set_text(suffix_leftover)
        for row in (self.custom_env_row, self.custom_prefix_row, self.custom_suffix_row):
            row.connect("changed", lambda _e: self._update_preview())
            advanced_group.add(row)
        outer.append(advanced_group)

        # --- Live preview -------------------------------------------------
        preview_group = Adw.PreferencesGroup(title="Live preview")

        self.steam_line_row = Adw.ActionRow(title="Steam launch options")
        self.steam_line_label = Gtk.Label(css_classes=["gamecmd-mono", "dim-label"],
                                           selectable=True, xalign=0)
        self.steam_line_row.add_suffix(self.steam_line_label)
        copy_launch_btn = Gtk.Button(icon_name="edit-copy-symbolic",
                                     tooltip_text="Copy", valign=Gtk.Align.CENTER)
        copy_launch_btn.add_css_class("flat")
        copy_launch_btn.connect("clicked", self._on_copy_launch_line)
        self.steam_line_row.add_suffix(copy_launch_btn)
        preview_group.add(self.steam_line_row)

        # A Gtk.Label here (even with wrap + max_width_chars tricks) can end
        # up asking for its full unwrapped width depending on GTK version,
        # which then drags the whole window wider as the resolved command
        # gets longer. A fixed-height, non-horizontally-scrolling TextView
        # doesn't have that failure mode at all: it always wraps to
        # whatever width it's given and never grows the window.
        preview_scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            has_frame=True, margin_top=6,
        )
        preview_scroller.set_size_request(-1, 110)  # roughly 4-5 lines
        self.preview_view = Gtk.TextView(
            editable=False, cursor_visible=False, monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR, hexpand=True,
            left_margin=10, right_margin=10, top_margin=10, bottom_margin=10,
        )
        self.preview_buffer = self.preview_view.get_buffer()
        preview_scroller.set_child(self.preview_view)
        preview_group.add(preview_scroller)

        outer.append(preview_group)

        self._update_preview()

    # -- row construction --------------------------------------------------

    def _build_option_row(self, opt, initial_value=None, checked=False):
        row = Adw.ActionRow(title=esc(opt.label), subtitle=esc(opt.description))

        check = Gtk.CheckButton(valign=Gtk.Align.CENTER, active=checked)
        row.add_prefix(check)
        row.set_activatable_widget(check)
        widgets = []

        if not opt.input:
            value = initial_value if initial_value is not None else opt.default
            entry = Gtk.Entry(text=value, valign=Gtk.Align.CENTER, sensitive=checked,
                               width_chars=12, max_width_chars=40, hexpand=False,
                               css_classes=["gamecmd-mono"], tooltip_text=value)
            entry.connect("changed", self._on_entry_changed)
            row.add_suffix(entry)
            widgets.append(entry)
            get_value = entry.get_text

        elif len(opt.input) == 1 and isinstance(opt.input[0], ChoiceField):
            field = opt.input[0]
            parsed = _parse_initial(opt, initial_value)
            combo = Gtk.ComboBoxText(valign=Gtk.Align.CENTER, sensitive=checked)
            for value_id, label in field.choices:
                combo.append(value_id, label)
            combo.set_active_id(parsed.get(field.name, field.default))
            combo.connect("changed", lambda _c: self._update_preview())
            row.add_suffix(combo)
            widgets.append(combo)
            template = opt.default
            get_value = lambda t=template, fld=field, c=combo: t.format(
                **{fld.name: c.get_active_id() or fld.default})

        elif len(opt.input) == 1 and isinstance(opt.input[0], TextField):
            field = opt.input[0]
            parsed = _parse_initial(opt, initial_value)
            start_text = parsed.get(field.name, field.default)
            entry = Gtk.Entry(text=start_text, valign=Gtk.Align.CENTER, sensitive=checked,
                               width_chars=12, max_width_chars=40, hexpand=False,
                               css_classes=["gamecmd-mono"], tooltip_text=start_text)
            entry.connect("changed", self._on_entry_changed)
            row.add_suffix(entry)
            widgets.append(entry)
            template = opt.default
            get_value = lambda t=template, fld=field, e=entry: t.format(
                **{fld.name: e.get_text() or fld.default})

        else:
            # Keep this compact no matter how many fields: a wide, unbounded
            # suffix box here can force the row's title/subtitle column down
            # to near-zero width, which makes GTK wrap that text into a
            # single vertical column of one letter per line. Each spin
            # button gets a small fixed width_chars regardless of its max
            # value, and multi-field labels are single letters (the row's
            # own description already spells out what each one means).
            parsed = _parse_initial(opt, initial_value)
            spin_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                                valign=Gtk.Align.CENTER)
            spins = {}
            for nf in opt.input:
                if len(opt.input) > 1:
                    spin_box.append(Gtk.Label(label=esc(nf.label), css_classes=["dim-label"]))
                start_value = int(parsed[nf.name]) if nf.name in parsed else nf.default
                adjustment = Gtk.Adjustment(value=start_value, lower=nf.min, upper=nf.max,
                                            step_increment=nf.step)
                spin = Gtk.SpinButton(adjustment=adjustment, valign=Gtk.Align.CENTER,
                                      sensitive=checked, numeric=True,
                                      width_chars=5, max_width_chars=5, hexpand=False)
                spin.connect("value-changed", lambda _s: self._update_preview())
                spin_box.append(spin)
                spins[nf.name] = spin
                widgets.append(spin)
            row.add_suffix(spin_box)
            template = opt.default
            get_value = lambda t=template, sp=spins: t.format(
                **{name: int(s.get_value()) for name, s in sp.items()})

        if opt.warning:
            warn_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            warn_icon.set_tooltip_text(opt.warning)
            warn_icon.add_css_class("warning")
            row.add_suffix(warn_icon)

        check.connect("toggled", self._on_option_toggled, opt, widgets)

        return row, check, get_value, widgets

    def _on_entry_changed(self, entry):
        entry.set_tooltip_text(entry.get_text())
        self._update_preview()

    # -- prefix ordering / requires-> dependency gating ------------------

    def _on_option_toggled(self, check, opt, widgets):
        self._apply_row_sensitivity(opt.id)

        if opt.target == "prefix" and not opt.group:
            if check.get_active():
                if opt.id not in self.prefix_order:
                    self.prefix_order.append(opt.id)
            else:
                if opt.id in self.prefix_order:
                    self.prefix_order.remove(opt.id)
            self._rebuild_prefix_order_box()

        # Anything that requires this option needs its sensitivity (and,
        # if the requirement just went away, its checked state) re-evaluated.
        for dependent_id in self._dependents.get(opt.id, ()):
            self._apply_row_sensitivity(dependent_id)

        if opt.id == GAMESCOPE_MASTER_ID and self.gamescope_extra_row is not None:
            self.gamescope_extra_row.set_sensitive(check.get_active())

        self._update_preview()

    def _apply_row_sensitivity(self, option_id):
        """
        Enforces `requires`: a dependent option's checkbox is disabled (and,
        if it was checked, forced back off) whenever the option it requires
        isn't itself checked -- so an inert value can never silently end up
        in the built command just because its checkbox still shows "on".
        """
        row = self.option_rows[option_id]
        opt = row.option
        gate = True
        if opt.requires:
            required_row = self.option_rows.get(opt.requires)
            gate = bool(required_row and required_row.check.get_active())
            row.check.set_sensitive(gate)
            if not gate and row.check.get_active():
                row.check.set_active(False)  # re-enters here via "toggled"; gate stays False, so it stops
        active = row.check.get_active()
        for w in row.widgets:
            w.set_sensitive(active and gate)

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
            hbox.append(Gtk.Label(label=esc(opt.label), use_markup=True, hexpand=True, xalign=0))
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
            value = row.get_value()
            if opt.target == "prefix" and not opt.group:
                order = (self.prefix_order.index(option_id)
                         if option_id in self.prefix_order else 9999)
            else:
                order = row.catalog_index
            selected.append(SelectedOption(option_id=option_id, target=opt.target,
                                            enabled=enabled, value=value, order=order,
                                            group=opt.group))
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
            gamescope_extra=self.gamescope_extra_row.get_text() if self.gamescope_extra_row else "",
        )

    def _update_preview(self):
        env_vars, prefix, suffix = self._build_fields()
        key = self._current_key() or "<profile>"
        self.steam_line_label.set_label(steam_launch_option_line(key))
        preview = render_preview(env_vars, prefix, suffix,
                                  game_cmd="/path/to/game_binary")
        self.preview_buffer.set_text(preview)

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
