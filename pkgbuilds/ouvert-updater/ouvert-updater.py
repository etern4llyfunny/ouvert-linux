#!/usr/bin/env python3
"""Ouvert Updater — лёгкая утилита проверки и установки обновлений Ouvert Linux."""
import locale
import os
import pty
import select
import subprocess
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPauseAnimation,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

IS_RU = (locale.getlocale()[0] or os.environ.get("LANG", "")).lower().startswith("ru")

T = {
    "title": ("Обновление Ouvert Linux", "Ouvert Linux Updater"),
    "subtitle": (
        "Рекомендуется регулярно обновлять систему для стабильности и безопасности.",
        "Regular updates keep your system stable and secure.",
    ),
    "btn_check": ("Проверить обновления", "Check for updates"),
    "btn_update": ("Обновить", "Update"),
    "btn_cancel": ("Отмена", "Cancel"),
    "checking": ("Проверка обновлений…", "Checking for updates…"),
    "up_to_date": ("Система уже обновлена.", "Your system is up to date."),
    "avail": ("Доступно обновлений: {n}", "Updates available: {n}"),
    "check_err": (
        "Не удалось проверить обновления (нет сети или ошибка pacman).",
        "Failed to check updates (offline or pacman error).",
    ),
    "updating": ("Идёт обновление системы…", "Updating system…"),
    "cancelling": ("Отмена обновления…", "Cancelling update…"),
    "done": ("Обновление успешно завершено.", "Update completed successfully."),
    "cancelled": ("Обновление отменено.", "Update cancelled."),
    "failed": ("Обновление завершилось с ошибкой (код {code}).", "Update failed (exit code {code})."),
}


def tr(key: str, **kw) -> str:
    ru, en = T[key]
    return (ru if IS_RU else en).format(**kw)


class CheckWorker(QThread):
    finished_check = Signal(int, str)

    def run(self) -> None:
        try:
            r = subprocess.run(["checkupdates"], capture_output=True, text=True, timeout=120)
            self.finished_check.emit(r.returncode, (r.stdout or "").strip())
        except Exception as e:
            self.finished_check.emit(1, str(e))


class UpdateWorker(QThread):
    output = Signal(str)
    done = Signal(int, bool)

    def __init__(self) -> None:
        super().__init__()
        self._master_fd: int | None = None
        self._proc: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, b"\x03")
            except OSError:
                pass
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self) -> None:
        master, slave = pty.openpty()
        self._master_fd = master
        try:
            self._proc = subprocess.Popen(
                ["pkexec", "pacman", "-Syu", "--noconfirm"],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                close_fds=True,
            )
            os.close(slave)
            while True:
                rlist, _, _ = select.select([master], [], [], 0.2)
                if rlist:
                    try:
                        chunk = os.read(master, 4096)
                        if not chunk:
                            break
                        self.output.emit(chunk.decode("utf-8", errors="replace"))
                    except OSError:
                        break
                elif self._proc.poll() is not None:
                    break
            code = self._proc.wait()
            self.done.emit(code, self._cancelled)
        except Exception as e:
            self.output.emit(f"\n{e}\n")
            self.done.emit(1, self._cancelled)
        finally:
            self._master_fd = None
            try:
                os.close(master)
            except OSError:
                pass


class UpdaterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("title"))
        self.resize(560, 400)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #141820; color: #e6ecf5; font-size: 14px; }
            QLabel#title { font-size: 20px; font-weight: 700; color: #4fa3ff; }
            QLabel#muted { color: #8c99ad; font-size: 13px; }
            QPushButton {
                background: #232b38; color: #e6ecf5; border: 1px solid #323d4f;
                border-radius: 8px; padding: 10px 18px; font-weight: 600;
            }
            QPushButton:hover { background: #2c3647; }
            QPushButton:disabled { color: #637085; background: #1a202b; }
            QPushButton#primary { background: #2f7fe6; border-color: #2f7fe6; color: #ffffff; }
            QPushButton#primary:hover { background: #3b8bf0; }
            QPushButton#primary:disabled { background: #2b313c; border-color: #3a4252; color: #7a8494; }
            QPushButton#danger { background: #e04f3e; border-color: #e04f3e; color: #ffffff; }
            QPushButton#danger:hover { background: #ef5e4d; }
            QPushButton#danger:disabled { background: #2b313c; border-color: #3a4252; color: #7a8494; }
            QPlainTextEdit {
                background: #0d1016; color: #cfd8e6; border: 1px solid #263042;
                border-radius: 8px; font-family: monospace; font-size: 12px;
            }
        """)

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(12)

        # Верхний спейсер: в исходном состоянии центрирует блок, при появлении списка сжимается до 0
        self.top_spacer = QWidget()
        self.top_spacer.setMaximumHeight(96)
        self.top_spacer.setMinimumHeight(96)
        lay.addWidget(self.top_spacer)

        lbl_title = QLabel(tr("title"))
        lbl_title.setObjectName("title")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_title)

        lbl_sub = QLabel(tr("subtitle"))
        lbl_sub.setObjectName("muted")
        lbl_sub.setWordWrap(True)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_sub)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.btn_check = QPushButton(tr("btn_check"))
        self.btn_check.clicked.connect(self._start_check)
        btn_row.addWidget(self.btn_check)

        self.btn_update = QPushButton(tr("btn_update"))
        self.btn_update.setObjectName("primary")
        self.btn_update.setEnabled(False)
        self.btn_update.clicked.connect(self._start_update)
        btn_row.addWidget(self.btn_update)

        self.btn_cancel = QPushButton(tr("btn_cancel"))
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.clicked.connect(self._cancel_update)
        self._cancel_target_w = max(96, self.btn_cancel.sizeHint().width() + 8)
        self.btn_cancel.setMaximumWidth(0)
        self.btn_cancel.hide()
        self._cancel_fx = QGraphicsOpacityEffect(self.btn_cancel)
        self._cancel_fx.setOpacity(0.0)
        self.btn_cancel.setGraphicsEffect(self._cancel_fx)
        btn_row.addWidget(self.btn_cancel)

        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(0)
        self.log.hide()
        self._log_fx = QGraphicsOpacityEffect(self.log)
        self._log_fx.setOpacity(0.0)
        self.log.setGraphicsEffect(self._log_fx)
        lay.addWidget(self.log, 1)

        self._anim: QParallelAnimationGroup | None = None
        self._expanded = False
        self._check_worker: CheckWorker | None = None
        self._update_worker: UpdateWorker | None = None

    def _stop_anim(self) -> None:
        if self._anim is not None:
            self._anim.stop()
            self._anim.deleteLater()
            self._anim = None

    def _animate_layout(self, expand_log: bool, show_cancel: bool) -> None:
        self._stop_anim()
        group = QParallelAnimationGroup(self)

        # 1. Плавный переезд шапки и кнопок наверх (или обратно в центр)
        spacer_target = 0 if expand_log else 96
        for prop in (b"maximumHeight", b"minimumHeight"):
            a = QPropertyAnimation(self.top_spacer, prop)
            a.setDuration(580)
            a.setStartValue(self.top_spacer.maximumHeight())
            a.setEndValue(spacer_target)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(a)

        # 2. Плавное появление / скрытие красной кнопки «Отмена»
        if show_cancel:
            self.btn_cancel.show()
            seq_c = QSequentialAnimationGroup()
            if not self._expanded and expand_log:
                seq_c.addAnimation(QPauseAnimation(180))
            par_c = QParallelAnimationGroup()
            a_w = QPropertyAnimation(self.btn_cancel, b"maximumWidth")
            a_w.setDuration(480)
            a_w.setStartValue(self.btn_cancel.maximumWidth())
            a_w.setEndValue(self._cancel_target_w)
            a_w.setEasingCurve(QEasingCurve.Type.OutCubic)
            a_o = QPropertyAnimation(self._cancel_fx, b"opacity")
            a_o.setDuration(480)
            a_o.setStartValue(self._cancel_fx.opacity())
            a_o.setEndValue(1.0)
            a_o.setEasingCurve(QEasingCurve.Type.OutCubic)
            par_c.addAnimation(a_w)
            par_c.addAnimation(a_o)
            seq_c.addAnimation(par_c)
            group.addAnimation(seq_c)
        elif self.btn_cancel.isVisible():
            par_c = QParallelAnimationGroup()
            a_w = QPropertyAnimation(self.btn_cancel, b"maximumWidth")
            a_w.setDuration(380)
            a_w.setStartValue(self.btn_cancel.maximumWidth())
            a_w.setEndValue(0)
            a_w.setEasingCurve(QEasingCurve.Type.OutCubic)
            a_o = QPropertyAnimation(self._cancel_fx, b"opacity")
            a_o.setDuration(340)
            a_o.setStartValue(self._cancel_fx.opacity())
            a_o.setEndValue(0.0)
            a_o.setEasingCurve(QEasingCurve.Type.OutCubic)
            par_c.addAnimation(a_w)
            par_c.addAnimation(a_o)
            group.addAnimation(par_c)

        # 3. Плавное раскрытие и проявление списка пакетов
        if expand_log:
            self.log.show()
            target_h = max(180, self.height() - 170)
            cur_h = self.log.height() if self._expanded else 0
            seq_l = QSequentialAnimationGroup()
            if not self._expanded:
                seq_l.addAnimation(QPauseAnimation(240))
            par_l = QParallelAnimationGroup()
            a_lh = QPropertyAnimation(self.log, b"maximumHeight")
            a_lh.setDuration(620)
            a_lh.setStartValue(cur_h)
            a_lh.setEndValue(target_h)
            a_lh.setEasingCurve(QEasingCurve.Type.OutCubic)
            a_lo = QPropertyAnimation(self._log_fx, b"opacity")
            a_lo.setDuration(620)
            a_lo.setStartValue(self._log_fx.opacity())
            a_lo.setEndValue(1.0)
            a_lo.setEasingCurve(QEasingCurve.Type.OutCubic)
            par_l.addAnimation(a_lh)
            par_l.addAnimation(a_lo)
            seq_l.addAnimation(par_l)
            group.addAnimation(seq_l)
        elif self.log.isVisible():
            par_l = QParallelAnimationGroup()
            a_lh = QPropertyAnimation(self.log, b"maximumHeight")
            a_lh.setDuration(420)
            a_lh.setStartValue(self.log.height())
            a_lh.setEndValue(0)
            a_lh.setEasingCurve(QEasingCurve.Type.OutCubic)
            a_lo = QPropertyAnimation(self._log_fx, b"opacity")
            a_lo.setDuration(360)
            a_lo.setStartValue(self._log_fx.opacity())
            a_lo.setEndValue(0.0)
            a_lo.setEasingCurve(QEasingCurve.Type.OutCubic)
            par_l.addAnimation(a_lh)
            par_l.addAnimation(a_lo)
            group.addAnimation(par_l)

        def _finish() -> None:
            if expand_log:
                self.log.setMaximumHeight(16777215)
            else:
                self.log.hide()
            if not show_cancel:
                self.btn_cancel.hide()
            self._expanded = expand_log

        group.finished.connect(_finish)
        self._anim = group
        group.start()

    def _set_busy(self, busy: bool, show_cancel: bool = False, can_update: bool = False, expand_log: bool = False) -> None:
        self.btn_check.setEnabled(not busy)
        self.btn_update.setEnabled((not busy) and can_update)
        self.btn_cancel.setEnabled(show_cancel)
        self._animate_layout(expand_log=expand_log, show_cancel=show_cancel)

    def _start_check(self) -> None:
        self._set_busy(True, show_cancel=False, can_update=False, expand_log=False)
        self.status.setText(tr("checking"))
        self.log.clear()
        self._check_worker = CheckWorker()
        self._check_worker.finished_check.connect(self._on_check_done)
        self._check_worker.start()

    def _on_check_done(self, code: int, out: str) -> None:
        if code == 2 or (code == 0 and not out):
            self._set_busy(False, show_cancel=False, can_update=False, expand_log=False)
            self.status.setText(tr("up_to_date"))
        elif code == 0:
            lines = [ln for ln in out.splitlines() if ln.strip()]
            self.log.setPlainText(out)
            self.status.setText(tr("avail", n=len(lines)))
            self._set_busy(False, show_cancel=True, can_update=True, expand_log=True)
        else:
            self.status.setText(tr("check_err"))
            if out:
                self.log.setPlainText(out)
                self._set_busy(False, show_cancel=False, can_update=False, expand_log=True)
            else:
                self._set_busy(False, show_cancel=False, can_update=False, expand_log=False)

    def _start_update(self) -> None:
        self.log.clear()
        self.status.setText(tr("updating"))
        self._set_busy(True, show_cancel=True, can_update=False, expand_log=True)
        self._update_worker = UpdateWorker()
        self._update_worker.output.connect(self._append_log)
        self._update_worker.done.connect(self._on_update_done)
        self._update_worker.start()

    def _cancel_update(self) -> None:
        if self._update_worker and self._update_worker.isRunning():
            self.btn_cancel.setEnabled(False)
            self.status.setText(tr("cancelling"))
            self._update_worker.cancel()
        else:
            self.status.setText("")
            self._set_busy(False, show_cancel=False, can_update=False, expand_log=False)

    def _append_log(self, text: str) -> None:
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.ensureCursorVisible()

    def _on_update_done(self, code: int, cancelled: bool) -> None:
        if cancelled:
            self._set_busy(False, show_cancel=True, can_update=True, expand_log=True)
            self.status.setText(tr("cancelled"))
        elif code == 0:
            self._set_busy(False, show_cancel=False, can_update=False, expand_log=True)
            self.status.setText(tr("done"))
        else:
            self._set_busy(False, show_cancel=True, can_update=True, expand_log=True)
            self.status.setText(tr("failed", code=code))


def main() -> int:
    app = QApplication(sys.argv)
    w = UpdaterWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
