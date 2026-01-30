"""
Gmail操作モジュール
Gmail APIを使用した認証、メール取得、ラベル付与、添付ファイルダウンロードを行う。
"""

import base64
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_config_path, load_settings

# Gmail APIのスコープ
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
]

# 「出品済み」ラベル名
PROCESSED_LABEL_NAME = "出品済み"

# グローバル変数でサービスインスタンスを保持
_gmail_service: Optional[Resource] = None


def authenticate_gmail() -> Resource:
    """
    Gmail APIの認証を行う。
    
    token.jsonが存在する場合はそれを使用し、
    存在しない場合は新規認証フローを実行する。
    
    Returns:
        Gmail APIサービスリソース
        
    Raises:
        Exception: 認証に失敗した場合
    """
    global _gmail_service
    
    settings = load_settings()
    creds_path = Path(settings.get("gmail_creds_path", ""))
    
    if not creds_path.exists():
        raise FileNotFoundError(f"Gmail認証情報ファイルが見つかりません: {creds_path}")
    
    token_path = get_config_path() / "token.json"
    creds = None
    
    # 既存のトークンファイルを読み込む
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    # トークンが無効または期限切れの場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # トークンを更新
            creds.refresh(Request())
        else:
            # 新規認証フロー（ローカルサーバー方式）
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # トークンを保存
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    # Gmail APIサービスを構築
    _gmail_service = build('gmail', 'v1', credentials=creds)
    
    return _gmail_service


def get_gmail_service() -> Resource:
    """
    Gmail APIサービスを取得する。
    未認証の場合は認証を行う。
    
    Returns:
        Gmail APIサービスリソース
    """
    global _gmail_service
    
    if _gmail_service is None:
        _gmail_service = authenticate_gmail()
    
    return _gmail_service


def get_listing_emails() -> List[Dict[str, Any]]:
    """
    未処理の「出品依頼メール」を取得する。
    
    検索条件:
        - 件名に「出品依頼」を含む
        - ラベル「出品済み」が付いていない
    
    Returns:
        メッセージ情報のリスト（id, subject, body等）
    """
    service = get_gmail_service()
    
    # 「出品済み」ラベルのIDを取得
    processed_label_id = _get_or_create_label(PROCESSED_LABEL_NAME)
    
    # 検索クエリ
    query = 'subject:出品依頼'
    if processed_label_id:
        query += f' -label:{PROCESSED_LABEL_NAME}'
    
    try:
        # メール一覧を取得
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=100
        ).execute()
        
        messages = results.get('messages', [])
        
        # 各メッセージの詳細を取得
        email_list = []
        for msg in messages:
            message_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()
            
            # ヘッダーから件名を取得
            headers = message_data.get('payload', {}).get('headers', [])
            subject = next(
                (h['value'] for h in headers if h['name'].lower() == 'subject'),
                ''
            )
            
            # 本文を取得
            body = _extract_body(message_data)
            
            email_list.append({
                'id': msg['id'],
                'subject': subject,
                'body': body,
                'raw': message_data
            })
        
        return email_list
        
    except HttpError as e:
        raise Exception(f"メール取得エラー: {e}")


def _extract_body(message: Dict[str, Any]) -> str:
    """
    メッセージから本文を抽出する。
    
    Args:
        message: Gmail APIのメッセージオブジェクト
        
    Returns:
        メール本文（プレーンテキスト）
    """
    payload = message.get('payload', {})
    
    # シンプルなメッセージの場合
    if 'body' in payload and payload['body'].get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    
    # マルチパートメッセージの場合
    parts = payload.get('parts', [])
    for part in parts:
        if part.get('mimeType') == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
    
    # text/htmlフォールバック
    for part in parts:
        if part.get('mimeType') == 'text/html':
            data = part.get('body', {}).get('data', '')
            if data:
                # HTML タグを除去（簡易実装）
                import re
                html = base64.urlsafe_b64decode(data).decode('utf-8')
                return re.sub(r'<[^>]+>', '', html)
    
    return ""


def _get_or_create_label(label_name: str) -> Optional[str]:
    """
    指定名のラベルIDを取得する。存在しない場合は作成する。
    
    Args:
        label_name: ラベル名
        
    Returns:
        ラベルID、または失敗時None
    """
    service = get_gmail_service()
    
    try:
        # 既存のラベルを検索
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        
        for label in labels:
            if label['name'] == label_name:
                return label['id']
        
        # ラベルが存在しない場合は作成
        label_body = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        created_label = service.users().labels().create(
            userId='me',
            body=label_body
        ).execute()
        
        return created_label['id']
        
    except HttpError:
        return None


def mark_as_processed(message_id: str) -> bool:
    """
    処理完了したメールに「出品済み」ラベルを付与する。
    
    Args:
        message_id: メッセージID
        
    Returns:
        成功時True、失敗時False
    """
    service = get_gmail_service()
    label_id = _get_or_create_label(PROCESSED_LABEL_NAME)
    
    if not label_id:
        return False
    
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'addLabelIds': [label_id]}
        ).execute()
        return True
    except HttpError:
        return False


def download_attachments(message_id: str, save_dir: Path) -> List[Path]:
    """
    添付ファイル（商品画像）をダウンロードして保存する。
    
    ファイル名形式: {message_id}_{index:02d}.{ext}
    対応形式: JPEG, PNG, GIF, WebP
    
    Args:
        message_id: メッセージID
        save_dir: 保存先ディレクトリ
        
    Returns:
        保存したファイルパスのリスト
    """
    service = get_gmail_service()
    
    # 保存先ディレクトリを作成
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 対応する画像MIMEタイプ
    valid_mime_types = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
    }
    
    saved_paths = []
    
    try:
        # メッセージの詳細を取得
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        parts = message.get('payload', {}).get('parts', [])
        index = 0
        
        for part in parts:
            mime_type = part.get('mimeType', '')
            
            if mime_type in valid_mime_types:
                attachment_id = part.get('body', {}).get('attachmentId')
                
                if attachment_id:
                    # 添付ファイルをダウンロード
                    attachment = service.users().messages().attachments().get(
                        userId='me',
                        messageId=message_id,
                        id=attachment_id
                    ).execute()
                    
                    data = attachment.get('data', '')
                    if data:
                        # ファイルを保存
                        ext = valid_mime_types[mime_type]
                        filename = f"{message_id}_{index:02d}{ext}"
                        file_path = save_dir / filename
                        
                        with open(file_path, 'wb') as f:
                            f.write(base64.urlsafe_b64decode(data))
                        
                        saved_paths.append(file_path)
                        index += 1
        
        return saved_paths
        
    except HttpError as e:
        raise Exception(f"添付ファイルダウンロードエラー: {e}")


def send_reply(message_id: str, item_name: str, auction_id: str) -> bool:
    """
    出品完了時、依頼メールに対して完了通知を返信する。
    
    設定のenable_reply_notificationがtrueの場合のみ実行。
    
    Args:
        message_id: 元のメッセージID
        item_name: 商品名
        auction_id: オークションID
        
    Returns:
        成功時True、失敗時False（設定で無効の場合もFalse）
    """
    settings = load_settings()
    
    if not settings.get("enable_reply_notification", False):
        return False
    
    service = get_gmail_service()
    
    try:
        # 元のメッセージを取得
        original = service.users().messages().get(
            userId='me',
            id=message_id,
            format='metadata',
            metadataHeaders=['From', 'Subject', 'Message-ID']
        ).execute()
        
        headers = original.get('payload', {}).get('headers', [])
        
        # 送信先アドレスを取得
        to_address = next(
            (h['value'] for h in headers if h['name'].lower() == 'from'),
            None
        )
        
        # Message-IDを取得（In-Reply-Toヘッダー用）
        original_message_id = next(
            (h['value'] for h in headers if h['name'].lower() == 'message-id'),
            None
        )
        
        if not to_address:
            return False
        
        # 返信メッセージを作成
        reply_body = f"""以下の商品の出品が完了しました。

商品名: {item_name}
オークションID: {auction_id}
出品URL: https://page.auctions.yahoo.co.jp/jp/auction/{auction_id}

---
本メールは自動送信されています。
"""
        
        # MIMEメッセージを構築
        import email.mime.text
        
        message = email.mime.text.MIMEText(reply_body)
        message['to'] = to_address
        message['subject'] = 'Re: 出品依頼'
        
        if original_message_id:
            message['In-Reply-To'] = original_message_id
            message['References'] = original_message_id
        
        # Base64エンコード
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # メール送信
        service.users().messages().send(
            userId='me',
            body={'raw': raw, 'threadId': original.get('threadId')}
        ).execute()
        
        return True
        
    except HttpError:
        return False
