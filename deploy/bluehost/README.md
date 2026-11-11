# Deploying HikeJournal on Bluehost

## Current public website

`hikejournal.wtsorlando.com` serves the static public site in
`deploy/bluehost/site/` from Bluehost shared Apache hosting. Its verified
cPanel document root is `/home3/mftphilo/public_html/website_4d9d652d`.
This website deployment is independent of Android/iOS builds and the API.

1. In the Bluehost portal, select **HikeJournal**, then **File Manager**.
2. Back up the affected homepage/assets outside the document root, in
   `/home3/mftphilo/hikejournal-backups/`.
3. Upload the changed static files. A ZIP preserving the paths relative to
   `site/` can be uploaded and extracted into the document root in cPanel.
4. Fetch the live files over HTTPS and compare their hashes with local source.
   Check desktop/mobile layouts and `/privacy/`, `/support/`, and
   `/account-deletion/`.
5. Move any temporary upload ZIP to cPanel Trash after extraction and verify
   that its public URL is no longer available.
6. Record deployment checks in the release evidence and use a Web-qualified
   tag when `VERSION` is unchanged. Do not rebuild mobile artifacts for a
   static website change.

## Optional Streamlit server on a VPS

The following legacy setup is for hosting the interactive Python/Streamlit
application on a VPS; it is separate from the current static public website.
The practical VPS path is:

1. Use a Bluehost **VPS** plan, not normal shared hosting.
2. SSH into the VPS.
3. Clone or copy this repo to the server.
4. Create a Python virtualenv and install requirements.
5. Copy `.env` and `.streamlit/secrets.toml` to the server with production values.
6. Run Streamlit behind `systemd` and `nginx`.

## Why VPS

HikeJournal is not a PHP site and not a static site. It runs its own Python server process, so it needs:

- a persistent Python process
- SSH access
- reverse proxy support
- the ability to keep a service running in the background

Bluehost documents root SSH access for VPS and dedicated hosting, which is the right fit for this app.

## Suggested server layout

```text
/home/YOUR_USER/hike-journal
```

Inside that folder:

- app code
- `.venv`
- `.env`
- `.streamlit/secrets.toml`

## Basic server bootstrap

```bash
cd /home/YOUR_USER
git clone YOUR_REPO_URL hike-journal
cd hike-journal
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Environment files

Copy these from local development and then update them for production:

- `.env`
- `.streamlit/secrets.toml`

Important production changes:

- set `R2_*` values if you are using Cloudflare R2
- set `REQUIRE_GOOGLE_AUTH=true` when ready
- change Google redirect URI in `.streamlit/secrets.toml` to:
  - `https://YOUR_DOMAIN/oauth2callback`

## Systemd service

Copy [`hikejournal.service.example`](/Users/adl/Documents/Playground/hike-journal/deploy/bluehost/hikejournal.service.example) to:

```text
/etc/systemd/system/hikejournal.service
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hikejournal
sudo systemctl start hikejournal
sudo systemctl status hikejournal
```

## Nginx reverse proxy

Copy [`nginx-hikejournal.conf.example`](/Users/adl/Documents/Playground/hike-journal/deploy/bluehost/nginx-hikejournal.conf.example) into your nginx site config, then replace:

- `YOUR_DOMAIN`
- `YOUR_USER`

Make sure nginx proxies to:

```text
127.0.0.1:8505
```

Then reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## SSL

Streamlit’s own docs recommend doing SSL termination in a reverse proxy instead of directly in the app.

That means:

- HTTPS at nginx
- Streamlit bound locally on `127.0.0.1:8505`

## Updating the app later

```bash
cd /home/YOUR_USER/hike-journal
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart hikejournal
```

## Honest recommendation

If your real goal is **easiest public deployment**, Bluehost VPS is workable but not the easiest.

The easiest path is usually:

- Render
- Railway
- Streamlit Community Cloud
- a small VPS you control directly

But if you already want Bluehost specifically, VPS + systemd + nginx is the correct shape.
