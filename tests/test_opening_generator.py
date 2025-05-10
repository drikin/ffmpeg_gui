"""
オープニング生成コア処理のテスト
"""
import os
import tempfile
from core.opening_generator import generate_opening

def test_generate_opening():
    text = "第1話"
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_opening.mp4")
        result = generate_opening(text, output_path, print)
        assert result, "オープニング動画生成に失敗しました"
        assert os.path.exists(output_path), "出力ファイルが存在しません"
        assert os.path.getsize(output_path) > 0, "出力ファイルサイズが0です"
