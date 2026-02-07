import sys
import os
import subprocess
import numpy as np
from pathlib import Path
from PIL import Image
from deepface import DeepFace
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QTextEdit,
    QProgressBar,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QRunnable, QThreadPool

# --- CONFIGURATION ---
SUPPORTED_EXT = {".png", ".jpg", ".jpeg"}
DEEPFACE_DETECTOR = "retinaface"
PORTRAIT_ASPECT_RATIO = 3 / 4
VERTICAL_EXPANSION_FACTOR = 1.8
FACE_HORIZONTAL_PADDING = 1.1
FACE_VERTICAL_ANCHOR = 0.23


# --- LOGIC WRAPPER ---
def get_face_bbox(img: Image.Image):
    img_np = np.array(img.convert("RGB"))
    try:
        detected_faces = DeepFace.extract_faces(
            img_path=img_np,
            detector_backend=DEEPFACE_DETECTOR,
            enforce_detection=False,
            align=False,
        )
        if not detected_faces or not any("facial_area" in d for d in detected_faces):
            return None
        largest = max(
            detected_faces, key=lambda d: d["facial_area"]["w"] * d["facial_area"]["h"]
        )
        area = largest["facial_area"]
        return (area["x"], area["y"], area["x"] + area["w"], area["y"] + area["h"])
    except:
        return None


def calculate_3_4_crop(face_bbox, img_w, img_h):
    x0_f, y0_f, x1_f, y1_f = face_bbox
    w_f, h_f = x1_f - x0_f, y1_f - y0_f
    H_crop = int(h_f * VERTICAL_EXPANSION_FACTOR)
    W_crop = int(H_crop * PORTRAIT_ASPECT_RATIO)

    if W_crop < w_f * FACE_HORIZONTAL_PADDING:
        W_crop = int(w_f * FACE_HORIZONTAL_PADDING)
        H_crop = int(W_crop / PORTRAIT_ASPECT_RATIO)

    y0_c = int(y0_f - H_crop * FACE_VERTICAL_ANCHOR)
    x0_c = int(((x0_f + x1_f) / 2) - W_crop / 2)

    x0_c = max(0, min(x0_c, img_w - W_crop))
    y0_c = max(0, min(y0_c, img_h - H_crop))

    return (x0_c, y0_c, x0_c + W_crop, y0_c + H_crop)


# --- QT THREADING ---
class WorkerSignals(QObject):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal()


class CropWorker(QRunnable):
    def __init__(self, in_dir, out_dir):
        super().__init__()
        self.in_dir = Path(in_dir)
        self.out_dir = Path(out_dir)
        self.signals = WorkerSignals()

    def run(self):
        files = [f for f in self.in_dir.rglob("*") if f.suffix.lower() in SUPPORTED_EXT]
        if not files:
            self.signals.log.emit("No supported images found.")
            self.signals.finished.emit()
            return

        for i, path in enumerate(files):
            try:
                img = Image.open(path).convert("RGB")
                bbox = get_face_bbox(img)
                if bbox:
                    crop = calculate_3_4_crop(bbox, *img.size)
                    final_img = img.crop(crop)

                    rel_path = path.parent.relative_to(self.in_dir)
                    target_dir = self.out_dir / rel_path
                    target_dir.mkdir(parents=True, exist_ok=True)

                    ext = "JPEG" if path.suffix.lower() in [".jpg", ".jpeg"] else "PNG"
                    final_img.save(target_dir / path.name, format=ext)
                    self.signals.log.emit(f"✅ Success: {path.name}")
                else:
                    self.signals.log.emit(f"❌ No face: {path.name}")
            except Exception as e:
                self.signals.log.emit(f"⚠️ Error {path.name}: {str(e)}")

            self.signals.progress.emit(int(((i + 1) / len(files)) * 100))

        self.signals.finished.emit()


# --- MAIN WINDOW ---
class PortraitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CROPPASS")
        self.setMinimumWidth(750)
        self.threadpool = QThreadPool()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Global Dark Theme CSS
        self.setStyleSheet(
            """
            QMainWindow { background-color: #1e1e1e; }
            QWidget { background-color: #1e1e1e; color: #ffffff; font-family: 'Segoe UI', Arial; }
            
            QLabel { color: #d4d4d4; font-size: 13px; }
            
            QLineEdit { 
                background-color: #2d2d2d; 
                border: 1px solid #3e3e42; 
                padding: 6px; 
                border-radius: 4px; 
                color: #ffffff; 
            }
            
            QPushButton#ActionBtn { 
                padding: 12px; 
                border-radius: 5px; 
                background-color: #007acc; 
                color: white; 
                font-weight: bold; 
                font-size: 14px; 
                border: none;
            }
            QPushButton#ActionBtn:hover { background-color: #1c97ea; }
            QPushButton#ActionBtn:disabled { background-color: #333333; color: #777777; }
            
            QPushButton#SecondaryBtn { 
                padding: 6px 15px; 
                background-color: #3e3e42; 
                color: #ffffff; 
                border-radius: 4px; 
                border: 1px solid #454545; 
            }
            QPushButton#SecondaryBtn:hover { background-color: #505050; }

            QProgressBar {
                border: 1px solid #3e3e42;
                border-radius: 4px;
                text-align: center;
                background-color: #252526;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                width: 20px;
            }
            
            QTextEdit { 
                background-color: #1e1e1e; 
                border: 1px solid #3e3e42; 
                color: #85e89d; 
                font-family: 'Consolas', 'Courier New'; 
                font-size: 12px; 
                padding: 5px;
            }
        """
        )

        # Inputs Section
        self.in_edit = self.create_path_section(layout, "Source Folder:")
        self.out_edit = self.create_path_section(layout, "Save Folder:")

        # Progress Section
        layout.addSpacing(10)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log Section
        self.log_box = QTextEdit()
        self.log_box.setPlaceholderText("Ready to process...")
        layout.addWidget(self.log_box)

        # Buttons Row
        btn_layout = QHBoxLayout()

        self.btn_run = QPushButton("⚡ START BATCH")
        self.btn_run.setObjectName("ActionBtn")
        self.btn_run.clicked.connect(self.start_task)
        btn_layout.addWidget(self.btn_run, 2)

        self.btn_open_folder = QPushButton("📂 OPEN OUTPUT")
        self.btn_open_folder.setObjectName("ActionBtn")
        self.btn_open_folder.setStyleSheet(
            "background-color: #4a4a4a;"
        )  # Override to gray
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        self.btn_open_folder.setEnabled(False)
        btn_layout.addWidget(self.btn_open_folder, 1)

        layout.addLayout(btn_layout)

    def create_path_section(self, layout, label_text):
        h_box = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFixedWidth(110)
        h_box.addWidget(lbl)

        line_edit = QLineEdit()
        h_box.addWidget(line_edit)

        btn = QPushButton("Browse")
        btn.setObjectName("SecondaryBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(
            lambda: line_edit.setText(QFileDialog.getExistingDirectory())
        )
        h_box.addWidget(btn)

        layout.addLayout(h_box)
        return line_edit

    def open_output_folder(self):
        path = self.out_edit.text()
        if os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        else:
            QMessageBox.warning(self, "Folder Error", "Output path not found.")

    def start_task(self):
        in_path = self.in_edit.text()
        out_path = self.out_edit.text()

        if not in_path or not out_path:
            QMessageBox.critical(
                self, "Input Error", "Please specify both folders before starting."
            )
            return

        worker = CropWorker(in_path, out_path)
        worker.signals.log.connect(lambda m: self.log_box.append(m))
        worker.signals.progress.connect(self.progress_bar.setValue)
        worker.signals.finished.connect(self.on_finished)

        self.btn_run.setEnabled(False)
        self.btn_open_folder.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_box.clear()
        self.log_box.append(
            "<span style='color:#e1e4e8;'>[SYSTEM] Starting face detection engine...</span>"
        )
        self.threadpool.start(worker)

    def on_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_open_folder.setEnabled(True)
        self.log_box.append(
            "<br><span style='color:#7928ca;'><b>*** BATCH COMPLETE ***</b></span>"
        )

        msg = QMessageBox(self)
        msg.setWindowTitle("Done")
        msg.setText("All images have been processed.")
        msg.setStyleSheet(
            "QLabel{ color: white; } QPushButton{ background-color: #3e3e42; color: white; }"
        )
        msg.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PortraitApp()
    window.show()
    sys.exit(app.exec())
