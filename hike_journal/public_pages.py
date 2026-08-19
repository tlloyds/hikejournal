from __future__ import annotations

import html
import json


_STYLE = """
:root { color-scheme: light; --ink:#20332b; --muted:#5e6c64; --paper:#f4eddd; --moss:#41664c; --line:#d4c9b3; }
* { box-sizing: border-box; }
body { margin:0; color:var(--ink); background:radial-gradient(circle at 20% 0%,#fffaf0 0,#f4eddd 48%,#e8dfcc 100%); font:17px/1.65 Georgia,serif; }
main { width:min(760px,calc(100% - 40px)); margin:0 auto; padding:72px 0 96px; }
.brand { font-size:clamp(2.8rem,9vw,5rem); line-height:.94; letter-spacing:-.055em; margin:0 0 18px; }
h1 { font-size:clamp(1.75rem,5vw,2.5rem); line-height:1.1; margin:0 0 18px; }
h2 { font-size:1.2rem; margin:36px 0 8px; }
p,li { color:var(--muted); }
a { color:var(--moss); }
button { appearance:none; border:0; border-radius:4px; padding:13px 18px; background:var(--moss); color:white; font:700 1rem Georgia,serif; cursor:pointer; }
button.danger { background:#8b3f32; }
button:disabled { opacity:.55; cursor:wait; }
.rule { border:0; border-top:1px solid var(--line); margin:34px 0; }
.status { min-height:1.7em; margin-top:14px; }
.fine { font-size:.88rem; }
"""


def _document(title: str, body: str, *, scripts: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{_STYLE}</style>{scripts}</head><body><main>{body}</main></body></html>"""


def privacy_page() -> str:
    return _document(
        "HikeJournal privacy policy",
        """
<p class="brand">HikeJournal</p><h1>Privacy policy</h1>
<p class="fine">Effective August 18, 2026</p>
<p>HikeJournal is a personal nature journal. It uses the information you choose to add to preserve outings, organize media, and help you learn about nearby species.</p>
<h2>Information we process</h2>
<ul><li>Your Google account identifier, name, email address, and profile image for sign-in.</li>
<li>Journal entries, saved places, hike routes, field marks, and precise location when you record a hike or retain media coordinates.</li>
<li>Photos, videos, captions, species identifications, and iNaturalist publishing choices.</li>
<li>Short-lived operational records needed to synchronize uploads, diagnose failures, and protect the service.</li></ul>
<h2>How it is used</h2>
<p>We use this information only to provide, secure, and maintain HikeJournal. We do not sell personal information, run advertising, or use your private journal to train advertising profiles.</p>
<h2>Service providers</h2>
<p>HikeJournal relies on Google Cloud for the application service, Supabase for database records, R2-compatible object storage for media, Google for sign-in, and optional nature and conditions services such as iNaturalist, Open-Meteo, and USGS. Map providers receive the normal network information required to deliver map tiles.</p>
<h2>Your choices and retention</h2>
<p>You control what you record and whether to connect iNaturalist. Journal data remains while your account is active. You can permanently delete your account and its associated journal data in app settings or through the <a href="/account-deletion">web deletion page</a>. Observations you deliberately published to iNaturalist remain governed by your iNaturalist account and must be managed there. Limited copies may remain temporarily in provider backups or security logs until their normal retention cycle expires.</p>
<h2>Children</h2><p>HikeJournal is not directed to children under 13.</p>
<h2>Contact</h2><p>For privacy or support questions, use the <a href="/support">HikeJournal support page</a>.</p>
""",
    )


def support_page() -> str:
    return _document(
        "HikeJournal support",
        """
<p class="brand">HikeJournal</p><h1>Support</h1>
<p>For help, bug reports, privacy questions, or data concerns, open an issue in the public HikeJournal support tracker.</p>
<p><a href="https://github.com/tlloyds/hikejournal/issues">Open the HikeJournal support tracker</a></p>
<hr class="rule"><p class="fine">Do not include private photos, precise locations, access tokens, or other sensitive account details in a public issue.</p>
""",
    )


def account_deletion_page(google_client_id: str) -> str:
    client_id = google_client_id.strip()
    if not client_id:
        return _document(
            "Delete a HikeJournal account",
            "<p class='brand'>HikeJournal</p><h1>Delete your account</h1><p>The account service is temporarily unavailable. Please try again later or visit <a href='/support'>support</a>.</p>",
        )
    escaped_client_id = html.escape(client_id, quote=True)
    js_client_id = json.dumps(client_id)
    return _document(
        "Delete a HikeJournal account",
        f"""
<p class="brand">HikeJournal</p><h1>Delete your account</h1>
<p>Sign in with the same Google account you use in HikeJournal. After you confirm, HikeJournal permanently removes the account, journal entries, saved places, routes, species records, and stored media associated with it.</p>
<div id="g_id_onload" data-client_id="{escaped_client_id}" data-callback="handleCredentialResponse" data-auto_prompt="false"></div>
<div class="g_id_signin" data-type="standard" data-shape="rectangular" data-theme="outline" data-text="signin_with" data-size="large"></div>
<section id="confirm" hidden><hr class="rule"><p id="account"></p><p>This cannot be undone.</p><button class="danger" id="delete">Permanently delete my account</button></section>
<p class="status" id="status" role="status"></p>
<p class="fine"><a href="/privacy">Privacy policy</a> · <a href="/support">Support</a></p>
""",
        scripts="""<script src="https://accounts.google.com/gsi/client" async defer></script><script>
const clientId = """ + js_client_id + """;
let accessToken = null;
const statusNode = () => document.getElementById('status');
async function handleCredentialResponse(response) {
  statusNode().textContent = 'Verifying your account…';
  const deviceId = localStorage.getItem('hikejournalDeletionDevice') || crypto.randomUUID();
  localStorage.setItem('hikejournalDeletionDevice', deviceId);
  const result = await fetch('/v1/auth/google', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({credential:response.credential, device_id:deviceId})});
  const payload = await result.json();
  if (!result.ok) { statusNode().textContent = payload.detail || 'Sign-in could not be verified.'; return; }
  accessToken = payload.access_token;
  document.getElementById('account').textContent = 'Signed in as ' + payload.account.email;
  document.getElementById('confirm').hidden = false;
  statusNode().textContent = '';
}
document.addEventListener('click', async event => {
  if (event.target.id !== 'delete' || !accessToken) return;
  if (!window.confirm('Permanently delete this HikeJournal account and all of its journal data?')) return;
  event.target.disabled = true; statusNode().textContent = 'Deleting your HikeJournal account…';
  const result = await fetch('/v1/account', {method:'DELETE', headers:{'Authorization':'Bearer ' + accessToken}});
  const payload = await result.json().catch(() => ({}));
  if (!result.ok) { event.target.disabled = false; statusNode().textContent = payload.detail || 'Deletion did not complete. Please try again.'; return; }
  accessToken = null; document.getElementById('confirm').hidden = true;
  statusNode().textContent = 'Your HikeJournal account and journal data were deleted.';
  google.accounts.id.disableAutoSelect();
});
</script>""",
    )
