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

from forge.editor.commenting import CommentStyle
from forge.editor.csv_lexer import CsvLexer
from forge.themes.theme import SyntaxColors, Theme

NO_COMMENT = CommentStyle()


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    lexer: type[QsciLexer] | None
    extensions: tuple[str, ...] = ()
    # Extension proposed by Save As. Empty for languages identified by file name.
    default_extension: str = ""
    comment: CommentStyle = NO_COMMENT


PLAIN_TEXT = Language("text", "Normal text", None, (".txt", ".log", ".text"), ".txt")

_LANGUAGES: tuple[Language, ...] = (
    Language(
        "python", "Python", QsciLexerPython, (".py", ".pyw", ".pyi"), ".py", CommentStyle("#")
    ),
    Language("json", "JSON", QsciLexerJSON, (".json", ".jsonc", ".geojson"), ".json"),
    Language("yaml", "YAML", QsciLexerYAML, (".yaml", ".yml"), ".yaml", CommentStyle("#")),
    Language(
        "xml",
        "XML",
        QsciLexerXML,
        (".xml", ".xsd", ".xsl", ".xslt", ".svg", ".plist"),
        ".xml",
        CommentStyle("", "<!--", "-->"),
    ),
    Language(
        "html",
        "HTML",
        QsciLexerHTML,
        (".html", ".htm", ".xhtml", ".vue"),
        ".html",
        CommentStyle("", "<!--", "-->"),
    ),
    Language(
        "css", "CSS", QsciLexerCSS, (".css", ".scss", ".less"), ".css", CommentStyle("", "/*", "*/")
    ),
    Language(
        "javascript",
        "JavaScript",
        QsciLexerJavaScript,
        (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"),
        ".js",
        CommentStyle("//"),
    ),
    Language(
        "bash", "Shell", QsciLexerBash, (".sh", ".bash", ".zsh", ".fish"), ".sh", CommentStyle("#")
    ),
    Language("markdown", "Markdown", QsciLexerMarkdown, (".md", ".markdown"), ".md"),
    Language("csv", "CSV", CsvLexer, (".csv", ".tsv", ".tab"), ".csv"),
    Language("sql", "SQL", QsciLexerSQL, (".sql",), ".sql", CommentStyle("--")),
    Language(
        "cpp",
        "C / C++",
        QsciLexerCPP,
        (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".m", ".mm"),
        ".cpp",
        CommentStyle("//"),
    ),
    Language("java", "Java", QsciLexerJava, (".java", ".kt", ".kts"), ".java", CommentStyle("//")),
    Language("csharp", "C#", QsciLexerCSharp, (".cs",), ".cs", CommentStyle("//")),
    Language(
        "properties",
        "Properties / INI",
        QsciLexerProperties,
        (".ini", ".cfg", ".conf", ".properties", ".toml", ".env"),
        ".ini",
        CommentStyle("#"),
    ),
    Language("makefile", "Makefile", QsciLexerMakefile, (".mk", ".mak"), comment=CommentStyle("#")),
    Language("cmake", "CMake", QsciLexerCMake, (".cmake",), ".cmake", CommentStyle("#")),
    Language("diff", "Diff", QsciLexerDiff, (".diff", ".patch"), ".diff"),
    Language("batch", "Batch", QsciLexerBatch, (".bat", ".cmd"), ".bat", CommentStyle("REM")),
    Language("perl", "Perl", QsciLexerPerl, (".pl", ".pm"), ".pl", CommentStyle("#")),
    Language("ruby", "Ruby", QsciLexerRuby, (".rb",), ".rb", CommentStyle("#")),
    Language("lua", "Lua", QsciLexerLua, (".lua",), ".lua", CommentStyle("--")),
    Language("tex", "TeX", QsciLexerTeX, (".tex", ".sty"), ".tex", CommentStyle("%")),
)

_BY_ID = {lang.id: lang for lang in (PLAIN_TEXT, *_LANGUAGES)}
_BY_EXTENSION = {ext: lang for lang in _LANGUAGES for ext in lang.extensions}
_BY_FILENAME = {
    "makefile": _BY_ID["makefile"],
    "gnumakefile": _BY_ID["makefile"],
    "cmakelists.txt": _BY_ID["cmake"],
    ".bashrc": _BY_ID["bash"],
    ".zshrc": _BY_ID["bash"],
    ".profile": _BY_ID["bash"],
    ".env": _BY_ID["properties"],
    ".gitlab-ci.yml": _BY_ID["yaml"],
}


def language_by_id(language_id: str) -> Language:
    return _BY_ID.get(language_id, PLAIN_TEXT)


def is_known_filename(path: Path) -> bool:
    return path.name.lower() in _BY_FILENAME


def language_for_path(path: Path | None) -> Language:
    if path is None:
        return PLAIN_TEXT
    name = path.name.lower()
    if name in _BY_FILENAME:
        return _BY_FILENAME[name]
    return _BY_EXTENSION.get(path.suffix.lower(), PLAIN_TEXT)


def all_languages() -> list[Language]:
    return [PLAIN_TEXT, *sorted(_LANGUAGES, key=lambda lang: lang.name.lower())]


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
    lexer.setDefaultPaper(QColor(theme.editor_bg))
    lexer.setDefaultColor(QColor(syntax.default))
    lexer.setDefaultFont(font)
    lexer.setPaper(QColor(theme.editor_bg), -1)
    lexer.setColor(QColor(syntax.default), -1)
    lexer.setFont(font, -1)
    if isinstance(lexer, CsvLexer):
        lexer.apply_palette(theme.rainbow or (syntax.default,), theme.text_muted, font)
        return
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
