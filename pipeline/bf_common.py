"""Shared settings for the Black Friday SMS dashboard build (runs on GitHub Actions or on the Mac).

Environment
  BF_SOURCE      'api'  = read the Drive exports with the service account (GitHub)  |  'local' (default) = Drive for desktop on the Mac
  BF_SA_KEY      service-account key file (default: the Mac's 2. PG_Exports/ppsd_report.json)
  BF_HASH_KEY    secret used to scramble customer emails/phones (default: ../../data/bf_hash_key.txt on the Mac)
  BF_WORK        scratch folder for downloads and the sales copy (default: <repo>/.work, never committed)
"""
import os, hmac, hashlib, datetime
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')
except Exception:  # pragma: no cover
    ET = None

PIPE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(PIPE)
BF_ROOT = os.path.dirname(REPO)                      # .../SMS Blast Campaigns/Black Friday (Mac only)
SOURCE = os.environ.get('BF_SOURCE', 'local')
SA_KEY = os.environ.get('BF_SA_KEY', "/Volumes/LHENHDD500 /Performance Golf Files (2026)/2. PG_Exports/ppsd_report.json")
WORK = os.environ.get('BF_WORK', os.path.join(REPO, '.work'))
os.makedirs(WORK, exist_ok=True)

import glob as _glob
_d = _glob.glob(os.path.expanduser('~/Library/CloudStorage/GoogleDrive-*/My Drive/Phone Team Reports/'))
LOCAL_DRIVE = os.environ.get('BF_LOCAL_DRIVE', _d[0] if _d else '')   # Drive for desktop on the Mac
SMS_FOLDER_ID = '1I5mnmGSrueNfuGrkjdZmnb6lUXqtOXvz'      # Phone Team Reports / Black Friday SMS
CALLS_FOLDER_ID = '1nR7-OTb_MJ6jYf3xpEWLKtBco2a1ok85'    # Phone Team Reports / Aloware Call Logs - BF2 (month subfolders)
TRACKER_ID, TRACKER_TAB = '1VeSDG4zeyn_nfsd2FuSk7I0A6CqhJfJlU1nbN8W1qCI', 'Call Tracking'
SMS_PATTERN = r'^Aloware - Blackfish 2 - Black Friday SMS logs - WB\d{4}\.csv$'
CALLS_PATTERN = r'^Aloware - Blackfish 2 - Call logs - WB\d{4}\.csv$'
FILES_SINCE = datetime.datetime(2026, 11, 16)             # ignore export files last changed before the campaign week
START = '2026-11-18'                                      # first campaign day
LINE = 'Black Friday SMS Blast'
SALES_CSV = os.path.join(WORK, 'bf_sales_tracker.csv')
SALES_META = os.path.join(WORK, 'bf_sales_pulled.json')
GROUPS_JSON = os.path.join(PIPE, 'groups.json')


def hash_key():
    k = os.environ.get('BF_HASH_KEY')
    if not k:
        p = os.path.join(BF_ROOT, 'data', 'bf_hash_key.txt')
        k = open(p).read().strip() if os.path.exists(p) else ''
    if not k:
        raise SystemExit('BF_HASH_KEY is not set')
    return k.encode()


def scramble(value):
    """Keyed hash (HMAC-SHA256, 16 hex) of a lowercased email or a 10-digit phone. Not reversible without the key."""
    return hmac.new(hash_key(), str(value).strip().lower().encode(), hashlib.sha256).hexdigest()[:16]


def now_et():
    return datetime.datetime.now(ET) if ET else datetime.datetime.now()
