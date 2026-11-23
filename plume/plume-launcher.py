#!/usr/bin/env python3
import configparser, os, shlex, signal, subprocess, sys
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget
)

PID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "plume-launcher.pid"


def toggle_existing() -> bool:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink(missing_ok=True)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)
    return False


def load_apps() -> list[tuple[str, str, str]]:
    dirs = [
        Path.home() / ".local/share/applications",
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
    ]
    seen = set()
    apps = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            if f.name in seen:
                continue
            cp = configparser.ConfigParser(interpolation=None)
            try:
                cp.read(f, encoding="utf-8")
            except Exception:
                continue
            if "Desktop Entry" not in cp:
                continue
            e = cp["Desktop Entry"]
            if e.get("Type") != "Application":
                continue
            if e.get("NoDisplay", "").lower() == "true" or e.get("Hidden", "").lower() == "true":
                continue
            name = e.get("Name[ru]") or e.get("Name")
            exec_cmd = e.get("Exec")
            icon = e.get("Icon", "")
            if not name or not exec_cmd:
                continue
            seen.add(f.name)
            apps.append((name, exec_cmd, icon))
    apps.sort(key=lambda x: x[0].lower())
    return apps


def clean_exec(cmd: str) -> list[str]:
    parts = [p for p in shlex.split(cmd) if not p.startswith("%")]
    return parts



ICON_CACHE: dict[str, str] = {}


def build_icon_cache() -> None:
    if ICON_CACHE:
        return
    roots = [
        Path.home() / ".local/share/icons",
        Path("/usr/share/pixmaps"),
        Path("/usr/share/icons/hicolor/scalable/apps"),
        Path("/usr/share/icons/hicolor/256x256/apps"),
        Path("/usr/share/icons/hicolor/128x128/apps"),
        Path("/usr/share/icons/hicolor/64x64/apps"),
        Path("/usr/share/icons/hicolor/48x48/apps"),
    ]
    for r in roots:
        if not r.is_dir():
            continue
        for f in r.rglob("*") if r.name == "icons" else r.iterdir():
            if f.is_file() and f.suffix.lower() in (".svg", ".png", ".xpm"):
                ICON_CACHE.setdefault(f.stem, str(f))


def resolve_icon(icon_name: str) -> QIcon:
    if not icon_name:
        return QIcon()
    if Path(icon_name).is_file():
        return QIcon(icon_name)
    ic = QIcon.fromTheme(icon_name)
    if not ic.isNull():
        return ic
    build_icon_cache()
    hit = ICON_CACHE.get(icon_name) or ICON_CACHE.get(Path(icon_name).stem)
    return QIcon(hit) if hit else QIcon()


class PlumeLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("plume-launcher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(340, 440)

        self.apps = load_apps()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск приложений…")
        self.search.textChanged.connect(self.filter_list)
        self.search.returnPressed.connect(self.launch_current)

        self.list = QListWidget()
        self.list.setIconSize(QSize(22, 22))
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.itemClicked.connect(self.launch_item)
        self.list.itemActivated.connect(self.launch_item)

        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)

        self.setStyleSheet("""
            QWidget {
                background: #171a21;
                color: #edf0f5;
                font-family: "Onest", "Sora", sans-serif;
                font-size: 13px;
            }
            PlumeLauncher {
                border: 1px solid #2f7fe6;
                border-radius: 6px;
            }
            QLineEdit {
                background: #1c212b;
                border: 1px solid #2b3342;
                border-radius: 6px;
                padding: 8px 10px;
                color: #edf0f5;
            }
            QLineEdit:focus {
                border-color: #2f7fe6;
            }
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 7px 8px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: #202633;
            }
            QListWidget::item:selected {
                background: #252b37;
                color: #ffffff;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #2b3342;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self.filter_list("")
        self.search.setFocus()

    def filter_list(self, text: str):
        q = text.strip().lower()
        self.list.clear()
        for name, cmd, icon_name in self.apps:
            if q and q not in name.lower():
                continue
            item = QListWidgetItem(name)
            if icon_name:
                ic = resolve_icon(icon_name)
                if not ic.isNull():
                    item.setIcon(ic)
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def launch_current(self):
        item = self.list.currentItem()
        if item:
            self.launch_item(item)

    def launch_item(self, item: QListWidgetItem):
        cmd = item.data(Qt.ItemDataRole.UserRole)
        parts = clean_exec(cmd)
        if parts:
            subprocess.Popen(parts, start_new_session=True)
        QApplication.quit()

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            QApplication.quit()
        elif k in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            row = self.list.currentRow()
            step = 1 if k == Qt.Key.Key_Down else -1
            nxt = max(0, min(self.list.count() - 1, row + step))
            self.list.setCurrentRow(nxt)
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow():
            QApplication.quit()
        super().changeEvent(event)


def main():
    if toggle_existing():
        return
    PID_FILE.write_text(str(os.getpid()))
    try:
        app = QApplication(sys.argv)
        app.setDesktopFileName("plume-launcher")
        if not QIcon.themeName():
            for th in ("Papirus-Dark", "Papirus", "breeze-dark", "breeze", "Adwaita", "hicolor"):
                if (Path("/usr/share/icons") / th).is_dir():
                    QIcon.setThemeName(th)
                    break
        w = PlumeLauncher()
        w.show()
        app.exec()
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
