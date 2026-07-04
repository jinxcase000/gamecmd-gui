#!/usr/bin/env python3
"""Entry point: `python3 -m gamecmd_gui` or the installed `gamecmd-gui` script."""

import sys


def run():
    from .app import main
    sys.exit(main())


if __name__ == "__main__":
    run()
