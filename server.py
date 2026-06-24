#!/usr/bin/env python3
"""
AmpyPay all-in-one server — requires pymysql, bcrypt (pip3 install pymysql bcrypt).
Serves static frontend AND handles API/admin on a single port.

Routes:
  GET  /                  → index.html
  GET  /css/*, /js/*, /assets/*  → static files
  GET  /demo              → demo.html (standalone form)
  POST /api/demo          → save submission to MariaDB, send emails
  GET  /admin             → legacy view (?token=)
  GET  /ap-control           → admin panel (login required)
  GET  /ap-control/login     → login page
  POST /ap-control/login     → process login
  GET  /ap-control/logout    → clear session
  GET  /ap-control/export    → export CSV
  GET  /ap-control/data      → JSON list (session required)
"""

import http.server
import json
import socketserver
import mimetypes
import os
import re
import smtplib
import sqlite3
import threading
import urllib.parse
import urllib.request
import http.cookies
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pymysql
import pymysql.cursors
import bcrypt
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _env(key, default=''):
    return os.environ.get(key, default)

PORT         = int(_env('PORT', '3001'))
SMTP_HOST    = _env('SMTP_HOST', 'mail.eunite.com')
SMTP_PORT    = int(_env('SMTP_PORT', '25'))
SMTP_SECURE  = _env('SMTP_SECURE', 'false').lower() == 'true'
SMTP_USER    = _env('SMTP_USER', 'noreply@eunite.com')
SMTP_PASS    = _env('SMTP_PASS', '')
NOTIFY_EMAIL = _env('NOTIFY_EMAIL', 'admin@eunite.com')
ADMIN_TOKEN  = _env('ADMIN_TOKEN', 'changeme')
DB_PATH      = _env('DB_PATH', os.path.join(BASE_DIR, 'demo_submissions.db'))

# ── Login rate limiter ────────────────────────────────────────────────────────
import time as _time

_login_attempts = {}
_RATE_LIMIT_MAX    = 5
_RATE_LIMIT_WINDOW = 15 * 60
_RATE_LIMIT_LOCK   = threading.Lock()

def _get_client_ip(handler):
    return handler.headers.get('X-Forwarded-For', handler.client_address[0]).split(',')[0].strip()

def login_is_blocked(ip):
    with _RATE_LIMIT_LOCK:
        now = _time.time()
        attempts = [t for t in _login_attempts.get(ip, []) if now - t < _RATE_LIMIT_WINDOW]
        _login_attempts[ip] = attempts
        return len(attempts) >= _RATE_LIMIT_MAX

def login_record_failure(ip):
    with _RATE_LIMIT_LOCK:
        now = _time.time()
        attempts = [t for t in _login_attempts.get(ip, []) if now - t < _RATE_LIMIT_WINDOW]
        attempts.append(now)
        _login_attempts[ip] = attempts

def login_clear(ip):
    with _RATE_LIMIT_LOCK:
        _login_attempts.pop(ip, None)

def login_remaining_wait(ip):
    with _RATE_LIMIT_LOCK:
        now = _time.time()
        attempts = [t for t in _login_attempts.get(ip, []) if now - t < _RATE_LIMIT_WINDOW]
        if not attempts:
            return 0
        oldest = min(attempts)
        return max(0, int(_RATE_LIMIT_WINDOW - (now - oldest)))

# ── MariaDB ───────────────────────────────────────────────────────────────────
def get_mysql():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=3,
        autocommit=True,
    )

def mysql_insert_submission(name, company, email, phone, ip, job_title='', employees='', client_time='', country=''):
    sql = """INSERT INTO demo_submissions
             (name,company,email,phone,job_title,employees,ip,created_at,country)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    with get_mysql() as conn:
        with conn.cursor() as cur:
            from datetime import datetime, timezone
            ts = client_time or datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            cur.execute(sql, (name, company, email, phone or None, job_title or None,
                               employees or None, ip or None, ts, country or None))

def mysql_get_all_submissions():
    with get_mysql() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,name,company,email,phone,job_title,employees,ip,country,created_at "
                        "FROM demo_submissions ORDER BY id ASC")
            return cur.fetchall()

def mysql_verify_admin(username, password):
    """Returns display_name on success, False on failure."""
    try:
        with get_mysql() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password_hash, display_name FROM admin_users WHERE username=%s AND is_active=1",
                    (username,)
                )
                row = cur.fetchone()
        if not row:
            return False
        if not bcrypt.checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            return False
        return row['display_name'] or username
    except Exception:
        return False

def mysql_update_last_login(username):
    try:
        with get_mysql() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE admin_users SET last_login_at=NOW() WHERE username=%s",
                    (username,)
                )
    except Exception:
        pass

def mysql_recent_count_by_email(email):
    with get_mysql() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM demo_submissions "
                        "WHERE email=%s AND created_at >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)", (email,))
            row = cur.fetchone()
            return row['c'] if row else 0

# ── SQLite (legacy /admin route) ──────────────────────────────────────────────
_db_lock = threading.Lock()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                company    TEXT NOT NULL,
                email      TEXT NOT NULL,
                phone      TEXT,
                job_title  TEXT,
                employees  TEXT,
                ip         TEXT,
                created_at TEXT
            )
        """)
        for col, typedef in [('job_title', 'TEXT'), ('employees', 'TEXT'), ('country', 'TEXT')]:
            try:
                conn.execute(f'ALTER TABLE submissions ADD COLUMN {col} {typedef}')
            except Exception:
                pass
        conn.commit()

# ── IP / Country ──────────────────────────────────────────────────────────────
_PRIVATE_IP = re.compile(
    r'^(127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|::1$|localhost)'
)

def _get_public_ip():
    try:
        with urllib.request.urlopen('https://api.ipify.org', timeout=4) as r:
            return r.read().decode().strip()
    except Exception:
        return ''

def lookup_country(ip):
    if not ip or _PRIVATE_IP.match(ip):
        ip = _get_public_ip()
    if not ip:
        return ''
    try:
        url = f'http://ip-api.com/json/{ip}?fields=country,countryCode'
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.loads(r.read())
        if data.get('status') == 'success' or data.get('country'):
            return f"{data.get('country', '')} ({data.get('countryCode', '')})"
    except Exception:
        pass
    return ''

# ── Name / Phone validation ───────────────────────────────────────────────────
NAME_BAD_RE    = re.compile(r'https?://|www\.|[<>]', re.IGNORECASE)
NAME_REPEAT_RE = re.compile(r'(.)\1{4,}')

def valid_name(v):
    s = (v or '').strip()
    if not (2 <= len(s) <= 254):
        return False
    if not any(ch.isalpha() for ch in s):
        return False
    if NAME_BAD_RE.search(s) or NAME_REPEAT_RE.search(s):
        return False
    return True

PHONE_RE = re.compile(r'^\+?\d{7,15}$')

def normalize_phone(v):
    s = re.sub(r'[\s().\-]', '', v or '')
    if s.startswith('00'):
        s = '+' + s[2:]
    return s

# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(to, subject, html):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = SMTP_USER
    recipients = [t.strip() for t in to.split(',') if t.strip()]
    msg['To']      = ', '.join(recipients)
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    try:
        if SMTP_SECURE:
            s = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        else:
            s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            try:
                s.starttls()
            except Exception:
                pass
        if SMTP_USER and SMTP_PASS:
            s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, recipients, msg.as_bytes())
        s.quit()
    except Exception as e:
        print(f'[email error] {e}')

def notify_admin(name, company, email, phone, job_title='', employees=''):
    rows = [
        ('Name',      name),
        ('Company',   company),
        ('Email',     f'<a href="mailto:{email}">{email}</a>'),
        ('Phone',     phone or '-'),
        ('Job Title', job_title or '-'),
        ('Employees', employees or '-'),
    ]
    rows_html = ''.join(
        f'<tr>'
        f'<td style="padding:6px 16px 6px 0;font-size:14px;color:#6b7280;white-space:nowrap">{k}</td>'
        f'<td style="padding:6px 0;font-size:14px;color:#111827;font-weight:500">{v}</td>'
        f'</tr>'
        for k, v in rows
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>New Demo Request</title>
</head>
<body style="margin:0;padding:0;background:#ffffff">
  <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#0A1F44">
    <div style="background:#0A1F44;padding:24px;text-align:center">
      <img src="https://www.ampypay.com/assets/logos/logo.svg" alt="AmpyPay" width="140" style="display:inline-block;height:auto;max-width:140px">
    </div>
    <div style="padding:32px 24px">
      <h2 style="margin:0 0 16px;font-size:18px">New Demo Request</h2>
      <table style="border-collapse:collapse;background:#f8fafc;border-radius:8px;border:1px solid #e5e7eb;width:100%">
        <tr><td style="padding:20px 24px">
          <table cellpadding="0" cellspacing="0">{rows_html}</table>
        </td></tr>
      </table>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
      <p style="font-size:13px;color:#6b7280">This is an automated notification from AmpyPay.</p>
    </div>
    <div style="background:#FBFBEE;padding:16px 24px;text-align:center;font-size:12px;color:#0A1F44">
      © 2026 AmpyPay · This email was sent because you requested a demo.
    </div>
  </div>
</body>
</html>"""
    threading.Thread(
        target=send_email,
        args=(NOTIFY_EMAIL, f'[AmpyPay] New demo request — {name} ({company})', html),
        daemon=True
    ).start()

def confirm_customer(name, company, email):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AmpyPay – Demo Request Confirmation</title>
</head>
<body style="margin:0;padding:0;background:#ffffff">
  <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#0A1F44">
    <div style="background:#0A1F44;padding:24px;text-align:center">
      <img src="https://www.ampypay.com/assets/logos/logo.svg" alt="AmpyPay" width="140" style="display:inline-block;height:auto;max-width:140px">
    </div>
    <div style="padding:32px 24px">
      <h2 style="margin:0 0 8px">Thanks, {name}!</h2>
      <p style="color:#0A1F44">We've received your demo request from <strong>{company}</strong>.<br>
      Our team will reach out within one business day to schedule your demo.</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
      <p style="font-size:13px;color:#6b7280">If you have any questions, just reply to this email.</p>
    </div>
    <div style="background:#FBFBEE;padding:16px 24px;text-align:center;font-size:12px;color:#0A1F44">
      © 2026 AmpyPay · This email was sent because you requested a demo.
    </div>
  </div>
</body>
</html>"""
    threading.Thread(
        target=send_email,
        args=(email, 'Your AmpyPay demo request is confirmed', html),
        daemon=True
    ).start()

# ── Admin HTML ────────────────────────────────────────────────────────────────
def login_html(error=False, attempts_left=None):
    if error:
        if attempts_left is not None and attempts_left <= 2:
            err_msg = f'Incorrect username or password. {attempts_left} attempt{"s" if attempts_left != 1 else ""} remaining.'
        else:
            err_msg = 'Incorrect username or password.'
        err_block = f'<div class="err" id="err" style="display:block">{err_msg}</div>'
    else:
        err_block = '<div class="err" id="err"></div>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AmpyPay — Admin Login</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: #071737;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .card {{
    background: #0A1F44;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 40px 36px;
    width: 100%;
    max-width: 380px;
    box-shadow: 0 24px 64px rgba(0,0,0,0.4);
  }}
  .logo {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 32px;
  }}
  .logo-mark {{
    width: 36px; height: 36px;
    background: #2563EA;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 16px; color: #fff;
  }}
  .logo-name {{ font-size: 18px; font-weight: 700; color: #FBFBEE; }}
  h1 {{ font-size: 22px; font-weight: 700; color: #FBFBEE; margin-bottom: 6px; }}
  .subtitle {{ font-size: 14px; color: rgba(251,251,238,0.5); margin-bottom: 28px; }}
  .field {{ margin-bottom: 16px; }}
  label {{ display: block; font-size: 13px; font-weight: 600; color: rgba(251,251,238,0.7); margin-bottom: 8px; }}
  .input-wrap {{ position: relative; }}
  input[type="password"], input[type="text"] {{
    width: 100%;
    padding: 13px 44px 13px 16px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    color: #FBFBEE;
    font-size: 15px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    font-family: inherit;
  }}
  input:focus {{ border-color: #2563EA; box-shadow: 0 0 0 3px rgba(37,99,234,0.2); }}
  .toggle-btn {{
    position: absolute; right: 12px; top: 50%;
    transform: translateY(-50%);
    background: none; border: none; cursor: pointer;
    color: rgba(251,251,238,0.4); padding: 4px;
    font-size: 16px; line-height: 1;
  }}
  .toggle-btn:hover {{ color: rgba(251,251,238,0.8); }}
  .err {{
    margin-top: 10px;
    font-size: 13px;
    color: #f87171;
    min-height: 18px;
  }}
  .btn {{
    width: 100%;
    margin-top: 8px;
    padding: 14px;
    background: #2563EA;
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    font-family: inherit;
  }}
  .btn:hover {{ background: #1d52cc; }}
  .btn:active {{ transform: scale(0.98); }}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="logo-mark">A</div>
    <span class="logo-name">AmpyPay</span>
  </div>
  <h1>Admin Login</h1>
  <p class="subtitle">Sign in to view demo submissions.</p>

  <form method="POST" action="/admin/login" id="loginForm">
    <div class="field">
      <label for="username">Username</label>
      <div class="input-wrap">
        <input type="text" id="username" name="username" placeholder="Enter username"
               autocomplete="username" autofocus>
      </div>
    </div>
    <div class="field">
      <label for="password">Password</label>
      <div class="input-wrap">
        <input type="password" id="password" name="password" placeholder="Enter password"
               autocomplete="current-password">
        <button class="toggle-btn" type="button" onclick="toggleVis()" id="eyeBtn">&#128065;</button>
      </div>
    </div>
    {err_block}
    <button class="btn" type="submit">Sign in</button>
  </form>
</div>
<script>
  function toggleVis() {{
    const inp = document.getElementById('password');
    const btn = document.getElementById('eyeBtn');
    if (inp.type === 'password') {{
      inp.type = 'text';
      btn.innerHTML = '&#128064;';
    }} else {{
      inp.type = 'password';
      btn.innerHTML = '&#128065;';
    }}
  }}
</script>
</body>
</html>"""


def admin_html(rows, user_menu='', export_btn=''):
    rows_html = ''
    for r in rows:
        rows_html += f"""
        <tr>
          <td>{r['id']}</td>
          <td class="ts" data-ts="{r['created_at']}">{r['created_at']}</td>
          <td>{r['name']}</td>
          <td>{r['company']}</td>
          <td><a href="mailto:{r['email']}">{r['email']}</a></td>
          <td>{r['phone'] or '-'}</td>
          <td>{r.get('job_title') or '-'}</td>
          <td>{r.get('employees') or '-'}</td>
          <td>{r.get('country') or '-'}</td>
          <td style="font-size:12px;color:#6b7280">{r['ip'] or '-'}</td>
        </tr>"""
    if not rows_html:
        rows_html = '<tr><td colspan="10" style="text-align:center;color:#9ca3af;padding:32px">No submissions yet.</td></tr>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AmpyPay — Demo Submissions</title>
<link rel="preload" href="/assets/fonts/inter-latin.woff2" as="font" type="font/woff2" crossorigin>
<style>
  @font-face{{font-family:'Inter';font-style:normal;font-weight:300 900;font-display:swap;src:url('/assets/fonts/inter-latin.woff2') format('woff2')}}
  body{{font-family:'Inter',system-ui,sans-serif;margin:0;background:#f9fafb;color:#111}}
  header{{background:#0a0a0a;color:#fff;padding:16px 24px;display:flex;align-items:center;gap:16px}}
  header .logo{{height:28px;width:auto;display:block}}
  header .actions{{margin-left:auto;display:flex;gap:8px;align-items:center}}
  .title-row{{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}}
  .title-row .page-title{{margin-bottom:0;margin-top:0}}
  .btn-export{{padding:7px 16px;background:#2563EA;border:1px solid #2563EA;color:#fff;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;text-decoration:none;transition:background 0.2s;white-space:nowrap}}
  .btn-export:hover{{background:#1d52cc}}
  .user-menu{{position:relative}}
  .user-btn{{padding:7px 14px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#fff;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;font-family:inherit;display:flex;align-items:center;gap:6px;transition:background 0.2s}}
  .user-btn:hover{{background:rgba(255,255,255,0.15)}}
  .user-btn .chevron{{font-size:10px;opacity:0.6}}
  .user-dropdown{{display:none;position:absolute;right:0;top:calc(100% + 6px);background:#1a1a1a;border:1px solid rgba(255,255,255,0.12);border-radius:8px;min-width:140px;overflow:hidden;z-index:100;box-shadow:0 8px 24px rgba(0,0,0,0.3)}}
  .user-dropdown.is-open{{display:block}}
  .user-dropdown a{{display:block;padding:10px 16px;font-size:13px;color:rgba(255,255,255,0.8);text-decoration:none;transition:background 0.15s}}
  .user-dropdown a:hover{{background:rgba(255,255,255,0.08);color:#fff}}
  main{{padding:24px;overflow-x:auto}}
  .page-title{{font-size:20px;font-weight:700;margin-bottom:4px}}
  .count{{font-size:14px;color:#6b7280;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  th{{background:#f3f4f6;padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;white-space:nowrap;cursor:pointer;user-select:none}}
  th:hover{{background:#e9eaec;color:#374151}}
  th.sort-asc::after{{content:' ↑'}}
  th.sort-desc::after{{content:' ↓'}}
  td{{padding:10px 14px;border-top:1px solid #f3f4f6;font-size:14px}}
  tr:hover td{{background:#fafafa}}
  a{{color:#3b82f6}}
  .ts{{white-space:nowrap}}
</style>
</head>
<body>
<header><img src="/assets/logos/logo.svg" class="logo" alt="AmpyPay">{user_menu}</header>
<main>
  <div class="title-row"><h2 class="page-title">Demo Submissions</h2>{export_btn}</div>
  <p class="count" id="countText">{len(rows)} submission(s) total</p>
  <input type="search" id="tableSearch" placeholder="Search…" style="width:100%;max-width:300px;padding:9px 14px;margin-bottom:12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box" />
  <table>
    <thead><tr id="sortRow"><th>#</th><th>Date</th><th>Name</th><th>Company</th><th>Email</th><th>Phone</th><th>Job Title</th><th>Employees</th><th>Country</th><th>IP</th></tr></thead>
    <tbody id="tableBody">{rows_html}</tbody>
  </table>
  <div id="emptySearch" style="display:none;text-align:center;padding:48px 24px;color:#9ca3af">
    <div style="font-size:32px;margin-bottom:12px">🔍</div>
    <div style="font-size:15px;font-weight:600;color:#6b7280;margin-bottom:4px">No results found</div>
    <div style="font-size:13px">Try a different keyword</div>
  </div>
</main>
<script>
  var sortCol = -1, sortDir = 1;
  document.getElementById('sortRow').querySelectorAll('th').forEach(function(th, i) {{
    th.addEventListener('click', function() {{
      var tbody = document.getElementById('tableBody');
      var rows = Array.from(tbody.querySelectorAll('tr'));
      if (sortCol === i) {{ sortDir *= -1; }} else {{ sortDir = 1; sortCol = i; }}
      document.querySelectorAll('#sortRow th').forEach(function(h) {{ h.className = ''; }});
      th.className = sortDir === 1 ? 'sort-asc' : 'sort-desc';
      rows.sort(function(a, b) {{
        var av = a.cells[i] ? a.cells[i].textContent.trim() : '';
        var bv = b.cells[i] ? b.cells[i].textContent.trim() : '';
        var an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return (an - bn) * sortDir;
        return av.localeCompare(bv, undefined, {{numeric: true}}) * sortDir;
      }});
      rows.forEach(function(r) {{ tbody.appendChild(r); }});
    }});
  }});

  document.getElementById('tableSearch').addEventListener('input', function() {{
    var q = this.value.toLowerCase();
    var rows = document.getElementById('tableBody').querySelectorAll('tr');
    var visible = 0;
    rows.forEach(function(r) {{
      var match = r.textContent.toLowerCase().includes(q);
      r.style.display = match ? '' : 'none';
      if (match) visible++;
    }});
    document.getElementById('countText').textContent = q
      ? visible + ' of {len(rows)} submission(s)'
      : '{len(rows)} submission(s) total';
    document.querySelector('table').style.display = visible === 0 && q ? 'none' : '';
    document.getElementById('emptySearch').style.display = visible === 0 && q ? 'block' : 'none';
  }});

  function toggleMenu() {{
    document.getElementById('userDropdown').classList.toggle('is-open');
  }}
  document.addEventListener('click', function(e) {{
    var menu = document.querySelector('.user-menu');
    if (menu && !menu.contains(e.target)) {{
      document.getElementById('userDropdown').classList.remove('is-open');
    }}
  }});
  document.querySelectorAll('.ts[data-ts]').forEach(function(el) {{
    var raw = el.getAttribute('data-ts');
    if (!raw) return;
    var d = new Date(raw.replace(' ', 'T'));
    if (isNaN(d)) return;
    el.textContent = d.toLocaleString(undefined, {{
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    }});
  }});
</script>
</body></html>"""

# ── Static file serving ───────────────────────────────────────────────────────
def serve_static(handler, path):
    if path == '/':
        path = '/index.html'
    file_path = os.path.join(BASE_DIR, path.lstrip('/'))
    if not os.path.abspath(file_path).startswith(BASE_DIR):
        handler._error_page(400, '400.html', '<h2>400 Bad Request</h2>')
        return
    if not os.path.isfile(file_path):
        handler._error_page(404, '404.html', '<h2>404 Not Found</h2>')
        return
    mime, _ = mimetypes.guess_type(file_path)
    mime = mime or 'application/octet-stream'
    with open(file_path, 'rb') as f:
        body = f.read()
    handler.send_response(200)
    handler.send_header('Content-Type', mime)
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

# ── Request Handler ───────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f'[{self.address_string()}] {fmt % args}')

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, code, html):
        body = html.encode()
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, set_cookie=None):
        self.send_response(302)
        if set_cookie:
            self.send_header('Set-Cookie', set_cookie)
        self.send_header('Location', location)
        self.end_headers()

    def _check_session(self):
        cookie_str = self.headers.get('Cookie', '')
        cookies = http.cookies.SimpleCookie(cookie_str)
        return cookies.get('ap_session') and cookies['ap_session'].value == ADMIN_TOKEN

    def _get_display_name(self):
        cookie_str = self.headers.get('Cookie', '')
        cookies = http.cookies.SimpleCookie(cookie_str)
        if cookies.get('ap_display'):
            return urllib.parse.unquote(cookies['ap_display'].value)
        return 'Admin'

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _error_page(self, code, filename, fallback):
        page = os.path.join(BASE_DIR, filename)
        try:
            self._html(code, open(page, encoding='utf-8').read())
        except Exception:
            self._html(code, fallback)

    def do_GET(self):
        try:
            self._route_get()
        except Exception as e:
            print(f'[500] {e}')
            self._error_page(500, '500.html', '<h2>500 — Something went wrong</h2>')

    def _route_get(self):
        parsed = urllib.parse.urlparse(self.path)
        qs     = urllib.parse.parse_qs(parsed.query)
        token  = qs.get('token', [''])[0]
        path   = parsed.path

        if path == '/demo':
            serve_static(self, '/demo.html')
        elif path == '/admin':
            if token != ADMIN_TOKEN:
                self._html(401, '<h2>401 Unauthorized — add ?token=YOUR_TOKEN to the URL</h2>')
                return
            try:
                rows = mysql_get_all_submissions()
            except Exception as e:
                self._html(503, f'<h2>Database unavailable</h2><pre>{e}</pre>')
                return
            self._html(200, admin_html(rows))
        elif path == '/admin/data':
            if token != ADMIN_TOKEN:
                self._json(401, {'error': 'Unauthorized'})
                return
            try:
                self._json(200, mysql_get_all_submissions())
            except Exception as e:
                self._json(503, {'error': str(e)})
        elif path in ('/ap-control', '/ap-control/login'):
            if not self._check_session():
                self._html(200, login_html())
                return
            try:
                rows = mysql_get_all_submissions()
            except Exception as e:
                self._html(503, f'<h2>Database unavailable</h2><pre>{e}</pre>')
                return
            display = self._get_display_name()
            user_menu = f'<div class="actions"><div class="user-menu"><button class="user-btn" onclick="toggleMenu()">{display} <span class="chevron">&#9660;</span></button><div class="user-dropdown" id="userDropdown"><a href="/ap-control/logout">Logout</a></div></div></div>'
            export_btn = '<a href="/ap-control/export" class="btn-export">Export CSV</a>'
            self._html(200, admin_html(rows, user_menu=user_menu, export_btn=export_btn))
        elif path == '/ap-control/logout':
            self.send_response(302)
            self.send_header('Set-Cookie', 'ap_session=; HttpOnly; Path=/; Max-Age=0')
            self.send_header('Set-Cookie', 'ap_display=; Path=/; Max-Age=0')
            self.send_header('Location', '/ap-control')
            self.end_headers()
        elif path == '/ap-control/export':
            if not self._check_session():
                self._redirect('/ap-control')
                return
            try:
                rows = mysql_get_all_submissions()
            except Exception as e:
                self._html(503, f'<h2>Database unavailable</h2><pre>{e}</pre>')
                return
            import csv, io
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(['#', 'Date', 'Name', 'Company', 'Email', 'Phone', 'Job Title', 'Employees', 'Country', 'IP'])
            for r in rows:
                writer.writerow([r['id'], r['created_at'], r['name'], r['company'], r['email'],
                                  r.get('phone',''), r.get('job_title',''), r.get('employees',''),
                                  r.get('country',''), r.get('ip','')])
            body = buf.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="demo_submissions.csv"')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == '/ap-control/data':
            if not self._check_session():
                self._json(401, {'error': 'Unauthorized'})
                return
            try:
                self._json(200, mysql_get_all_submissions())
            except Exception as e:
                self._json(503, {'error': str(e)})
        else:
            serve_static(self, path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ('/admin/login', '/ap-control/login'):
            ip = _get_client_ip(self)
            if login_is_blocked(ip):
                wait = login_remaining_wait(ip)
                self._html(429, f'<h2>Too many failed attempts</h2><p>Try again in {wait // 60}m {wait % 60}s.</p>')
                return
            length = int(self.headers.get('Content-Length', 0))
            data = urllib.parse.parse_qs(self.rfile.read(length).decode())
            username = data.get('username', [''])[0].strip()
            password = data.get('password', [''])[0].strip()
            display = mysql_verify_admin(username, password)
            if display:
                login_clear(ip)
                mysql_update_last_login(username)
                self.send_response(302)
                self.send_header('Set-Cookie', f'ap_session={ADMIN_TOKEN}; HttpOnly; Path=/; SameSite=Strict')
                self.send_header('Set-Cookie', f'ap_display={urllib.parse.quote(display)}; Path=/; SameSite=Strict')
                self.send_header('Location', '/ap-control')
                self.end_headers()
            else:
                login_record_failure(ip)
                remaining = _RATE_LIMIT_MAX - len([t for t in _login_attempts.get(ip, []) if _time.time() - t < _RATE_LIMIT_WINDOW])
                self._html(200, login_html(error=True, attempts_left=max(0, remaining)))
            return

        if parsed.path != '/api/demo':
            self._json(404, {'error': 'Not found'})
            return

        length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {'error': 'Invalid JSON'})
            return

        name        = (body.get('name') or '').strip()
        company     = (body.get('company') or '').strip()
        email       = (body.get('email') or '').strip()
        phone       = normalize_phone(body.get('phone') or '')
        job_title   = (body.get('job_title') or '').strip()
        employees   = (body.get('employees') or '').strip()
        hp          = body.get('_hp', '')
        client_time = (body.get('client_time') or '').strip()

        if hp:
            self._json(200, {'ok': True})
            return
        if not name or not company or not email:
            self._json(400, {'error': 'Name, company and email are required.'})
            return
        if not valid_name(name):
            self._json(400, {'error': 'Please enter a valid name.'})
            return
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            self._json(400, {'error': 'Invalid email address.'})
            return
        if phone and not PHONE_RE.match(phone):
            self._json(400, {'error': 'Enter a valid phone number.'})
            return

        try:
            if mysql_recent_count_by_email(email) >= 3:
                self._json(429, {'error': 'This email already has a pending request. We will be in touch.'})
                return
        except Exception as e:
            self._json(503, {'error': f'Database unavailable: {e}'})
            return

        raw_ip = self.headers.get('X-Forwarded-For', self.client_address[0]).split(',')[0].strip()
        ip = raw_ip if not _PRIVATE_IP.match(raw_ip) else (_get_public_ip() or raw_ip)
        country = lookup_country(ip)
        try:
            mysql_insert_submission(name, company, email, phone, ip, job_title, employees, client_time, country)
        except Exception as e:
            self._json(503, {'error': f'Database unavailable: {e}'})
            return
        notify_admin(name, company, email, phone, job_title, employees)
        confirm_customer(name, company, email)
        self._json(200, {'ok': True})

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
        PORT         = int(_env('PORT', '3001'))
        SMTP_HOST    = _env('SMTP_HOST', 'mail.eunite.com')
        SMTP_PORT    = int(_env('SMTP_PORT', '25'))
        SMTP_SECURE  = _env('SMTP_SECURE', 'false').lower() == 'true'
        SMTP_USER    = _env('SMTP_USER', 'noreply@eunite.com')
        SMTP_PASS    = _env('SMTP_PASS', '')
        NOTIFY_EMAIL = _env('NOTIFY_EMAIL', 'admin@eunite.com')
        ADMIN_TOKEN  = _env('ADMIN_TOKEN', 'changeme')
        _db = _env('DB_PATH', os.path.join(BASE_DIR, 'demo_submissions.db'))
        DB_PATH      = _db if os.path.isabs(_db) else os.path.join(BASE_DIR, _db)

    init_db()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f'AmpyPay running on http://0.0.0.0:{PORT}')
    print(f'Admin: http://localhost:{PORT}/ap-control')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
