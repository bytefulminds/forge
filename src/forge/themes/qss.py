"""Generate the Qt stylesheet for a theme (see the UI spec for the rationale)."""

from __future__ import annotations

from forge.themes.theme import Theme


def build_stylesheet(theme: Theme, arrows: dict[str, str] | None = None) -> str:
    """Stylesheet for ``theme``.

    ``arrows`` maps "up" and "down" to small SVG files (made by the UI layer)
    for spin box and combo box arrows; QSS cannot draw them itself once those
    controls are styled.
    """
    c = theme
    up = (arrows or {}).get("up", "")
    down = (arrows or {}).get("down", "")
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
QWidget#languagePicker QListView {{
    background: transparent; border: none; outline: 0; color: {c.text};
}}
QWidget#languagePicker QListView::item {{ padding: 5px 10px; border-radius: 6px; }}
QWidget#languagePicker QListView::item:hover {{ background: {c.hover_bg}; }}
QWidget#languagePicker QListView::item:selected {{
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
QToolButton#statusProblem {{
    color: {c.error}; background: transparent; border: none; border-radius: 6px;
    padding: 2px 8px; font-size: 12px;
}}
QToolButton#statusProblem:hover {{ background: {c.hover_bg}; }}
QToolButton#statusSegment::menu-indicator {{ image: none; width: 0; }}

QDockWidget {{ color: {c.text_muted}; font-size: 12px; }}
QDockWidget::title {{
    background: {c.chrome_bg}; padding: 6px 10px; border-top: 1px solid {c.border};
}}
QDockWidget::close-button, QDockWidget::float-button {{
    border: none; background: transparent; padding: 2px; border-radius: 4px;
}}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {{ background: {c.hover_bg}; }}
QWidget#toolPanel {{ background: {c.elevated_bg}; }}
QTreeWidget, QListWidget {{
    background: {c.editor_bg}; color: {c.text}; border: 1px solid {c.border};
    border-radius: 6px; outline: 0;
}}
QTreeWidget::item, QListWidget::item {{ padding: 2px 4px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {c.menu_selected_bg}; color: {c.text};
}}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {c.hover_bg}; }}
QHeaderView::section {{
    background: {c.chrome_bg}; color: {c.text_muted}; border: none;
    border-bottom: 1px solid {c.border}; padding: 4px 8px; font-size: 12px;
}}
QLabel#compareTitle {{ color: {c.text_muted}; font-size: 12px; }}
QSplitter::handle {{ background: {c.border}; width: 1px; }}

QWidget#tabCorner {{ background: {c.chrome_bg}; }}
QWidget#documentToolbar {{
    background: {c.editor_bg}; border-bottom: 1px solid {c.border};
}}
QToolButton#docToolButton {{
    background: transparent; border: none; border-radius: 5px;
    padding: 3px; min-width: 18px; min-height: 18px;
}}
QToolButton#docToolButton:hover {{ background: {c.hover_bg}; }}
QToolButton#docToolButton:pressed {{ background: {c.menu_selected_bg}; }}
QToolButton#docToolButton:checked {{ background: {c.menu_selected_bg}; }}
QFrame#docToolSeparator {{ background: {c.border}; margin: 0 4px; }}
QTextBrowser#markdownPreview {{ background: {c.editor_bg}; border: none; }}
QTableView#csvTable {{
    background: {c.editor_bg}; alternate-background-color: {c.caret_line};
    gridline-color: {c.border}; border: none; color: {c.text};
    selection-background-color: {c.selection}; selection-color: {c.text};
}}
QTableView#csvTable QTableCornerButton::section {{ background: {c.chrome_bg}; border: none; }}
QTreeWidget#jsonTree {{ border: none; border-radius: 0; }}
QLabel#previewMessage {{ color: {c.text_muted}; background: {c.editor_bg}; }}

QFrame#findBar {{ background: {c.elevated_bg}; border-top: 1px solid {c.border}; }}
QFrame#findBar QLineEdit[invalid="true"] {{ border-color: {c.error}; }}
QToolButton#findOption, QToolButton#findNav {{
    border: none; border-radius: 4px; background: transparent; color: {c.text_muted};
    min-width: 26px; min-height: 24px; padding: 0 4px;
}}
QToolButton#findOption {{ font-family: "JetBrains Mono"; font-size: 12px; }}
QToolButton#findNav {{ font-size: 14px; }}
QToolButton#findOption:hover, QToolButton#findNav:hover {{
    background: {c.hover_bg}; color: {c.text};
}}
QToolButton#findOption:checked {{
    background: {c.menu_selected_bg}; color: {c.text}; border: 1px solid {c.accent};
}}
QLabel#findCount {{ color: {c.text_muted}; font-size: 12px; }}

QFrame#noticeBar {{
    background: {c.elevated_bg}; border-top: 1px solid {c.border};
    border-left: 3px solid {c.accent};
}}
QFrame#noticeBar[kind="warning"] {{ border-left: 3px solid {c.warning}; }}
QFrame#noticeBar QLabel {{ color: {c.text}; }}
QToolButton#noticeDismiss {{
    border: none; border-radius: 4px; background: transparent; color: {c.text_muted};
    font-size: 14px; min-width: 22px; min-height: 22px;
}}
QToolButton#noticeDismiss:hover {{ background: {c.hover_bg}; color: {c.text}; }}

QLabel#prefSection {{
    color: {c.text_muted}; font-size: 12px; font-weight: 600; padding-top: 8px;
}}
QLabel#prefNote {{ color: {c.warning}; font-size: 12px; }}
QCheckBox {{ spacing: 8px; }}

QDialog, QMessageBox {{ background: {c.elevated_bg}; }}
QFrame#dialogFrame {{ background: {c.elevated_bg}; border: 1px solid {c.border_strong}; }}
QWidget#dialogTitleBar {{ background: {c.chrome_bg}; border-bottom: 1px solid {c.border}; }}
QLabel#dialogTitle {{ color: {c.text_muted}; font-size: 12px; font-weight: 600; }}
QWidget#dialogBody {{ background: {c.elevated_bg}; }}
QFileDialog {{ background: {c.elevated_bg}; }}
QFileDialog QListView, QFileDialog QTreeView {{
    background: {c.editor_bg}; color: {c.text}; border: 1px solid {c.border};
    border-radius: 6px; outline: none;
    selection-background-color: {c.menu_selected_bg}; selection-color: {c.text};
}}
QFileDialog QListView#sidebar {{ background: {c.chrome_bg}; padding: 4px; }}
QFileDialog QListView::item, QFileDialog QTreeView::item {{ padding: 3px 4px; }}
QFileDialog QListView::item:hover, QFileDialog QTreeView::item:hover {{
    background: {c.hover_bg};
}}
QFileDialog QListView::item:selected, QFileDialog QTreeView::item:selected {{
    background: {c.menu_selected_bg}; color: {c.text};
}}
QFileDialog QToolButton {{
    background: transparent; border: none; border-radius: 5px; padding: 3px;
}}
QFileDialog QToolButton:hover {{ background: {c.hover_bg}; }}
QFileDialog QLabel {{ color: {c.text_muted}; }}
QSizeGrip {{ width: 12px; height: 12px; }}
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
QComboBox::drop-down {{ width: 22px; border: none; }}
QComboBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}
QSpinBox {{ padding-right: 22px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; background: transparent;
}}
QSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {c.hover_bg}; }}
QSpinBox::up-arrow {{ image: url("{up}"); width: 8px; height: 8px; }}
QSpinBox::down-arrow {{ image: url("{down}"); width: 8px; height: 8px; }}
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
