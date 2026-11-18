"""Finds the Aloware export files: on the Mac from Drive for desktop, on GitHub by downloading them with the service account.
inputs() -> (sms_paths, call_paths, newest_change_epoch)"""
import os, re, glob, io, json, datetime
from bf_common import *


def _local():
    sms = [f for f in glob.glob(LOCAL_DRIVE + "Black Friday SMS/*.csv") if re.match(SMS_PATTERN, os.path.basename(f))]
    calls = [f for f in glob.glob(LOCAL_DRIVE + "Aloware Call Logs - BF2/*/*.csv")
             if re.match(CALLS_PATTERN, os.path.basename(f)) and os.path.getmtime(f) >= FILES_SINCE.timestamp()]
    newest = max([os.path.getmtime(f) for f in sms + calls] + [0])
    return sorted(sms), sorted(calls), newest


def _api():
    import warnings; warnings.filterwarnings('ignore')
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    cr = Credentials.from_service_account_file(SA_KEY, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    d = build('drive', 'v3', credentials=cr, cache_discovery=False)
    kw = dict(supportsAllDrives=True, includeItemsFromAllDrives=True, fields='files(id,name,mimeType,modifiedTime)', pageSize=200)
    ls = lambda fid: d.files().list(q=f"'{fid}' in parents and trashed=false", **kw).execute().get('files', [])
    since = FILES_SINCE.strftime('%Y-%m-%dT%H:%M:%S')
    want = [(f, 'sms') for f in ls(SMS_FOLDER_ID) if re.match(SMS_PATTERN, f['name'])]
    for sub in ls(CALLS_FOLDER_ID):
        if sub['mimeType'] == 'application/vnd.google-apps.folder' and sub['modifiedTime'] >= since:
            want += [(f, 'calls') for f in ls(sub['id']) if re.match(CALLS_PATTERN, f['name']) and f['modifiedTime'] >= since]
    cache = os.path.join(WORK, 'drive'); os.makedirs(cache, exist_ok=True)
    idx_p = os.path.join(cache, 'index.json')
    idx = json.load(open(idx_p)) if os.path.exists(idx_p) else {}
    sms, calls, newest = [], [], 0
    for f, kind in want:
        dest = os.path.join(cache, f['id'] + '__' + f['name'])
        if idx.get(f['id']) != f['modifiedTime'] or not os.path.exists(dest):
            buf = io.FileIO(dest, 'wb')
            dl = MediaIoBaseDownload(buf, d.files().get_media(fileId=f['id'], supportsAllDrives=True), chunksize=16 * 1024 * 1024)
            done = False
            while not done:
                _, done = dl.next_chunk()
            buf.close()
            idx[f['id']] = f['modifiedTime']
        (sms if kind == 'sms' else calls).append(dest)
        newest = max(newest, datetime.datetime.strptime(f['modifiedTime'][:19], '%Y-%m-%dT%H:%M:%S').replace(
            tzinfo=datetime.timezone.utc).timestamp())
    json.dump(idx, open(idx_p, 'w'))
    return sorted(sms), sorted(calls), newest


def inputs():
    return _api() if SOURCE == 'api' else _local()


def display_name(path):
    b = os.path.basename(path)
    return b.split('__', 1)[1] if '__' in b else b
