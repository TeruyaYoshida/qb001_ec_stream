"""
Gmail API認証の統合テスト

使用方法:
1. config/credentials.json を配置
2. uv run python tests/integration/test_gmail_auth.py を実行
3. ブラウザが開くので、Googleアカウントでログイン
4. 認証成功後、token.json が生成される

注意:
- このスクリプトは実際のGmail APIにアクセスします
- 初回実行時はブラウザでの認証が必要です
- 2回目以降は token.json を使用して自動認証されます
"""

import sys
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from services.gmail_service import authenticate_gmail, list_unread_emails


def test_gmail_authentication():
    """Gmail API認証テスト"""
    print("=== Gmail API認証テスト ===\n")
    
    # 認証情報ファイルの確認
    creds_path = Path(__file__).parent.parent.parent / 'config' / 'credentials.json'
    if not creds_path.exists():
        print(f"エラー: 認証情報ファイルが見つかりません")
        print(f"必要なファイル: {creds_path}")
        print("\nGoogle Cloud Consoleで以下の手順を実行してください:")
        print("1. プロジェクトを作成")
        print("2. Gmail APIを有効化")
        print("3. OAuth 2.0クライアントIDを作成（デスクトップアプリ）")
        print("4. credentials.jsonをダウンロードして config/ に配置")
        return False
    
    print(f"✓ 認証情報ファイル: {creds_path}")
    
    # 認証実行
    print("\n認証を開始します...")
    try:
        service = authenticate_gmail(creds_path)
        print("✓ 認証成功")
    except Exception as e:
        print(f"✗ 認証失敗: {e}")
        return False
    
    # トークンファイルの確認
    token_path = Path(__file__).parent.parent.parent / 'config' / 'token.json'
    if token_path.exists():
        print(f"✓ トークンファイル生成: {token_path}")
    
    # メール一覧取得テスト
    print("\n未読メールの取得テスト...")
    try:
        messages = list_unread_emails(service, max_results=5)
        print(f"✓ 未読メール取得成功: {len(messages)}件")
        
        if messages:
            print("\n最初の未読メール:")
            msg = messages[0]
            print(f"  件名: {msg.get('subject', '(件名なし)')}")
            print(f"  送信者: {msg.get('from', '(不明)')}")
            print(f"  日時: {msg.get('date', '(不明)')}")
    except Exception as e:
        print(f"✗ メール取得失敗: {e}")
        return False
    
    print("\n=== すべてのテストが成功しました ===")
    return True


if __name__ == '__main__':
    success = test_gmail_authentication()
    sys.exit(0 if success else 1)
