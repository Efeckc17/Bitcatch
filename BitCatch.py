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
import requests
import threading
import time
import json
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit, QProgressBar, QFrame, QTableWidget, QTableWidgetItem, QComboBox, QFileDialog, QMessageBox, QStackedWidget, QFormLayout, QCheckBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal


class DownloadThread(QThread):
    progress_signal = pyqtSignal(int)
    speed_signal = pyqtSignal(float)
    time_signal = pyqtSignal(float)
    size_signal = pyqtSignal(int)
    part_count_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)
    def __init__(self, url, output_folder, num_parts=1, hpd_mode=False, iso_mode=False):
        super().__init__()
        self.url = url
        self.output_folder = output_folder
        self.num_parts = num_parts
        self.hpd_mode = hpd_mode
        self.iso_mode = iso_mode
        self.progress = [0] * num_parts
        self.total_size = 0
        self.pause = False
        self.cancel = False
    def run(self):
        try:
            head = requests.head(self.url, timeout=10)
            head.raise_for_status()
            cl = head.headers.get("content-length")
            if cl and cl.isdigit():
                self.total_size = int(cl)
            self.size_signal.emit(self.total_size)
        except Exception as e:
            try:
                r = requests.get(self.url, stream=True, timeout=10)
                r.raise_for_status()
                cl = r.headers.get("content-length")
                if cl and cl.isdigit():
                    self.total_size = int(cl)
                self.size_signal.emit(self.total_size)
            except Exception as e2:
                self.error_signal.emit(str(e2))
                return
        self.start_time = time.time()
        if self.num_parts < 2 or self.total_size <= 0:
            self.download_single()
            if self.iso_mode and self.total_size > 0 and not self.cancel:
                filename = os.path.join(self.output_folder, self.url.split("/")[-1])
                try:
                    if os.path.getsize(filename) != self.total_size:
                        os.remove(filename)
                        self.error_signal.emit("ISO file corrupted: downloaded size does not match expected size")
                except Exception as e:
                    self.error_signal.emit("Error checking ISO file integrity: " + str(e))
        else:
            self.download_multi()
    def download_single(self):
        try:
            r = requests.get(self.url, stream=True, timeout=10)
            r.raise_for_status()
        except Exception as e:
            self.error_signal.emit(str(e))
            return
        filename = os.path.join(self.output_folder, self.url.split("/")[-1])
        with open(filename, "wb") as f:
            downloaded = 0
            cs = 131072 if self.hpd_mode else 65536
            for chunk in r.iter_content(cs):
                if self.cancel:
                    break
                while self.pause:
                    time.sleep(0.1)
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    self.progress[0] = downloaded
                    self.emit_overall()
    def download_multi(self):
        filename = os.path.join(self.output_folder, self.url.split("/")[-1].split(".")[0])
        ps = self.total_size // self.num_parts if self.total_size > 0 else 0
        self.part_count_signal.emit(self.num_parts)
        threads = []
        for i in range(self.num_parts):
            st = ps * i
            en = (st + ps - 1) if i < (self.num_parts - 1) else None
            t = threading.Thread(target=self.part_worker, args=(i, st, en, filename))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        if not self.cancel:
            self.merge_parts(filename)
    def part_worker(self, idx, start, end, filename):
        hs = {}
        if end is not None:
            hs["Range"] = f"bytes={start}-{end}"
        try:
            r = requests.get(self.url, headers=hs, stream=True, timeout=10)
            r.raise_for_status()
        except Exception as e:
            self.error_signal.emit(str(e))
            return
        ppath = f"{filename}.part{idx}"
        cs = 131072 if self.hpd_mode else 65536
        downloaded = 0
        with open(ppath, "wb") as f:
            for chunk in r.iter_content(cs):
                if self.cancel:
                    break
                while self.pause:
                    time.sleep(0.1)
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    self.progress[idx] = downloaded
                    self.emit_overall()
        if self.cancel and os.path.exists(ppath):
            os.remove(ppath)
    def emit_overall(self):
        td = sum(self.progress)
        et = time.time() - self.start_time
        sp = td / 1048576 / et if et > 0 else 0
        rt = (self.total_size - td) / (sp * 1048576) if sp > 0 and self.total_size > 0 else 0
        pp = int(td / self.total_size * 100) if self.total_size > 0 else 0
        self.progress_signal.emit(pp)
        self.speed_signal.emit(sp)
        self.time_signal.emit(rt)
    def merge_parts(self, filename):
        fn = filename
        ext = self.url.split("/")[-1].split(".")[-1]
        if ext:
            fn += f".{ext}"
        with open(fn, "wb") as out:
            for i in range(self.num_parts):
                p = f"{filename}.part{i}"
                if os.path.exists(p):
                    with open(p, "rb") as rd:
                        out.write(rd.read())
                    os.remove(p)
        if self.iso_mode and self.total_size > 0 and not self.cancel:
            try:
                if os.path.getsize(fn) != self.total_size:
                    os.remove(fn)
                    self.error_signal.emit("ISO file corrupted: downloaded size does not match expected size")
            except Exception as e:
                self.error_signal.emit("Error checking ISO file integrity: " + str(e))


class BitCatch2_0(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BitCatch2.0 Downloader")
        self.setGeometry(100, 80, 1200, 700)
        self.download_history = []
        self.load_history()
        self.download_thread = None
        self.download_mode = "Single Thread"
        self.performance_mode = "Normal"
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QHBoxLayout(central)
        self.sidebar = self.create_sidebar()
        self.main_layout.addWidget(self.sidebar)
        self.right_content = QWidget()
        self.right_layout = QVBoxLayout(self.right_content)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.header = self.create_header()
        self.right_layout.addWidget(self.header, stretch=0)
        self.stacked_widget = QStackedWidget()
        self.right_layout.addWidget(self.stacked_widget, stretch=1)
        self.main_layout.addWidget(self.right_content)
        self.downloader_page = self.create_downloader_page()
        self.history_page = self.create_history_page()
        self.stacked_widget.addWidget(self.downloader_page)
        self.stacked_widget.addWidget(self.history_page)
        self.apply_theme("Dark Default")
    def create_sidebar(self):
        frame = QFrame()
        frame.setObjectName("SidebarFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        title = QLabel("BITCATCH 2.0")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignCenter)
        btn1 = QPushButton("Downloader")
        btn1.setObjectName("SidebarButton")
        btn1.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        btn2 = QPushButton("History")
        btn2.setObjectName("SidebarButton")
        btn2.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        layout.addSpacing(30)
        layout.addWidget(title)
        layout.addSpacing(30)
        layout.addWidget(btn1)
        layout.addWidget(btn2)
        layout.addStretch()
        return frame
    def create_header(self):
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        hlayout = QHBoxLayout(frame)
        hlayout.setContentsMargins(10, 5, 10, 5)
        logo = QLabel("BitCatch2.0 - Modern")
        logo.setObjectName("HeaderLogo")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Default", "Dark Purple", "Dark Red", "Dark Green", "Dark Blue"])
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        hlayout.addWidget(logo, alignment=Qt.AlignVCenter)
        hlayout.addStretch()
        hlayout.addWidget(self.theme_combo, alignment=Qt.AlignRight)
        return frame
    def create_downloader_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        form = QFormLayout()
        self.url_input = QLineEdit()
        self.folder_input = QLineEdit()
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.select_folder)
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.browse_button)
        form.addRow("Download URL:", self.url_input)
        form.addRow("Output Folder:", folder_layout)
        layout.addLayout(form)
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Single Thread", "Multi-part Download"])
        self.mode_combo.currentTextChanged.connect(self.set_download_mode)
        self.performance_combo = QComboBox()
        self.performance_combo.addItems(["Normal", "HPD (High Performance)"])
        self.performance_combo.currentTextChanged.connect(self.set_performance_mode)
        mode_layout.addWidget(QLabel("Download Mode:"))
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addSpacing(30)
        mode_layout.addWidget(QLabel("Performance Mode:"))
        mode_layout.addWidget(self.performance_combo)
        layout.addLayout(mode_layout)
        self.iso_checkbox = QCheckBox("ISO Mode")
        layout.addWidget(self.iso_checkbox)
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_download)
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.clicked.connect(self.resume_download)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_download)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setTextVisible(True)
        layout.addWidget(self.overall_progress_bar)
        self.size_label = QLabel("File Size: - ")
        self.parts_label = QLabel("Parts: - ")
        self.speed_label = QLabel("Speed: - ")
        self.time_label = QLabel("Time Remaining: - ")
        layout.addWidget(self.size_label)
        layout.addWidget(self.parts_label)
        layout.addWidget(self.speed_label)
        layout.addWidget(self.time_label)
        return page
    def create_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["URL", "Output Folder", "Date", "Mode", "Performance", "Parts"])
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.history_table)
        self.update_history_table()
        return page
    def update_history_table(self):
        if not hasattr(self, "history_table"):
            return
        self.history_table.setRowCount(len(self.download_history))
        for i, entry in enumerate(self.download_history):
            self.history_table.setItem(i, 0, QTableWidgetItem(entry["url"]))
            self.history_table.setItem(i, 1, QTableWidgetItem(entry["output_folder"]))
            self.history_table.setItem(i, 2, QTableWidgetItem(entry["time"]))
            self.history_table.setItem(i, 3, QTableWidgetItem(entry["mode"]))
            self.history_table.setItem(i, 4, QTableWidgetItem(entry["performance"]))
            self.history_table.setItem(i, 5, QTableWidgetItem(str(entry["parts"])))
    def apply_theme(self, t):
        if t == "Dark Purple":
            s = """
            QMainWindow, QWidget {background-color: #2b2b3b; color: #ffffff; font-size: 14px; border-radius: 15px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #3c3f60; color: #ffffff; border-radius: 15px; border: 1px solid #555555;}
            QPushButton {background-color: #6c5ce7; color: #ffffff; border-radius: 15px; border: none; padding: 8px;}
            QPushButton:hover {background-color: #8e7fff;}
            QProgressBar {border: 1px solid #555555; border-radius: 15px; text-align: center;}
            QProgressBar::chunk {background-color: #6c5ce7; border-radius: 15px;}
            #SidebarFrame {background-color: #36354b; border-radius: 15px;}
            #HeaderFrame {background-color: #3c3f60; border-radius: 15px;}
            #SidebarTitle {font-weight: bold; font-size: 18px; color: #ffffff; border-radius: 15px;}
            """
        elif t == "Dark Red":
            s = """
            QMainWindow, QWidget {background-color: #2b2b2b; color: #ffffff; font-size: 14px; border-radius: 15px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #3c3f41; color: #ffffff; border-radius: 15px; border: 1px solid #555555;}
            QPushButton {background-color: #e74c3c; color: #ffffff; border-radius: 15px; border: none; padding: 8px;}
            QPushButton:hover {background-color: #ff6b5f;}
            QProgressBar {border: 1px solid #555555; border-radius: 15px; text-align: center;}
            QProgressBar::chunk {background-color: #e74c3c; border-radius: 15px;}
            #SidebarFrame {background-color: #3c3f41; border-radius: 15px;}
            #HeaderFrame {background-color: #393c3f; border-radius: 15px;}
            #SidebarTitle {font-weight: bold; font-size: 18px; color: #e74c3c; border-radius: 15px;}
            """
        elif t == "Dark Green":
            s = """
            QMainWindow, QWidget {background-color: #1c1f1c; color: #ffffff; font-size: 14px; border-radius: 15px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #2d352d; color: #ffffff; border-radius: 15px; border: 1px solid #555555;}
            QPushButton {background-color: #27ae60; color: #ffffff; border-radius: 15px; border: none; padding: 8px;}
            QPushButton:hover {background-color: #2ecc71;}
            QProgressBar {border: 1px solid #555555; border-radius: 15px; text-align: center;}
            QProgressBar::chunk {background-color: #27ae60; border-radius: 15px;}
            #SidebarFrame {background-color: #243224; border-radius: 15px;}
            #HeaderFrame {background-color: #2d352d; border-radius: 15px;}
            #SidebarTitle {font-weight: bold; font-size: 18px; color: #27ae60; border-radius: 15px;}
            """
        elif t == "Dark Blue":
            s = """
            QMainWindow, QWidget {background-color: #1c1c2b; color: #ffffff; font-size: 14px; border-radius: 15px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #2b2b3b; color: #ffffff; border-radius: 15px; border: 1px solid #555555;}
            QPushButton {background-color: #0984e3; color: #ffffff; border-radius: 15px; border: none; padding: 8px;}
            QPushButton:hover {background-color: #74b9ff;}
            QProgressBar {border: 1px solid #555555; border-radius: 15px; text-align: center;}
            QProgressBar::chunk {background-color: #0984e3; border-radius: 15px;}
            #SidebarFrame {background-color: #2b2b3b; border-radius: 15px;}
            #HeaderFrame {background-color: #2f2f4a; border-radius: 15px;}
            #SidebarTitle {font-weight: bold; font-size: 18px; color: #0984e3; border-radius: 15px;}
            """
        else:
            s = """
            QMainWindow, QWidget {background-color: #2b2b2b; color: #ffffff; font-size: 14px; border-radius: 15px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #3c3f41; color: #ffffff; border-radius: 15px; border: 1px solid #555555;}
            QPushButton {background-color: #3c3f41; color: #ffffff; border-radius: 15px; border: 1px solid #555555; padding: 8px;}
            QPushButton:hover {background-color: #505050;}
            QProgressBar {border: 1px solid #555555; border-radius: 15px; text-align: center;}
            QProgressBar::chunk {background-color: #795548; border-radius: 15px;}
            #SidebarFrame {background-color: #3c3f41; border-radius: 15px;}
            #HeaderFrame {background-color: #393c3f; border-radius: 15px;}
            #SidebarTitle {font-weight: bold; font-size: 18px; color: #ffffff; border-radius: 15px;}
            """
        self.setStyleSheet(s)
    def set_download_mode(self, mode):
        self.download_mode = mode
    def set_performance_mode(self, mode):
        self.performance_mode = mode
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)
    def start_download(self):
        u = self.url_input.text().strip()
        o = self.folder_input.text().strip()
        if not u or not o:
            QMessageBox.warning(self, "Missing Info", "Please provide both URL and output folder.")
            return
        n = 1 if self.download_mode == "Single Thread" else (os.cpu_count() if self.performance_mode == "HPD (High Performance)" else 4)
        iso = self.iso_checkbox.isChecked()
        self.download_thread = DownloadThread(u, o, n, (self.performance_mode == "HPD (High Performance)"), iso)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.speed_signal.connect(self.update_speed)
        self.download_thread.time_signal.connect(self.update_time)
        self.download_thread.size_signal.connect(self.update_size)
        self.download_thread.part_count_signal.connect(self.update_part_count)
        self.download_thread.error_signal.connect(self.handle_error)
        self.download_thread.start()
        self.download_history.append({
            "url": u,
            "output_folder": o,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": self.download_mode,
            "performance": self.performance_mode,
            "parts": n
        })
        self.save_history()
        self.update_history_table()
    def pause_download(self):
        if self.download_thread and not self.download_thread.isFinished():
            self.download_thread.pause = True
        else:
            QMessageBox.warning(self, "No Active Download", "No active download to pause.")
    def resume_download(self):
        if self.download_thread and not self.download_thread.isFinished():
            self.download_thread.pause = False
        else:
            QMessageBox.warning(self, "No Paused Download", "No paused download to resume.")
    def cancel_download(self):
        if self.download_thread and not self.download_thread.isFinished():
            self.download_thread.cancel = True
            QMessageBox.information(self, "Cancelled", "Download cancelled and partial files removed.")
            self.reset_ui()
        else:
            QMessageBox.warning(self, "No Active Download", "No active download to cancel.")
    def update_progress(self, v):
        self.overall_progress_bar.setValue(v)
        if v == 100:
            QMessageBox.information(self, "Download Complete", "Your download has finished successfully!")
            self.reset_ui()
    def update_size(self, s):
        mb = s / (1024 * 1024) if s > 0 else 0
        self.size_label.setText(f"File Size: {mb:.2f} MB")
    def update_part_count(self, c):
        self.parts_label.setText(f"Parts: {c}")
    def update_speed(self, sp):
        self.speed_label.setText(f"Speed: {sp:.2f} MB/s")
    def update_time(self, rt):
        self.time_label.setText(f"Time Remaining: {rt:.2f} s")
    def handle_error(self, err):
        QMessageBox.critical(self, "Error", err)
        self.reset_ui()
    def reset_ui(self):
        self.overall_progress_bar.setValue(0)
        self.size_label.setText("File Size: - ")
        self.parts_label.setText("Parts: - ")
        self.speed_label.setText("Speed: - ")
        self.time_label.setText("Time Remaining: - ")
    def load_history(self):
        try:
            with open("history.json", "r", encoding="utf-8") as f:
                self.download_history = json.load(f)
        except:
            self.download_history = []
    def save_history(self):
        with open("history.json", "w", encoding="utf-8") as f:
            json.dump(self.download_history, f, ensure_ascii=False)

if __name__ == "__main__":
    app = QApplication([])
    window = BitCatch2_0()
    window.show()
    app.exec_()
