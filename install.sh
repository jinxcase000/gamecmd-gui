#!/bin/bash
# gamecmd-gui installer
set -e

echo "==> Installing system dependencies (GTK4, libadwaita, PyGObject)..."
if command -v pacman &> /dev/null; then
    sudo pacman -S --needed --noconfirm python-gobject gtk4 libadwaita python-pip
elif command -v apt &> /dev/null; then
    sudo apt install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-pip
elif command -v dnf &> /dev/null; then
    sudo dnf install -y python3-gobject gtk4 libadwaita python3-pip
elif command -v zypper &> /dev/null; then
    sudo zypper install -y python3-gobject gtk4 libadwaita python3-pip
else
    echo "WARNING: Could not detect package manager."
    echo "Install these manually before continuing: PyGObject, GTK4, libadwaita"
    echo "(with GObject introspection / gir typelibs), python3-pip."
fi

echo "==> Installing gamecmd-gui..."
if ! pip install --user . 2>/tmp/gamecmd-gui-pip-err; then
    if grep -q "externally-managed-environment" /tmp/gamecmd-gui-pip-err; then
        pip install --user --break-system-packages .
    else
        cat /tmp/gamecmd-gui-pip-err
        exit 1
    fi
fi
rm -f /tmp/gamecmd-gui-pip-err

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "WARNING: \$HOME/.local/bin is not in your PATH."
    echo "Add the following to your shell config (~/.config/fish/config.fish for fish):"
    echo ""
    echo "  fish_add_path \$HOME/.local/bin"
    echo ""
fi

echo ""
echo "==> Done! Launch with: gamecmd-gui"
echo "==> (gamecmd itself must already be installed -- see ../gamecmd/install.sh)"
