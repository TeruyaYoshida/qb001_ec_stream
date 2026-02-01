"""
ログインセッション維持検証スクリプト

ユーザーのChromeプロファイルを使用してブラウザを起動し、
Yahoo!オークションおよび佐川スマートクラブへの自動ログイン（セッション維持）
が機能しているかを確認します。
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from config import load_settings

# ログ保存ディレクトリ
LOG_DIR = Path(__file__).parent.parent.parent / "logs" / "verification"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_chrome_profile_path():
    """Chromeプロファイルパスを取得（設定ファイル優先、なければデフォルト）"""
    settings = load_settings()
    profile_path = settings.get("browser_profile_path")

    if not profile_path:
        # Macの標準的なパスを推定
        home = Path.home()
        default_path = home / "Library/Application Support/Google/Chrome"
        if default_path.exists():
            return str(default_path)

    return profile_path

def verify_login():
    user_data_dir = get_chrome_profile_path()

    if not user_data_dir:
        print("❌ エラー: Chromeプロファイルパスが見つかりません。config/settings.jsonを設定してください。")
        return

    print(f"🔍 Chromeプロファイルを使用します: {user_data_dir}")
    print("⚠️  注意: Google Chromeが起動している場合は、終了してください。起動したままだとエラーになります。")
    print("   (3秒後に開始します...)")
    time.sleep(3)

    try:
        with sync_playwright() as p:
            # プロファイルを読み込んでブラウザ起動
            # headless=False にして実際の動きが見えるようにする
            print("   -> ブラウザを起動しています...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",  # インストールされているChromeを使用
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars"
                ],
                no_viewport=True,
                timeout=20000  # タイムアウト20秒
            )
            print("   -> ブラウザ起動成功！")

            page = context.pages[0] if context.pages else context.new_page()

            # ---------------------------------------------------------
            # 1. Yahoo!オークション 検証
            # ---------------------------------------------------------
            print("\n--- Yahoo!オークション 検証 ---")
            print("🌐 マイ・オークションにアクセス中...")
            try:
                page.goto("https://auctions.yahoo.co.jp/closeduser/jp/show/mystatus", timeout=30000)
                page.wait_for_load_state("domcontentloaded")

                # ログイン状態チェック
                # 未ログインだとログイン画面にリダイレクトされるか、ログインリンクが表示される
                if "login.yahoo.co.jp" in page.url:
                    print("❌ 結果: 未ログイン（ログイン画面にリダイレクトされました）")
                elif page.locator('a:has-text("ログイン")').count() > 0:
                     print("❌ 結果: 未ログイン（ヘッダーにログインボタンがあります）")
                else:
                    # ユーザーIDが表示されているか確認（セレクタは一般的推測）
                    user_id_elem = page.locator('.yjid, .Welcome__user, #Welcome')
                    user_text = user_id_elem.first.inner_text().strip() if user_id_elem.count() > 0 else "不明"
                    print(f"✅ 結果: ログイン済み (表示ユーザー: {user_text})")

                # スクリーンショット
                ss_path = LOG_DIR / "yahoo_login_status.png"
                page.screenshot(path=str(ss_path))
                print(f"📸 スクリーンショット保存: {ss_path}")

            except Exception as e:
                print(f"❌ エラー: {e}")

            # ---------------------------------------------------------
            # 2. 佐川スマートクラブ 検証
            # ---------------------------------------------------------
            print("\n--- 佐川スマートクラブ 検証 ---")
            print("🌐 ログインページにアクセス中...")
            try:
                # まずログインページへ
                page.goto("https://www.e-service.sagawa-exp.co.jp/portal/do/login/show", timeout=30000)
                page.wait_for_load_state("domcontentloaded")

                # ログイン済みならダッシュボードやトップにリダイレクトされるか？
                # 佐川は通常、セッションが切れるのが早い

                if "login" in page.url:
                    print("ℹ️  状態: ログイン画面です（通常、再ログインが必要です）")
                    # ID/パスワードが自動入力されているかチェック
                    user_val = page.locator('#user2').input_value()
                    pass_val = page.locator('#pass2').input_value()

                    if user_val:
                        print(f"✨ ブラウザによるID自動入力: あり ({user_val})")
                    else:
                        print("⚪️ ブラウザによるID自動入力: なし")

                else:
                    print("✅ 結果: 既にログイン済みです")

                # スクリーンショット
                ss_path = LOG_DIR / "sagawa_login_status.png"
                page.screenshot(path=str(ss_path))
                print(f"📸 スクリーンショット保存: {ss_path}")

            except Exception as e:
                print(f"❌ エラー: {e}")

            print("\n完了しました。5秒後に閉じます。")
            time.sleep(5)
            context.close()

    except Exception as e:
        print(f"\n❌ 致命的なエラー: ブラウザを起動できませんでした。\n{e}")
        print("👉 Chromeが完全に終了しているか確認してください。")

if __name__ == "__main__":
    verify_login()
