"""
file_scanner.py テスト
"""
from core.file_scanner import scan_video_files
from pathlib import Path
import tempfile
import shutil

def test_scan_video_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d/"a.mp4").write_text("")
        (d/"b.txt").write_text("")
        (d/"sub").mkdir()
        (d/"sub"/"c.mkv").write_text("")
        files = scan_video_files(d)
        assert any(f.name == "a.mp4" for f in files)
        assert any(f.name == "c.mkv" for f in files)
        assert not any(f.name == "b.txt" for f in files)
