#!/usr/bin/env python3
"""
AmpyPay demo-request backend — stdlib only, no pip install needed.
Endpoints:
  POST /api/demo        — save submission, send emails
  GET  /admin           — view submissions (password via ?token=)
  GET  /admin/data      — JSON list (same auth)
"""

import http.server
import json
import os
import re
import smtplib
import sqlite3
import threading
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
def _env(key, default=''):
    return os.environ.get(key, default)

PORT        = int(_env('PORT', '3001'))
SMTP_HOST   = _env('SMTP_HOST', 'mail.eunite.com')
SMTP_PORT   = int(_env('SMTP_PORT', '25'))
SMTP_SECURE = _env('SMTP_SECURE', 'false').lower() == 'true'
SMTP_USER   = _env('SMTP_USER', 'noreply@eunite.com')
SMTP_PASS   = _env('SMTP_PASS', '')
NOTIFY_EMAIL= _env('NOTIFY_EMAIL', 'admin@eunite.com')
ADMIN_TOKEN = _env('ADMIN_TOKEN', 'changeme')
DB_PATH     = _env('DB_PATH', 'demo_submissions.db')

# ── Database ─────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                company   TEXT NOT NULL,
                email     TEXT NOT NULL,
                phone     TEXT,
                ip        TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()

def insert_submission(name, company, email, phone, ip):
    with _db_lock:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO submissions (name,company,email,phone,ip) VALUES (?,?,?,?,?)",
                (name, company, email, phone or '', ip)
            )
            conn.commit()

def recent_count_by_email(email):
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM submissions WHERE email=? AND created_at >= datetime('now','-30 minutes','localtime')",
            (email,)
        ).fetchone()
        return row['c'] if row else 0

def get_all_submissions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id,name,company,email,phone,ip,created_at FROM submissions ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

# ── Email ────────────────────────────────────────────────────────────────────
def send_email(to, subject, html):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = SMTP_USER
    msg['To']      = to
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
        s.sendmail(SMTP_USER, [to], msg.as_bytes())
        s.quit()
        return True
    except Exception as e:
        print(f'[email error] {e}')
        return False

def notify_admin(name, company, email, phone):
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
      <h2 style="color:#111">New Demo Request</h2>
      <table style="border-collapse:collapse;width:100%">
        <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600">Name</td><td style="padding:8px 12px">{name}</td></tr>
        <tr><td style="padding:8px 12px;font-weight:600">Company</td><td style="padding:8px 12px">{company}</td></tr>
        <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600">Email</td><td style="padding:8px 12px"><a href="mailto:{email}">{email}</a></td></tr>
        <tr><td style="padding:8px 12px;font-weight:600">Phone</td><td style="padding:8px 12px">{phone or '-'}</td></tr>
      </table>
    </div>
    """
    threading.Thread(
        target=send_email,
        args=(NOTIFY_EMAIL, f'[AmpyPay] New demo request — {name} ({company})', html),
        daemon=True
    ).start()

def confirm_customer(name, company, email):
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#111">
      <div style="background:#0a0a0a;padding:24px;text-align:center">
        <span style="color:#fff;font-size:20px;font-weight:700;letter-spacing:0.04em">AmpyPay</span>
      </div>
      <div style="padding:32px 24px">
        <h2 style="margin:0 0 8px">Thanks, {name}!</h2>
        <p style="color:#4b5563">We've received your demo request from <strong>{company}</strong>.<br>
        Our team will reach out within one business day to schedule your demo.</p>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
        <p style="font-size:13px;color:#6b7280">If you have any questions, just reply to this email.</p>
      </div>
      <div style="background:#f3f4f6;padding:16px 24px;text-align:center;font-size:12px;color:#9ca3af">
        © 2024 AmpyPay · This email was sent because you requested a demo.
      </div>
    </div>
    """
    threading.Thread(
        target=send_email,
        args=(email, 'Your AmpyPay demo request is confirmed', html),
        daemon=True
    ).start()

# ── Admin HTML ───────────────────────────────────────────────────────────────
def admin_html(rows, token):
    rows_html = ''
    for r in rows:
        rows_html += f"""
        <tr>
          <td>{r['id']}</td>
          <td>{r['created_at']}</td>
          <td>{r['name']}</td>
          <td>{r['company']}</td>
          <td><a href="mailto:{r['email']}">{r['email']}</a></td>
          <td>{r['phone'] or '-'}</td>
          <td style="font-size:12px;color:#6b7280">{r['ip'] or '-'}</td>
        </tr>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AmpyPay — Demo Submissions</title>
<style>
  body{{font-family:system-ui,sans-serif;margin:0;background:#f9fafb;color:#111}}
  header{{background:#0a0a0a;color:#fff;padding:16px 24px;display:flex;align-items:center;gap:16px}}
  header h1{{margin:0;font-size:18px;font-weight:700}}
  header span{{font-size:13px;opacity:.5}}
  main{{padding:24px}}
  .count{{font-size:14px;color:#6b7280;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  th{{background:#f3f4f6;padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#6b7280}}
  td{{padding:10px 14px;border-top:1px solid #f3f4f6;font-size:14px}}
  tr:hover td{{background:#fafafa}}
  a{{color:#3b82f6}}
</style>
</head>
<body>
<header>
  <h1>AmpyPay</h1>
  <span>Demo Submissions</span>
</header>
<main>
  <p class="count">{len(rows)} submission(s) total</p>
  <table>
    <thead><tr><th>#</th><th>Date</th><th>Name</th><th>Company</th><th>Email</th><th>Phone</th><th>IP</th></tr></thead>
    <tbody>{rows_html if rows_html else '<tr><td colspan="7" style="text-align:center;color:#9ca3af;padding:32px">No submissions yet.</td></tr>'}</tbody>
  </table>
</main>
</body></html>"""

# ── Request Handler ──────────────────────────────────────────────────────────
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

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        token = qs.get('token', [''])[0]

        if parsed.path == '/admin':
            if token != ADMIN_TOKEN:
                self._html(401, '<h2>401 Unauthorized — add ?token=YOUR_TOKEN to the URL</h2>')
                return
            rows = get_all_submissions()
            self._html(200, admin_html(rows, token))

        elif parsed.path == '/admin/data':
            if token != ADMIN_TOKEN:
                self._json(401, {'error': 'Unauthorized'})
                return
            self._json(200, get_all_submissions())

        else:
            self._json(404, {'error': 'Not found'})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == '/api/demo':
            length = int(self.headers.get('Content-Length', 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self._json(400, {'error': 'Invalid JSON'})
                return

            name    = (body.get('name') or '').strip()
            company = (body.get('company') or '').strip()
            email   = (body.get('email') or '').strip()
            phone   = (body.get('phone') or '').strip()
            hp      = body.get('_hp', '')

            # honeypot
            if hp:
                self._json(200, {'ok': True})
                return

            if not name or not company or not email:
                self._json(400, {'error': 'Name, company and email are required.'})
                return
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                self._json(400, {'error': 'Invalid email address.'})
                return
            if recent_count_by_email(email) >= 3:
                self._json(429, {'error': 'This email already has a pending request. We will be in touch.'})
                return

            ip = self.headers.get('X-Forwarded-For', self.client_address[0])
            insert_submission(name, company, email, phone, ip)
            notify_admin(name, company, email, phone)
            confirm_customer(name, company, email)

            self._json(200, {'ok': True})
        else:
            self._json(404, {'error': 'Not found'})

# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Load .env if present
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
        # Re-read after loading .env
        SMTP_HOST    = _env('SMTP_HOST', 'mail.eunite.com')
        SMTP_PORT    = int(_env('SMTP_PORT', '25'))
        SMTP_SECURE  = _env('SMTP_SECURE', 'false').lower() == 'true'
        SMTP_USER    = _env('SMTP_USER', 'noreply@eunite.com')
        SMTP_PASS    = _env('SMTP_PASS', '')
        NOTIFY_EMAIL = _env('NOTIFY_EMAIL', 'admin@eunite.com')
        ADMIN_TOKEN  = _env('ADMIN_TOKEN', 'changeme')
        DB_PATH      = _env('DB_PATH', 'demo_submissions.db')

    init_db()
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    print(f'AmpyPay backend running on http://0.0.0.0:{PORT}')
    print(f'Admin panel: http://localhost:{PORT}/admin?token={ADMIN_TOKEN}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
