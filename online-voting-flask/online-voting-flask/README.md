# Online Voting System (Flask)

A simple but complete online voting system built with Flask, SQLite, and CSS.
It separates user and admin roles. Admin can customize election settings,
manage positions & candidates, view live results, and reset the election.

## Features
- User sign up / login (passwords hashed)
- Role-based access (admin vs voter)
- Positions (e.g., President, Secretary)
- Candidates under each position
- One vote per user *per position*
- Admin dashboard to:
  - Toggle election open/close
  - Toggle public visibility of results
  - Edit site title
  - CRUD for positions & candidates
  - Live results & CSV export
  - Reset election (delete all votes)
- Modern CSS styling (no external CDN required)

## Quickstart

```bash
# 1) Create and activate a virtualenv (Windows PowerShell)
py -m venv .venv
.venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Run the app
set FLASK_APP=app.py  # Windows (PowerShell): $env:FLASK_APP="app.py"
flask run
```

Then open http://127.0.0.1:5000

### Default Admin
- Email: admin@example.com
- Password: Admin@123

Change this immediately in the admin dashboard.

## Notes
- Database file: `instance/votes.db` (auto-created)
- To reset everything, delete `instance/votes.db` or use Admin → Reset Election.
- This app is intentionally compact for learning—extend/secure it further for production.
