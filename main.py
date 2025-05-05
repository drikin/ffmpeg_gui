"""
アプリケーションエントリポイント
PySide6 + Draculaテーマ + サイドバー + QStackedWidget構成
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QLabel
from PySide6.QtCore import Qt
from ui_pages.loudness_page import LoudnessPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg MultiTool GUI")
        self.resize(1000, 700)
        # メインレイアウト
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        # サイドバー
        sidebar = QVBoxLayout()
        self.btn_loudness = QPushButton("Loudness Normalization")
        self.btn_loudness.setObjectName("btn_loudness")
        sidebar.addWidget(self.btn_loudness)
        sidebar.addStretch()
        # スタックページ
        self.stack = QStackedWidget()
        self.loudness_page = LoudnessPage()
        self.stack.addWidget(self.loudness_page)
        # レイアウト結合
        main_layout.addLayout(sidebar, 1)
        main_layout.addWidget(self.stack, 6)
        self.setCentralWidget(central_widget)
        # イベント接続
        self.btn_loudness.clicked.connect(lambda: self.stack.setCurrentWidget(self.loudness_page))
        # Draculaテーマ適用（必要ならQSSを読み込み）
        self.apply_dracula_theme()

    def apply_dracula_theme(self):
        # 必要に応じてQSSファイルを読み込む（ここではシンプルなダークテーマ例）
        self.setStyleSheet("""
            QWidget { background: #282a36; color: #f8f8f2; }
            QPushButton { background: #44475a; color: #f8f8f2; border-radius: 6px; padding: 8px; }
            QPushButton:hover { background: #6272a4; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
