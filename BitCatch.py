import os
import requests
import threading
import time
import json
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QProgressBar, QFileDialog, QMessageBox, QComboBox, QHBoxLayout, QDialog, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class DownloadThread(QThread):
    progress_signal = pyqtSignal(int)
    speed_signal = pyqtSignal(float)
    time_signal = pyqtSignal(float)
    size_signal = pyqtSignal(int)
    part_count_signal = pyqtSignal(int)

    def __init__(self, url, output_folder, num_parts=1, hpd_mode=False):
        super().__init__()
        self.url = url
        self.output_folder = output_folder
        self.num_parts = num_parts
        self.hpd_mode = hpd_mode
        self.progress = [0] * num_parts
        self.total_size = 0
        self.pause = False
        self.cancel = False

    def download_part(self, start, end, part_num, filename):
        headers = {"Range": f"bytes={start}-{end}"}
        response = requests.get(self.url, headers=headers, stream=True)
        
        with open(f"{filename}.part{part_num}", "wb") as file:
            downloaded = 0
            for chunk in response.iter_content(8192 if self.hpd_mode else 4096):
                if self.cancel:
                    break
                while self.pause:
                    time.sleep(0.1)
                if chunk:
                    file.write(chunk)
                    downloaded += len(chunk)
                    self.progress[part_num] = downloaded
                    self.emit_progress()
        
        if self.cancel:
            os.remove(f"{filename}.part{part_num}")

    def emit_progress(self):
        total_downloaded = sum(self.progress)
        speed = total_downloaded / 1024 / 1024 / (time.time() - self.start_time)
        remaining_time = (self.total_size - total_downloaded) / (speed * 1024 * 1024) if speed > 0 else 0
        progress_percent = int((total_downloaded / self.total_size) * 100)
        self.progress_signal.emit(progress_percent)
        self.speed_signal.emit(speed)
        self.time_signal.emit(remaining_time)

    def merge_parts(self, filename, original_extension):
        final_filename = f"{filename}.{original_extension}"
        with open(final_filename, "wb") as output_file:
            for i in range(self.num_parts):
                part_file = f"{filename}.part{i}"
                with open(part_file, "rb") as file:
                    output_file.write(file.read())
                os.remove(part_file)

    def run(self):
        response = requests.head(self.url)
        self.total_size = int(response.headers.get("content-length", 0))
        self.size_signal.emit(self.total_size)
        original_extension = self.url.split('.')[-1]
        filename = os.path.join(self.output_folder, self.url.split("/")[-1].split(".")[0])

        self.start_time = time.time()
        
        part_size = self.total_size // self.num_parts
        self.part_count_signal.emit(self.num_parts)

        threads = []
        for i in range(self.num_parts):
            start = part_size * i
            end = start + part_size - 1 if i < self.num_parts - 1 else self.total_size
            thread = threading.Thread(target=self.download_part, args=(start, end, i, filename))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if not self.cancel:
            self.merge_parts(filename, original_extension)

class DownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BitCatch Downloader")
        self.setGeometry(100, 100, 600, 400)
        self.download_history = []
        self.load_history()

        self.download_mode = "Single Thread"
        self.performance_mode = "Normal"
        self.download_thread = None

        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLineEdit, QComboBox, QProgressBar {
                background-color: #3c3f41;
                border: 1px solid #555555;
                color: #ffffff;
            }
            QPushButton {
                background-color: #3c3f41;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QComboBox {
                border-radius: 10px;
                padding: 3px;
            }
            QLabel {
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #3c3f41;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #555555;
            }
            QTableWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel("Download URL:"))
        self.url_input = QLineEdit()
        self.url_input.setFixedHeight(30)
        layout.addWidget(self.url_input)

        layout.addWidget(QLabel("Save Folder:"))
        self.output_folder = QLineEdit()
        self.output_folder.setFixedHeight(30)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.select_folder)
        layout.addWidget(self.output_folder)
        layout.addWidget(self.browse_button)

        mode_layout = QHBoxLayout()
        layout.addLayout(mode_layout)

        self.download_mode_label = QLabel("Download Mode:")
        mode_layout.addWidget(self.download_mode_label)
        self.download_mode_combo = QComboBox()
        self.download_mode_combo.addItems(["Single Thread", "Multi-part Download"])
        self.download_mode_combo.currentTextChanged.connect(self.set_download_mode)
        mode_layout.addWidget(self.download_mode_combo)

        self.performance_mode_label = QLabel("Performance Mode:")
        mode_layout.addWidget(self.performance_mode_label)
        self.performance_mode_combo = QComboBox()
        self.performance_mode_combo.addItems(["Normal", "HPD (High Performance)"])
        self.performance_mode_combo.currentTextChanged.connect(self.set_performance_mode)
        mode_layout.addWidget(self.performance_mode_combo)

        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_download)
        layout.addWidget(self.pause_button)

        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self.resume_download)
        layout.addWidget(self.resume_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_download)
        layout.addWidget(self.cancel_button)

        # Düz indirme çubuğu
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)  # Yüzde metni ortada gözükecek
        layout.addWidget(self.progress_bar)

        self.size_label = QLabel("Total Size: No file downloaded yet")
        self.part_count_label = QLabel("Parts: No parts created yet")
        layout.addWidget(self.size_label)
        layout.addWidget(self.part_count_label)

        self.speed_label = QLabel("Speed: No file downloaded yet")
        self.time_label = QLabel("Time Remaining: No file downloaded yet")
        layout.addWidget(self.speed_label)
        layout.addWidget(self.time_label)

        self.history_button = QPushButton("History")
        self.history_button.clicked.connect(self.show_history)
        layout.addWidget(self.history_button)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.output_folder.setText(folder)

    def start_download(self):
        url = self.url_input.text()
        output_folder = self.output_folder.text()
        if not url or not output_folder:
            QMessageBox.warning(self, "Missing Information", "Please enter both URL and save folder.")
            return

        num_parts = os.cpu_count() if self.performance_mode == "HPD (High Performance)" else 4
        hpd_mode = self.performance_mode == "HPD (High Performance)"
        if self.download_mode == "Single Thread":
            num_parts = 1

        self.download_thread = DownloadThread(url, output_folder, num_parts, hpd_mode)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.speed_signal.connect(self.update_speed)
        self.download_thread.time_signal.connect(self.update_time)
        self.download_thread.size_signal.connect(self.update_size)
        self.download_thread.part_count_signal.connect(self.update_part_count)
        self.download_thread.start()

        self.download_history.append({
            "url": url,
            "output_folder": output_folder,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": self.download_mode,
            "performance": self.performance_mode,
            "parts": num_parts
        })
        self.save_history()

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        if value == 100:
            QMessageBox.information(self, "Completed", "Download finished and saved with the correct file extension.")
            self.reset_ui()

    def update_size(self, size):
        size_mb = size / (1024 * 1024)
        self.size_label.setText(f"Total Size: {size_mb:.2f} MB")

    def update_part_count(self, part_count):
        self.part_count_label.setText(f"Parts: {part_count}")

    def update_speed(self, speed):
        self.speed_label.setText(f"Speed: {speed:.2f} MB/s")

    def update_time(self, time_remaining):
        self.time_label.setText(f"Time Remaining: {time_remaining:.2f} seconds")

    def set_download_mode(self, mode):
        self.download_mode = mode

    def set_performance_mode(self, mode):
        self.performance_mode = mode

    def pause_download(self):
        if self.download_thread and not self.download_thread.isFinished():
            self.download_thread.pause = True
        else:
            QMessageBox.warning(self, "No Download", "There is no active download to pause.")

    def resume_download(self):
        if self.download_thread and not self.download_thread.isFinished():
            self.download_thread.pause = False
        else:
            QMessageBox.warning(self, "No Download", "There is no paused download to resume.")

    def cancel_download(self):
        if self.download_thread and not self.download_thread.isFinished():
            self.download_thread.cancel = True
            QMessageBox.information(self, "Cancelled", "Download has been cancelled and partial files have been deleted.")
            self.reset_ui()
        else:
            QMessageBox.warning(self, "No Download", "There is no active download to cancel.")

    def reset_ui(self):
        self.progress_bar.setValue(0)
        self.size_label.setText("Total Size: No file downloaded yet")
        self.part_count_label.setText("Parts: No parts created yet")
        self.speed_label.setText("Speed: No file downloaded yet")
        self.time_label.setText("Time Remaining: No file downloaded yet")
        self.url_input.clear()
        self.output_folder.clear()

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Download History")
        dialog.setGeometry(150, 150, 500, 300)

        table = QTableWidget(len(self.download_history), 6)
        table.setHorizontalHeaderLabels(["URL", "Save Location", "Date", "Mode", "Performance", "Parts"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        for row, entry in enumerate(self.download_history):
            table.setItem(row, 0, QTableWidgetItem(entry["url"]))
            table.setItem(row, 1, QTableWidgetItem(entry["output_folder"]))
            table.setItem(row, 2, QTableWidgetItem(entry["time"]))
            table.setItem(row, 3, QTableWidgetItem(entry["mode"]))
            table.setItem(row, 4, QTableWidgetItem(entry["performance"]))
            table.setItem(row, 5, QTableWidgetItem(str(entry["parts"])))

        layout = QVBoxLayout()
        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec_()

    def load_history(self):
        try:
            with open("history.json", "r") as file:
                self.download_history = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.download_history = []

    def save_history(self):
        with open("history.json", "w") as file:
            json.dump(self.download_history, file)

app = QApplication([])
window = DownloaderApp()
window.show()
app.exec_()
