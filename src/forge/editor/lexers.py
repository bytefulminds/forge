"""File type to lexer mapping and palette driven lexer styling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.Qsci import (
    QsciLexer,
    QsciLexerBash,
    QsciLexerBatch,
    QsciLexerCMake,
    QsciLexerCPP,
    QsciLexerCSharp,
    QsciLexerCSS,
    QsciLexerDiff,
    QsciLexerHTML,
    QsciLexerJava,
    QsciLexerJavaScript,
    QsciLexerJSON,
    QsciLexerLua,
    QsciLexerMakefile,
    QsciLexerMarkdown,
    QsciLexerPerl,
    QsciLexerProperties,
    QsciLexerPython,
    QsciLexerRuby,
    QsciLexerSQL,
    QsciLexerTeX,
    QsciLexerXML,
    QsciLexerYAML,
)
from PyQt6.QtGui import QColor, QFont

from forge.themes.theme import SyntaxColors, Theme


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    lexer: type[QsciLexer] | None


PLAIN_TEXT = Language("text", "Normal text", None)

_LANGUAGES: list[tuple[Language, tuple[str, ...]]] = [
    (Language("python", "Python", QsciLexerPython), (".py", ".pyw", ".pyi")),
    (Language("json", "JSON", QsciLexerJSON), (".json", ".jsonc", ".geojson")),
    (Language("yaml", "YAML", QsciLexerYAML), (".yaml", ".yml")),
    (Language("xml", "XML", QsciLexerXML), (".xml", ".xsd", ".xsl", ".xslt", ".svg", ".plist")),
    (Language("html", "HTML", QsciLexerHTML), (".html", ".htm", ".xhtml", ".vue")),
    (Language("css", "CSS", QsciLexerCSS), (".css", ".scss", ".less")),
    (
        Language("javascript", "JavaScript", QsciLexerJavaScript),
        (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"),
    ),
    (Language("bash", "Shell", QsciLexerBash), (".sh", ".bash", ".zsh", ".fish")),
    (Language("markdown", "Markdown", QsciLexerMarkdown), (".md", ".markdown")),
    (Language("sql", "SQL", QsciLexerSQL), (".sql",)),
    (
        Language("cpp", "C / C++", QsciLexerCPP),
        (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".m", ".mm"),
    ),
    (Language("java", "Java", QsciLexerJava), (".java", ".kt", ".kts")),
    (Language("csharp", "C#", QsciLexerCSharp), (".cs",)),
    (
        Language("properties", "Properties / INI", QsciLexerProperties),
        (".ini", ".cfg", ".conf", ".properties", ".toml", ".env"),
    ),
    (Language("makefile", "Makefile", QsciLexerMakefile), (".mk", ".mak")),
    (Language("cmake", "CMake", QsciLexerCMake), (".cmake",)),
    (Language("diff", "Diff", QsciLexerDiff), (".diff", ".patch")),
    (Language("batch", "Batch", QsciLexerBatch), (".bat", ".cmd")),
    (Language("perl", "Perl", QsciLexerPerl), (".pl", ".pm")),
    (Language("ruby", "Ruby", QsciLexerRuby), (".rb",)),
    (Language("lua", "Lua", QsciLexerLua), (".lua",)),
    (Language("tex", "TeX", QsciLexerTeX), (".tex", ".sty")),
]

_BY_EXTENSION = {ext: lang for lang, exts in _LANGUAGES for ext in exts}
_BY_FILENAME = {
    "makefile": _BY_EXTENSION[".mk"],
    "gnumakefile": _BY_EXTENSION[".mk"],
    "cmakelists.txt": _BY_EXTENSION[".cmake"],
    ".bashrc": _BY_EXTENSION[".sh"],
    ".zshrc": _BY_EXTENSION[".sh"],
    ".profile": _BY_EXTENSION[".sh"],
    ".gitlab-ci.yml": _BY_EXTENSION[".yml"],
}


def language_for_path(path: Path | None) -> Language:
    if path is None:
        return PLAIN_TEXT
    name = path.name.lower()
    if name in _BY_FILENAME:
        return _BY_FILENAME[name]
    return _BY_EXTENSION.get(path.suffix.lower(), PLAIN_TEXT)


def all_languages() -> list[Language]:
    return [PLAIN_TEXT, *sorted((lang for lang, _ in _LANGUAGES), key=lambda lang: lang.name)]


# Style descriptions from Scintilla lexers are matched against these keywords,
# in order, to pick a syntax role. This keeps every lexer on-palette without a
# hand written style table per language.
_ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("error", ("error", "unclosed", "bad ", "invalid")),
    ("comment", ("comment", "pod", "doc")),
    (
        "string",
        (
            "string",
            "character",
            "quoted",
            "here document",
            "heredoc",
            "verbatim",
            "regex",
            "text block",
        ),
    ),
    ("number", ("number", "numeric")),
    (
        "preprocessor",
        ("preprocessor", "pre-processor", "decorator", "directive", "document delimiter"),
    ),
    ("attribute", ("attribute", "property", "key", "variable", "reference")),
    ("tag", ("tag", "entity", "section", "header", "target")),
    ("keyword", ("keyword", "instruction", "builtin", "command", "function")),
    ("operator", ("operator", "punctuation", "delimiter")),
)


def role_for_description(description: str) -> str:
    lowered = description.lower()
    for role, keywords in _ROLE_KEYWORDS:
        if any(word in lowered for word in keywords):
            return role
    return "default"


def style_lexer(lexer: QsciLexer, theme: Theme, font: QFont) -> None:
    syntax: SyntaxColors = theme.syntax
    lexer.setDefaultPaper(QColor(theme.background))
    lexer.setDefaultColor(QColor(syntax.default))
    lexer.setDefaultFont(font)
    lexer.setPaper(QColor(theme.background), -1)
    lexer.setColor(QColor(syntax.default), -1)
    lexer.setFont(font, -1)
    for style in range(128):
        description = lexer.description(style)
        if not description:
            continue
        role = role_for_description(description)
        lexer.setColor(QColor(getattr(syntax, role)), style)
        if role == "keyword":
            bold = QFont(font)
            bold.setBold(True)
            lexer.setFont(bold, style)
        elif role == "comment":
            italic = QFont(font)
            italic.setItalic(True)
            lexer.setFont(italic, style)
