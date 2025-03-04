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
import time
import threading
import requests
from PySide6.QtCore import QThread, Signal

class DownloadThread(QThread):
    progress_signal = Signal(int)
    speed_signal = Signal(float)
    time_signal = Signal(float)
    size_signal = Signal(int)
    part_count_signal = Signal(int)
    error_signal = Signal(str)
    def __init__(self, url, output_folder, num_parts=1, hpd_mode=False, iso_mode=False, proxy=None):
        super().__init__()
        self.url = url
        self.output_folder = output_folder
        self.num_parts = num_parts
        self.hpd_mode = hpd_mode
        self.iso_mode = iso_mode
        self.proxy = proxy
        self.progress = [0] * num_parts
        self.total_size = 0
        self.pause = False
        self.cancel = False
    def run(self):
        try:
            head = requests.head(self.url, proxies=self.proxy, timeout=10)
            head.raise_for_status()
            cl = head.headers.get("content-length")
            if cl and cl.isdigit():
                self.total_size = int(cl)
            self.size_signal.emit(self.total_size)
        except Exception as e:
            try:
                r = requests.get(self.url, proxies=self.proxy, stream=True, timeout=10)
                r.raise_for_status()
                cl = r.headers.get("content-length")
                if cl and cl.isdigit():
                    self.total_size = int(cl)
                self.size_signal.emit(self.total_size)
            except Exception as e2:
                self.error_signal.emit("Connection error: " + str(e2))
                return
        self.start_time = time.time()
        if self.num_parts < 2 or self.total_size <= 0:
            self.download_single()
            if self.iso_mode and self.total_size > 0 and not self.cancel:
                filename = os.path.join(self.output_folder, self.url.split("/")[-1])
                try:
                    if os.path.getsize(filename) != self.total_size:
                        os.remove(filename)
                        self.error_signal.emit("ISO file corrupted: downloaded size mismatch")
                except Exception as e:
                    self.error_signal.emit("ISO verification error: " + str(e))
        else:
            self.download_multi()
    def download_single(self):
        try:
            r = requests.get(self.url, proxies=self.proxy, stream=True, timeout=10)
            r.raise_for_status()
        except Exception as e:
            self.error_signal.emit("Download error: " + str(e))
            return
        filename = os.path.join(self.output_folder, self.url.split("/")[-1])
        with open(filename, "wb") as f:
            downloaded = 0
            chunk_size = 524288 if self.hpd_mode else 65536
            for chunk in r.iter_content(chunk_size):
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
        base_filename = os.path.join(self.output_folder, self.url.split("/")[-1].split(".")[0])
        part_size = self.total_size // self.num_parts if self.total_size > 0 else 0
        self.part_count_signal.emit(self.num_parts)
        threads = []
        for i in range(self.num_parts):
            start = part_size * i
            end = (start + part_size - 1) if i < (self.num_parts - 1) else None
            t = threading.Thread(target=self.part_worker, args=(i, start, end, base_filename))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        if not self.cancel:
            self.merge_parts(base_filename)
    def part_worker(self, idx, start, end, base_filename):
        headers = {}
        if end is not None:
            headers["Range"] = f"bytes={start}-{end}"
        try:
            r = requests.get(self.url, headers=headers, proxies=self.proxy, stream=True, timeout=10)
            r.raise_for_status()
        except Exception as e:
            self.error_signal.emit("Part error: " + str(e))
            return
        part_path = f"{base_filename}.part{idx}"
        chunk_size = 524288 if self.hpd_mode else 65536
        downloaded = 0
        with open(part_path, "wb") as f:
            for chunk in r.iter_content(chunk_size):
                if self.cancel:
                    break
                while self.pause:
                    time.sleep(0.1)
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    self.progress[idx] = downloaded
                    self.emit_overall()
        if self.cancel and os.path.exists(part_path):
            os.remove(part_path)
    def emit_overall(self):
        total_downloaded = sum(self.progress)
        elapsed = time.time() - self.start_time
        if elapsed < 1: elapsed = 1
        speed = total_downloaded / (1024 * 1024) / elapsed
        remaining = (self.total_size - total_downloaded) / (speed * 1024 * 1024) if speed > 0 and self.total_size > 0 else 0
        percent = int(total_downloaded / self.total_size * 100) if self.total_size > 0 else 0
        self.progress_signal.emit(percent)
        self.speed_signal.emit(speed)
        self.time_signal.emit(remaining)
    def merge_parts(self, base_filename):
        ext = self.url.split("/")[-1].split(".")[-1]
        full_filename = base_filename + f".{ext}" if ext else base_filename
        with open(full_filename, "wb") as out_file:
            for i in range(self.num_parts):
                part_path = f"{base_filename}.part{i}"
                if os.path.exists(part_path):
                    with open(part_path, "rb") as part_file:
                        out_file.write(part_file.read())
                    os.remove(part_path)
        if self.iso_mode and self.total_size > 0 and not self.cancel:
            try:
                if os.path.getsize(full_filename) != self.total_size:
                    os.remove(full_filename)
                    self.error_signal.emit("ISO file corrupted: downloaded size mismatch")
            except Exception as e:
                self.error_signal.emit("ISO verification error: " + str(e))
