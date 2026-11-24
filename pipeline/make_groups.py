"""Mac only: turns the upload lists (../../Cohorts/BF_cohort_*.csv, which hold real phones and emails) into
groups.json, which holds only scrambled keys, so the cloud build can split numbers by group.
Run after each new Black Friday upload, then commit + push groups.json (bf_site_watch.py does this by itself).
Usage: python3 make_groups.py   -> prints the group sizes; exits 0 and writes nothing if unchanged"""
import os, csv, glob, json
from bf_common import *


def make():
    files = sorted(glob.glob(os.path.join(BF_ROOT, 'Cohorts', 'BF_cohort_*.csv')))
    if not files:
        raise SystemExit('no cohort files found')
    names = ['Past buyers 2026', 'Past buyers 2025', 'Past buyers 2024', 'Past buyers 2023 and older',
             'Paid Ads leads', 'Failed Close (Oct-Nov)']
    size = {n: 0 for n in names}

    def group(f, r):   # Failed Close list, then Paid Ads leads, then past buyers by order year
        if 'FailedClose' in os.path.basename(f): return 5
        if (r.get('Lead Source') or '').startswith('Paid Ads'): return 4
        y = (r.get('Order Year') or '').strip()
        return {'2026': 0, '2025': 1, '2024': 2}.get(y, 3)
    phones, emails = {}, {}
    for f in files:
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            gi = group(f, r)
            size[names[gi]] += 1
            if r.get('Clean Phone'):
                phones[scramble(r['Clean Phone'])] = gi
            if r.get('Email'):
                emails[scramble(r['Email'])] = gi
    keep = [n for n in names if size[n]]   # drop empty groups, renumber
    ren = {names.index(n): i for i, n in enumerate(keep)}
    phones = {k: ren[v] for k, v in phones.items()}; emails = {k: ren[v] for k, v in emails.items()}
    size = {n: size[n] for n in keep}; names = keep
    out = {'groups': names, 'size': size, 'files': [os.path.basename(f) for f in files],
           'phones': dict(sorted(phones.items())), 'emails': dict(sorted(emails.items()))}
    new = json.dumps(out, separators=(',', ':'), sort_keys=True)
    old = open(GROUPS_JSON).read() if os.path.exists(GROUPS_JSON) else ''
    if new != old:
        open(GROUPS_JSON, 'w').write(new)
    return size, new != old


if __name__ == '__main__':
    s, changed = make()
    print('groups', s, '| changed' if changed else '| unchanged')
