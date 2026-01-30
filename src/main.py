"""
GUIとイベントハンドリング - メインモジュール
Flet GUIの構築、イベントハンドリング、およびスレッド制御を行う。
"""

import sys
import threading
from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Optional

import flet as ft

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    load_settings,
    save_settings,
    validate_settings,
    ensure_directories,
    get_images_path,
)
from models.item import ListingItem, ItemCondition, ShippingMethod
from services.browser_service import (
    check_chrome_conflict,
    launch_browser_context,
    close_browser_context,
)
from services.gmail_service import (
    authenticate_gmail,
    get_listing_emails,
    mark_as_processed,
    download_attachments,
    send_reply,
)
from services.auction_service import (
    list_new_item,
    get_unsold_items,
    relist_item,
    relist_all_unsold,
)
from services.shipping_service import (
    get_sold_items,
    register_shipping,
)
from utils.logger import get_logger, cleanup_old_logs
from utils.text_parser import parse_listing_email, validate_listing_data
from utils.file_manager import (
    cleanup_item_images,
    cleanup_orphan_images,
    cleanup_old_history,
)


class WorkerThread(threading.Thread):
    """
    業務処理を実行するワーカースレッド
    """
    
    def __init__(
        self,
        task_func: Callable[[Queue], None],
        log_queue: Queue,
        on_complete: Callable[[], None]
    ):
        """
        Args:
            task_func: 実行するタスク関数（log_queueを引数として受け取る）
            log_queue: ログメッセージを送信するキュー
            on_complete: 完了時に呼び出すコールバック
        """
        super().__init__(daemon=True)
        self.task_func = task_func
        self.log_queue = log_queue
        self.on_complete = on_complete
    
    def run(self):
        try:
            self.task_func(self.log_queue)
        except Exception as e:
            self.log_queue.put({
                "level": "ERROR",
                "message": f"エラーが発生しました: {e}"
            })
        finally:
            self.on_complete()


class MainApp:
    """
    メインアプリケーションクラス
    """
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.log_queue: Queue = Queue()
        self.worker_thread: Optional[WorkerThread] = None
        self.is_processing = False
        
        # ログエリア
        self.log_view: Optional[ft.ListView] = None
        
        # ボタン
        self.listing_button: Optional[ft.ElevatedButton] = None
        self.shipping_button: Optional[ft.ElevatedButton] = None
        self.relisting_button: Optional[ft.ElevatedButton] = None
        
        # ロガー
        self.logger = get_logger("main", self.log_queue)
        
        # 初期化処理
        self._initialize()
        
        # UIを構築
        self._build_ui()
        
        # ログ更新タイマーを開始
        self._start_log_timer()
    
    def _initialize(self) -> None:
        """初期化処理"""
        # 必要なディレクトリを確認・作成
        ensure_directories()
        
        # 孤児画像を削除
        deleted_images = cleanup_orphan_images()
        if deleted_images > 0:
            self.logger.info(f"孤児画像を{deleted_images}件削除しました")
        
        # 古い発送履歴を削除
        deleted_history = cleanup_old_history()
        if deleted_history > 0:
            self.logger.info(f"古い発送履歴を{deleted_history}件削除しました")
        
        # 古いログファイルを削除
        deleted_logs = cleanup_old_logs()
        if deleted_logs > 0:
            self.logger.info(f"古いログファイルを{deleted_logs}件削除しました")
    
    def _build_ui(self) -> None:
        """UIを構築"""
        self.page.title = "中古衣料品販売自動化システム"
        self.page.window.width = 800
        self.page.window.height = 600
        self.page.padding = 20
        
        # ヘッダー
        header = ft.Container(
            content=ft.Text(
                "中古衣料品販売自動化システム",
                size=24,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.alignment.center,
            padding=10,
        )
        
        # アクションボタン群
        self.listing_button = ft.ElevatedButton(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.WB_SUNNY, size=40, color=ft.Colors.ORANGE),
                    ft.Text("朝", size=12),
                    ft.Text("出品", size=18, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=20,
            ),
            width=180,
            height=140,
            on_click=self._on_listing_click,
        )
        
        self.shipping_button = ft.ElevatedButton(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.WB_CLOUDY, size=40, color=ft.Colors.BLUE),
                    ft.Text("昼", size=12),
                    ft.Text("発送", size=18, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=20,
            ),
            width=180,
            height=140,
            on_click=self._on_shipping_click,
        )
        
        self.relisting_button = ft.ElevatedButton(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.NIGHTLIGHT_ROUND, size=40, color=ft.Colors.PURPLE),
                    ft.Text("夜", size=12),
                    ft.Text("再出品", size=18, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=20,
            ),
            width=180,
            height=140,
            on_click=self._on_relisting_click,
        )
        
        button_row = ft.Row(
            [
                self.listing_button,
                self.shipping_button,
                self.relisting_button,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=30,
        )
        
        # ログ表示エリア
        self.log_view = ft.ListView(
            expand=True,
            spacing=2,
            auto_scroll=True,
        )
        
        log_container = ft.Container(
            content=self.log_view,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10,
            expand=True,
        )
        
        # 設定ボタン
        settings_button = ft.TextButton(
            text="設定",
            icon=ft.Icons.SETTINGS,
            on_click=self._on_settings_click,
        )
        
        footer = ft.Row(
            [settings_button],
            alignment=ft.MainAxisAlignment.START,
        )
        
        # レイアウト
        self.page.add(
            ft.Column(
                [
                    header,
                    ft.Divider(),
                    ft.Container(content=button_row, padding=20),
                    ft.Divider(),
                    ft.Container(
                        content=ft.Text("ログ", weight=ft.FontWeight.BOLD),
                        padding=ft.padding.only(bottom=5),
                    ),
                    log_container,
                    ft.Divider(),
                    footer,
                ],
                expand=True,
            )
        )
        
        # 初期メッセージ
        self._add_log_message("INFO", "アプリケーションを起動しました")
    
    def _start_log_timer(self) -> None:
        """ログ更新タイマーを開始"""
        def check_logs():
            self._process_log_queue()
            self.page.update()
        
        # 100ミリ秒ごとにキューをチェック
        self.page.run_thread(self._log_polling_loop)
    
    def _log_polling_loop(self) -> None:
        """ログポーリングループ"""
        import time
        while True:
            self._process_log_queue()
            time.sleep(0.1)
    
    def _process_log_queue(self) -> None:
        """ログキューからメッセージを処理"""
        try:
            while True:
                log_data = self.log_queue.get_nowait()
                level = log_data.get("level", "INFO")
                message = log_data.get("message", "")
                self._add_log_message(level, message)
        except Empty:
            pass
    
    def _add_log_message(self, level: str, message: str) -> None:
        """ログメッセージを表示に追加"""
        if self.log_view is None:
            return
        
        # レベルに応じた色を設定
        color = ft.Colors.BLACK
        if level == "ERROR" or level == "CRITICAL":
            color = ft.Colors.RED
        elif level == "WARNING":
            color = ft.Colors.ORANGE
        elif level == "DEBUG":
            color = ft.Colors.GREY
        
        self.log_view.controls.append(
            ft.Text(message, color=color, size=12)
        )
        
        # 最大500件まで保持
        if len(self.log_view.controls) > 500:
            self.log_view.controls = self.log_view.controls[-500:]
        
        self.page.update()
    
    def _set_buttons_enabled(self, enabled: bool) -> None:
        """ボタンの有効/無効を設定"""
        if self.listing_button:
            self.listing_button.disabled = not enabled
        if self.shipping_button:
            self.shipping_button.disabled = not enabled
        if self.relisting_button:
            self.relisting_button.disabled = not enabled
        self.page.update()
    
    def _on_processing_complete(self) -> None:
        """処理完了時のコールバック"""
        self.is_processing = False
        self._set_buttons_enabled(True)
        self._add_log_message("INFO", "処理が完了しました")
    
    def _check_browser_available(self) -> bool:
        """ブラウザが利用可能かチェック"""
        settings = load_settings()
        profile_path = settings.get("browser_profile_path", "")
        
        if not profile_path:
            self._show_error_dialog(
                "ブラウザプロファイルパスが設定されていません。\n"
                "設定画面からブラウザプロファイルパスを設定してください。"
            )
            return False
        
        is_available, message = check_chrome_conflict(profile_path)
        
        if not is_available:
            self._show_error_dialog(message)
            return False
        
        return True
    
    def _show_error_dialog(self, message: str) -> None:
        """エラーダイアログを表示"""
        def close_dialog(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("エラー"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("OK", on_click=close_dialog),
            ],
            bgcolor=ft.Colors.RED_50,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_listing_click(self, e) -> None:
        """出品ボタンクリック時の処理"""
        if self.is_processing:
            return
        
        if not self._check_browser_available():
            return
        
        self.is_processing = True
        self._set_buttons_enabled(False)
        self._add_log_message("INFO", "出品処理を開始します...")
        
        self.worker_thread = WorkerThread(
            self._listing_task,
            self.log_queue,
            self._on_processing_complete
        )
        self.worker_thread.start()
    
    def _listing_task(self, log_queue: Queue) -> None:
        """出品処理タスク"""
        logger = get_logger("listing", log_queue)
        settings = load_settings()
        context = None
        
        try:
            # Gmail認証
            logger.info("Gmail認証を行います...")
            authenticate_gmail()
            logger.info("Gmail認証が完了しました")
            
            # メールを取得
            logger.info("出品依頼メールを取得中...")
            emails = get_listing_emails()
            logger.info(f"出品依頼メール: {len(emails)}件")
            
            if not emails:
                logger.info("処理対象のメールがありません")
                return
            
            # ブラウザを起動
            logger.info("ブラウザを起動中...")
            profile_path = settings.get("browser_profile_path", "")
            context = launch_browser_context(profile_path)
            logger.info("ブラウザが起動しました")
            
            success_count = 0
            skip_count = 0
            
            for email_data in emails:
                try:
                    message_id = email_data['id']
                    subject = email_data.get('subject', '')
                    body = email_data.get('body', '')
                    
                    logger.info(f"処理中: {subject}")
                    
                    # メール本文を解析
                    parsed_data = parse_listing_email(body)
                    is_valid, errors = validate_listing_data(parsed_data)
                    
                    if not is_valid:
                        logger.warning(f"データ不備: {', '.join(errors)}")
                        mark_as_processed(message_id)
                        skip_count += 1
                        continue
                    
                    # 添付画像をダウンロード
                    images_dir = get_images_path()
                    image_paths = download_attachments(message_id, images_dir)
                    
                    # ListingItemを作成
                    item = ListingItem(
                        name=parsed_data['name'],
                        price=parsed_data['price'],
                        description=parsed_data.get('description', ''),
                        category=parsed_data.get('category', ''),
                        condition=ItemCondition.from_string(parsed_data.get('condition', '')),
                        shipping_method=ShippingMethod.from_string(parsed_data.get('shipping_method', '')),
                        auction_duration=parsed_data.get('auction_duration', 7),
                        image_paths=image_paths,
                        email_message_id=message_id,
                    )
                    
                    # 出品実行
                    if list_new_item(context, item):
                        logger.info(f"出品完了: {item.name} (ID: {item.auction_id})")
                        
                        # 完了通知メールを送信（設定有効時）
                        if item.auction_id:
                            send_reply(message_id, item.name, item.auction_id)
                        
                        success_count += 1
                    else:
                        logger.warning(f"出品失敗: {item.name}")
                        skip_count += 1
                    
                    # メールを処理済みにマーク
                    mark_as_processed(message_id)
                    
                    # 画像を削除
                    cleanup_item_images(image_paths)
                    
                except Exception as e:
                    logger.error(f"処理エラー: {e}")
                    skip_count += 1
                    continue
            
            logger.info(f"出品処理完了: 成功{success_count}件, スキップ{skip_count}件")
            
        except Exception as e:
            logger.error(f"出品処理でエラーが発生しました: {e}")
            
        finally:
            if context:
                close_browser_context()
    
    def _on_shipping_click(self, e) -> None:
        """発送ボタンクリック時の処理"""
        if self.is_processing:
            return
        
        if not self._check_browser_available():
            return
        
        self.is_processing = True
        self._set_buttons_enabled(False)
        self._add_log_message("INFO", "発送処理を開始します...")
        
        self.worker_thread = WorkerThread(
            self._shipping_task,
            self.log_queue,
            self._on_processing_complete
        )
        self.worker_thread.start()
    
    def _shipping_task(self, log_queue: Queue) -> None:
        """発送処理タスク"""
        logger = get_logger("shipping", log_queue)
        settings = load_settings()
        context = None
        
        try:
            # ブラウザを起動
            logger.info("ブラウザを起動中...")
            profile_path = settings.get("browser_profile_path", "")
            context = launch_browser_context(profile_path)
            logger.info("ブラウザが起動しました")
            
            # 落札商品を取得
            logger.info("落札商品を取得中...")
            sold_items = get_sold_items(context)
            logger.info(f"発送対象: {len(sold_items)}件")
            
            if not sold_items:
                logger.info("発送対象の商品がありません")
                return
            
            success_count = 0
            
            for item in sold_items:
                try:
                    logger.info(f"発送登録中: {item.name}")
                    
                    # 佐川e飛伝に登録
                    if register_shipping(context, item):
                        logger.info(f"発送登録完了: {item.name}")
                        success_count += 1
                    
                except Exception as e:
                    # 発送業務のエラーは即時停止
                    logger.critical(f"発送登録エラー: {e}")
                    logger.critical("発送処理を中断します。内容を確認してください。")
                    raise
            
            logger.info(f"発送処理完了: 成功{success_count}件")
            
        except Exception as e:
            logger.error(f"発送処理でエラーが発生しました: {e}")
            
        finally:
            if context:
                close_browser_context()
    
    def _on_relisting_click(self, e) -> None:
        """再出品ボタンクリック時の処理"""
        if self.is_processing:
            return
        
        if not self._check_browser_available():
            return
        
        self.is_processing = True
        self._set_buttons_enabled(False)
        self._add_log_message("INFO", "再出品処理を開始します...")
        
        self.worker_thread = WorkerThread(
            self._relisting_task,
            self.log_queue,
            self._on_processing_complete
        )
        self.worker_thread.start()
    
    def _relisting_task(self, log_queue: Queue) -> None:
        """再出品処理タスク"""
        logger = get_logger("relisting", log_queue)
        settings = load_settings()
        context = None
        
        try:
            # ブラウザを起動
            logger.info("ブラウザを起動中...")
            profile_path = settings.get("browser_profile_path", "")
            context = launch_browser_context(profile_path)
            logger.info("ブラウザが起動しました")
            
            # 未落札商品を取得して再出品
            logger.info("未落札商品を取得中...")
            unsold_items = get_unsold_items(context)
            logger.info(f"再出品対象: {len(unsold_items)}件")
            
            if not unsold_items:
                logger.info("再出品対象の商品がありません")
                return
            
            success_count = 0
            skip_count = 0
            
            for item in unsold_items:
                try:
                    logger.info(f"再出品中: {item.name}")
                    
                    if relist_item(context, item):
                        logger.info(f"再出品完了: {item.name} (新ID: {item.auction_id})")
                        success_count += 1
                    else:
                        logger.warning(f"再出品失敗: {item.name}")
                        skip_count += 1
                        
                except Exception as e:
                    logger.error(f"再出品エラー ({item.name}): {e}")
                    skip_count += 1
                    continue
            
            logger.info(f"再出品処理完了: 成功{success_count}件, スキップ{skip_count}件")
            
        except Exception as e:
            logger.error(f"再出品処理でエラーが発生しました: {e}")
            
        finally:
            if context:
                close_browser_context()
    
    def _on_settings_click(self, e) -> None:
        """設定ボタンクリック時の処理"""
        self._show_settings_dialog()
    
    def _show_settings_dialog(self) -> None:
        """設定ダイアログを表示"""
        settings = load_settings()
        
        # 入力フィールド
        browser_path_field = ft.TextField(
            label="ブラウザプロファイルパス",
            value=settings.get("browser_profile_path", ""),
            width=500,
            hint_text="例: /Users/xxx/Library/Application Support/Google/Chrome/Default",
        )
        
        gmail_creds_field = ft.TextField(
            label="Gmail認証情報パス",
            value=settings.get("gmail_creds_path", ""),
            width=500,
            hint_text="例: ./config/credentials.json",
        )
        
        reply_switch = ft.Switch(
            label="出品完了時にメール返信を送信する",
            value=settings.get("enable_reply_notification", False),
        )
        
        error_text = ft.Text("", color=ft.Colors.RED, visible=False)
        
        def save_settings_click(e):
            new_settings = {
                "browser_profile_path": browser_path_field.value,
                "gmail_creds_path": gmail_creds_field.value,
                "enable_reply_notification": reply_switch.value,
            }
            
            # バリデーション
            is_valid, errors = validate_settings(new_settings)
            
            if not is_valid:
                error_text.value = "\n".join(errors)
                error_text.visible = True
                self.page.update()
                return
            
            # 保存
            if save_settings(new_settings):
                dialog.open = False
                self._add_log_message("INFO", "設定を保存しました")
            else:
                error_text.value = "設定の保存に失敗しました"
                error_text.visible = True
            
            self.page.update()
        
        def close_dialog(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("設定"),
            content=ft.Container(
                content=ft.Column(
                    [
                        browser_path_field,
                        gmail_creds_field,
                        reply_switch,
                        error_text,
                    ],
                    spacing=15,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=550,
                height=300,
            ),
            actions=[
                ft.TextButton("キャンセル", on_click=close_dialog),
                ft.ElevatedButton("保存", on_click=save_settings_click),
            ],
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()


def main(page: ft.Page):
    """アプリケーションエントリーポイント"""
    app = MainApp(page)


if __name__ == "__main__":
    ft.app(target=main)
