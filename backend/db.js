const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, 'demo-requests.db'));

db.exec(`
  CREATE TABLE IF NOT EXISTS submissions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL,
    company   TEXT    NOT NULL,
    email     TEXT    NOT NULL,
    phone     TEXT    DEFAULT '',
    ip        TEXT    DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

const insert = db.prepare(
  'INSERT INTO submissions (name, company, email, phone, ip) VALUES (?, ?, ?, ?, ?)'
);

const selectAll = db.prepare(
  'SELECT id, name, company, email, phone, created_at FROM submissions ORDER BY created_at DESC'
);

const countByEmailWindow = db.prepare(
  "SELECT COUNT(*) AS n FROM submissions WHERE email = ? AND created_at >= datetime('now', '-1 hour')"
);

module.exports = {
  insertSubmission({ name, company, email, phone, ip }) {
    return insert.run(name, company, email, phone || '', ip || '').lastInsertRowid;
  },
  getSubmissions() {
    return selectAll.all();
  },
  recentCountByEmail(email) {
    return countByEmailWindow.get(email).n;
  },
};
