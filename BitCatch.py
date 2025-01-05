import os
import requests
import threading
import time
import json
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit, QProgressBar, QScrollArea, QFrame, QTableWidget, QTableWidgetItem, QComboBox, QFileDialog, QMessageBox, QStackedWidget, QFormLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal

###############################################################################
#                           DOWNLOAD THREAD
###############################################################################
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

    def run(self):
        r = requests.get(self.url, stream=True)
        cl = r.headers.get("content-length")
        if cl is not None and cl.isdigit():
            self.total_size = int(cl)
        self.size_signal.emit(self.total_size)
        self.start_time = time.time()
        if self.num_parts < 2:
            self.download_single()
        else:
            self.download_multi()

    def download_single(self):
        r = requests.get(self.url, stream=True)
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
        ps = 0
        if self.total_size > 0:
            ps = self.total_size // self.num_parts
        else:
            ps = 0
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
        r = requests.get(self.url, headers=hs, stream=True)
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
        sp = 0
        if et > 0:
            sp = td / 1048576 / et
        rt = 0
        if sp > 0 and self.total_size > 0:
            rt = (self.total_size - td) / (sp * 1048576)
        pp = 0
        if self.total_size > 0:
            pp = int(td / self.total_size * 100)
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

###############################################################################
#                           MAIN WINDOW
###############################################################################
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
        c = QWidget()
        self.setCentralWidget(c)
        self.main_layout = QHBoxLayout(c)
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

    ############################################################################
    #                          SIDEBAR
    ############################################################################
    def create_sidebar(self):
        f = QFrame()
        f.setObjectName("SidebarFrame")
        l = QVBoxLayout(f)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(20)
        t = QLabel("BITCATCH 2.0")
        t.setObjectName("SidebarTitle")
        t.setAlignment(Qt.AlignCenter)
        b1 = QPushButton("Downloader")
        b1.setObjectName("SidebarButton")
        b1.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        b2 = QPushButton("History")
        b2.setObjectName("SidebarButton")
        b2.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        l.addSpacing(30)
        l.addWidget(t)
        l.addSpacing(30)
        l.addWidget(b1)
        l.addWidget(b2)
        l.addStretch()
        return f

    ############################################################################
    #                          HEADER
    ############################################################################
    def create_header(self):
        f = QFrame()
        f.setObjectName("HeaderFrame")
        lh = QHBoxLayout(f)
        lh.setContentsMargins(10, 5, 10, 5)
        ll = QLabel("BitCatch2.0 - Dark Themes")
        ll.setObjectName("HeaderLogo")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Default","Dark Purple","Dark Red","Dark Green","Dark Blue"])
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        lh.addWidget(ll, alignment=Qt.AlignVCenter)
        lh.addStretch()
        lh.addWidget(self.theme_combo, alignment=Qt.AlignRight)
        return f

    ############################################################################
    #                          DOWNLOADER PAGE
    ############################################################################
    def create_downloader_page(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        fm = QFormLayout()
        self.url_input = QLineEdit()
        self.folder_input = QLineEdit()
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.select_folder)
        hb = QHBoxLayout()
        hb.addWidget(self.folder_input)
        hb.addWidget(self.browse_button)
        fm.addRow("Download URL:", self.url_input)
        fm.addRow("Output Folder:", hb)
        l.addLayout(fm)
        ml = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Single Thread","Multi-part Download"])
        self.mode_combo.currentTextChanged.connect(self.set_download_mode)
        self.performance_combo = QComboBox()
        self.performance_combo.addItems(["Normal","HPD (High Performance)"])
        self.performance_combo.currentTextChanged.connect(self.set_performance_mode)
        ml.addWidget(QLabel("Download Mode:"))
        ml.addWidget(self.mode_combo)
        ml.addSpacing(30)
        ml.addWidget(QLabel("Performance Mode:"))
        ml.addWidget(self.performance_combo)
        l.addLayout(ml)
        bl = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_download)
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.clicked.connect(self.resume_download)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_download)
        bl.addWidget(self.download_btn)
        bl.addWidget(self.pause_btn)
        bl.addWidget(self.resume_btn)
        bl.addWidget(self.cancel_btn)
        l.addLayout(bl)
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setTextVisible(True)
        l.addWidget(self.overall_progress_bar)
        self.size_label = QLabel("File Size: - ")
        self.parts_label = QLabel("Parts: - ")
        self.speed_label = QLabel("Speed: - ")
        self.time_label = QLabel("Time Remaining: - ")
        l.addWidget(self.size_label)
        l.addWidget(self.parts_label)
        l.addWidget(self.speed_label)
        l.addWidget(self.time_label)
        return p

    ############################################################################
    #                          HISTORY PAGE
    ############################################################################
    def create_history_page(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["URL","Output Folder","Date","Mode","Performance","Parts"])
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        l.addWidget(self.history_table)
        self.update_history_table()
        return p

    def update_history_table(self):
        if not hasattr(self, "history_table"):
            return
        self.history_table.setRowCount(len(self.download_history))
        for i, e in enumerate(self.download_history):
            self.history_table.setItem(i,0,QTableWidgetItem(e["url"]))
            self.history_table.setItem(i,1,QTableWidgetItem(e["output_folder"]))
            self.history_table.setItem(i,2,QTableWidgetItem(e["time"]))
            self.history_table.setItem(i,3,QTableWidgetItem(e["mode"]))
            self.history_table.setItem(i,4,QTableWidgetItem(e["performance"]))
            self.history_table.setItem(i,5,QTableWidgetItem(str(e["parts"])))

    ############################################################################
    #                          THEME
    ############################################################################
    def apply_theme(self, t):
        if t=="Dark Purple":
            s="""
            QMainWindow,QWidget{background-color:#2b2b3b;color:#ffffff;font-size:14px;}
            QLineEdit,QComboBox,QTableWidget{background-color:#3c3f60;color:#ffffff;border-radius:8px;border:1px solid #555555;}
            QPushButton{background-color:#6c5ce7;color:#ffffff;border-radius:8px;border:none;padding:8px;}
            QPushButton:hover{background-color:#8e7fff;}
            QProgressBar{border:1px solid #555555;border-radius:8px;text-align:center;}
            QProgressBar::chunk{background-color:#6c5ce7;border-radius:8px;}
            #SidebarFrame{background-color:#36354b;}
            #HeaderFrame{background-color:#3c3f60;}
            #SidebarTitle{font-weight:bold;font-size:18px;color:#ffffff;}
            """
        elif t=="Dark Red":
            s="""
            QMainWindow,QWidget{background-color:#2b2b2b;color:#ffffff;font-size:14px;}
            QLineEdit,QComboBox,QTableWidget{background-color:#3c3f41;color:#ffffff;border-radius:8px;border:1px solid #555555;}
            QPushButton{background-color:#e74c3c;color:#ffffff;border-radius:8px;border:none;padding:8px;}
            QPushButton:hover{background-color:#ff6b5f;}
            QProgressBar{border:1px solid #555555;border-radius:8px;text-align:center;}
            QProgressBar::chunk{background-color:#e74c3c;border-radius:8px;}
            #SidebarFrame{background-color:#3c3f41;}
            #HeaderFrame{background-color:#393c3f;}
            #SidebarTitle{font-weight:bold;font-size:18px;color:#e74c3c;}
            """
        elif t=="Dark Green":
            s="""
            QMainWindow,QWidget{background-color:#1c1f1c;color:#ffffff;font-size:14px;}
            QLineEdit,QComboBox,QTableWidget{background-color:#2d352d;color:#ffffff;border-radius:8px;border:1px solid #555555;}
            QPushButton{background-color:#27ae60;color:#ffffff;border-radius:8px;border:none;padding:8px;}
            QPushButton:hover{background-color:#2ecc71;}
            QProgressBar{border:1px solid #555555;border-radius:8px;text-align:center;}
            QProgressBar::chunk{background-color:#27ae60;border-radius:8px;}
            #SidebarFrame{background-color:#243224;}
            #HeaderFrame{background-color:#2d352d;}
            #SidebarTitle{font-weight:bold;font-size:18px;color:#27ae60;}
            """
        elif t=="Dark Blue":
            s="""
            QMainWindow,QWidget{background-color:#1c1c2b;color:#ffffff;font-size:14px;}
            QLineEdit,QComboBox,QTableWidget{background-color:#2b2b3b;color:#ffffff;border-radius:8px;border:1px solid #555555;}
            QPushButton{background-color:#0984e3;color:#ffffff;border-radius:8px;border:none;padding:8px;}
            QPushButton:hover{background-color:#74b9ff;}
            QProgressBar{border:1px solid #555555;border-radius:8px;text-align:center;}
            QProgressBar::chunk{background-color:#0984e3;border-radius:8px;}
            #SidebarFrame{background-color:#2b2b3b;}
            #HeaderFrame{background-color:#2f2f4a;}
            #SidebarTitle{font-weight:bold;font-size:18px;color:#0984e3;}
            """
        else:
            s="""
            QMainWindow,QWidget{background-color:#2b2b2b;color:#ffffff;font-size:14px;}
            QLineEdit,QComboBox,QTableWidget{background-color:#3c3f41;color:#ffffff;border-radius:8px;border:1px solid #555555;}
            QPushButton{background-color:#3c3f41;color:#ffffff;border-radius:8px;border:1px solid #555555;padding:8px;}
            QPushButton:hover{background-color:#505050;}
            QProgressBar{border:1px solid #555555;border-radius:8px;text-align:center;}
            QProgressBar::chunk{background-color:#795548;border-radius:8px;}
            #SidebarFrame{background-color:#3c3f41;}
            #HeaderFrame{background-color:#393c3f;}
            #SidebarTitle{font-weight:bold;font-size:18px;color:#ffffff;}
            """
        self.setStyleSheet(s)

    ############################################################################
    #                          DOWNLOAD LOGIC
    ############################################################################
    def set_download_mode(self, mode):
        self.download_mode = mode

    def set_performance_mode(self, mode):
        self.performance_mode = mode

    def select_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Select Folder")
        if f:
            self.folder_input.setText(f)

    def start_download(self):
        u = self.url_input.text().strip()
        o = self.folder_input.text().strip()
        if not u or not o:
            QMessageBox.warning(self, "Missing Info", "Please provide both URL and output folder.")
            return
        n = 1 if self.download_mode=="Single Thread" else (os.cpu_count() if self.performance_mode=="HPD (High Performance)" else 4)
        self.download_thread = DownloadThread(u, o, n, (self.performance_mode=="HPD (High Performance)"))
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.speed_signal.connect(self.update_speed)
        self.download_thread.time_signal.connect(self.update_time)
        self.download_thread.size_signal.connect(self.update_size)
        self.download_thread.part_count_signal.connect(self.update_part_count)
        self.download_thread.start()
        self.download_history.append({
            "url":u,
            "output_folder":o,
            "time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode":self.download_mode,
            "performance":self.performance_mode,
            "parts":n
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
        if v==100:
            QMessageBox.information(self, "Download Complete", "Your download has finished successfully!")
            self.reset_ui()

    def update_size(self, s):
        mb = s/(1024*1024) if s>0 else 0
        self.size_label.setText(f"File Size: {mb:.2f} MB")

    def update_part_count(self, c):
        self.parts_label.setText(f"Parts: {c}")

    def update_speed(self, sp):
        self.speed_label.setText(f"Speed: {sp:.2f} MB/s")

    def update_time(self, rt):
        self.time_label.setText(f"Time Remaining: {rt:.2f} s")

    def reset_ui(self):
        self.overall_progress_bar.setValue(0)
        self.size_label.setText("File Size: - ")
        self.parts_label.setText("Parts: - ")
        self.speed_label.setText("Speed: - ")
        self.time_label.setText("Time Remaining: - ")

    def load_history(self):
        try:
            with open("history.json","r",encoding="utf-8") as f:
                self.download_history=json.load(f)
        except:
            self.download_history=[]

    def save_history(self):
        with open("history.json","w",encoding="utf-8") as f:
            json.dump(self.download_history,f,ensure_ascii=False)

###############################################################################
#                          MAIN
###############################################################################
if __name__=="__main__":
    a=QApplication([])
    w=BitCatch2_0()
    w.show()
    a.exec_()
