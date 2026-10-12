"""Generate the Qt stylesheet for a theme (see the UI spec for the rationale)."""

from __future__ import annotations

from forge.themes.theme import Theme


def build_stylesheet(theme: Theme) -> str:
    c = theme
    return f"""
QMainWindow {{ background: {c.chrome_bg}; }}
QsciScintilla {{ border: none; }}
QAbstractScrollArea::corner {{ background: {c.editor_bg}; }}

QWidget#titleBar {{ background: {c.chrome_bg}; }}
QWidget#menuRow {{ background: {c.chrome_bg}; border-bottom: 1px solid {c.border}; }}
QWidget#menuRow QMenuBar {{ background: transparent; border: none; padding: 0; }}
QLabel#windowTitle {{ color: {c.text_muted}; font-size: 12px; }}
QToolButton#windowButton, QToolButton#windowButtonClose {{
    border: none; border-radius: 0; background: transparent; color: {c.text_muted};
}}
QToolButton#windowButton:hover {{ background: {c.hover_bg}; color: {c.text}; }}
QToolButton#windowButton:pressed {{ background: {c.pressed_bg}; }}
QToolButton#windowButtonClose:hover {{ background: {c.error}; }}

QMenuBar {{ background: {c.chrome_bg}; border-bottom: 1px solid {c.border}; padding: 2px 4px; }}
QMenuBar::item {{
    padding: 4px 10px; margin: 0 1px; border-radius: 4px; background: transparent;
}}
QMenuBar::item:selected {{ background: {c.hover_bg}; }}
QMenuBar::item:pressed {{ background: {c.pressed_bg}; }}
QMenu {{
    background: {c.elevated_bg}; border: 1px solid {c.border_strong};
    border-radius: 8px; padding: 5px;
}}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c.menu_selected_bg}; }}
QMenu::item:disabled {{ color: {c.text_disabled}; }}
QMenu::separator {{ height: 1px; background: {c.border}; margin: 4px 8px; }}

QWidget#languagePicker {{ background: transparent; }}
QWidget#languagePicker QListWidget {{
    background: transparent; border: none; outline: 0; color: {c.text};
}}
QWidget#languagePicker QListWidget::item {{ padding: 5px 10px; border-radius: 6px; }}
QWidget#languagePicker QListWidget::item:hover {{ background: {c.hover_bg}; }}
QWidget#languagePicker QListWidget::item:selected {{
    background: {c.menu_selected_bg}; color: {c.text};
}}

QTabWidget::pane {{ border: 0; top: 0; }}
QToolButton#newTabButton {{
    border: none; border-radius: 6px; background: transparent; color: {c.text_muted};
    font-size: 17px; padding: 0 0 2px 0;
}}
QToolButton#newTabButton:hover {{ background: {c.hover_bg}; color: {c.text}; }}
QToolButton#newTabButton:pressed {{ background: {c.pressed_bg}; }}
QTabBar {{ background: {c.chrome_bg}; qproperty-drawBase: 0; border-bottom: 1px solid {c.border}; }}
QTabBar::tab {{
    height: 32px; min-width: 72px; max-width: 220px; padding: 0 0 0 14px;
    margin: 4px 2px 0 0; border-top-left-radius: 6px; border-top-right-radius: 6px;
    border-top: 2px solid transparent; background: transparent; color: {c.text_muted};
}}
QTabBar::tab:first {{ margin-left: 6px; }}
QTabBar::tab:hover:!selected {{ background: {c.hover_bg}; color: {c.text}; }}
QTabBar::tab:selected {{
    background: {c.editor_bg}; color: {c.text}; border-top: 2px solid {c.focus};
}}
QTabBar QToolButton {{ background: {c.chrome_bg}; border: none; color: {c.text_muted}; }}
QToolButton#tabCloseButton {{
    min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px;
    border: none; border-radius: 4px; background: transparent; color: {c.text_muted};
    font-size: 14px; padding: 0;
}}
QWidget#tabButtonBox {{ background: transparent; }}
QToolButton#tabCloseButton:hover {{ background: {c.error}; color: white; }}
QToolButton#tabCloseButton:pressed {{ background: {c.error}; color: white; }}
QToolButton#tabCloseButton[dirty="true"] {{ color: {c.accent}; font-size: 10px; }}
QToolButton#tabCloseButton[dirty="true"]:hover {{
    background: {c.error}; color: white; font-size: 14px;
}}

QStatusBar {{
    background: {c.chrome_bg}; color: {c.text_muted}; border-top: 1px solid {c.border};
    font-size: 12px; min-height: 24px;
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {c.text_muted}; padding: 0 8px; }}
QFrame#statusSeparator {{ background: {c.border}; max-width: 1px; min-width: 1px; }}
QToolButton#statusSegment {{
    color: {c.text_muted}; background: transparent; border: none;
    border-radius: 6px; padding: 2px 8px; font-size: 12px;
}}
QToolButton#statusSegment:hover {{ background: {c.hover_bg}; color: {c.text}; }}
QToolButton#statusSegment:pressed {{ background: {c.pressed_bg}; }}
QToolButton#statusSegment::menu-indicator {{ image: none; width: 0; }}

QDialog, QMessageBox {{ background: {c.elevated_bg}; }}
QPushButton {{
    background: transparent; color: {c.text}; border: 1px solid {c.border_strong};
    border-radius: 6px; padding: 6px 16px; min-height: 18px; font-weight: 500;
}}
QPushButton:hover {{ background: {c.hover_bg}; }}
QPushButton:pressed {{ background: {c.pressed_bg}; }}
QPushButton:focus {{ border-color: {c.focus}; }}
QPushButton:default, QPushButton[primary="true"] {{
    background: {c.accent}; color: {c.on_accent}; border-color: {c.accent};
}}
QPushButton:default:hover, QPushButton[primary="true"]:hover {{
    background: {c.accent_hover}; border-color: {c.accent_hover};
}}
QPushButton:default:focus {{ border-color: {c.text}; }}
QPushButton:disabled {{
    color: {c.text_disabled}; border-color: {c.border}; background: transparent;
}}

QLineEdit, QComboBox, QSpinBox {{
    background: {c.editor_bg}; color: {c.text}; border: 1px solid {c.border_strong};
    border-radius: 6px; padding: 4px 8px; min-height: 20px;
    selection-background-color: {c.selection};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {c.focus}; }}
QComboBox::drop-down {{ width: 20px; border: none; }}
QComboBox QAbstractItemView {{
    background: {c.elevated_bg}; border: 1px solid {c.border_strong};
    selection-background-color: {c.menu_selected_bg}; selection-color: {c.text};
}}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle {{
    background: {c.scroll_handle}; border-radius: 3px; margin: 3px;
    min-height: 32px; min-width: 32px;
}}
QScrollBar::handle:hover {{ background: {c.scroll_handle_hover}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QToolTip {{
    background: {c.elevated_bg}; color: {c.text}; border: 1px solid {c.border_strong};
    padding: 4px 8px; font-size: 12px;
}}
"""
