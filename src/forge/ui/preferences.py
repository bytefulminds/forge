"""Preferences dialog (Settings > Preferences, Notepad++ style).

Changes are previewed live. OK keeps them, Cancel restores the settings the
dialog started with.
"""

from __future__ import annotations

import copy
from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from forge.core.settings import Settings
from forge.i18n.catalog import LANGUAGES
from forge.i18n.translator import current_language, tr
from forge.themes.theme import SYSTEM_THEME_ID, THEME_CHOICES


def theme_label(theme_id: str) -> str:
    labels = {
        "dark": tr("Forge Dark"),
        "light": tr("Forge Light"),
        SYSTEM_THEME_ID: tr("Follow System"),
    }
    return labels.get(theme_id, theme_id)


def _spin(low: int, high: int, value: int, parent: QWidget) -> QSpinBox:
    spin = QSpinBox(parent)
    spin.setRange(low, high)
    spin.setValue(value)
    spin.setAccelerated(True)
    return spin


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("prefSection")
    return label


class PreferencesDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        apply: Callable[[Settings], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("preferencesDialog")
        self.setWindowTitle(tr("Preferences"))
        self._original = copy.deepcopy(settings)
        self.settings = copy.deepcopy(settings)
        self._apply = apply
        self._loading = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(10)
        # One form for all sections so labels and fields line up.
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(form)

        # Editor ------------------------------------------------------------
        form.addRow(_section(tr("Editor")))
        ed = self.settings.editor
        self.font_family = QFontComboBox(self)
        self.font_family.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        self.font_family.setCurrentFont(QFont(ed.font_family))
        self.font_size = _spin(6, 48, ed.font_size, self)
        self.tab_width = _spin(1, 16, ed.tab_width, self)
        self.indent = QComboBox(self)
        self.indent.addItem(tr("Spaces"), True)
        self.indent.addItem(tr("Tabs"), False)
        self.indent.setCurrentIndex(0 if ed.use_spaces else 1)
        form.addRow(tr("Font"), self.font_family)
        form.addRow(tr("Font size"), self.font_size)
        form.addRow(tr("Tab width"), self.tab_width)
        form.addRow(tr("Indent with"), self.indent)

        self.word_wrap = QCheckBox(tr("Word wrap"), self)
        self.word_wrap.setChecked(ed.word_wrap)
        self.show_whitespace = QCheckBox(tr("Show whitespace and line endings"), self)
        self.show_whitespace.setChecked(ed.show_whitespace)
        self.show_line_numbers = QCheckBox(tr("Show line numbers"), self)
        self.show_line_numbers.setChecked(ed.show_line_numbers)
        self.highlight_line = QCheckBox(tr("Highlight the current line"), self)
        self.highlight_line.setChecked(ed.highlight_current_line)
        for box in (
            self.word_wrap,
            self.show_whitespace,
            self.show_line_numbers,
            self.highlight_line,
        ):
            form.addRow("", box)

        # Appearance ----------------------------------------------------------
        form.addRow(_section(tr("Appearance")))
        self.theme = QComboBox(self)
        for theme_id in THEME_CHOICES:
            self.theme.addItem(theme_label(theme_id), theme_id)
        self.theme.setCurrentIndex(max(0, self.theme.findData(self.settings.appearance.theme)))
        self.language = QComboBox(self)
        self.language.addItem(tr("System Default"), "")
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(
            max(0, self.language.findData(self.settings.appearance.language))
        )
        form.addRow(tr("Theme"), self.theme)
        form.addRow(tr("Interface language"), self.language)
        self.restart_note = QLabel(tr("The interface language changes after restarting Forge."))
        self.restart_note.setObjectName("prefNote")
        self.restart_note.setWordWrap(True)
        form.addRow("", self.restart_note)
        self.restart_note.hide()

        # Session -------------------------------------------------------------
        form.addRow(_section(tr("Session")))
        self.remember_session = QCheckBox(tr("Remember open tabs and unsaved text"), self)
        self.remember_session.setChecked(self.settings.general.remember_session)
        form.addRow("", self.remember_session)

        layout.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addSpacing(6)
        layout.addWidget(buttons)
        self.setMinimumWidth(480)
        self.adjustSize()

        for spin in (self.font_size, self.tab_width):
            spin.valueChanged.connect(self._changed)
        for combo in (self.font_family, self.indent, self.theme, self.language):
            combo.currentIndexChanged.connect(self._changed)
        for box in (
            self.word_wrap,
            self.show_whitespace,
            self.show_line_numbers,
            self.highlight_line,
            self.remember_session,
        ):
            box.toggled.connect(self._changed)
        self._loading = False

    def _collect(self) -> None:
        ed = self.settings.editor
        ed.font_family = self.font_family.currentFont().family()
        ed.font_size = self.font_size.value()
        ed.tab_width = self.tab_width.value()
        ed.use_spaces = bool(self.indent.currentData())
        ed.word_wrap = self.word_wrap.isChecked()
        ed.show_whitespace = self.show_whitespace.isChecked()
        ed.show_line_numbers = self.show_line_numbers.isChecked()
        ed.highlight_current_line = self.highlight_line.isChecked()
        self.settings.appearance.theme = str(self.theme.currentData())
        self.settings.appearance.language = str(self.language.currentData())
        self.settings.general.remember_session = self.remember_session.isChecked()

    def _changed(self) -> None:
        if self._loading:
            return
        self._collect()
        chosen = self.settings.appearance.language
        effective = chosen or current_language()
        self.restart_note.setVisible(effective != current_language())
        self._apply(copy.deepcopy(self.settings))

    def reject(self) -> None:
        self._apply(copy.deepcopy(self._original))
        super().reject()
