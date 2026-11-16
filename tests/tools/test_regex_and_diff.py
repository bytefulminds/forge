"""Regex tester and quick diff."""

from __future__ import annotations

import re

import pytest
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.tools.utilities import regex_core as core
from forge.ui.framed_dialog import FramedDialog
from forge.ui.main_window import MainWindow


def test_evaluate_reports_matches_and_groups() -> None:
    result = core.evaluate(r"(?P<key>\w+)=(\d+)?", 0, "a=1 b= c=33")
    assert [m.text for m in result.matches] == ["a=1", "b=", "c=33"]
    first = result.matches[0]
    assert [(g.name, g.text) for g in first.groups] == [("key", "a"), ("2", "1")]
    assert result.matches[1].groups[1].start == -1  # the group did not take part


def test_evaluate_errors_flags_and_limit() -> None:
    error = core.evaluate("(a", 0, "a")
    assert error.error and error.error_position is not None
    assert len(core.evaluate("^x", core.flag_value("m"), "x\nx").matches) == 2
    assert len(core.evaluate("^x", 0, "x\nx").matches) == 1
    capped = core.evaluate("a", 0, "a" * 20, limit=5)
    assert len(capped.matches) == 5 and capped.truncated
    assert core.evaluate("", 0, "abc").matches == []


def test_replace_and_python_literal() -> None:
    assert core.replace(r"(\w+)@(\w+)", 0, "me@host", r"\2/\1") == ("host/me", 1)
    assert isinstance(core.replace(r"(\w+)", 0, "x", r"\3"), str)
    code = core.python_literal(r'\d+"', core.flag_value("im"))
    assert code == "re.compile(r'\\d+\"', re.IGNORECASE | re.MULTILINE)"
    assert eval(code, {"re": re}).pattern == '\\d+"'
    assert core.byte_offsets("aé€b", [0, 2, 3, 4]) == {0: 0, 2: 3, 3: 6, 4: 7}


def make_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def test_regex_tester_window(qtbot: QtBot) -> None:
    from forge.tools.utilities.regex_tester import GROUP_INDICATORS, MATCH_INDICATOR, RegexTester

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("id=7 name=forge")
    window.extension_host.run_command("utilities.regex")
    tester = next(
        d.property("forgeTool")
        for d in window.findChildren(FramedDialog)
        if isinstance(d.property("forgeTool"), RegexTester)
    )
    assert str(tester.text.text()) == "id=7 name=forge"
    tester.pattern.setText(r"(\w+)=(\w+)")
    tester.run()
    assert tester.matches.topLevelItemCount() == 2
    assert "2 matches" in tester.summary.text()
    send = tester.text.SendScintilla
    assert send(send.__self__.SCI_INDICATORVALUEAT, MATCH_INDICATOR, 0) == 1
    assert send(send.__self__.SCI_INDICATORVALUEAT, GROUP_INDICATORS[1], 3) == 1
    tester.flags["i"].setChecked(True)
    assert tester.flag_value() == re.IGNORECASE
    tester.replacement.setText(r"\2")
    tester.run()
    assert str(tester.replaced.text()) == "7 forge" and tester.replaced.isVisibleTo(tester.dialog)
    tester.pattern.setText("(")
    tester.run()
    assert tester.pattern.property("invalid") is True
    assert tester.matches.topLevelItemCount() == 0
    tester.dialog.close()


def test_compare_with_clipboard(qtbot: QtBot) -> None:
    from PyQt6.QtWidgets import QApplication

    from forge.tools.compare.view import CompareView

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("a\nb\nc\n")
    clipboard = QApplication.clipboard()
    assert clipboard is not None
    clipboard.setText("a\nB\nc\n")
    window.extension_host.run_command("compare.clipboard")
    view = window.tabs.currentWidget()
    assert isinstance(view, CompareView)
    assert not view.comparison.identical


def test_quick_diff(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from forge.tools.compare import quick
    from forge.tools.compare.view import CompareView

    window = make_window(qtbot)

    def fill(self: quick.QuickDiff) -> int:
        self.left.setText("one\ntwo\n")
        self.right.setText("one\n2\n")
        return int(self.dialog.DialogCode.Accepted.value)

    monkeypatch.setattr(quick.QuickDiff, "exec", fill)
    window.extension_host.run_command("compare.quick")
    view = window.tabs.currentWidget()
    assert isinstance(view, CompareView)
    assert not view.comparison.identical
