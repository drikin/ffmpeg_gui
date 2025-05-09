from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QListWidget, QComboBox, QCheckBox, QLineEdit
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from ui_parts.file_select_widget import FileSelectWidget
from ui_parts.log_console_widget import LogConsoleWidget
from core.slideshow_builder import SlideshowBuilder
import threading
from pathlib import Path
import os

class SlideshowPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        # ファイル選択ウィジェット（画像のみ）
        self.file_select = FileSelectWidget(file_types=("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff"))
        self.file_select.files_changed.connect(self.update_file_list)
        layout.addWidget(self.file_select)
        # ファイルリスト
        self.list_files = QListWidget()
        self.list_files.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_files.setDragDropMode(QListWidget.InternalMove)  # 並べ替え可能に
        self.list_files.currentItemChanged.connect(self.preview_selected_image)
        layout.addWidget(self.list_files)
        # プレビュー用ラベル
        self.preview_label = QLabel()
        self.preview_label.setFixedHeight(220)
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview_label)
        # SE選択コンボボックス
        self.se_combo = QComboBox()
        self.se_combo.addItem("SEなし", "")
        self.se_files = self._get_se_files()
        for name, path in self.se_files.items():
            self.se_combo.addItem(name, path)
        layout.addWidget(QLabel("切り替え時SE"))
        layout.addWidget(self.se_combo)
        # Exif表示オプション
        self.exif_checkbox = QCheckBox("Exif情報を左下に表示")
        self.exif_checkbox.setChecked(False)
        layout.addWidget(self.exif_checkbox)
        # Exif情報がない場合のテキスト入力欄
        self.exif_missing_text_label = QLabel("Exif情報がない場合のテキスト：")
        self.exif_missing_text_input = QLineEdit()
        self.exif_missing_text_input.setPlaceholderText("Leica M4")
        self.exif_missing_text_input.setText("Leica M4")
        layout.addWidget(self.exif_missing_text_label)
        layout.addWidget(self.exif_missing_text_input)
        # スライドショー生成ボタン
        self.btn_generate = QPushButton("スライドショー生成")
        self.btn_generate.clicked.connect(self.on_generate_slideshow)
        layout.addWidget(self.btn_generate)
        # ffmpegログ表示
        self.log_console = LogConsoleWidget()
        layout.addWidget(self.log_console)
        self.setLayout(layout)

    def _get_se_files(self):
        se_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "se")
        se_files = {}
        if os.path.exists(se_dir):
            for fname in os.listdir(se_dir):
                if fname.lower().endswith((".wav", ".mp3", ".ogg")):
                    se_files[os.path.splitext(fname)[0]] = os.path.join(se_dir, fname)
        return se_files

    def update_file_list(self, files):
        self.list_files.clear()
        for f in files:
            self.list_files.addItem(str(f))

    def reset_file_list(self):
        self.list_files.clear()
        self.preview_label.clear()

    def preview_selected_image(self, current, previous):
        if current is None:
            self.preview_label.clear()
            return
        path = current.text()
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaledToHeight(200, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
        else:
            self.preview_label.setText("画像プレビュー不可")

    def on_generate_slideshow(self):
        file_list = [self.list_files.item(i).text() for i in range(self.list_files.count())]
        if not file_list:
            QMessageBox.warning(self, "エラー", "画像ファイルを選択してください。")
            return
        se_path = self.se_combo.currentData()
        exif_enable = self.exif_checkbox.isChecked()
        outdir = str(Path(file_list[0]).parent)
        self.btn_generate.setEnabled(False)
        self.log_console.append("[INFO] スライドショー生成を開始します...")
        # Exif情報がない場合のテキストを取得
        exif_missing_text = self.exif_missing_text_input.text().strip()
        def task():
            output = SlideshowBuilder.run_slideshow(
                file_list, outdir, log_func=self.log_console.append, duration_per_image=5, se_path=se_path, exif_enable=exif_enable, exif_missing_text=exif_missing_text)
            if output:
                self.log_console.append(f"[完了] 動画ファイル: {output}")
            else:
                self.log_console.append("[エラー] スライドショー生成に失敗しました")
            self.btn_generate.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()

# TODO: コア処理との連携・進捗表示・エラーハンドリング等を追加予定
