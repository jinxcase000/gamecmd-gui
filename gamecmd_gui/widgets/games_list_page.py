"""
games_list_page.py

The main "Games" page: every profile currently defined in games.yaml,
with Add / Import-from-Steam / Edit / Delete / Copy-launch-option actions.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GObject, Gtk  # noqa: E402

from ..command_builder import steam_launch_option_line  # noqa: E402
from ..gtk_util import esc  # noqa: E402


def _summarize(profile) -> str:
    bits = []
    if profile.env_vars:
        bits.append(f"env: {profile.env_vars}")
    if profile.prefix:
        bits.append(f"prefix: {profile.prefix}")
    if profile.suffix:
        bits.append(f"suffix: {profile.suffix}")
    return "  •  ".join(bits) if bits else "No options set yet"


class GamesListPage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title="gamecmd GUI")
        self.window = window

        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        add_button = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add a game manually")
        add_button.connect("clicked", self._on_add_clicked)
        header.pack_start(add_button)

        import_button = Gtk.Button(label="Import from Steam")
        import_button.add_css_class("suggested-action")
        import_button.connect("clicked", self._on_import_clicked)
        header.pack_end(import_button)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Filter games…")
        self.search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self.search_entry)

        self.toast_overlay = Adw.ToastOverlay()
        toolbar_view.set_content(self.toast_overlay)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        self.toast_overlay.set_child(scroller)

        clamp = Adw.Clamp(maximum_size=760, tightening_threshold=560)
        scroller.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                       margin_top=24, margin_bottom=24, margin_start=12, margin_end=12)
        clamp.set_child(box)

        self.status_page = Adw.StatusPage(
            icon_name="applications-games-symbolic",
            title="No games yet",
            description="Add a game manually, or import your installed Steam library.",
            vexpand=True,
        )

        self.list_group = Adw.PreferencesGroup(title="Games")
        self.listbox = Gtk.ListBox(css_classes=["boxed-list"])
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_group.add(self.listbox)

        self._content_box = box
        self._current_view = None

        self.refresh()

    # -- data --------------------------------------------------------

    def refresh(self):
        for child in list(self._content_box):
            self._content_box.remove(child)

        profiles = self.window.games_file.list_profiles()
        query = self.search_entry.get_text().strip().lower()
        if query:
            profiles = [p for p in profiles if query in p.key.lower()]

        if not profiles:
            self._content_box.append(self.status_page)
            return

        # Rebuild the listbox contents
        while True:
            row = self.listbox.get_row_at_index(0)
            if row is None:
                break
            self.listbox.remove(row)

        for profile in profiles:
            row = Adw.ActionRow(title=esc(profile.key), subtitle=esc(_summarize(profile)))
            row.set_activatable(True)
            row.connect("activated", self._on_row_activated, profile.key)

            copy_btn = Gtk.Button(icon_name="edit-copy-symbolic",
                                   tooltip_text="Copy Steam launch option to clipboard",
                                   valign=Gtk.Align.CENTER)
            copy_btn.add_css_class("flat")
            copy_btn.connect("clicked", self._on_copy_clicked, profile.key)
            row.add_suffix(copy_btn)

            edit_btn = Gtk.Button(icon_name="document-edit-symbolic",
                                   tooltip_text="Edit", valign=Gtk.Align.CENTER)
            edit_btn.add_css_class("flat")
            edit_btn.connect("clicked", lambda _b, k=profile.key: self.window.open_editor(k))
            row.add_suffix(edit_btn)

            del_btn = Gtk.Button(icon_name="user-trash-symbolic",
                                  tooltip_text="Delete", valign=Gtk.Align.CENTER)
            del_btn.add_css_class("flat")
            del_btn.add_css_class("error")
            del_btn.connect("clicked", self._on_delete_clicked, profile.key)
            row.add_suffix(del_btn)

            self.listbox.append(row)

        self._content_box.append(self.list_group)

    # -- handlers ------------------------------------------------------

    def _on_search_changed(self, _entry):
        self.refresh()

    def _on_row_activated(self, _row, key):
        self.window.open_editor(key)

    def _on_add_clicked(self, _button):
        self.window.open_editor(None)

    def _on_import_clicked(self, _button):
        self.window.open_import_dialog()

    def _on_copy_clicked(self, _button, key):
        line = steam_launch_option_line(key)
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(line)
        self.toast_overlay.add_toast(Adw.Toast(title=esc(f"Copied: {line}"), timeout=3))

    def _on_delete_clicked(self, _button, key):
        dialog = Adw.AlertDialog(
            heading=esc(f"Delete “{key}”?"),
            body="This removes the profile from games.yaml. This can't be undone.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response, key)
        dialog.present(self.window)

    def _on_delete_response(self, _dialog, response, key):
        if response == "delete":
            self.window.games_file.delete_profile(key)
            self.window.games_file.save()
            self.refresh()
            self.toast_overlay.add_toast(Adw.Toast(title=esc(f"Deleted “{key}”"), timeout=3))
