"""
Whisperを用いた音声セリフ区間抽出・SRT生成・FFmpegコマンド生成モジュール
"""
import whisper
import tempfile
import os
import re
import subprocess
import mimetypes
from typing import List, Tuple

class SpeechSegmentExtractor:
    def __init__(self, whisper_model: str = "small"):
        self.whisper_model = whisper_model
        self.model = None  # 必要時に遅延ロード
        self._load_model()
        
    def _load_model(self):
        """モデルをロードする。既にロード済みの場合は何もしない。"""
        if self.model is not None:
            return
            
        try:
            print(f"[INFO] Whisperモデル '{self.whisper_model}' をロード中...")
            self.model = whisper.load_model(self.whisper_model)
            if hasattr(self.model, 'name'):
                print(f"[INFO] Whisperモデル '{self.model.name()}' のロードに成功しました")
            else:
                print(f"[INFO] Whisperモデルのロードに成功しました")
        except Exception as e:
            error_msg = f"[ERROR] Whisperモデル '{self.whisper_model}' のロードに失敗しました: {str(e)}"
            print(error_msg)
            self.model = None
            raise RuntimeError(error_msg)
    
    def _ensure_model_loaded(self):
        """モデルがロードされていることを確認し、必要に応じて再ロードする"""
        try:
            # モデルが変更されていたら再ロード
            if self.model is not None and hasattr(self, 'whisper_model'):
                current_model = getattr(self.model, 'name', lambda: 'unknown')()
                if current_model != self.whisper_model:
                    print(f"[INFO] モデルが変更されたため再ロード: {current_model} -> {self.whisper_model}")
                    self.model = None
            
            # モデルがまだロードされていないか、Noneの場合はロードを試みる
            if self.model is None:
                self._load_model()
                
            # ロード後もNoneの場合は例外をスロー
            if self.model is None:
                raise RuntimeError("Whisperモデルのロードに失敗しました")
                
        except Exception as e:
            error_msg = f"モデルのロード中にエラーが発生しました: {str(e)}"
            print(f"[ERROR] {error_msg}")
            self.model = None
            raise RuntimeError(error_msg)

    def transcribe_to_srt(self, audio_path: str, srt_path: str = None, language: str = 'ja', log_func=None, output_path: str = None, word_level: bool = False, word_timestamps: bool = None, api_key: str = None, model: str = 'small', merge_gap_sec: float = 0.0) -> str:
        def log(msg):
            if log_func:
                log_func(msg)
            else:
                print(msg)
                
        # 後方互換性のためword_timestampsも受け付けるが、word_levelを優先
        if word_timestamps is not None:
            word_level = word_timestamps
            
        # モデルが変更されたか、現在のモデルがNoneの場合は再ロードを試みる
        model_changed = False
        if not hasattr(self, 'whisper_model') or self.whisper_model != model:
            log(f"[INFO] モデルが変更されました: {getattr(self, 'whisper_model', 'None')} -> {model}")
            self.whisper_model = model
            model_changed = True
            
        # モデルのロードを必要に応じて行う
        if api_key is None:  # ローカルモデルのみロード
            try:
                # モデルが変更されたか、現在のモデルがNoneの場合は強制的に再ロード
                if model_changed or self.model is None:
                    log(f"[INFO] モデルを再ロードします: {self.whisper_model}")
                    self.model = None  # 強制的に再ロード
                    
                self._ensure_model_loaded()
                
                if self.model is None:
                    raise RuntimeError("Whisperモデルが正しくロードされていません")
                    
                log(f"[INFO] 使用中のモデル: {getattr(self.model, 'name', lambda: 'unknown')() if hasattr(self.model, 'name') else 'unknown'}")
                
            except Exception as e:
                error_msg = f"Whisperモデルのロード中にエラーが発生しました: {str(e)}"
                log(error_msg)
                self.model = None  # エラーが発生した場合はモデルをクリア
                raise RuntimeError(error_msg)
        """
        指定音声ファイルからWhisperでSRTを生成し、パスを返す
        language: 言語コード（'ja'=日本語, 'en'=英語, None=自動判定）
        log_func: ログ出力用コールバック（Noneならprint）
        output_path: 実際に書き出される動画ファイルパス（再生時間を測定する場合に指定）
        """
        def log(msg):
            if log_func:
                log_func(msg)
            else:
                print(msg)

        # OpenAI APIキーが指定された場合は環境変数に設定
        is_server = False
        use_openai_api = False
        if api_key and api_key.startswith("sk-"):
            is_server = True
            use_openai_api = True
        # トランスクライブオプションを設定
        transcribe_kwargs = dict(
            task="transcribe",
            verbose=False,
            language=language if language != 'auto' else None,
            word_timestamps=word_level
        )
        # ログ: サーバー/ローカル判定
        if is_server:
            log("[INFO] Whisper API（サーバー）でワードレベル解析を実行します")
        else:
            log("[INFO] ローカルWhisperモデルで解析を実行します")

        import sys
        import contextlib
        import io
        if use_openai_api:
            try:
                # 入力が動画またはwav等の場合はaac(m4a)に変換してからAPIに渡す
                ext = os.path.splitext(audio_path)[1].lower()
                mime, _ = mimetypes.guess_type(audio_path)
                need_extract = ext not in ['.m4a', '.aac'] or (mime and not mime.startswith('audio'))
                if need_extract:
                    fd, tmp_aac = tempfile.mkstemp(suffix='.m4a')
                    os.close(fd)
                    ffmpeg_cmd = [
                        'ffmpeg', '-y', '-i', audio_path, '-vn', '-acodec', 'aac', '-b:a', '128k', tmp_aac
                    ]
                    log(f"[INFO] ffmpegで音声のみAAC(m4a)に切り出し: {' '.join(ffmpeg_cmd)}")
                    subprocess.run(ffmpeg_cmd, check=True)
                    upload_path = tmp_aac
                else:
                    upload_path = audio_path
                import openai
                with open(upload_path, "rb") as audio_file:
                    log("[INFO] OpenAI Whisper APIへ音声ファイルをアップロードします...")
                    response = openai.Audio.transcribe(
                        "whisper-1",
                        audio_file,
                        api_key=api_key,
                        response_format="verbose_json",
                        language=language if language != 'auto' else None,
                        word_timestamps=word_timestamps
                    )
                    result = response
                if need_extract:
                    os.remove(tmp_aac)
            except Exception as e:
                log(f"[ERROR] OpenAI APIリクエスト失敗: {e}")
                raise
        else:
            # Whisperのstdout/stderrをキャプチャしてlog_funcに流す
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            log(f"[INFO] Whisperモデル '{self.whisper_model}' で音声認識を開始します...")
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                result = self.model.transcribe(audio_path, **transcribe_kwargs)
            # キャプチャした内容をlog_funcに流す
            std_out = stdout_buf.getvalue()
            std_err = stderr_buf.getvalue()
            if std_out.strip():
                for line in std_out.strip().splitlines():
                    log(f"[Whisper-stdout] {line}")
            if std_err.strip():
                for line in std_err.strip().splitlines():
                    log(f"[Whisper-stderr] {line}")
        segments = result["segments"]
        # セリフ区間リストと合計再生時間をログ出力
        log("[セリフ区間リスト]")
        # duration制限・重複除外済みの区間リストで再計算
        total_speech = 0.0
        used = []
        for seg in segments:
            st, ed = seg["start"], seg["end"]
            # duration制限・重複除外済み（parse_srt_segments側で保証済み）
            if used and abs(st - used[-1][0]) < 1e-3 and abs(ed - used[-1][1]) < 1e-3:
                continue
            log(f"  {st:.2f} - {ed:.2f}秒")
            total_speech += ed-st
            used.append((st, ed))
        # 元動画の再生時間を取得
        try:
            import subprocess, re
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            out = subprocess.check_output(cmd, encoding="utf-8", errors="ignore").strip()
            original_duration = float(re.findall(r"[\d.]+", out)[0])
        except Exception as e:
            original_duration = None
            log(f"[警告] 元動画の再生時間取得失敗: {e}")
        log("[再生時間]")
        if original_duration:
            log(f"  元動画: {original_duration:.2f} 秒")
        log(f"  切り取り後(理論値): {total_speech:.2f} 秒")
        if original_duration:
            log(f"  差分(理論値): {original_duration-total_speech:.2f} 秒")

        # 出力ファイルの実測再生時間もログ
        if output_path:
            try:
                cmd2 = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", output_path]
                out2 = subprocess.check_output(cmd2, encoding="utf-8", errors="ignore").strip()
                actual_duration = float(re.findall(r"[\d.]+", out2)[0])
                log(f"  出力ファイル実測: {actual_duration:.2f} 秒")
                if original_duration:
                    log(f"  差分(実測): {original_duration-actual_duration:.2f} 秒")
                log(f"  理論値と実測の差: {actual_duration-total_speech:.2f} 秒")
            except Exception as e:
                log(f"[警告] 出力ファイル再生時間取得失敗: {e}")

        if srt_path is None:
            srt_fd, srt_path = tempfile.mkstemp(suffix=".srt")
            os.close(srt_fd)
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(result["segments"], 1):
                # SRT形式で書き出し
                start = self._format_srt_time(seg["start"])
                end = self._format_srt_time(seg["end"])
                text = seg["text"].strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        return srt_path

    def parse_srt_segments(self, srt_path: str, offset_sec: float = 1.0, merge_gap_sec: float = 0.0, reference_media_path: str = None) -> List[Tuple[float, float]]:
        """
        SRTファイルをパースし、start/endにオフセットを加えた区間リストを返す。
        merge_gap_sec（デフォルト0）はセリフ間隔のマージ閾値。0の時はSRTセグメント単位で返す。
        reference_media_pathが指定されていれば、その長さを超える区間は無視する。
        """
        # 入力メディアの長さ取得
        max_duration = None
        if reference_media_path:
            try:
                import subprocess
                cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", reference_media_path
                ]
                out = subprocess.check_output(cmd, encoding="utf-8", errors="ignore").strip()
                max_duration = float(re.findall(r"[\d.]+", out)[0])
            except Exception:
                max_duration = None
        raw_segments = []
        with open(srt_path, encoding="utf-8") as f:
            content = f.read()
        for match in re.finditer(r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", content):
            start = self._parse_srt_time(match.group(2))
            end = self._parse_srt_time(match.group(3))
            # オフセット適用
            start = max(0, start - offset_sec)
            if max_duration is not None:
                if start >= max_duration:
                    # startがduration超えた時点で以降の区間は無視
                    break
                end = min(end + offset_sec, max_duration)
            else:
                end = end + offset_sec
            # 無効・ゼロ長・逆転区間・重複区間を除外
            if end <= start:
                continue
            if raw_segments and abs(start - raw_segments[-1][0]) < 1e-3 and abs(end - raw_segments[-1][1]) < 1e-3:
                continue  # 完全重複
            raw_segments.append((start, end))
        # 最後のトリム範囲のendをdurationに合わせる
        if max_duration is not None and raw_segments:
            last_start, last_end = raw_segments[-1]
            if last_end > max_duration:
                raw_segments[-1] = (last_start, max_duration)
        if not raw_segments:
            return []
        def _normalize_segments(segments):
            if not segments:
                return []
            segments = sorted(segments, key=lambda x: x[0])
            merged = [segments[0]]
            for cur in segments[1:]:
                prev = merged[-1]
                if cur[0] <= prev[1]:  # 重複・連続・オーバーラップ
                    merged[-1] = (prev[0], max(prev[1], cur[1]))
                else:
                    merged.append(cur)
            return merged
        if merge_gap_sec == 0:
            # SRTセグメント単位で重複・オーバーラップも正規化して返す
            return _normalize_segments(raw_segments)
        # 区間のマージ処理
        merged = [raw_segments[0]]
        for seg in raw_segments[1:]:
            prev_start, prev_end = merged[-1]
            cur_start, cur_end = seg
            # 前区間と現区間がmerge_gap_sec以内なら結合
            if cur_start - prev_end <= merge_gap_sec:
                merged[-1] = (prev_start, max(prev_end, cur_end))
            else:
                merged.append(seg)
        return merged

    def build_ffmpeg_commands(self, video_path: str, segments: List[Tuple[float, float]], output_path: str, 
                          merge_gap_sec: float = 0.0, crossfade_duration: float = 0.2, log_func=None) -> str:
        """
        FFmpegコマンド文字列を生成
        
        Args:
            video_path: 入力動画ファイルのパス
            segments: トリム範囲のリスト [(start1, end1), (start2, end2), ...]
            output_path: 出力ファイルのパス
            merge_gap_sec: セリフ間隔のマージ閾値（秒）
            crossfade_duration: クロスフェードの持続時間（秒）
            log_func: ログ出力用コールバック関数
            
        Returns:
            FFmpegコマンドのリスト（複数のエンコーダオプションを試す場合）
        """
        if not segments or len(segments) == 0:
            return "# セリフ区間がありません"
            
        # ログ出力用のヘルパー関数
        def log(msg):
            if log_func:
                log_func(msg)
            
        afilters = []  # 音声フィルタ
        vfilters = []  # 映像フィルタ
        a_labels = []  # 各セグメント音声ラベル
        v_labels = []  # 各セグメント映像ラベル
        
        # 各セグメントをトリミング
        for idx, (start, end) in enumerate(segments):
            a_label = f"a{idx}"
            v_label = f"v{idx}"
            a_labels.append(a_label)
            v_labels.append(v_label)
            afilters.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[{a_label}]")
            vfilters.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[{v_label}]")
        
        # クロスフェード処理（2つ以上のセグメントがあり、クロスフェードが有効な場合）
        if len(a_labels) > 1 and crossfade_duration > 0:
            log(f"\n[クロスフェード処理] クロスフェード時間: {crossfade_duration:.3f}秒")
            
            # クロスフェード用に各セグメントの最後に余分な時間を追加
            for i in range(len(a_labels)):
                afilters.append(f"[{a_labels[i]}]apad=pad_dur={crossfade_duration}[p{i}]")
                a_labels[i] = f"p{i}"
            
            # クロスフェードを適用
            prev = a_labels[0]
            for i in range(1, len(a_labels)):
                curr = a_labels[i]
                out = f"cf{i}"
                
                # クロスフェードが適用される区間をログに出力
                prev_seg_idx = i-1
                curr_seg_idx = i
                prev_start, prev_end = segments[prev_seg_idx]
                curr_start, curr_end = segments[curr_seg_idx]
                
                # クロスフェードが適用される時間範囲を計算
                fade_start = max(prev_start, prev_end - crossfade_duration)
                fade_end = min(curr_start + crossfade_duration, curr_end)
                
                log(f"  セグメント {prev_seg_idx+1} と {curr_seg_idx+1} の間にクロスフェードを適用:")
                log(f"    前のセグメント: {fade_start:.3f} - {prev_end:.3f} 秒")
                log(f"    次のセグメント: {curr_start:.3f} - {fade_end:.3f} 秒")
                log(f"    クロスフェード区間: {fade_start:.3f} - {fade_end:.3f} 秒 (長さ: {fade_end-fade_start:.3f}秒)")
                
                afilters.append(f"[{prev}][{curr}]acrossfade=d={crossfade_duration}:c1=tri:c2=tri[{out}]")
                prev = out
            aout = prev
        else:
            # 単純連結
            if len(a_labels) == 1:
                aout = a_labels[0]
            else:
                a_concat_labels = ''.join([f'[{a}]' for a in a_labels])
                aout = 'aout'
                afilters.append(f"{a_concat_labels}concat=n={len(a_labels)}:v=0:a=1[{aout}]")

        # 映像concat
        vconcat_labels = ''.join([f'[{v}]' for v in v_labels])
        vout = 'vout'
        vfilters.append(f"{vconcat_labels}concat=n={len(v_labels)}:v=1:a=0[{vout}]")
        # filter_complex全体
        filter_complex = ';'.join(afilters + vfilters)
        # コマンド組み立て
        # macではHWエンコーダ(hevc_videotoolbox)を優先しH.265で出力
        # libx265でのエンコードも可能だが速度・消費電力の観点でHW優先
        # クォートは不要。コマンドリストをそのままExecutorに渡す
        import platform
        # OSごとに適切なエンコーダを選択し、順に試せるようリストで返す
        system = platform.system()
        cmd_list = []
        if system == "Windows" or system == "Linux":
            # NVIDIA→Intel QSV→ソフトウェアの順で試行
            for video_codec in ["h264_nvenc", "h264_qsv", "libx264"]:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-filter_complex", filter_complex,
                    "-map", f"[{vout}]", "-map", f"[{aout}]",
                    "-c:v", video_codec,  # HWエンコーダ指定
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",  # 映像・音声ストリーム長不一致時に短い方で切ることでmux不整合を防ぐ
                    "-movflags", "faststart",  # QuickTime/Final Cut Pro互換性向上
                    str(output_path)
                ]
                cmd_list.append(cmd)
        elif system == "Darwin":
            # macOSはHWエンコーダ(hevc_videotoolbox)で出力し、Apple互換性を最大化
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-filter_complex", filter_complex,
                "-map", f"[{vout}]", "-map", f"[{aout}]",
                "-c:v", "hevc_videotoolbox",
                "-pix_fmt", "yuv420p",  # 8bit 4:2:0でApple互換性
                "-profile:v", "main",   # Main10ではなくMain
                "-tag:v", "hvc1",       # QuickTime/Final Cut Pro互換タグ
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                "-movflags", "faststart",
                str(output_path)
            ]
            cmd_list.append(cmd)
        # 返り値をリストに変更（呼び出し側で順に実行し、成功したものを採用）
        # 既存呼び出し側がstr/リスト両対応なので、1つだけの時はそのまま返す
        return cmd_list if len(cmd_list) > 1 else cmd_list[0]

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    @staticmethod
    def _parse_srt_time(srt_time: str) -> float:
        h, m, s_ms = srt_time.split(":")
        s, ms = s_ms.split(",")
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000
