# Deploying CVC Pawnshop

Flask + SQLite app. Repository: https://github.com/Carljamesnew31/cvcpawnshop

## Read this first

1. **The repo is public.** Login credentials are in `app.py` as defaults. On the live host,
   set these environment variables so the public defaults are NOT used:
   - `SECRET_KEY` — any long random string (e.g. `cvc-2026-8f3a91b2d7`)
   - `OWNER_USER`, `OWNER_PASS`
   - `STAFF1_USER`, `STAFF1_PASS`
   - `STAFF2_USER`, `STAFF2_PASS`
2. **Your current database is not in GitHub.** `cvcpawnshop.db` is gitignored, so a fresh
   deploy starts with an empty inventory. The local file currently has 10 inventory items,
   1 pawn and 12 audit-log entries. Do **not** commit it to the public repo — it contains
   customer names/contact numbers. Upload it directly to the host instead (steps below).
3. **Free Render services have an ephemeral filesystem** — every restart/redeploy wipes
   all data and uploaded images. Use a paid service with a persistent disk, or use
   PythonAnywhere (files persist there even on the free plan).

## Option A — PythonAnywhere (easiest, data persists, free subdomain)

1. Sign up at https://www.pythonanywhere.com (Beginner / free is enough to start).
2. Open a **Bash console** and run:
   ```bash
   git clone https://github.com/Carljamesnew31/cvcpawnshop.git
   cd cvcpawnshop
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Upload your existing database** (optional): go to the **Files** tab, navigate into
   `cvcpawnshop`, and upload your local `cvcpawnshop.db`. Skip this to start empty.
   (If you upload it, make sure any images referenced in it also exist under
   `static/uploads` — those are gitignored too.)
4. Go to the **Web** tab → **Add a new web app** → Flask → Python 3.x.
5. In the app's WSGI configuration file, replace its contents with:
   ```python
   import sys
   path = '/home/<your-username>/cvcpawnshop'
   if path not in sys.path:
       sys.path.insert(0, path)
   from app import app as application
   ```
   (Replace `<your-username>`.)
6. Set **Source code** and **Working directory** to
   `/home/<your-username>/cvcpawnshop`.
7. Add the environment variables listed in **Read this first** in the Web tab if your
   plan supports env vars; on Beginner, put them in a `.env` file in the project
   directory instead (one `KEY=value` per line) — Flask loads it automatically when
   `python-dotenv` is installed. Add `python-dotenv` to `requirements.txt` if needed.
8. Set **Static files** URL `/static/` → `/home/<your-username>/cvcpawnshop/static`.
9. Click **Reload**. Your site is at `https://<your-username>.pythonanywhere.com`.
   A custom domain requires the paid Developer plan ($10/month).

## Option B — Render (custom domain easy, needs a paid plan for data to persist)

1. Sign in at https://dashboard.render.com → **New + → Web Service** → connect the
   GitHub repo `CarlJamesNew31/cvcpawnshop` (branch `main`).
2. Choose a **paid** instance (e.g. `0.5c-512mb`) — free instances cannot have a disk.
3. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn app:app`
4. Click **Advanced → Add disk**: mount path `/data`, size 1 GB.
5. Add environment variables:
   - `DB_PATH = /data/cvcpawnshop.db`
   - `SECRET_KEY`, `OWNER_USER`, `OWNER_PASS`, `STAFF1_USER`, `STAFF1_PASS`,
     `STAFF2_USER`, `STAFF2_PASS` (see **Read this first**)
6. Create the service. It will be live at `https://cvcpawnshop.onrender.com`.
7. To copy your existing local database up: after deploy, open the service's **Shell**
   page and use the shell's upload feature, or use `wormhole send`/`receive` from your
   PC (see https://render.com/docs/disks#transferring-files). Put the file at
   `/data/cvcpawnshop.db`, then restart the service.

The included `render.yaml` uses the **free** plan — use the manual Web Service flow
above instead, otherwise data will be lost on every restart.

## After deploying

- Visit `/` and `/remate` to confirm the public pages load.
- Log in at `/login`, then open `/admin` — check Inventory, Sales and Pawns tabs.
- Use `/backup` (owner only) to download a database backup regularly.
