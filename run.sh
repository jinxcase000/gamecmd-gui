#!/bin/bash
# Run gamecmd-gui straight from source, no install needed
# (still requires the system GTK4/libadwaita/PyGObject deps -- see install.sh)
cd "$(dirname "$0")"
exec python3 -m gamecmd_gui
