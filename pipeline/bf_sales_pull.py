"""Copies the Black Friday SMS sales (Call Type "SMS blast", from 11/18/2026) from the Call Tracking sheet into
<work>/bf_sales_tracker.csv, reading with the service account (Viewer on the sheet). Customer emails are scrambled.
Usage: python3 bf_sales_pull.py"""
import os, re, csv, json, warnings
warnings.filterwarnings('ignore')
from bf_common import *


def pull():
    import gspread
    from google.oauth2.service_account import Credentials
    cr = Credentials.from_service_account_file(SA_KEY, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    vals = gspread.authorize(cr).open_by_key(TRACKER_ID).worksheet(TRACKER_TAB).get('A:H')
    h = [str(x).strip().lower() for x in vals[0]]
    c = {k: h.index(n) for k, n in [('date', 'date'), ('rep', 'rep name'), ('email', 'customer email'),
                                    ('type', 'call type'), ('product', 'product purchase name'), ('amount', 'upfront payment')]}
    g = lambda r, k: (r[c[k]] if c[k] < len(r) else '').strip()
    y0, m0, d0 = map(int, START.split('-'))
    rows = []
    for r in vals[1:]:
        if g(r, 'type').lower() != 'sms blast' or not g(r, 'product'):
            continue
        m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})$', g(r, 'date'))
        if not m or (int(m[3]), int(m[1]), int(m[2])) < (y0, m0, d0):
            continue
        rows.append([g(r, 'date'), g(r, 'rep'), scramble(g(r, 'email')), g(r, 'product'), g(r, 'amount')])
    tmp = SALES_CSV + '.tmp'
    with open(tmp, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['date', 'rep', 'customer_key', 'product', 'amount']); w.writerows(rows)
    os.replace(tmp, SALES_CSV)
    json.dump({'pulled_at': now_et().strftime('%Y-%m-%d %H:%M:%S'), 'rows': len(rows)}, open(SALES_META, 'w'))
    return len(rows)


if __name__ == '__main__':
    print('sales rows', pull())
