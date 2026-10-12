"""Generate the Qt stylesheet for a theme."""

from __future__ import annotations

from forge.themes.theme import Theme


def build_stylesheet(theme: Theme) -> str:
    c = theme
    return f"""
QMainWindow, QDialog {{ background: {c.surface}; color: {c.text}; }}
QWidget {{ color: {c.text}; }}

QMenuBar {{ background: {c.surface}; color: {c.text}; border-bottom: 1px solid {c.border}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {c.surface_alt}; }}
QMenu {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; padding: 4px; }}
QMenu::item {{ padding: 5px 24px 5px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {c.selection}; }}
QMenu::item:disabled {{ color: {c.text_muted}; }}
QMenu::separator {{ height: 1px; background: {c.border}; margin: 4px 8px; }}

QTabWidget::pane {{ border: none; }}
QTabBar {{ background: {c.surface}; }}
QTabBar::tab {{
    background: {c.surface}; color: {c.text_muted};
    padding: 6px 12px; border: none; border-right: 1px solid {c.border};
    border-top: 2px solid transparent;
}}
QTabBar::tab:hover {{ background: {c.surface_alt}; color: {c.text}; }}
QTabBar::tab:selected {{
    background: {c.background}; color: {c.text}; border-top: 2px solid {c.focus};
}}

QToolButton#tabCloseButton {{
    color: {c.text_muted}; background: transparent; border: none; border-radius: 3px;
    font-size: 15px; padding: 0 4px; margin-left: 4px;
}}
QToolButton#tabCloseButton:hover {{ color: {c.text}; background: {c.surface_alt}; }}

QStatusBar {{ background: {c.surface}; color: {c.text_muted}; border-top: 1px solid {c.border}; }}
QStatusBar QLabel {{ color: {c.text_muted}; padding: 0 8px; }}
QStatusBar::item {{ border: none; }}

QPushButton {{
    background: {c.surface_alt}; color: {c.text}; border: 1px solid {c.border};
    border-radius: 4px; padding: 5px 14px;
}}
QPushButton:hover {{ border-color: {c.accent}; }}
QPushButton:default {{ border-color: {c.accent}; }}
QPushButton:focus {{ border-color: {c.focus}; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {c.background}; color: {c.text}; border: 1px solid {c.border};
    border-radius: 4px; padding: 4px 6px; selection-background-color: {c.selection};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {c.focus}; }}

QScrollBar:vertical {{ background: {c.background}; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: {c.background}; height: 12px; margin: 0; }}
QScrollBar::handle {{
    background: {c.border}; border-radius: 4px; min-height: 24px; min-width: 24px;
}}
QScrollBar::handle:hover {{ background: {c.text_muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QToolTip {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; }}
"""
