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


CONN = {}   # disposition -> 1/0 connected, from the sheet


def load_dispositions():
    """{disposition: category} from the TMA disposition master sheet; cached so a failed read keeps the last copy."""
    cache = os.path.join(WORK, 'dispositions.json')
    try:
        import gspread, warnings; warnings.filterwarnings('ignore')
        from google.oauth2.service_account import Credentials
        cr = Credentials.from_service_account_file(SA_KEY, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        m = {}
        for w in gspread.authorize(cr).open_by_key(DISP_SHEET_ID).worksheets():
            if not w.title.strip().lower().startswith('call disposition'): continue
            v = w.get_all_values()
            if not v: continue
            h = [x.strip().lower() for x in v[0]]
            di = h.index('call disposition') if 'call disposition' in h else 0
            ci = h.index('disposition category') if 'disposition category' in h else 1
            si = next((i for i, x in enumerate(h) if x.startswith('suggested category')), None)   # used until column B is filled
            ki = next((i for i, x in enumerate(h) if x.startswith('connects')), None)               # "Connects Based on Call Disposition"
            for r in v[1:]:
                if ki is not None and len(r) > ki and r[0].strip() and r[0].strip() not in CONN and r[ki].strip() in ('0', '1'):
                    CONN[r[0].strip()] = int(r[ki])
            for r in v[1:]:
                if len(r) <= max(di, ci) or not r[di].strip() or r[di].strip() in m: continue
                c = r[ci].strip() or (r[si].strip() if si is not None and len(r) > si else '')
                if c: m[r[di].strip()] = c
        if m:
            json.dump(m, open(cache, 'w')); json.dump(CONN, open(cache.replace('.json', '_connects.json'), 'w'))
            return m
    except Exception as e:
        print('disposition sheet not read (%s); using cache' % str(e)[:80])
    cc = cache.replace('.json', '_connects.json')
    if os.path.exists(cc): CONN.update(json.load(open(cc)))
    return json.load(open(cache)) if os.path.exists(cache) else {}


DISP = load_dispositions()


def category(disp, status, talk):
    d = (disp or '').strip()
    if d:
        if d in DISP: return DISP[d]
        l = d.lower()
        for keys, cat in [(('vm', 'unreachable', 'voicemail'), 'Unreachable/Voicemail'), (('busy', 'follow up', 'ffup', 'callback', 'call back'), 'Busy/Follow Up'),
                          (('declined', 'not interested'), 'Declined'), (('sold',), 'Sold'), (('transfer',), 'Transferred call'),
                          (('refund',), 'Refunded'), (('dnc', 'do not call'), 'DNC'), (('wrong', 'invalid'), 'Invalid number')]:
            if any(k in l for k in keys): return cat
        return 'Other'
    if status == 'failed': return 'No answer / failed'
    if status in ('abandoned', 'missed'): return 'Abandoned / missed'
    return 'No outcome logged' if talk < 90 else 'Talked, no outcome logged'
seen, sms = set(), []
for f in sms_files:
    for r in rd(f):
        r['Started At'] = ts(r['Started At'])
        k = r.get('Communication ID') or (r['Started At'] + r['Contact Number'] + r['Direction'])
        if k in seen or r.get('Line Name') != LINE or r['Started At'][:10] < START: continue
        seen.add(k); sms.append(r)
seen, calls, call_asof, any_out = set(), [], '', []
for f in call_files:
    for r in rd(f):
        r['Started At'] = ts(r['Started At'])
        call_asof = max(call_asof, r['Started At'])        # newest call of any line = how fresh the export is
        k = r.get('Communication ID') or (r['Started At'] + r['Contact Number'])
        if k in seen or r['Started At'][:10] < START: continue
        seen.add(k)
        if r['Direction'] == 'outbound': any_out.append((r['Started At'], r['Contact Number']))   # every line, for "Called"
        if r.get('Line Name') == LINE: calls.append(r)

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
# calls (BF line) for the operations view: one row per call, people/reps/outcomes as index numbers
def tmin(t):
    try:
        return int((datetime.datetime.strptime(t[:19], '%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(START, '%Y-%m-%d')).total_seconds() // 60)
    except ValueError:
        return None
norm = lambda n: re.sub(r'[^a-z ]', '', (n or '').lower()).split()
fl = lambda n: (lambda t: (t[0], t[-1]) if t else None)(norm(n))
reps, rep_ix = [], {}
def rid(name):
    k = fl(name)
    if not k: return -1
    if k not in rep_ix: rep_ix[k] = len(reps); reps.append(name.strip())
    return rep_ix[k]
cats, cat_ix, disps, disp_ix = [], {}, [], {}
def ix(lst, d, v):
    if v not in d: d[v] = len(lst); lst.append(v)
    return d[v]
call_rows = []
for r in calls:
    p = p10(r['Contact Number']); t = tmin(r['Started At'])
    if not p or t is None: continue
    who = (r.get('User Name') or '').strip() or (r.get('Attempting') or '').split(',')[0].strip()
    talk = sec(r['Talk Time'])
    disp = (r.get('Call Disposition') or '').strip()
    cat = category(disp, r['Disposition Status'], talk)
    call_rows.append([t, pid(p), rid(who), talk, ix(cats, cat_ix, cat), ix(disps, disp_ix, disp or '(none) ' + r['Disposition Status']),
                      1 if r['Direction'] == 'outbound' else 0, 1 if r['Disposition Status'] == 'completed' else 0,
                      CONN.get(disp, 0)])   # 8: connected by disposition
call_rows.sort()
yes_first = {}
for r in sms:
    if r['Direction'] == 'inbound' and YES in (r.get('Tags') or '') and p10(r['Contact Number']):
        i, t = pid(p10(r['Contact Number'])), tmin(r['Started At'])
        k = (i, r['Started At'][:10])   # first YES per person per day, so a repeat YES on a new day counts that day too
        if t is not None and (k not in yes_first or t < yes_first[k]): yes_first[k] = t
yes_rows = sorted([[t, i] for (i, _), t in yes_first.items()])
yes_ids = {i for (i, _) in yes_first}
yes_calls = collections.defaultdict(list)   # YES lead -> outbound call times on ANY line (minutes), used for "Called"
for st, num in any_out:
    p = p10(num)
    if p and p in idx and idx[p] in yes_ids:
        t = tmin(st)
        if t is not None: yes_calls[idx[p]].append(t)
yes_calls = {i: sorted(v) for i, v in yes_calls.items()}
for o in orders: o['rep_i'] = rid(o['rep'])


ROSTER_ID = '1ntDeRRIGL-w4BqGsbRW0vB-GqEzBK6D4_A9FPdDxAZA'   # phone team roster (Schedule tab), same source as phone-team-calls


def load_roster():
    """{(first, last): [team, lob]} from each person's latest scheduled day up to today; cached for failed reads."""
    cache = os.path.join(WORK, 'roster.json')
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        cr = Credentials.from_service_account_file(SA_KEY, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        v = gspread.authorize(cr).open_by_key(ROSTER_ID).worksheet('Schedule').get_all_values()
        h = v[0]; di, ti, li = h.index('Date'), h.index('Team'), h.index('LOB')
        forms = [i for i, x in enumerate(h) if x in ('Name', 'Aloware Name', 'Call Tracker Name')]
        today = datetime.date.today(); best = {}
        for r in v[1:]:
            try: d = datetime.datetime.strptime(r[di].strip(), '%m/%d/%Y').date()
            except ValueError: continue
            if d > today: continue
            for i in forms:
                k = fl(r[i])
                if k and (k not in best or d >= best[k][0]): best[k] = (d, r[ti].strip() or 'Unmatched', r[li].strip() or 'Unmatched')
        m = {' '.join(k): [t, l] for k, (_, t, l) in best.items()}
        json.dump(m, open(cache, 'w')); return m
    except Exception as e:
        print('roster not read (%s); using cache' % str(e)[:80])
        return json.load(open(cache)) if os.path.exists(cache) else {}


ROS = load_roster()
rep_meta = [ROS.get(' '.join(fl(n)), ['Unmatched', 'Unmatched']) for n in reps]
print('reps matched to roster:', sum(1 for x in rep_meta if x[0] != 'Unmatched'), 'of', len(reps))
pg = pg + [-1] * (len(idx) - len(pg))
for p, i in idx.items():
    if pg[i] == -1:
        g = group_of_phone(p); pg[i] = gi[g] if g in gi else -1

days = {d: {'sent': x['sent'], 'failed': x['failed'], 'yesTexts': x['yesTexts'],
            'hours': [[h, v[0], v[1]] for h, v in sorted(x['hours'].items())],
            **{k: sorted(x[k]) for k in ('texted', 'replied', 'yes', 'no', 'dnc', 'called', 'conn')}} for d, x in sorted(per.items())}
order_rows = [[o['date'], o['rep'], [[it, kind(it)] for it in o['items']], round(o['upfront'], 2),
               gi.get(group_of_email(o['customer']), -1), o['rep_i']] for o in orders]
asof = max([r['Started At'] for r in sms] + [''])
sales_asof = json.load(open(SALES_META))['pulled_at'] if os.path.exists(SALES_META) else ''
core = {'updated': {'sms': asof, 'calls': call_asof}, 'days': days, 'orders': order_rows, 'pg': pg,
        'groups': G['groups'], 'gsize': [G['size'].get(g, 0) for g in G['groups']],
        'calls': call_rows, 'yesFirst': yes_rows, 'yesCalls': yes_calls, 'reps': reps, 'repMeta': rep_meta, 'cats': cats, 'disps': disps, 'start': START}
data = dict(core, asof=asof, built=now_et().strftime('%Y-%m-%d %H:%M'))
data['updated'] = dict(core['updated'], sales=sales_asof)
built_at = now_et().strftime('%Y-%m-%d %H:%M:%S')   # sheets are read fresh on every build
data['sourceList'] = [
    ['SMS (texts and replies)', 'Aloware export in Drive › Phone Team Reports › Black Friday SMS', ', '.join(display_name(f) for f in sms_files), asof],
    ['Calls', 'Aloware export in Drive › Phone Team Reports › Aloware Call Logs - BF2', ', '.join(display_name(f) for f in call_files), call_asof],
    ['Sales', 'Google Sheet "Call Tracking - PG Phone Support", tab Call Tracking (Call Type "SMS blast")', 'Call Tracking', sales_asof],
    ['Groups', 'Upload lists we sent (Cohorts)', ', '.join(G.get('files', [])), ''],
    ['Outcomes and connects', 'Google Sheet "Call Disposition Category (main source)", tabs Call Disposition_BF2 / _BF1 (Disposition Category, Connects)', 'Call Disposition_BF2', built_at],
    ['Team and LOB', 'Google Sheet "2026Schedule_Aloware Name" (phone team roster), tab Schedule, same as the Phone Team Calls dashboard', 'Schedule', built_at]]

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
