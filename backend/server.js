require('dotenv').config();
const express = require('express');
const cors = require('cors');
const session = require('express-session');
const bcrypt = require('bcryptjs');
const speakeasy = require('speakeasy');
const rateLimit = require('express-rate-limit');
const nodemailer = require('nodemailer');
const path = require('path');
const db = require('./db');

const app = express();
const PORT = process.env.PORT || 3001;

app.set('trust proxy', 1);
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(cors({ origin: process.env.ALLOWED_ORIGIN || '*', credentials: true }));
app.use(session({
  secret: process.env.SESSION_SECRET || 'dev-secret-change-me',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 8 * 60 * 60 * 1000 }, // 8 h
}));

// Rate limit for demo form: 5 requests per IP per 30 min
const demoLimiter = rateLimit({
  windowMs: 30 * 60 * 1000,
  max: 5,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests. Please try again later.' },
});

// Rate limit for login: 10 attempts per IP per 15 min
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: 'Too many login attempts. Please try again later.',
  skipSuccessfulRequests: true,
});

const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  port: parseInt(process.env.SMTP_PORT || '587', 10),
  secure: process.env.SMTP_SECURE === 'true',
  auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS },
});

function requireAuth(req, res, next) {
  if (req.session?.authenticated) return next();
  res.redirect('/ap-control/login');
}

/* ── POST /api/demo ── */
app.post('/api/demo', demoLimiter, async (req, res) => {
  const { name, company, email, phone, _hp } = req.body;
  const ip = req.ip;

  if (_hp) return res.json({ success: true });

  if (!name?.trim() || !company?.trim() || !email?.trim()) {
    return res.status(400).json({ error: 'Name, company and email are required.' });
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email address.' });
  }
  if (db.recentCountByEmail(email) >= 3) {
    return res.status(429).json({ error: 'This email has already submitted a request. We will be in touch.' });
  }

  db.insertSubmission({ name: name.trim(), company: company.trim(), email: email.trim(), phone: phone?.trim() || '', ip });

  transporter.sendMail({
    from: `"AmpyPay Demo" <${process.env.SMTP_USER}>`,
    to: process.env.NOTIFY_EMAIL,
    subject: `[AmpyPay] New demo request — ${name.trim()} (${company.trim()})`,
    html: `
      <h2 style="font-family:sans-serif">New Demo Request</h2>
      <table style="font-family:sans-serif;border-collapse:collapse">
        <tr><td style="padding:6px 12px;font-weight:bold">Name</td><td style="padding:6px 12px">${name.trim()}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:bold">Company</td><td style="padding:6px 12px">${company.trim()}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:bold">Email</td><td style="padding:6px 12px"><a href="mailto:${email.trim()}">${email.trim()}</a></td></tr>
        <tr><td style="padding:6px 12px;font-weight:bold">Phone</td><td style="padding:6px 12px">${phone?.trim() || '—'}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:bold">Time</td><td style="padding:6px 12px">${new Date().toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' })}</td></tr>
      </table>
    `,
  }).catch((err) => console.error('Email send error:', err.message));

  res.json({ success: true });
});

/* ── GET /ap-control/login ── Login page */
app.get('/ap-control/login', (req, res) => {
  if (req.session?.authenticated) return res.redirect('/ap-control');
  res.sendFile(path.join(__dirname, 'views', 'login.html'));
});

/* ── POST /ap-control/login ── Authenticate */
app.post('/ap-control/login', loginLimiter, async (req, res) => {
  const { username, password, totp } = req.body;

  const validUser = username === process.env.ADMIN_USER;
  const validPass = validUser && await bcrypt.compare(password, process.env.ADMIN_PASS_HASH || '');

  if (!validUser || !validPass) {
    return res.redirect('/ap-control/login?error=credentials');
  }

  const validTotp = speakeasy.totp.verify({
    secret: process.env.TOTP_SECRET,
    encoding: 'base32',
    token: (totp || '').replace(/\s/g, ''),
    window: 1, // ±30s tolerance
  });

  if (!validTotp) {
    return res.redirect('/ap-control/login?error=totp');
  }

  req.session.authenticated = true;
  req.session.username = username;
  res.redirect('/ap-control');
});

/* ── GET /ap-control/setup-2fa ── Show QR code for initial Authenticator setup */
app.get('/ap-control/setup-2fa', requireAuth, async (req, res) => {
  const QRCode = require('qrcode');
  const otpauthUrl = speakeasy.otpauthURL({
    secret: process.env.TOTP_SECRET,
    label: encodeURIComponent('AmpyPay Admin'),
    issuer: 'AmpyPay',
    encoding: 'base32',
  });
  const qrDataUrl = await QRCode.toDataURL(otpauthUrl);
  res.send(`<!DOCTYPE html><html><head>
    <meta charset="UTF-8"><title>2FA Setup — AmpyPay</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
      *{box-sizing:border-box;margin:0;padding:0}
      body{font-family:'Inter',sans-serif;background:#071737;color:#FBFBEE;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
      .card{background:rgba(13,37,80,.7);border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:40px;max-width:420px;width:100%;text-align:center;backdrop-filter:blur(16px)}
      h1{font-size:20px;font-weight:700;margin-bottom:8px}
      p{font-size:13px;color:rgba(251,251,238,.6);margin-bottom:24px;line-height:1.6}
      img{border-radius:12px;border:4px solid #fff;width:200px;height:200px;margin-bottom:20px}
      .secret{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:12px 16px;font-family:monospace;font-size:14px;letter-spacing:.1em;margin-bottom:24px;word-break:break-all}
      a{display:inline-block;padding:11px 28px;background:#2563EA;color:#fff;border-radius:10px;text-decoration:none;font-weight:600;font-size:14px}
      a:hover{background:#1d4ed8}
      .note{font-size:11px;color:rgba(251,251,238,.35);margin-top:16px}
    </style>
  </head><body>
    <div class="card">
      <h1>Scan with Google Authenticator</h1>
      <p>Open Google Authenticator → tap <strong>+</strong> → <strong>Scan a QR code</strong><br>จากนั้น login จะต้องใส่รหัส 6 หลักทุกครั้ง</p>
      <img src="${qrDataUrl}" alt="QR Code" />
      <p style="font-size:12px;color:rgba(251,251,238,.5);margin-bottom:8px">หรือพิมพ์ manual secret:</p>
      <div class="secret">${process.env.TOTP_SECRET}</div>
      <a href="/ap-control">← Back to Dashboard</a>
      <p class="note">หน้านี้ใช้ได้เฉพาะตอน login อยู่เท่านั้น — ไม่ต้องเข้าอีกหลังจาก scan แล้ว</p>
    </div>
  </body></html>`);
});

/* ── GET /ap-control/logout ── */
app.get('/ap-control/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/ap-control/login'));
});

/* ── GET /ap-control ── Dashboard (protected) */
app.get('/ap-control', requireAuth, (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'admin.html'));
});

/* ── GET /api/demos ── JSON API (protected by session) */
app.get('/api/demos', requireAuth, (req, res) => {
  res.json(db.getSubmissions());
});

app.listen(PORT, () => console.log(`AmpyPay backend → http://localhost:${PORT}`));
