"""Entry point for the packaged builds (PyInstaller freezes this script)."""

from forge.app import main

raise SystemExit(main())
