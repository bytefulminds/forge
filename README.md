# Forge

A fast, lightweight text editor for **macOS** and **Linux** in the spirit of Notepad++.

> Status: early development (phase a: skeleton). Not ready for daily use yet.

## Requirements

- [uv](https://docs.astral.sh/uv/) `0.11.32` or newer (CI uses exactly `0.11.32`).
  Install on macOS with `brew install uv`, or on macOS/Linux with
  `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- Python `3.12.13` is installed automatically by uv from `.python-version`

All dependencies are pinned to exact versions in `pyproject.toml` and `uv.lock`,
so every machine gets the same build.

## Run

```sh
uv sync
uv run forge                # start Forge
uv run forge path/to/file   # open one or more files
```

## Develop

```sh
uv run ruff check .         # lint
uv run ruff format .        # format
uv run mypy                 # type check
uv run pytest               # tests (headless, no display needed)
```

### Project layout

```
src/forge/
  core/        documents, encodings, line endings, file IO, settings (no Qt widgets)
  editor/      the QScintilla based editor widget and lexers
  ui/          main window, tabs, status bar
  themes/      design tokens, dark and light themes, stylesheet
  i18n/        translation catalogs and tr()
  extensions/  internal extension API for the built-in tools (later phases)
  tools/       built-in tools: JSON, YAML, XML, Compare, Find in Files (later phases)
  resources/   icons, fonts and translation files
tests/
```

### Translations

Every user-facing string goes through `tr("English text")`. Translations live in
`src/forge/resources/i18n/<language>.toml` as `"English text" = "Translation"`.
`tests/test_i18n.py` fails when a string is missing, unused, or has mismatched
`{placeholders}`, so the catalogs stay complete.

To add a language: add its code to `LANGUAGES` in `src/forge/i18n/catalog.py` and
create the matching `.toml` file.

### Settings and logs

| | Linux | macOS |
|---|---|---|
| Settings | `~/.config/forge/settings.toml` | `~/Library/Application Support/Forge/settings.toml` |
| Logs | `~/.local/state/forge/log/` | `~/Library/Logs/Forge/` |

Set `FORGE_HOME=/some/dir` to keep everything in one folder (used by the tests).

## License

GPL-3.0. See [LICENSE](LICENSE).

Bundled fonts: [Inter](https://rsms.me/inter/) and [JetBrains Mono](https://www.jetbrains.com/lp/mono/),
both under the SIL Open Font License 1.1 (license texts in `src/forge/resources/fonts/`).
