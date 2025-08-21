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
