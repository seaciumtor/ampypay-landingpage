#!/usr/bin/env python3
"""
AmpyPay all-in-one server — stdlib only, no pip install needed.
Serves static frontend AND handles API/admin on a single port.

Routes:
  GET  /              → index.html
  GET  /css/*, /js/*, /assets/*  → static files
  POST /api/demo      → save submission, send emails
  GET  /admin         → view submissions (?token=)
  GET  /admin/data    → JSON list (?token=)
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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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

# ── Database ──────────────────────────────────────────────────────────────────
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
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        for col, typedef in [('job_title', 'TEXT'), ('employees', 'TEXT')]:
            try:
                conn.execute(f'ALTER TABLE submissions ADD COLUMN {col} {typedef}')
            except Exception:
                pass
        conn.commit()

def insert_submission(name, company, email, phone, ip, job_title='', employees=''):
    with _db_lock:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO submissions (name,company,email,phone,job_title,employees,ip) VALUES (?,?,?,?,?,?,?)",
                (name, company, email, phone or '', job_title or '', employees or '', ip)
            )
            conn.commit()

def recent_count_by_email(email):
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM submissions WHERE email=? "
            "AND created_at >= datetime('now','-30 minutes','localtime')",
            (email,)
        ).fetchone()
        return row['c'] if row else 0

def get_all_submissions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id,name,company,email,phone,job_title,employees,ip,created_at "
            "FROM submissions ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

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
def admin_html(rows):
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
          <td>{r.get('job_title') or '-'}</td>
          <td>{r.get('employees') or '-'}</td>
          <td style="font-size:12px;color:#6b7280">{r['ip'] or '-'}</td>
        </tr>"""
    if not rows_html:
        rows_html = '<tr><td colspan="9" style="text-align:center;color:#9ca3af;padding:32px">No submissions yet.</td></tr>'
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
  main{{padding:24px;overflow-x:auto}}
  .count{{font-size:14px;color:#6b7280;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  th{{background:#f3f4f6;padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;white-space:nowrap}}
  td{{padding:10px 14px;border-top:1px solid #f3f4f6;font-size:14px}}
  tr:hover td{{background:#fafafa}}
  a{{color:#3b82f6}}
</style>
</head>
<body>
<header><h1>AmpyPay</h1><span>Demo Submissions</span></header>
<main>
  <p class="count">{len(rows)} submission(s) total</p>
  <table>
    <thead><tr><th>#</th><th>Date</th><th>Name</th><th>Company</th><th>Email</th><th>Phone</th><th>Job Title</th><th>Employees</th><th>IP</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</main>
</body></html>"""

# ── Static file serving ───────────────────────────────────────────────────────
def serve_static(handler, path):
    # map / → index.html
    if path == '/':
        path = '/index.html'
    file_path = os.path.join(BASE_DIR, path.lstrip('/'))
    # prevent directory traversal
    if not os.path.abspath(file_path).startswith(BASE_DIR):
        handler._json(403, {'error': 'Forbidden'})
        return
    if not os.path.isfile(file_path):
        handler._html(404, '<h2>404 Not Found</h2>')
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

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs     = urllib.parse.parse_qs(parsed.query)
        token  = qs.get('token', [''])[0]
        path   = parsed.path

        if path == '/admin':
            if token != ADMIN_TOKEN:
                self._html(401, '<h2>401 Unauthorized — add ?token=YOUR_TOKEN to the URL</h2>')
                return
            self._html(200, admin_html(get_all_submissions()))
        elif path == '/admin/data':
            if token != ADMIN_TOKEN:
                self._json(401, {'error': 'Unauthorized'})
                return
            self._json(200, get_all_submissions())
        else:
            serve_static(self, path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != '/api/demo':
            self._json(404, {'error': 'Not found'})
            return

        length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {'error': 'Invalid JSON'})
            return

        name      = (body.get('name') or '').strip()
        company   = (body.get('company') or '').strip()
        email     = (body.get('email') or '').strip()
        phone     = (body.get('phone') or '').strip()
        job_title = (body.get('job_title') or '').strip()
        employees = (body.get('employees') or '').strip()
        hp        = body.get('_hp', '')

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
        insert_submission(name, company, email, phone, ip, job_title, employees)
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
        DB_PATH      = _env('DB_PATH', os.path.join(BASE_DIR, 'demo_submissions.db'))

    init_db()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f'AmpyPay running on http://0.0.0.0:{PORT}')
    print(f'Admin: http://localhost:{PORT}/admin?token={ADMIN_TOKEN}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
