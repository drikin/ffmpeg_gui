"""
ffmpegコマンド実行＋ログストリーム
"""
import subprocess
from typing import Callable, List

class Executor:
    """
    コマンド実行・ログストリームクラス
    """
    @staticmethod
    def run_command(cmd: List[str], log_callback: Callable[[str], None]=None) -> int:
        """
        コマンドを実行し、標準出力・標準エラーをリアルタイムでコールバックに渡す
        Args:
            cmd (List[str]): 実行コマンド
            log_callback (Callable): ログ出力用コールバック
        Returns:
            int: プロセスの終了コード
        """
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            if log_callback:
                log_callback(line.rstrip())
        process.stdout.close()
        return process.wait()
