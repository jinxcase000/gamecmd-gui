"""
app.py

Top-level Adw.Application + Adw.ApplicationWindow wiring: a NavigationView
holding the Games list page, which pushes the Game Editor page for
add/edit and opens the Import-from-Steam window as a dialog.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from .gtk_util import MONOSPACE_CSS  # noqa: E402
from .models import GamesFile  # noqa: E402
from .widgets.game_editor_page import GameEditorPage  # noqa: E402
from .widgets.games_list_page import GamesListPage  # noqa: E402
from .widgets.import_steam_dialog import ImportSteamDialog  # noqa: E402

APP_ID = "io.github.jinxcase000.gamecmd-gui"


def _install_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(MONOSPACE_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


class GamecmdGuiWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="gamecmd GUI",
                          default_width=1000, default_height=760)

        self.games_file = GamesFile()

        self.nav_view = Adw.NavigationView()
        self.set_content(self.nav_view)

        self.games_page = GamesListPage(self)
        self.nav_view.push(self.games_page)

    # -- navigation helpers, called from the pages themselves ----------

    def open_editor(self, profile_key):
        page = GameEditorPage(self, profile_key)
        self.nav_view.push(page)

    def close_editor(self, saved: bool, key: str = ""):
        self.nav_view.pop()
        self.games_page.refresh()
        if saved:
            self.games_page.toast_overlay.add_toast(
                Adw.Toast(title=f"Saved “{key}”", timeout=2))

    def open_import_dialog(self):
        dialog = ImportSteamDialog(self)
        dialog.present()


class GamecmdGuiApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                          flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None

    def do_activate(self):
        if self.window is None:
            _install_css()
            self.window = GamecmdGuiWindow(self)
        self.window.present()


def main():
    app = GamecmdGuiApp()
    return app.run()
