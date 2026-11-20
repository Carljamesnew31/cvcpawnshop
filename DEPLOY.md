# Deploying CVC Pawnshop — cvcpawnshops.com

Flask + SQLite app. Repository: https://github.com/Carljamesnew31/cvcpawnshop
Domain registrar: GoDaddy (domain only, no hosting package).
Important: the domain is **cvcpawnshops.com** (with an "s" after pawnshop).
The Render service URL is **cvcpawnshop.onrender.com** (no "s") — do not mix them up.
Current DNS status: A @ → 216.24.57.1 plus two leftover GoDaddy parking A records
(15.197.148.33, 3.33.130.190) that should be deleted; CNAME www → cvcpawnshop.onrender.com.

## Read this first

1. **The GitHub repo is public.** Login credentials are in `app.py` as defaults. On the
   live host, set these environment variables so the public defaults are NOT used:
   - `SECRET_KEY` — a long random string, e.g. `cvc-2026-8f3a91b2d7`
   - `OWNER_USER`, `OWNER_PASS`
   - `STAFF1_USER`, `STAFF1_PASS`
   - `STAFF2_USER`, `STAFF2_PASS`
2. **Your current database is not in GitHub.** `cvcpawnshop.db` is gitignored, so a fresh
   deploy starts with an empty inventory. The local file currently has 10 inventory items,
   1 pawn and 12 audit-log entries. Do **not** commit it to the public repo — it contains
   customer names and contact numbers. Upload it directly to the host (step 9 below).
3. **Free Render services have an ephemeral filesystem** — every restart/redeploy wipes
   all data and uploaded images, and free services spin down after 15 minutes of
   inactivity. Use a paid service with a persistent disk (step 3 below).

---

## If you choose Render's Free plan (no cost)

Your domain and SSL both work on Free. The setup is the same as below except:

- Compute plan: **Free** — skip the disk entirely (step 2).
- Do **not** set `DB_PATH` (leave the default `cvcpawnshop.db`), since there is no disk.
- Still set `SECRET_KEY` and all the credential environment variables.
- GoDaddy DNS records are identical: `A` `@` → `216.24.57.1`,
  `CNAME` `www` → your `.onrender.com` URL.
- Step 7 (uploading your existing database) is **not possible** on Free — no disk and
  no shell access. The site always starts empty.

**Critical limitation:** Free services spin down after 15 minutes of inactivity and
Render can restart them at any time. Each restart **deletes the entire SQLite database
and all uploaded images** — inventory, sales, pawns, audit logs. Free Render is only
safe for a demo or a read-only catalog, not for recording real transactions.

To keep data on a free budget, the app needs to store it in a free hosted database
(e.g. Neon or Supabase) instead of a local SQLite file. That requires a code change.

---

## Recommended: Render + your GoDaddy domain

### 1. Create the web service

1. Sign in at https://dashboard.render.com → **New + → Web Service**.
2. Connect GitHub account, choose repo `Carljamesnew31/cvcpawnshop`, branch `main`.
3. Name: `cvcpawnshop`. Region: choose the one closest to your customers (e.g. Singapore).
4. **Compute plan: choose a paid plan**, e.g. `0.5c-512mb`. Free plans cannot have a disk.
5. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn app:app`
6. Note the service's `.onrender.com` URL shown after creation — you'll need it for DNS.
   It will be something like `cvcpawnshop.onrender.com`.

### 2. Add the persistent disk

1. Open the service → **Disk** tab → **Add disk**.
2. Mount path: `/data` — size: 1 GB.
3. Save; Render will redeploy the service.

### 3. Add environment variables

In the service's **Environment** tab, add:

| Key | Value |
| --- | --- |
| `DB_PATH` | `/data/cvcpawnshop.db` |
| `SECRET_KEY` | a long random string you make up |
| `OWNER_USER` | e.g. `Chezl` (or a new username) |
| `OWNER_PASS` | a strong new password |
| `STAFF1_USER` | e.g. `Chanda` |
| `STAFF1_PASS` | a strong new password |
| `STAFF2_USER` | e.g. `Kenrose` |
| `STAFF2_PASS` | a strong new password |

Save — Render restarts the service.

> Do not use the passwords currently written in `app.py`; they are public on GitHub.

### 4. Add your domain in Render

1. Service → **Settings** → **Custom Domains** → **+ Add Custom Domain**.
2. Enter `cvcpawnshops.com` and save.
3. Render automatically adds `www.cvcpawnshops.com` as well and redirects it to the
   bare domain. You'll see "DNS update needed" until the next step.

### 5. Set the DNS records in GoDaddy

1. Log in to GoDaddy → **My Products** → next to `cvcpawnshops.com` click **DNS**
   (or **Manage DNS**).
2. In the **Records** section, delete/edit any existing `A`, `CNAME`, or `AAAA`
   records for `@` and `www`. Leave `NS`, `SOA`, `MX`, and `TXT` records alone.
3. Add these two records:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| `A` | `@` | `216.24.57.1` | 600 seconds (or default) |
| `CNAME` | `www` | `cvcpawnshop.onrender.com` | 600 seconds (or default) |

   Replace `cvcpawnshop.onrender.com` with the actual URL from step 1.6 if different.
   Remove any `AAAA` records — Render uses IPv4 only and IPv6 records can break it.

4. **Delete any other `A` records at `@`** (GoDaddy default parking addresses such as
   `15.197.148.33` and `3.33.130.190`). Only `216.24.57.1` should remain, otherwise
   visitors may land on a GoDaddy parking page instead of the site.
5. Save. DNS can take a few minutes to spread across the internet.

### 6. Verify and enable HTTPS

1. Back in Render → **Settings → Custom Domains** → click **Verify** next to
   `cvcpawnshops.com`.
2. Once verified, Render automatically issues a free SSL certificate. HTTP traffic
   redirects to HTTPS by itself.
3. Visit `https://cvcpawnshops.com` and `https://www.cvcpawnshops.com` — both should load.

### 7. Upload your existing database (optional)

The site works fine starting empty, but to keep your current 10 inventory items,
1 pawn and audit logs:

1. Use Render **Shell** (or Magic Wormhole — https://render.com/docs/disks#transferring-files)
   to upload your local `cvcpawnshop.db` to `/data/cvcpawnshop.db`.
2. Restart the service so it picks up the file.
3. Any product images referenced by the database also need uploading to
   `static/uploads` on the server; that folder is gitignored too.

### 8. Ongoing backups

Log in as owner and open `/backup` regularly to download a database backup.
Render also takes automatic daily snapshots of the disk (kept for 7 days).

---

## Alternative: PythonAnywhere

Works too, but with your own domain it's less suitable:

- Custom domains require the paid **Developer** plan ($10/month).
- PythonAnywhere recommends hosting on `www.cvcpawnshops.com` via a CNAME to
  `webapp-XXXX.pythonanywhere.com`, then setting up GoDaddy domain forwarding from
  `cvcpawnshops.com` to `www.cvcpawnshops.com`. GoDaddy's forwarding is HTTP-only, so
  `https://cvcpawnshops.com` won't work cleanly.

If you choose this route, follow https://help.pythonanywhere.com/pages/CustomDomains/
and use the GoDaddy CNAME instructions there. The app itself needs no changes.

---

## After deploying

- Visit `/` and `/remate` to confirm the public pages load.
- Log in at `/login`, then open `/admin` — check Inventory, Sales and Pawns tabs.
- Test `/backup` (owner only).
