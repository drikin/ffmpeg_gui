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

def test_build_video_concat_cmd_same_properties(monkeypatch):
    """
    主要プロパティが一致する場合：demuxer方式・copyで結合されるかテスト
    """
    # ffprobeの戻り値をモック
    def mock_get_video_format_info(file_path):
        return {
            'codec_name': 'h264',
            'width': 1920,
            'height': 1080,
            'r_frame_rate': '30/1',
            'pix_fmt': 'yuv420p',
        }
    monkeypatch.setattr(CommandBuilder, 'get_video_format_info', mock_get_video_format_info)

    files = ["a.mp4", "b.mp4"]
    output = Path("out.mp4")
    cmd, concat_list, need_reencode, format_list, force_reason = CommandBuilder.build_video_concat_cmd(files, output)
    assert need_reencode is False
    assert "-f" in cmd and "concat" in cmd
    assert "-c" in cmd and "copy" in cmd
    assert force_reason is None


def test_build_video_concat_cmd_diff_properties(monkeypatch):
    """
    主要プロパティが不一致の場合：filter_complex方式・h264_videotoolbox再エンコードになるかテスト
    """
    # ffprobeの戻り値をモック
    def mock_get_video_format_info(file_path):
        if "a" in file_path:
            return {
                'codec_name': 'h264',
                'width': 1920,
                'height': 1080,
                'r_frame_rate': '30/1',
                'pix_fmt': 'yuv420p',
            }
        else:
            return {
                'codec_name': 'prores',
                'width': 1280,
                'height': 720,
                'r_frame_rate': '24/1',
                'pix_fmt': 'yuv422p10le',
            }
    monkeypatch.setattr(CommandBuilder, 'get_video_format_info', mock_get_video_format_info)

    files = ["a.mp4", "b.mov"]
    output = Path("out.mp4")
    cmd, concat_list, need_reencode, format_list, force_reason = CommandBuilder.build_video_concat_cmd(files, output)
    assert need_reencode is True
    assert "-filter_complex" in cmd
    assert "h264_videotoolbox" in cmd
    assert force_reason is not None
    assert "不一致" in force_reason or "再エンコード" in force_reason
