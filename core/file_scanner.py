"""
動画ファイル再帰抽出ユーティリティ
"""
from pathlib import Path
from typing import List

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv'}

def scan_video_files(directory: Path) -> List[Path]:
    """
    指定ディレクトリ以下から動画ファイルを再帰的に抽出
    Args:
        directory (Path): 走査対象ディレクトリ
    Returns:
        List[Path]: 動画ファイルのパス一覧
    """
    files = []
    for path in directory.rglob('*'):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            files.append(path)
    return files
