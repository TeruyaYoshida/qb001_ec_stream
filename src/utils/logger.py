"""
ログ出力基盤モジュール
JSON Lines形式でログを出力し、日次ローテーションと30日保持を行う。
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue
from typing import Any, Dict, Optional

# srcディレクトリをパスに追加（相対インポート用）
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_logs_path


class AppLogger:
    """
    アプリケーションロガー
    JSON Lines形式でログを出力する。
    """
    
    # ログレベルの定義
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    
    # ログ保持期間（日）
    RETENTION_DAYS = 30
    
    def __init__(self, module_name: str, log_queue: Optional[Queue] = None):
        """
        Args:
            module_name: ログを出力するモジュール名
            log_queue: GUIへの通知用キュー（オプション）
        """
        self.module_name = module_name
        self.log_queue = log_queue
        self._ensure_log_directory()
    
    def _ensure_log_directory(self) -> None:
        """ログディレクトリが存在することを確認"""
        get_logs_path().mkdir(parents=True, exist_ok=True)
    
    def _get_log_file_path(self) -> Path:
        """今日のログファイルパスを取得"""
        today = datetime.now().strftime("%Y-%m-%d")
        return get_logs_path() / f"app_{today}.json"
    
    def _format_timestamp(self) -> str:
        """ISO 8601形式のタイムスタンプを生成"""
        return datetime.now().astimezone().isoformat()
    
    def _write_log(
        self, 
        level: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        ログをファイルに書き込む
        
        Args:
            level: ログレベル
            message: ログメッセージ
            details: 追加情報（辞書）
        """
        log_record = {
            "timestamp": self._format_timestamp(),
            "level": level,
            "module": self.module_name,
            "message": message,
        }
        
        if details:
            log_record["details"] = details
        
        # ファイルに追記
        log_file = self._get_log_file_path()
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_record, ensure_ascii=False) + '\n')
        except IOError as e:
            print(f"ログ書き込みエラー: {e}", file=sys.stderr)
        
        # GUIへの通知（キューが設定されている場合）
        if self.log_queue:
            display_message = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
            self.log_queue.put({
                "level": level,
                "message": display_message,
                "details": details
            })
    
    def debug(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """DEBUGレベルのログを出力"""
        self._write_log(self.DEBUG, message, details)
    
    def info(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """INFOレベルのログを出力"""
        self._write_log(self.INFO, message, details)
    
    def warning(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """WARNINGレベルのログを出力"""
        self._write_log(self.WARNING, message, details)
    
    def error(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """ERRORレベルのログを出力"""
        self._write_log(self.ERROR, message, details)
    
    def critical(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """CRITICALレベルのログを出力"""
        self._write_log(self.CRITICAL, message, details)


def get_logger(module_name: str, log_queue: Optional[Queue] = None) -> AppLogger:
    """
    ロガーインスタンスを取得する
    
    Args:
        module_name: モジュール名
        log_queue: GUIへの通知用キュー（オプション）
        
    Returns:
        AppLoggerインスタンス
    """
    return AppLogger(module_name, log_queue)


def cleanup_old_logs(retention_days: int = AppLogger.RETENTION_DAYS) -> int:
    """
    指定日数より古いログファイルを削除する
    
    Args:
        retention_days: 保持日数（デフォルト30日）
        
    Returns:
        削除したファイル数
    """
    logs_path = get_logs_path()
    if not logs_path.exists():
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0
    
    for log_file in logs_path.glob("app_*.json"):
        try:
            # ファイル名から日付を抽出（app_YYYY-MM-DD.json）
            date_str = log_file.stem.replace("app_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            if file_date < cutoff_date:
                log_file.unlink()
                deleted_count += 1
        except (ValueError, OSError):
            # 日付パースエラーやファイル削除エラーは無視
            continue
    
    return deleted_count
