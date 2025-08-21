from __future__ import annotations
import csv, os, datetime as dt
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-please"),
    SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(INSTANCE_DIR, "votes.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------------------- Models ----------------------
class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(256), nullable=False)

    @staticmethod
    def get(key, default=None):
        s = Setting.query.get(key)
        return s.value if s else default

    @staticmethod
    def set(key, value):
        s = Setting.query.get(key)
        if not s:
            s = Setting(key=key, value=str(value))
            db.session.add(s)
        else:
            s.value = str(value)
        db.session.commit()

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="voter")  # 'admin' or 'voter'
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

    def set_password(self, p):
        self.password_hash = generate_password_hash(p)

    def check_password(self, p):
        return check_password_hash(self.password_hash, p)

    def is_admin(self): return self.role == "admin"

class Position(db.Model):
    __tablename__ = "positions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)

    candidates = db.relationship("Candidate", backref="position", cascade="all, delete-orphan")

class Candidate(db.Model):
    __tablename__ = "candidates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    manifesto = db.Column(db.Text)
    position_id = db.Column(db.Integer, db.ForeignKey("positions.id"), nullable=False)

    votes = db.relationship("Vote", backref="candidate", cascade="all, delete-orphan")

class Vote(db.Model):
    __tablename__ = "votes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("positions.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidates.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "position_id", name="uq_vote_user_position"),
    )

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ---------------------- Helpers ----------------------
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    return {
        "site_title": Setting.get("site_title", "Campus Election"),
        "election_open": Setting.get("election_open", "true") == "true",
        "show_results_public": Setting.get("show_results_public", "false") == "false" and False or Setting.get("show_results_public", "false") == "true",
    }

# ---------------------- Setup (create DB & seed admin) ----------------------
@app.before_request
def ensure_initialized():
    db.create_all()
    # seed settings
    if Setting.get("site_title") is None:
        Setting.set("site_title", "Campus Election")
        Setting.set("election_open", "true")
        Setting.set("show_results_public", "false")
    # seed admin
    if not User.query.filter_by(role="admin").first():
        admin = User(name="Admin", email="admin@123.com", role="admin")
        admin.set_password("1234")
        db.session.add(admin)
        db.session.commit()

# ---------------------- Public Routes ----------------------
@app.route("/")
def index():
    positions = Position.query.order_by(Position.name.asc()).all()
    return render_template("index.html", positions=positions)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").lower().strip()
        password = request.form.get("password","")
        if not name or not email or not password:
            flash("All fields are required.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created! Please sign in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").lower().strip()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.name.split()[0]}!", "success")
            return redirect(url_for("admin_dashboard" if user.is_admin() else "vote"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("index"))

# ---------------------- Voting ----------------------
@app.route("/vote", methods=["GET","POST"])
@login_required
def vote():
    election_open = Setting.get("election_open", "true") == "true"
    positions = Position.query.order_by(Position.name.asc()).all()

    if request.method == "POST":
        if not election_open:
            flash("Election is closed.", "error")
            return redirect(url_for("vote"))

        chosen = []
        for p in positions:
            cand_id = request.form.get(f"position_{p.id}")
            if cand_id:
                chosen.append((p.id, int(cand_id)))

        if not chosen:
            flash("Please make at least one selection.", "error")
            return redirect(url_for("vote"))

        # record votes per position (enforce 1 vote/position)
        for pos_id, cand_id in chosen:
            existing = Vote.query.filter_by(user_id=current_user.id, position_id=pos_id).first()
            if existing:
                existing.candidate_id = cand_id
            else:
                db.session.add(Vote(user_id=current_user.id, position_id=pos_id, candidate_id=cand_id))
        db.session.commit()
        flash("Your selections have been recorded.", "success")
        return redirect(url_for("vote"))

    # prefetch user's choices
    my_votes = {v.position_id: v.candidate_id for v in Vote.query.filter_by(user_id=current_user.id).all()}
    return render_template("vote.html", positions=positions, my_votes=my_votes, election_open=election_open)

@app.route("/results")
def results():
    public = Setting.get("show_results_public", "false") == "true"
    if not public and (not current_user.is_authenticated or not current_user.is_admin()):
        flash("Results are not public right now.", "error")
        return redirect(url_for("index"))
    positions = Position.query.order_by(Position.name.asc()).all()
    # compute counts
    counts = {}
    for p in positions:
        rows = db.session.query(Candidate, db.func.count(Vote.id)).join(Vote, isouter=True).filter(Candidate.position_id==p.id).group_by(Candidate.id).all()
        counts[p.id] = rows
    total_voters = User.query.filter_by(role="voter").count()
    voted_voters = db.session.query(Vote.user_id).distinct().count()
    return render_template("results.html", positions=positions, counts=counts, total_voters=total_voters, voted_voters=voted_voters)

# ---------------------- Admin ----------------------
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    positions = Position.query.order_by(Position.name.asc()).all()
    total_users = User.query.count()
    total_voters = User.query.filter_by(role="voter").count()
    votes_cast = db.session.query(Vote.user_id).distinct().count()
    return render_template("admin/dashboard.html", positions=positions, total_users=total_users, total_voters=total_voters, votes_cast=votes_cast)

@app.route("/admin/settings", methods=["POST"])
@login_required
@admin_required
def admin_settings():
    title = request.form.get("site_title", "Campus Election").strip() or "Campus Election"
    election_open = "election_open" in request.form
    show_public = "show_results_public" in request.form
    Setting.set("site_title", title)
    Setting.set("election_open", "true" if election_open else "false")
    Setting.set("show_results_public", "true" if show_public else "false")
    flash("Settings saved.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/position/new", methods=["POST"])
@login_required
@admin_required
def admin_position_new():
    name = request.form.get("name","").strip()
    desc = request.form.get("description","").strip()
    if not name:
        flash("Position name required.", "error")
    elif Position.query.filter_by(name=name).first():
        flash("Position already exists.", "error")
    else:
        db.session.add(Position(name=name, description=desc))
        db.session.commit()
        flash("Position created.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/position/<int:pid>/delete", methods=["POST"])
@login_required
@admin_required
def admin_position_delete(pid):
    p = db.session.get(Position, pid) or abort(404)
    db.session.delete(p)
    db.session.commit()
    flash("Position deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/candidate/new", methods=["POST"])
@login_required
@admin_required
def admin_candidate_new():
    name = request.form.get("name","").strip()
    manifesto = request.form.get("manifesto","").strip()
    position_id = int(request.form.get("position_id"))
    if not name:
        flash("Candidate name required.", "error")
    else:
        db.session.add(Candidate(name=name, manifesto=manifesto, position_id=position_id))
        db.session.commit()
        flash("Candidate added.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/candidate/<int:cid>/delete", methods=["POST"])
@login_required
@admin_required
def admin_candidate_delete(cid):
    c = db.session.get(Candidate, cid) or abort(404)
    db.session.delete(c)
    db.session.commit()
    flash("Candidate removed.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reset", methods=["POST"])
@login_required
@admin_required
def admin_reset():
    db.session.query(Vote).delete()
    db.session.commit()
    flash("All votes cleared.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/export")
@login_required
@admin_required
def admin_export():
    positions = Position.query.order_by(Position.name.asc()).all()
    out_path = os.path.join(INSTANCE_DIR, "results.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Position","Candidate","Votes"])
        for p in positions:
            rows = db.session.query(Candidate.name, db.func.count(Vote.id)).join(Vote, isouter=True).filter(Candidate.position_id==p.id).group_by(Candidate.id).all()
            for name, count in rows:
                writer.writerow([p.name, name, count])
    return send_file(out_path, as_attachment=True, download_name="results.csv")

# ---- Error pages ----
@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", title="Forbidden", message="You don't have permission for this action."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", title="Not Found", message="That page doesn't exist."), 404

if __name__ == "__main__":
    app.run(debug=True)
