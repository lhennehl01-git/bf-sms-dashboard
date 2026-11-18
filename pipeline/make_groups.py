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
    names = ['Past buyers (main blast)', 'Failed Close (Oct-Nov)']
    size = {n: 0 for n in names}
    phones, emails = {}, {}
    for f in files:
        gi = 1 if 'FailedClose' in os.path.basename(f) else 0
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            size[names[gi]] += 1
            if r.get('Clean Phone'):
                phones[scramble(r['Clean Phone'])] = gi
            if r.get('Email'):
                emails[scramble(r['Email'])] = gi
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
