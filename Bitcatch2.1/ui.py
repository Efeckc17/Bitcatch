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

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit, QProgressBar, QFrame, QTableWidget, QTableWidgetItem, QComboBox, QFileDialog, QStackedWidget, QFormLayout, QCheckBox
from PySide6.QtCore import Qt, QPoint

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("BitCatch 2.1 Downloader")
        self.setGeometry(100, 80, 1200, 700)
        self.download_history = []
        self.download_thread = None
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QHBoxLayout(central)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
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
        self.oldPos = self.pos()

    def create_sidebar(self):
        frame = QFrame()
        frame.setObjectName("SidebarFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(20)
        title = QLabel("BitCatch 2.1")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignCenter)
        btn_downloader = QPushButton("Downloader")
        btn_downloader.setObjectName("SidebarButton")
        btn_downloader.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        btn_history = QPushButton("History")
        btn_history.setObjectName("SidebarButton")
        btn_history.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        layout.addSpacing(30)
        layout.addWidget(title)
        layout.addSpacing(30)
        layout.addWidget(btn_downloader)
        layout.addWidget(btn_history)
        layout.addStretch()
        return frame

    def create_header(self):
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        hlayout = QHBoxLayout(frame)
        hlayout.setContentsMargins(10, 5, 10, 5)
        logo = QLabel("BitCatch 2.1 - Modern")
        logo.setObjectName("HeaderLogo")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Default", "Dark Purple", "Dark Red", "Dark Green", "Dark Blue"])
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        btn_close = QPushButton("Close")
        btn_close.setObjectName("HeaderCloseButton")
        btn_close.clicked.connect(self.close)
        hlayout.addWidget(logo, alignment=Qt.AlignVCenter)
        hlayout.addStretch()
        hlayout.addWidget(self.theme_combo)
        hlayout.addWidget(btn_close)
        return frame

    def create_downloader_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        form = QFormLayout()
        self.url_input = QLineEdit()
        self.folder_input = QLineEdit()
        self.browse_button = QPushButton("Browse")
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
        self.performance_combo = QComboBox()
        self.performance_combo.addItems(["Normal", "HPD (High Performance)"])
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addSpacing(30)
        mode_layout.addWidget(QLabel("Performance:"))
        mode_layout.addWidget(self.performance_combo)
        layout.addLayout(mode_layout)
        self.iso_checkbox = QCheckBox("ISO Mode")
        layout.addWidget(self.iso_checkbox)
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.pause_btn = QPushButton("Pause")
        self.resume_btn = QPushButton("Resume")
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setTextVisible(True)
        layout.addWidget(self.overall_progress_bar)
        self.size_label = QLabel("Size: -")
        self.parts_label = QLabel("Parts: -")
        self.speed_label = QLabel("Speed: -")
        self.time_label = QLabel("Time Left: -")
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
        return page

    def update_history_table(self, history):
        self.history_table.setRowCount(len(history))
        for i, entry in enumerate(history):
            self.history_table.setItem(i, 0, QTableWidgetItem(entry["url"]))
            self.history_table.setItem(i, 1, QTableWidgetItem(entry["output_folder"]))
            self.history_table.setItem(i, 2, QTableWidgetItem(entry["time"]))
            self.history_table.setItem(i, 3, QTableWidgetItem(entry["mode"]))
            self.history_table.setItem(i, 4, QTableWidgetItem(entry["performance"]))
            self.history_table.setItem(i, 5, QTableWidgetItem(str(entry["parts"])))

    def apply_theme(self, theme_name):
        if theme_name == "Dark Purple":
            s = """
            QMainWindow, QWidget {background-color: #2b2b3b; color: #ffffff; font-size: 14px; border-radius: 30px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #3c3f60; color: #ffffff; border: 1px solid #555; border-radius: 25px;}
            QPushButton {background-color: #6c5ce7; color: #ffffff; padding: 10px; border: none; border-radius: 25px;}
            QPushButton:hover {background-color: #8e7fff;}
            QProgressBar {border: 1px solid #555; text-align: center; border-radius: 25px;}
            QProgressBar::chunk {background-color: #6c5ce7; border-radius: 25px;}
            #SidebarFrame {background-color: #36354b; border-radius: 30px;}
            #HeaderFrame {background-color: #3c3f60; border-radius: 30px;}
            #SidebarTitle {font-weight: bold; font-size: 22px; color: #ffffff;}
            """
        elif theme_name == "Dark Red":
            s = """
            QMainWindow, QWidget {background-color: #2b2b2b; color: #ffffff; font-size: 14px; border-radius: 30px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #3c3f41; color: #ffffff; border: 1px solid #555; border-radius: 25px;}
            QPushButton {background-color: #e74c3c; color: #ffffff; padding: 10px; border: none; border-radius: 25px;}
            QPushButton:hover {background-color: #ff6b5f;}
            QProgressBar {border: 1px solid #555; text-align: center; border-radius: 25px;}
            QProgressBar::chunk {background-color: #e74c3c; border-radius: 25px;}
            #SidebarFrame {background-color: #3c3f41; border-radius: 30px;}
            #HeaderFrame {background-color: #393c3f; border-radius: 30px;}
            #SidebarTitle {font-weight: bold; font-size: 22px; color: #e74c3c;}
            """
        elif theme_name == "Dark Green":
            s = """
            QMainWindow, QWidget {background-color: #1c1f1c; color: #ffffff; font-size: 14px; border-radius: 30px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #2d352d; color: #ffffff; border: 1px solid #555; border-radius: 25px;}
            QPushButton {background-color: #27ae60; color: #ffffff; padding: 10px; border: none; border-radius: 25px;}
            QPushButton:hover {background-color: #2ecc71;}
            QProgressBar {border: 1px solid #555; text-align: center; border-radius: 25px;}
            QProgressBar::chunk {background-color: #27ae60; border-radius: 25px;}
            #SidebarFrame {background-color: #243224; border-radius: 30px;}
            #HeaderFrame {background-color: #2d352d; border-radius: 30px;}
            #SidebarTitle {font-weight: bold; font-size: 22px; color: #27ae60;}
            """
        elif theme_name == "Dark Blue":
            s = """
            QMainWindow, QWidget {background-color: #1c1c2b; color: #ffffff; font-size: 14px; border-radius: 30px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #2b2b3b; color: #ffffff; border: 1px solid #555; border-radius: 25px;}
            QPushButton {background-color: #0984e3; color: #ffffff; padding: 10px; border: none; border-radius: 25px;}
            QPushButton:hover {background-color: #74b9ff;}
            QProgressBar {border: 1px solid #555; text-align: center; border-radius: 25px;}
            QProgressBar::chunk {background-color: #0984e3; border-radius: 25px;}
            #SidebarFrame {background-color: #2b2b3b; border-radius: 30px;}
            #HeaderFrame {background-color: #2f2f4a; border-radius: 30px;}
            #SidebarTitle {font-weight: bold; font-size: 22px; color: #0984e3;}
            """
        else:
            s = """
            QMainWindow, QWidget {background-color: #2b2b2b; color: #ffffff; font-size: 14px; border-radius: 30px;}
            QLineEdit, QComboBox, QTableWidget {background-color: #3c3f41; color: #ffffff; border: 1px solid #555; border-radius: 25px;}
            QPushButton {background-color: #3c3f41; color: #ffffff; padding: 10px; border: 1px solid #555; border-radius: 25px;}
            QPushButton:hover {background-color: #505050;}
            QProgressBar {border: 1px solid #555; text-align: center; border-radius: 25px;}
            QProgressBar::chunk {background-color: #795548; border-radius: 25px;}
            #SidebarFrame {background-color: #3c3f41; border-radius: 30px;}
            #HeaderFrame {background-color: #393c3f; border-radius: 30px;}
            #SidebarTitle {font-weight: bold; font-size: 22px; color: #ffffff;}
            """
        self.setStyleSheet(s)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()
