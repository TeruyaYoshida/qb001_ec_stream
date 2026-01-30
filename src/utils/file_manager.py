"""
ファイル管理・発送履歴管理モジュール
一時ファイルおよびステータス管理ファイルの操作を行う。
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set

# srcディレクトリをパスに追加（相対インポート用）
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_images_path, get_history_path


# 発送履歴の保持期間（日）
HISTORY_RETENTION_DAYS = 90


def cleanup_item_images(image_paths: list, force: bool = False) -> int:
    """
    商品画像を削除する。
    
    Args:
        image_paths: 削除する画像パスのリスト
        force: True の場合、エラースキップ時でも削除（孤児画像防止）
        
    Returns:
        削除したファイル数
    """
    deleted_count = 0
    
    for path in image_paths:
        try:
            path_obj = Path(path) if not isinstance(path, Path) else path
            if path_obj.exists():
                path_obj.unlink()
                deleted_count += 1
        except OSError:
            # 削除エラーは無視（forceモードでも続行）
            continue
    
    return deleted_count


def cleanup_orphan_images(max_age_hours: int = 24) -> int:
    """
    data/images/ 内で作成から指定時間経過した画像を削除する。
    アプリ起動時に自動実行される（孤児画像の定期クリーンアップ）。
    
    Args:
        max_age_hours: 削除対象とする経過時間（デフォルト24時間）
        
    Returns:
        削除したファイル数
    """
    images_path = get_images_path()
    if not images_path.exists():
        return 0
    
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    deleted_count = 0
    
    # 対応する画像形式
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    for image_file in images_path.iterdir():
        if image_file.is_file() and image_file.suffix.lower() in image_extensions:
            try:
                # ファイルの更新日時を取得
                file_mtime = datetime.fromtimestamp(image_file.stat().st_mtime)
                
                if file_mtime < cutoff_time:
                    image_file.unlink()
                    deleted_count += 1
            except OSError:
                # ファイル操作エラーは無視
                continue
    
    return deleted_count


def _get_shipped_history_path() -> Path:
    """発送履歴ファイルのパスを取得"""
    return get_history_path() / "shipped_ids.json"


def load_shipped_history() -> Set[str]:
    """
    発送済みIDのセットを読み込む。
    
    Returns:
        発送済みオークションIDのセット
    """
    history_path = _get_shipped_history_path()
    
    if not history_path.exists():
        return set()
    
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            shipped_items = data.get("shipped_items", [])
            return {item["auction_id"] for item in shipped_items if "auction_id" in item}
    except (json.JSONDecodeError, IOError, KeyError):
        return set()


def save_shipped_id(auction_id: str, tracking_number: Optional[str] = None) -> bool:
    """
    発送済みIDを履歴ファイルに追記保存する。
    
    Args:
        auction_id: オークションID
        tracking_number: 追跡番号（オプション）
        
    Returns:
        成功時True、失敗時False
    """
    history_path = _get_shipped_history_path()
    
    # 履歴ディレクトリが存在しない場合は作成
    history_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 現在の履歴を読み込む
    shipped_items = []
    if history_path.exists():
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                shipped_items = data.get("shipped_items", [])
        except (json.JSONDecodeError, IOError):
            shipped_items = []
    
    # 新しいレコードを追加
    new_record = {
        "auction_id": auction_id,
        "shipped_at": datetime.now().astimezone().isoformat(),
        "tracking_number": tracking_number
    }
    shipped_items.append(new_record)
    
    # ファイルに保存
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump({"shipped_items": shipped_items}, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def cleanup_old_history(days: int = HISTORY_RETENTION_DAYS) -> int:
    """
    指定日数より古い発送履歴レコードを削除する。
    アプリ起動時に自動実行（履歴ファイルの肥大化防止）。
    
    Args:
        days: 保持日数（デフォルト90日）
        
    Returns:
        削除したレコード数
    """
    history_path = _get_shipped_history_path()
    
    if not history_path.exists():
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            shipped_items = data.get("shipped_items", [])
    except (json.JSONDecodeError, IOError):
        return 0
    
    original_count = len(shipped_items)
    
    # 有効なレコードのみを残す
    valid_items = []
    for item in shipped_items:
        try:
            shipped_at = item.get("shipped_at", "")
            # タイムゾーン情報を含むISO 8601形式をパース
            if shipped_at:
                # タイムゾーン情報を除去して比較（簡易実装）
                date_part = shipped_at.split("T")[0]
                item_date = datetime.strptime(date_part, "%Y-%m-%d")
                
                if item_date >= cutoff_date:
                    valid_items.append(item)
            else:
                # 日付情報がない場合は残す
                valid_items.append(item)
        except (ValueError, AttributeError):
            # パースエラーの場合は残す
            valid_items.append(item)
    
    deleted_count = original_count - len(valid_items)
    
    # 変更があった場合のみ保存
    if deleted_count > 0:
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump({"shipped_items": valid_items}, f, ensure_ascii=False, indent=2)
        except IOError:
            return 0
    
    return deleted_count
