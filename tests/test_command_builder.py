"""
command_builder.py テスト
"""
from core.command_builder import CommandBuilder
from pathlib import Path

def test_build_loudness_normalization_cmd():
    input_path = Path("input.mp4")
    output_path = Path("input_norm-14LUFS.mp4")
    cmd = CommandBuilder.build_loudness_normalization_cmd(input_path, output_path)
    assert "ffmpeg" in cmd[0]
    assert str(input_path) in cmd
    assert str(output_path) in cmd
    assert "loudnorm=I=-14" in " ".join(cmd)
