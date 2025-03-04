"""
MIT License

Copyright (c) 2024-2025 toxi360

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


import os
import json
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QFont
from PySide6.QtCore import Qt
from ui import MainWindow
from download_thread import DownloadThread
from notifications import send_notification, send_error

def create_tray_icon(text):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setPen(Qt.black)
    painter.setFont(QFont("Segoe UI Emoji", 48))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)

def load_history():
    try:
        with open("history.json", "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []
    return history

def save_history(history):
    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

def main():
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    tray = QSystemTrayIcon(create_tray_icon("🔔"), window)
    tray_menu = QMenu()
    show_action = QAction("Show", window)
    exit_action = QAction("Exit", window)
    show_action.triggered.connect(window.showNormal)
    exit_action.triggered.connect(app.quit)
    tray_menu.addAction(show_action)
    tray_menu.addAction(exit_action)
    tray.setContextMenu(tray_menu)
    tray.show()
    history = load_history()
    window.download_history = history
    window.update_history_table(history)
    window.download_btn.clicked.connect(lambda: start_download(window, tray))
    window.pause_btn.clicked.connect(lambda: pause_download(window))
    window.resume_btn.clicked.connect(lambda: resume_download(window))
    window.cancel_btn.clicked.connect(lambda: cancel_download(window))
    window.show()
    sys.exit(app.exec())

def start_download(window, tray):
    url = window.url_input.text().strip()
    output_folder = window.folder_input.text().strip()
    if not url or not output_folder:
        QMessageBox.warning(window, "Missing Information", "Please specify both URL and folder.")
        return
    mode = window.mode_combo.currentText()
    performance = window.performance_combo.currentText()
    parts = 1 if mode == "Single Thread" else (os.cpu_count() if performance == "HPD (High Performance)" else 4)
    iso_mode = window.iso_checkbox.isChecked()
    proxy = None
    download_thread = DownloadThread(url, output_folder, parts, (performance == "HPD (High Performance)"), iso_mode, proxy)
    window.download_thread = download_thread
    download_thread.progress_signal.connect(window.overall_progress_bar.setValue)
    download_thread.speed_signal.connect(lambda sp: window.speed_label.setText(f"Speed: {sp:.2f} MB/s"))
    download_thread.time_signal.connect(lambda rt: window.time_label.setText(f"Time Left: {rt:.2f} s"))
    download_thread.size_signal.connect(lambda s: window.size_label.setText(f"Size: {s / (1024*1024):.2f} MB"))
    download_thread.part_count_signal.connect(lambda c: window.parts_label.setText(f"Parts: {c}"))
    download_thread.error_signal.connect(lambda err: QMessageBox.critical(window, "Error", err))
    download_thread.start()
    entry = {
        "url": url,
        "output_folder": output_folder,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "performance": performance,
        "parts": parts
    }
    window.download_history.append(entry)
    save_history(window.download_history)
    window.update_history_table(window.download_history)
    download_thread.progress_signal.connect(lambda p: p == 100 and send_notification(tray, "Download", "Download completed successfully."))

def pause_download(window):
    if window.download_thread and window.download_thread.isRunning():
        window.download_thread.pause = True
    else:
        QMessageBox.warning(window, "Warning", "No active download.")

def resume_download(window):
    if window.download_thread and window.download_thread.isRunning():
        window.download_thread.pause = False
    else:
        QMessageBox.warning(window, "Warning", "No paused download.")

def cancel_download(window):
    if window.download_thread and window.download_thread.isRunning():
        window.download_thread.cancel = True
        QMessageBox.information(window, "Cancelled", "Download cancelled.")
        window.overall_progress_bar.setValue(0)
        window.size_label.setText("Size: -")
        window.parts_label.setText("Parts: -")
        window.speed_label.setText("Speed: -")
        window.time_label.setText("Time Left: -")
    else:
        QMessageBox.warning(window, "Warning", "No active download.")

if __name__ == "__main__":
    main()
