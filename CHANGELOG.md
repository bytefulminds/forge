# Changelog

All notable changes to Forge. The newest version is at the top. Versions follow
[semantic versioning](https://semver.org). The release notes on GitLab are taken from
this file by `scripts/release_notes.py`, so every release needs a section here.

## [Unreleased]

### Added

- Forge Dark is now a near black theme with grey surfaces. The night blue theme it
  replaces is still there as Forge Blue.
- A new cron window: the expression in words, a card per field, the next runs in local
  time or UTC, a 12 or 24-hour clock, and a cheat sheet whose examples load with one
  click. It takes whole crontab lines, six-field expressions with seconds and `@reboot`,
  and puts the edited expression back in the document.
- Epoch to ISO 8601 in local time, with the UTC offset, next to UTC: in the right-click
  menu, the Date and Time menu and the CSV toolbar.

### Changed

- Relative times are shorter and exact to the minute, such as "in 1 h 8 min".

### Removed

- The *Use Local Time* option, replaced by the separate local time commands.

## [0.1.0] - 2026-10-13

The first release, with downloads for macOS (Apple Silicon), Linux (AppImage, x86-64)
and Windows (installer, x86-64).

### Editor

- Tabs and sessions: open tabs and unsaved text come back after a restart.
- Open files are watched: unchanged tabs reload, tabs with unsaved changes ask first.
- Large files load in the background; above 20 MB the heavy features switch off.
- Encodings and line endings (LF, CRLF, CR) can be seen and converted per file.
- Syntax highlighting for 23 languages, rainbow brackets and rainbow indentation.
- Live syntax checks for Python, JSON, YAML, XML, TOML and CSV.
- Autocomplete from the words in the document and the language's keywords.
- Find and replace with regular expressions, Find in Files with file filters.
- Classic editor shortcuts, such as toggle comment (`Ctrl+Q`) and find next (`F3`).

### Language tools

- A toolbar per document with the tools for its language, and Text, Split and
  Preview views.
- JSON: format, minify, validate, and a tree view that selects the clicked item in
  the code.
- XML: pretty print, minify, well-formedness check, an XPath panel and auto-closing tags.
- YAML: validation while you type and on request.
- Markdown: a live preview with tables, task lists and footnotes, Mermaid diagrams
  in the rich preview, and buttons for bold, headings, lists, links, code and tables.
- CSV: a color per column, a table view, delimiter and header detection with a
  per-file override, sort, align, remove duplicates, Unix time to ISO 8601 and back,
  and export to JSON or a Markdown table.
- Compare a document with its saved version or another tab, side by side.

### Developer tools

- Hashes (MD5, SHA-1, SHA-256, SHA-512) of a selection or a file.
- Base64, URL, HTML and JSON string encoding and decoding, and JWT decoding.
- Letter case conversions (camelCase, snake_case, kebab-case and more), sorting and
  deduplicating lines.
- UUIDs (version 4 and 7, one or many), the current date and time, timestamp
  conversion and a cron expression explainer with the next run times.
- A language-aware right-click menu with the tools that fit the selection.

### Look and feel

- Forge's own window frame, menus and dialogs, in a dark and a light theme, the same
  on macOS, Linux and Windows.
- English and Dutch, following the system language by default.
- An About window with a one-click "Copy System Info" for bug reports.
