import base64, json, os, mimetypes
from typing import Optional, Tuple
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

AUDIO_EXTS = {'.mp3','.m4a','.wav','.flac','.aac','.ogg','.opus'}

def _creds_from_env(sa_b64: Optional[str], creds_path: Optional[str]):
    if sa_b64:
        data = json.loads(base64.b64decode(sa_b64).decode('utf-8'))
        return service_account.Credentials.from_service_account_info(data, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    if creds_path and os.path.exists(creds_path):
        return service_account.Credentials.from_service_account_file(creds_path, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    raise RuntimeError('Service Account non configurato: imposta GDRIVE_SA_JSON_BASE64 o GOOGLE_APPLICATION_CREDENTIALS')

def _is_audio(name: str, mime: Optional[str]) -> bool:
    ext = os.path.splitext(name or '')[1].lower()
    if ext in AUDIO_EXTS: return True
    if mime and mime.startswith('audio/'): return True
    if not mime and ext:
        guess = mimetypes.guess_type(name)[0]
        return bool(guess and guess.startswith('audio/'))
    return False

def find_latest_audio_and_download(folder_id: str, dest_dir: str, sa_b64: Optional[str], creds_path: Optional[str]) -> Tuple[str, str]:
    creds = _creds_from_env(sa_b64, creds_path)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    q = f"'{folder_id}' in parents and trashed = false"
    fields = 'files(id,name,mimeType,modifiedTime), nextPageToken'
    files = service.files().list(q=q, fields=fields, orderBy='modifiedTime desc', pageSize=50).execute().get('files', [])
    for f in files:
        if _is_audio(f.get('name',''), f.get('mimeType')):
            file_id = f['id']; name = f['name']
            local_path = os.path.join(dest_dir, name)
            request = service.files().get_media(fileId=file_id)
            with open(local_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request); done = False
                while not done: _, done = downloader.next_chunk()
            return file_id, local_path
    raise FileNotFoundError('Nessun file audio trovato nella cartella Drive indicata.')
