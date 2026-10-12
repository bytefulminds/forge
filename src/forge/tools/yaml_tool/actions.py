"""YAML validation."""

from __future__ import annotations

import yaml

from forge.extensions.api import ForgeAPI, tr

_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def check(text: str) -> tuple[int, str, int, int] | None:
    """Return (documents, error, line, column); error is empty when valid."""
    try:
        documents = sum(1 for _ in yaml.load_all(text, Loader=_Loader))
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        line = mark.line + 1 if mark is not None else 1
        column = mark.column + 1 if mark is not None else 1
        message = exc.problem or str(exc)
        return 0, message, line, column
    except yaml.YAMLError as exc:
        return 0, str(exc), 1, 1
    return documents, "", 0, 0


def validate_yaml(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None:
        return
    result = check(editor.text())
    assert result is not None
    documents, error, line, column = result
    if error:
        api.show_error_at(
            editor,
            tr(
                "Invalid YAML at line {line}, column {column}: {error}",
                line=line,
                column=column,
                error=error,
            ),
            line,
            column,
        )
        return
    api.notify(tr("Valid YAML ({count} documents).", count=documents), "info")
