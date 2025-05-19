"""
ffmpegコマンド生成モジュール（ラウドネス補正用）
"""
from pathlib import Path
from typing import Optional
import subprocess
import json

class CommandBuilder:
    """
    ffmpegコマンド生成クラス
    """
    @staticmethod
    def build_loudness_normalization_cmd(
        input_path: Path,
        output_path: Path,
        use_dynaudnorm: bool = True,
        material_mode: bool = False,
        measured_params: dict = None,
        true_peak_limit: float = -1.5,
        add_limiter: bool = True
    ) -> list:
        """
        映像を再エンコードせず、音声のみをloudnormで補正するコマンドを生成
        - 映像はそのままコピー
        - 音声は一時ファイルに抽出して補正後、映像とマージ
        """
        import tempfile
        import os
        import shutil
        from pathlib import Path

        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp(prefix='ffmpeg_gui_')
        temp_video = os.path.join(temp_dir, 'video.mp4')
        temp_audio = os.path.join(temp_dir, 'audio.aac')
        temp_audio_norm = os.path.join(temp_dir, 'audio_norm.aac')

        try:
            # 1. 映像をそのままコピー（再エンコードなし）
            video_cmd = [
                'ffmpeg',
                '-y',
                '-i', str(input_path),
                '-c:v', 'copy',
                '-an',  # 音声を無効化
                temp_video
            ]

            # 2. 音声を抽出して補正
            # オーディオフィルターの構築
            if material_mode:
                af = f"loudnorm=I=-18:LRA=11:TP={true_peak_limit}:linear=true:print_format=summary"
            elif use_dynaudnorm:
                af = (
                    f"dynaudnorm=f=250:g=15:p=0.95:m=5:r=0.0:n=1," +
                    f"loudnorm=I=-14:LRA=7:TP={true_peak_limit}:print_format=summary"
                )
            else:
                af = f"loudnorm=I=-14:LRA=7:TP={true_peak_limit}:print_format=summary"
            
            if add_limiter:
                af += f",alimiter=limit={true_peak_limit}dB"

            audio_cmd = [
                'ffmpeg',
                '-y',
                '-i', str(input_path),
                '-vn',  # 映像を無効化
                '-c:a', 'pcm_s16le',  # 一時的に非圧縮PCMで抽出
                '-f', 'wav',
                'pipe:1'
            ]

            audio_filter_cmd = [
                'ffmpeg',
                '-y',
                '-f', 'wav',
                '-i', 'pipe:0',
                '-af', af,
                '-c:a', 'aac',
                '-b:a', '192k',
                temp_audio_norm
            ]

            # 3. 映像と補正済み音声をマージ
            merge_cmd = [
                'ffmpeg',
                '-y',
                '-i', temp_video,
                '-i', temp_audio_norm,
                '-c:v', 'copy',
                '-c:a', 'copy',
                '-map', '0:v',
                '-map', '1:a',
                '-movflags', '+faststart',
                str(output_path)
            ]

            # コマンドのリストを返す（実行は呼び出し元で行う）
            return [video_cmd, audio_cmd, audio_filter_cmd, merge_cmd]

        except Exception as e:
            # エラーが発生したら一時ファイルを削除
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise e


    @staticmethod
    def get_video_format_info(file_path: str) -> dict:
        """
        ffprobeで主要な動画プロパティ（コーデック・解像度・フレームレート等）を取得
        """
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=codec_name,width,height,r_frame_rate,pix_fmt", "-of", "json", file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            stream = info['streams'][0] if 'streams' in info and info['streams'] else {}
            return {
                'codec_name': stream.get('codec_name'),
                'width': stream.get('width'),
                'height': stream.get('height'),
                'r_frame_rate': stream.get('r_frame_rate'),
                'pix_fmt': stream.get('pix_fmt'),
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def build_video_concat_cmd(input_files: list, output_path: Path) -> tuple:
        """
        ffmpeg concat demuxer用のコマンド生成
        - input_files: 結合対象ファイルのパスリスト
        - output_path: 出力ファイルパス
        戻り値: (コマンドリスト, 一時リストファイルパス, 再エンコード有無[bool], フォーマット判定情報, 強制再エンコード理由)
        """
        # 各ファイルのフォーマット取得
        format_list = [CommandBuilder.get_video_format_info(f) for f in input_files]
        ref = format_list[0]
        need_reencode = False
        force_reason = None
        reencode_reasons = []
        for idx, fmt in enumerate(format_list[1:], 1):
            # 主要プロパティが全て一致しているか
            for k in ['codec_name', 'width', 'height', 'r_frame_rate', 'pix_fmt']:
                if fmt.get(k) != ref.get(k):
                    need_reencode = True
                    reencode_reasons.append(f"{k}不一致: {input_files[0]}={ref.get(k)}, {input_files[idx]}={fmt.get(k)}")
            if need_reencode:
                break
        # 出力ファイル拡張子によるmux可否チェック
        ext = output_path.suffix.lower()
        # proresはmovでのみ-mux可能
        if not need_reencode and ref.get('codec_name') == 'prores' and ext != '.mov':
            need_reencode = True
            force_reason = 'proresコーデックはmp4コンテナにコピー不可のため再エンコードを強制します'
        elif need_reencode and not force_reason:
            force_reason = ' / '.join(reencode_reasons) if reencode_reasons else '動画プロパティ不一致のため再エンコードを強制します'

        import tempfile
        concat_list = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt')
        for f in input_files:
            concat_list.write(f"file '{str(Path(f).absolute())}'\n")
        concat_list.close()

        if not need_reencode:
            cmd = [
                "ffmpeg", "-y",
                "-fflags", "+genpts",  # タイムスタンプを再生成
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list.name,
                "-c:v", "copy",  # ビデオコーデックをコピー
                "-c:a", "copy",  # オーディオコーデックをコピー
                "-map", "0:v",   # ビデオストリームのみマッピング
                "-map", "0:a",   # オーディオストリームのみマッピング
                "-async", "1",    # 音声同期を改善
                str(output_path)
            ]
        else:
            # filter_complex方式でコマンド生成
            # 入力ファイルをすべて -i で指定
            cmd = ["ffmpeg", "-y"]
            for f in input_files:
                cmd += ["-i", str(f)]
            n = len(input_files)
            # 映像・音声両方concatする（aformatフィルタでフォーマットを正規化）
            filter_complex = (
                f"[0:v]fps=30000/1001,setpts=N/FRAME_RATE/TB[v0];"
                f"[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a0];"
                f"[v0][a0]concat=n={n}:v=1:a=1[outv][outa]"
            )
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-map", "[outa]",
                "-c:v", "h264_videotoolbox",
                "-pix_fmt", "yuv420p",
                "-profile:v", "high",
                "-level", "4.2",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-movflags", "+faststart",
                str(output_path)
            ]
        return cmd, concat_list.name, need_reencode, format_list, force_reason
