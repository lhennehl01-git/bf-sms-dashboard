# Black Friday SMS dashboard

Live: https://bf-sms-site.vercel.app (Vercel team performance-golf1, project bf-sms-site).

GitHub Actions rebuilds `index.html` every 15 minutes from the Aloware exports in Google Drive and the
Call Tracking sheet (read with a Google service account), commits it when the numbers change (or hourly),
and Vercel redeploys on push. The page shows totals only: no customer names, emails or phone numbers.
`pipeline/groups.json` holds only keyed hashes (secret `BF_HASH_KEY`), made on the Mac by `make_groups.py`.

Secrets: `GCP_SA_KEY` (service-account JSON), `BF_HASH_KEY`.
Local run (Mac): `cd pipeline && python3 bf_sales_pull.py && python3 bf_site_build.py`.
