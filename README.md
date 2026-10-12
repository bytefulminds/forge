<p align="center">
  <img src="src/forge/resources/icons/forge.svg" width="96" alt="Forge logo">
</p>

<h1 align="center">Forge</h1>

<p align="center">
  <strong>A fast, lightweight text editor for macOS and Linux, in the spirit of Notepad++.</strong><br>
  Open a file, get to work. Tools for JSON, CSV, Markdown, XML and YAML are built in,
  not bolted on.
</p>

<p align="center">
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-macOS%20%7C%20Linux-081A33">
  <img alt="Python" src="https://img.shields.io/badge/python-3.12-3C7DD9">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-5CC8E8">
  <img alt="Languages" src="https://img.shields.io/badge/UI-English%20%7C%20Nederlands-A6D84A">
</p>

![Forge with a Markdown document and its live preview, including a Mermaid diagram](docs/images/forge-markdown.png)

> **Status:** early development. Forge runs from source today; packaged downloads
> (AppImage and a macOS app) come later.

## Why Forge

- **Starts fast, stays fast.** Large files load in the background. Above 20 MB, Forge turns off
  the heavy features, as Notepad++ does, so even huge logs scroll smoothly.
- **Knows your files.** Every document gets a toolbar with the tools for its language:
  formatting, validation, previews and conversions, one click away.
- **Looks the same everywhere.** Forge draws its own window, menus and dialogs, in a dark
  and a light theme, on macOS and on Linux.
- **Never loses work.** Unsaved text and open tabs come back after a restart, and Forge
  notices when a file changes on disk.

## Highlights

### Markdown with a live preview

Write on the left, read on the right. Tables, task lists, footnotes and
[Mermaid](https://mermaid.js.org) diagrams render as you type. The toolbar has buttons for
bold, headings, lists, links, code blocks and tables.

### JSON: format, validate, explore

Format or minify with one click. Errors are underlined at the exact spot as you type,
and the tree view shows the structure of the document.

![JSON document next to its tree view](docs/images/forge-json.png)

### CSV that understands your data

Every column has its own color, and a table view sits next to the text. Forge detects
the delimiter (comma, semicolon, tab or pipe) and the status bar shows the column name
at the cursor. Sort by a column, align columns, remove duplicate rows, convert Unix
timestamps to ISO 8601 and back, or export to JSON or a Markdown table.

![CSV file with colored columns, a table view and the column name in the status bar](docs/images/forge-csv.png)

### Compare two versions

Compare a document with its saved version or with another tab. Added lines are green,
changed lines orange, removed lines red, and changes within a line are marked too.

![Side by side comparison of two versions of a JSON file](docs/images/forge-compare.png)

### Find in Files

Search and replace across a whole folder, with regular expressions, case and whole word
options and file filters such as `*.py *.json !build`. Click a result to jump to it.

![Find in Files panel with results grouped per file](docs/images/forge-find-in-files.png)

### Made for code

Syntax highlighting for 23 languages, rainbow brackets and indentation, live syntax
checks for Python, JSON, YAML, XML, TOML and CSV, autocomplete from the words in your
file, and Notepad++ shortcuts that your fingers already know.

![Python file in the light theme with rainbow brackets and an underlined syntax error](docs/images/forge-light.png)

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) (version `0.11.32` or
newer). uv installs the right Python version by itself.

```sh
git clone https://gitlab.com/bytefulminds/forge.git
cd forge
uv sync
uv run forge
```

Open files directly with `uv run forge notes.md data.csv`.

For the full Markdown preview with Mermaid diagrams, install the optional browser engine
(about 200 MB) with `uv sync --extra web` instead.

### First steps

| To | Press (Linux) | Press (macOS) |
|---|---|---|
| Open a file | `Ctrl+O` | `Cmd+O` |
| Save as | `Ctrl+Alt+S` | `Cmd+Shift+S` |
| Find, replace | `Ctrl+F`, `Ctrl+H` | `Cmd+F`, `Cmd+Option+F` |
| Find in files | `Ctrl+Shift+F` | `Cmd+Shift+F` |
| Go to line | `Ctrl+G` | `Cmd+L` |
| Toggle comment | `Ctrl+Q` | `Ctrl+Q` |
| Show the preview | `Ctrl+Shift+V` | `Cmd+Shift+V` |
| Preferences | `Ctrl+,` | `Cmd+,` |

**Read the [manual](MANUAL.md)** for every feature, tool and shortcut.

## Development

```sh
uv run ruff check .         # lint
uv run ruff format .        # format
uv run mypy                 # type check
uv run pytest               # tests (headless, no display needed)
FORGE_TEST_WEBENGINE=1 uv run pytest tests/ui/test_web_preview.py   # rich preview (web extra)
```

Every dependency is pinned to an exact version in `pyproject.toml` and `uv.lock`, so every
machine gets the same build.

### Project layout

```
src/forge/
  core/        documents, encodings, line endings, file IO, settings, CSV parsing (no widgets)
  editor/      the QScintilla based editor, lexers, syntax checks, bracket colors
  ui/          main window, tabs, toolbar, previews, dialogs, status bar
  themes/      design tokens, dark and light themes, stylesheet
  i18n/        translation catalogs and tr()
  extensions/  the internal API the built-in tools use
  tools/       JSON, YAML, XML, Markdown, CSV, Compare, Find in Files
  resources/   fonts, Lucide icons, Mermaid, translations
docs/images/   screenshots for this README
tests/
```

### Translations

Every user-facing string goes through `tr("English text")`. Translations live in
`src/forge/resources/i18n/<language>.toml` as `"English text" = "Translation"`.
`tests/test_i18n.py` fails when a string is missing, unused, or has mismatched
`{placeholders}`, so the catalogs stay complete. To add a language, add its code to
`LANGUAGES` in `src/forge/i18n/catalog.py` and create the matching `.toml` file.

## Credits

Forge is built on [Qt](https://www.qt.io) through [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
and [QScintilla](https://www.riverbankcomputing.com/software/qscintilla/). It bundles
[Inter](https://rsms.me/inter/) and [JetBrains Mono](https://www.jetbrains.com/lp/mono/) (SIL OFL),
[Lucide](https://lucide.dev) icons (ISC) and [Mermaid](https://mermaid.js.org) (MIT).

## License

GPL-3.0. See [LICENSE](LICENSE).
