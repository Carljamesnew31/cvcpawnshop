# Deploying CVC Pawnshop — cvcpawnshops.com

Flask + PostgreSQL (Neon free) app hosted on Render.
Repository: https://github.com/Carljamesnew31/cvcpawnshop
Domain: **cvcpawnshops.com** (with an "s" after pawnshop), registered at GoDaddy.
Render URL: **cvcpawnshop.onrender.com** (no "s") — don't mix them up.

Current status: the site is live at https://cvcpawnshops.com with free SSL, and the
GoDaddy DNS records are correct:
- `A` — `@` — `216.24.57.1`
- `CNAME` — `www` — `cvcpawnshop.onrender.com.`

## How data is stored now

Render's free plan deletes local files on every restart. The app has therefore been
changed to store data in **Neon**, a free hosted PostgreSQL database:

- Inventory, sales, pawns, payments and audit logs are kept in Neon — they survive
  restarts and never disappear.
- Uploaded product images are resized and stored in the database as data URIs, so
  they survive restarts too (no image files on disk).
- The app still uses a local SQLite file when `DATABASE_URL` is not set, for
  development on your own computer.
- `/backup` (owner only) now downloads a JSON backup of all tables.

## Set up the free Neon database (one time)

1. Go to https://neon.tech/signup and create a free account (no credit card needed).
2. Create a new project named `cvcpawnshop`; pick a region close to your customers.
3. On the project dashboard, find the **Connection string** (or "Connection details").
   Choose the pooled connection string if offered. It looks like:
   `postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`
4. Copy that whole string.

## Connect Neon to Render

In the Render dashboard, open your `cvcpawnshop` web service → **Environment**:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | the connection string copied from Neon |
| `SECRET_KEY` | a long random string you make up |
| `OWNER_USER` | e.g. `Chezl` (or a new username) |
| `OWNER_PASS` | a strong new password |
| `STAFF1_USER` | e.g. `Chanda` |
| `STAFF1_PASS` | a strong new password |
| `STAFF2_USER` | e.g. `Kenrose` |
| `STAFF2_PASS` | a strong new password |

Remove `DB_PATH` if you set it earlier — it's only for local SQLite mode.
Save; Render redeploys automatically. On startup the app creates all tables in Neon.

## Verify it works

1. Open https://cvcpawnshops.com/login and sign in with the owner credentials you set.
2. Add an item in `/admin` (Inventory tab).
3. Wait 20 minutes with no visitors so the free Render service spins down, then visit
   the site again and confirm the item is still there. That proves data persistence.
4. Download a backup from `/backup` and keep a copy somewhere safe.

## Notes

- The default login credentials in `app.py` are public on GitHub. The environment
  variables above override them — always set them before going live.
- Your old local `cvcpawnshop.db` (10 items, 1 pawn) is not in GitHub and has not been
  imported into Neon. Start fresh, or ask for a one-time migration script.
- Neon's free plan is permanent: 1 GB storage, 100 compute-hours/month. It scales its
  compute to zero when idle and wakes on the next request. None of your data is deleted.
