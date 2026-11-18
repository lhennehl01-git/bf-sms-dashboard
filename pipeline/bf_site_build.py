"""Builds the Black Friday SMS dashboard page (index.html at the repo root) from:
  - Texts:  Aloware "Black Friday SMS logs - WB####.csv" (Drive: Phone Team Reports / Black Friday SMS)
  - Calls:  Aloware "Call logs - WB####.csv", only rows on the Black Friday SMS Blast line (Drive: Aloware Call Logs - BF2)
  - Sales:  <work>/bf_sales_tracker.csv from bf_sales_pull.py (Call Type "SMS blast")
  - Groups: groups.json from make_groups.py (scrambled keys only)
No customer names, emails or phone numbers go into the page.
Usage: python3 bf_site_build.py      Prints PUBLISH=yes when the numbers changed or the page is over an hour old."""
import csv, os, re, json, collections, datetime
from bf_common import *
from bf_inputs import inputs, display_name

YES, NO, DNC = "(Admin) Black Friday SMS Blast - Yes - A", "(Admin) Black Friday SMS Blast - No - A", "(Admin) Black Friday SMS Blast - DNC - A"
csv.field_size_limit(10**9)
rd = lambda p: list(csv.DictReader(open(p, encoding='utf-8-sig', newline='')))


def p10(s):
    d = re.sub(r'\D', '', s or ''); return d[-10:] if len(d) >= 10 else ''


def sec(t):
    try:
        h, m, s = (t or '0:0:0').split(':'); return int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError:
        return 0


def ts(s):
    """'2026-11-18 09:00:08' or '11/18/2026 9:00' -> '2026-11-18 09:00:08'."""
    s = (s or '').strip()
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?', s)
    if m:
        return f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d} {int(m[4]):02d}:{m[5]}:{m[6] or '00'}"
    return s[:19]


def kind(p):
    s = p.strip()
    if re.match(r'(?i)^bfcm\b', s): return 'bfcm'
    if re.search(r'(?i)trial', s): return 'trial'
    if re.match(r'(?i)^pg1\b', s): return 'pg1'
    if re.search(r'(?i)hybrid|sf2|sf1|rs1|putter|wedge|driver|iron|^35[79]\b', s): return 'club'
    return 'other'


sms_files, call_files, _ = inputs()
seen, sms = set(), []
for f in sms_files:
    for r in rd(f):
        r['Started At'] = ts(r['Started At'])
        k = r.get('Communication ID') or (r['Started At'] + r['Contact Number'] + r['Direction'])
        if k in seen or r.get('Line Name') != LINE or r['Started At'][:10] < START: continue
        seen.add(k); sms.append(r)
seen, calls, call_asof = set(), [], ''
for f in call_files:
    for r in rd(f):
        r['Started At'] = ts(r['Started At'])
        call_asof = max(call_asof, r['Started At'])        # newest call of any line = how fresh the export is
        k = r.get('Communication ID') or (r['Started At'] + r['Contact Number'])
        if k in seen or r.get('Line Name') != LINE or r['Started At'][:10] < START: continue
        seen.add(k); calls.append(r)

orders = collections.OrderedDict()
for r in (rd(SALES_CSV) if os.path.exists(SALES_CSV) else []):
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', r['date'].strip())
    if not m: continue
    d = f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"
    o = orders.setdefault((d, r['rep'].strip(), r['customer_key']),
                          {'date': d, 'rep': r['rep'].strip(), 'customer': r['customer_key'], 'items': [], 'upfront': 0.0})
    o['items'].append(r['product'].strip())
    o['upfront'] += float(re.sub(r'[$,\s]', '', r['amount']) or 0)
orders = list(orders.values())

G = json.load(open(GROUPS_JSON)) if os.path.exists(GROUPS_JSON) else {'groups': [], 'size': {}, 'phones': {}, 'emails': {}, 'files': []}
_pk = {}
def group_of_phone(p):
    if p not in _pk:
        gi = G['phones'].get(scramble(p)) if p else None
        _pk[p] = G['groups'][gi] if gi is not None else None
    return _pk[p]
group_of_email = lambda k: (G['groups'][G['emails'][k]] if k in G['emails'] else None)


# ---- per-day building blocks; the page adds them up for any date range (people are counted once per range)
idx = {}
def pid(p):
    if p not in idx: idx[p] = len(idx)
    return idx[p]
blank = lambda: {'sent': 0, 'failed': 0, 'yesTexts': 0, 'hours': collections.defaultdict(lambda: [0, 0]),
                 'texted': set(), 'replied': set(), 'yes': set(), 'no': set(), 'dnc': set(), 'called': set(), 'conn': set()}
per = collections.defaultdict(blank)
for r in sms:
    d, h, p = r['Started At'][:10], int(r['Started At'][11:13] or 0), p10(r['Contact Number'])
    x = per[d]
    if r['Direction'] == 'outbound':
        x['sent'] += 1; x['hours'][h][0] += 1
        if r['Disposition Status'] in ('failed', 'invalid'): x['failed'] += 1
        if p: x['texted'].add(pid(p))
    elif r['Direction'] == 'inbound' and p:
        i, t = pid(p), r.get('Tags') or ''
        x['replied'].add(i)
        if YES in t: x['yes'].add(i); x['yesTexts'] += 1; x['hours'][h][1] += 1
        if NO in t: x['no'].add(i)
        if DNC in t: x['dnc'].add(i)
for r in calls:
    d, p = r['Started At'][:10], p10(r['Contact Number'])
    if not p: continue
    if r['Direction'] == 'outbound': per[d]['called'].add(pid(p))
    if sec(r['Talk Time']) >= 90: per[d]['conn'].add(pid(p))
for o in orders: per[o['date']]
gi = {g: i for i, g in enumerate(G['groups'])}
pg = [-1] * len(idx)
for p, i in idx.items():
    g = group_of_phone(p); pg[i] = gi[g] if g in gi else -1
days = {d: {'sent': x['sent'], 'failed': x['failed'], 'yesTexts': x['yesTexts'],
            'hours': [[h, v[0], v[1]] for h, v in sorted(x['hours'].items())],
            **{k: sorted(x[k]) for k in ('texted', 'replied', 'yes', 'no', 'dnc', 'called', 'conn')}} for d, x in sorted(per.items())}
order_rows = [[o['date'], o['rep'], [[it, kind(it)] for it in o['items']], round(o['upfront'], 2),
               gi.get(group_of_email(o['customer']), -1)] for o in orders]
asof = max([r['Started At'] for r in sms] + [''])
sales_asof = json.load(open(SALES_META))['pulled_at'] if os.path.exists(SALES_META) else ''
core = {'updated': {'sms': asof, 'calls': call_asof}, 'days': days, 'orders': order_rows, 'pg': pg,
        'groups': G['groups'], 'gsize': [G['size'].get(g, 0) for g in G['groups']]}
data = dict(core, asof=asof, built=now_et().strftime('%Y-%m-%d %H:%M'))
data['updated'] = dict(core['updated'], sales=sales_asof)
data['sourceList'] = [
    ['SMS (texts and replies)', 'Aloware export in Drive › Phone Team Reports › Black Friday SMS', ', '.join(display_name(f) for f in sms_files), asof],
    ['Calls', 'Aloware export in Drive › Phone Team Reports › Aloware Call Logs - BF2', ', '.join(display_name(f) for f in call_files), call_asof],
    ['Sales', 'Google Sheet "Call Tracking - PG Phone Support", tab Call Tracking (Call Type "SMS blast")', 'Call Tracking', sales_asof],
    ['Groups', 'Upload lists we sent (Cohorts)', ', '.join(G.get('files', [])), '']]

# publish only when the numbers changed, or the live page is over an hour old (keeps the "updated as of" times true)
out = os.path.join(REPO, 'index.html')
old = None
if os.path.exists(out):
    mm = re.search(r'<script id="bf-data" type="application/json">(.*?)</script>', open(out, encoding='utf-8').read(), re.S)
    try:
        old = json.loads(mm[1].replace('<\\/', '</')) if mm else None
    except ValueError:
        old = None
changed = not old or {k: old.get(k) for k in core} != json.loads(json.dumps(core))
age_min = 999
if old and old.get('built'):
    try:
        b = datetime.datetime.strptime(old['built'], '%Y-%m-%d %H:%M').replace(tzinfo=ET)
        age_min = (now_et() - b).total_seconds() / 60
    except ValueError:
        pass
publish = changed or age_min >= 60
if publish:
    tpl = open(os.path.join(PIPE, 'bf_site_template.html'), encoding='utf-8').read()
    open(out, 'w', encoding='utf-8').write(tpl.replace('/*BF_DATA*/null', json.dumps(data, separators=(',', ':')).replace('</', '<\\/')))
u = lambda k: len(set().union(*[set(x[k]) for x in days.values()])) if days else 0
print('as of', asof, '| calls as of', call_asof, '| sales as of', sales_asof, '| texts', len(sms), 'calls', len(calls), 'orders', len(orders))
print({'sent': sum(x['sent'] for x in days.values()), 'replied': u('replied'), 'yes': u('yes'), 'called': u('called'),
       'connected': u('conn'), 'converted': len(orders), 'revenue': round(sum(o['upfront'] for o in orders), 2)})
print('PUBLISH=' + ('yes' if publish else 'no'), '(numbers changed)' if changed else '(page age %d min)' % age_min)
