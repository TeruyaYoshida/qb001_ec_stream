import sys
from pathlib import Path

# srcディレクトリをパスに追加
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

try:
    from services.browser_service import launch_auth_browser
    from config import get_browser_profile_path
except ImportError as e:
    print(f"モジュールの読み込みに失敗しました: {e}")
    sys.exit(1)

def main():
    profile_path = get_browser_profile_path()

    print("\n=== Chromeプロファイル認証永続化 検証ツール ===")
    print(f"プロファイル保存先: {profile_path}")
    print("-" * 50)
    print("【確認手順】")
    print("1. ブラウザが起動したら、Yahoo! / 佐川 / Google にログインしてください。")
    print("   ※ ログイン時に必ず「ログインしたままにする」等のチェックを入れてください。")
    print("2. ログイン完了後、ブラウザを閉じてください。")
    print("3. 【重要】もう一度このスクリプトを実行し、ログイン画面が表示されず")
    print("   ログイン後の画面（またはログイン済みの状態）が表示されれば成功です。")
    print("-" * 50)
    print("ブラウザを起動しています...\n")

    try:
        launch_auth_browser()
        print("\n✅ ブラウザが正常に閉じられました。")
        print("検証のために、もう一度このスクリプトを実行してみてください。")
        print("python verify_auth.py")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
