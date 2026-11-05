import os
import re
import io
import base64
import secrets
import unicodedata
import math
import smtplib
import ssl
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from sqlalchemy import text, Index
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from functools import wraps
from PIL import Image, ImageDraw, ImageFont, ImageOps
from locations import PH_LOCATIONS, PH_LOCATION_VALUES

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = 'netsync-2026-secure-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:LupinThe3rd!@localhost:5432/netsync_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- EMAIL (Gmail SMTP) - used to send the admin password-reset code ---
# Set these as environment variables (use a Gmail *App Password*, not the normal Gmail password):
#   NETSYNC_MAIL_USER          e.g. yourname@gmail.com  (the Gmail that SENDS the code)
#   NETSYNC_MAIL_APP_PASSWORD  16-character Google App Password
app.config['MAIL_SERVER'] = os.environ.get('NETSYNC_MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('NETSYNC_MAIL_PORT', '587'))
app.config['MAIL_USERNAME'] = os.environ.get('NETSYNC_MAIL_USER', '')
app.config['MAIL_PASSWORD'] = os.environ.get('NETSYNC_MAIL_APP_PASSWORD', '')

RESET_CODE_TTL_MINUTES = 10      # how long a code stays valid
RESET_CODE_MAX_ATTEMPTS = 5      # wrong guesses before the code is thrown away
RESET_RESEND_COOLDOWN_SECONDS = 60

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# --- ROLE CONSTANTS ---
ROLE_ADMIN = 'admin'
ROLE_PROJECT_MANAGER = 'project_manager'
ROLE_TEAM_LEADER = 'team_leader'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default=ROLE_TEAM_LEADER)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    middle_name = db.Column(db.String(100), nullable=True)
    suffix = db.Column(db.String(20), nullable=True)           # optional: Jr., Sr., III ...
    contact_number = db.Column(db.String(30), nullable=True)
    is_archived = db.Column(db.Boolean, default=False)
    profile_photo = db.Column(db.String(200), nullable=True)   # file name inside static/uploads (profile picture)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False, server_default='false')  # admin-set password: user must choose their own at first login

    def photo_url(self):
        """Web address of the profile picture, or None when the user has not uploaded one."""
        if not self.profile_photo:
            return None
        return url_for('static', filename='uploads/' + self.profile_photo)

    def display_name(self):
        """'Last Suffix, First M.'  e.g. 'Cruz Jr., Juan M.'  (suffix always sits right after the last name)."""
        if self.first_name and self.last_name:
            mi = f" {self.middle_name.strip()[0]}." if self.middle_name and self.middle_name.strip() else ""
            sfx = f" {self.suffix.strip()}" if self.suffix and self.suffix.strip() else ""
            return f"{self.last_name}{sfx}, {self.first_name}{mi}"
        return self.username

    def full_name(self):
        """'First Middle Last Suffix'  e.g. 'Juan Michael Cruz Jr.'  (suffix always sits right after the last name)."""
        parts = [self.first_name, self.middle_name, self.last_name, self.suffix]
        return ' '.join(p.strip() for p in parts if p and p.strip()) or self.username

    def can_manage_users(self):
        return self.role == ROLE_ADMIN

    def can_manage_projects(self):
        return self.role in [ROLE_ADMIN, ROLE_PROJECT_MANAGER]

    def can_mark_complete(self):
        return self.role in [ROLE_ADMIN, ROLE_PROJECT_MANAGER]

    def can_change_password(self):
        return self.role in [ROLE_ADMIN, ROLE_PROJECT_MANAGER, ROLE_TEAM_LEADER]

    def can_set_progress(self):
        return self.role in [ROLE_ADMIN, ROLE_PROJECT_MANAGER]

    def can_archive_project(self):
        return self.role in [ROLE_ADMIN, ROLE_PROJECT_MANAGER]

    def can_edit_inventory(self):
        return self.role in [ROLE_ADMIN, ROLE_PROJECT_MANAGER]

    def can_delete_project(self):
        """Permanently deleting an archived project is Admin-only."""
        return self.role == ROLE_ADMIN


class ProjectAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='New')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    photo_filename = db.Column(db.String(200), nullable=True)
    floor_area = db.Column(db.String(100), nullable=True)
    survey_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    progress = db.Column(db.Integer, default=0)
    target_start_date = db.Column(db.Date, nullable=True)
    target_completion_date = db.Column(db.Date, nullable=True)
    actual_start_date = db.Column(db.Date, nullable=True)
    actual_completion_date = db.Column(db.Date, nullable=True)
    is_archived = db.Column(db.Boolean, default=False)
    survey_required = db.Column(db.Boolean, default=True)
    is_awarded = db.Column(db.Boolean, default=False)
    project_code = db.Column(db.String(20), unique=True, nullable=True)   # e.g. PRJ-2026-0001
    acceptance_photo = db.Column(db.String(200), nullable=True)   # camera photo of the signed acceptance letter
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    archived_by = db.relationship('User', foreign_keys=[archived_by_id])
    materials = db.relationship('Material', backref='project', lazy=True, cascade="all, delete-orphan")
    logs = db.relationship('TaskLog', backref='project', lazy=True, cascade="all, delete-orphan")
    assignments = db.relationship('ProjectAssignment', backref='project', lazy=True, cascade="all, delete-orphan")
    survey_photos = db.relationship('SurveyPhoto', backref='project', lazy=True, cascade="all, delete-orphan")
    work_sessions = db.relationship('WorkSession', backref='project', lazy=True, cascade="all, delete-orphan")

    # --- Workflow gating ---------------------------------------------------
    @property
    def survey_completed(self):
        """True when no survey is needed, or every required survey field is filled in."""
        if not self.survey_required:
            return True
        return bool(
            self.floor_area and self.survey_note
            and self.target_start_date and self.target_completion_date
            and self.survey_photos
        )

    @property
    def work_locked(self):
        """Costing and Logs stay closed until a required survey is completed."""
        return not self.survey_completed

    MIN_LOGS_PER_LEADER = 2

    @property
    def leader_log_status(self):
        """[(user, logs_posted)] for every active team leader assigned to this project."""
        ids = [a.user_id for a in self.assignments]
        leaders = [u for u in User.query.filter(User.id.in_(ids)).all()
                   if u.role == ROLE_TEAM_LEADER and not u.is_archived] if ids else []
        leaders.sort(key=lambda u: (u.display_name() or '').lower())
        return [(u, sum(1 for l in self.logs if l.posted_by_id == u.id)) for u in leaders]

    @property
    def logs_requirement_met(self):
        """Every assigned team leader has posted at least 2 logs (no leader assigned: 2 logs in total)."""
        status = self.leader_log_status
        if not status:
            return len(self.logs) >= self.MIN_LOGS_PER_LEADER
        return all(n >= self.MIN_LOGS_PER_LEADER for _, n in status)

    @property
    def can_be_completed(self):
        """'Mark as Completed' opens only after the survey is done AND every team leader posted at least 2 logs."""
        return self.survey_completed and self.logs_requirement_met

    @property
    def completion_block_message(self):
        """Why the project cannot be completed yet ('' when it can)."""
        if not self.survey_completed:
            return SURVEY_LOCK_MSG
        if self.logs_requirement_met:
            return ''
        n = self.MIN_LOGS_PER_LEADER
        status = self.leader_log_status
        if not status:
            return 'Complete the logs first.'
        short = [f'{u.display_name()} ({c}/{n})' for u, c in status if c < n]
        return 'Complete the logs first.'



class SurveyPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(300), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    quantity_estimated = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False, default='unit')
    unit_price = db.Column(db.Float, nullable=False)
    actual_quantity_used = db.Column(db.Float, nullable=True)


class TaskLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    posted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    posted_by = db.relationship('User', foreign_keys=[posted_by_id])
    description = db.Column(db.Text, nullable=False)
    materials_used = db.Column(db.String(500), nullable=True)
    log_photo = db.Column(db.String(200), nullable=True)
    photo_source = db.Column(db.String(10), nullable=True)   # 'camera' or 'upload' (older logs: empty)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkSession(db.Model):
    """One START WORK -> END WORK shift of a Team Leader on a project.

    Kept separate from TaskLog (the Progress Reports). Both photos are camera-only and are stamped
    with the server clock; start_at / end_at are the same instants that are burned into the photos.
    A Team Leader can have only ONE open session (end_at IS NULL) per project at a time, but any
    number of finished ones, so history is never overwritten.
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    user = db.relationship('User', foreign_keys=[user_id])
    start_at = db.Column(db.DateTime, nullable=False)
    start_photo = db.Column(db.String(200), nullable=False)
    end_at = db.Column(db.DateTime, nullable=True)
    end_photo = db.Column(db.String(200), nullable=True)

    # database-level guard against a duplicate START (e.g. a double click or two devices at once)
    __table_args__ = (
        Index('ux_work_session_one_open', 'project_id', 'user_id', unique=True,
              postgresql_where=text('end_at IS NULL'), sqlite_where=text('end_at IS NULL')),
    )

    @property
    def is_open(self):
        return self.end_at is None

    @property
    def duration_seconds(self):
        if not self.end_at:
            return None
        return max(0, int((self.end_at - self.start_at).total_seconds()))

    @property
    def duration_label(self):
        secs = self.duration_seconds
        if secs is None:
            return None
        h, rem = divmod(secs, 3600)
        m = rem // 60
        return f'{h}h {m:02d}m' if h else f'{m} min'

    @property
    def code(self):
        return f'WS-{self.id:05d}'


class Notification(db.Model):
    """In-app notification (e.g. 'a Team Leader posted a log') shown under the bell icon."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)   # who receives it
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=True)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class PasswordResetCode(db.Model):
    """One-time 6-digit code emailed to the admin during 'Forgot password'. Only a hash is stored."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)


class GlobalInventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False, default='General')
    description = db.Column(db.String(300), nullable=True)
    unit_price = db.Column(db.Float, nullable=False)
    unit_label = db.Column(db.String(50), nullable=False, default='unit')
    stock_quantity = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('item_name', 'category', name='_item_category_uc'),)


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    # An archived account is never treated as signed in, even if its session cookie is still valid.
    if user is None or user.is_archived:
        return None
    return user


@app.before_request
def sign_out_archived_users():
    """If an admin archives someone who is already signed in, end their session on their very next request."""
    if request.endpoint in (None, 'static'):
        return None
    uid = session.get('_user_id')
    if not uid:
        return None
    try:
        user = User.query.get(int(uid))
    except (TypeError, ValueError):
        user = None
    if user is not None and user.is_archived:
        logout_user()
        session.pop('_user_id', None)
        if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Your account has been archived. Please contact an administrator.'}), 401
        flash('Your account has been archived. Please contact an administrator.', 'error')
        return redirect(url_for('login'))
    return None


# Pages a flagged user may still reach while they are being forced to choose a new password.
_FORCED_PW_ALLOWED = ('force_password_change', 'logout', 'static')


@app.before_request
def require_password_change():
    """Admin-set passwords are temporary: until the user picks their own, every page sends them to the change screen."""
    if request.endpoint is None or request.endpoint in _FORCED_PW_ALLOWED:
        return None
    if not current_user.is_authenticated or not getattr(current_user, 'must_change_password', False):
        return None
    if current_user.role == ROLE_ADMIN:          # the admin signs in on its own page and sets its own password
        return None
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Please set a new password first.', 'redirect': url_for('force_password_change')}), 403
    return redirect(url_for('force_password_change'))


# --- IMAGE WATERMARK ---
def _load_font(size):
    """Try to load a TrueType font; fall back to PIL's default."""
    candidates = [
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def watermark_photo(file_storage, save_path):
    """Open an uploaded photo, burn the server date/time into the bottom-right,
    and save as JPEG. Returns True on success, False if the image couldn't be read."""
    try:
        img = Image.open(file_storage.stream)
    except Exception:
        return False

    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Cap dimensions to avoid huge uploads
    max_dim = 1920
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)

    draw = ImageDraw.Draw(img)
    now = datetime.now()
    line1 = now.strftime('%B %d, %Y')
    line2 = now.strftime('%I:%M %p')
    line3 = "NetSync • Verified"

    font_big = _load_font(28)
    font_small = _load_font(20)

    b1 = draw.textbbox((0, 0), line1, font=font_big)
    b2 = draw.textbbox((0, 0), line2, font=font_big)
    b3 = draw.textbbox((0, 0), line3, font=font_small)

    w = max(b1[2] - b1[0], b2[2] - b2[0], b3[2] - b3[0])
    h1 = b1[3] - b1[1]
    h2 = b2[3] - b2[1]
    h3 = b3[3] - b3[1]

    padding = 14
    box_w = w + padding * 2 + 12
    box_h = h1 + h2 + h3 + padding * 2 + 14

    img_w, img_h = img.size
    x0 = img_w - box_w - 24
    y0 = img_h - box_h - 24
    x1 = x0 + box_w
    y1 = y0 + box_h

    # Solid dark rounded rectangle
    draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=(12, 12, 18))
    # Accent stripe
    draw.rectangle([x0, y0, x0 + 5, y1], fill=(123, 44, 191))

    tx = x0 + padding + 8
    ty = y0 + padding
    draw.text((tx, ty), line1, font=font_big, fill=(255, 255, 255))
    ty += h1 + 6
    draw.text((tx, ty), line2, font=font_big, fill=(179, 102, 255))
    ty += h2 + 4
    draw.text((tx, ty), line3, font=font_small, fill=(180, 180, 190))

    img.save(save_path, 'JPEG', quality=88, optimize=True)
    return True


def _load_bold_font(size):
    """Bold TrueType font for the work-session stamp (falls back to the regular loader)."""
    candidates = [
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    return _load_font(size)


def prepare_photo(img, max_dim=1920):
    """Apply the phone's rotation, convert to RGB and cap the size."""
    from PIL import ImageOps
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert('RGB')
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)
    return img


def stamp_work_photo(img, action, now, project, user, ref):
    """Burn the NetSync verification stamp onto a photo and return the RGB image.

    The stamp is a small, compact card in the bottom-left corner: a coloured badge
    (START WORK / END WORK / PROGRESS REPORT ...), the exact time with seconds and the date on
    the left, and project / Team Leader / brand on the right.

    Everything scales with the photo's SHORTER side, so the card takes the same small share of
    the picture whether the photo is portrait or landscape (it used to scale with the width,
    which made it cover over a third of a landscape photo).
    """
    img = prepare_photo(img)

    W, H = img.size
    u = max(min(W, H), 480) / 1000.0              # scale unit: 1.0 when the short side is 1000px

    def S(v):
        return max(1, int(round(v * u)))

    f_badge = _load_bold_font(S(12))
    f_time = _load_bold_font(S(34))
    f_date = _load_font(S(14))
    f_meta = _load_font(S(14))
    f_brand = _load_bold_font(S(12))

    accent, badge_text = {'start': ((61, 220, 132), 'Start Work'),
                          'end': ((255, 130, 90), 'End Work'),
                          'progress': ((90, 160, 255), 'PROGRESS REPORT'),
                          'acceptance': ((242, 177, 52), 'ACCEPTANCE LETTER')}[action]
    time_text = now.strftime('%I:%M:%S %p').lstrip('0')
    date_text = now.strftime('%a, %b %d, %Y').replace(' 0', ' ')
    proj_text = project.site_name + (f'  \u2022  {project.project_code}' if project.project_code else '')
    meta_text = user.display_name() if user else 'Team Leader'
    brand = 'NetSync  \u2022  Verified'

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    margin, pad, gap = S(14), S(13), S(22)
    bar = S(4)

    def tb(text_, font_):
        b = d.textbbox((0, 0), text_, font=font_)
        return b[0], b[1], b[2] - b[0], b[3] - b[1]

    # ---- left block: badge, time, date ----
    _, bby, bw, bh = tb(badge_text, f_badge)
    badge_w, badge_h = bw + S(16), bh + S(9)
    _, tby, tw_, th_ = tb('0123456789:APM', f_time)          # fixed height so every time lines up
    time_w = d.textlength(time_text, font=f_time)
    _, dby, dw_, dh_ = tb(date_text, f_date)
    left_w = max(badge_w, time_w, dw_)
    row_gap = S(7)
    left_h = badge_h + row_gap + th_ + row_gap + dh_

    # ---- right block: project, team leader, brand ----
    avail_total = W - 2 * margin
    right_max = max(avail_total - (pad * 2 + bar + left_w + gap), S(140))
    def fit(text_, font_):
        while d.textlength(text_, font=font_) > right_max and len(text_) > 6:
            text_ = text_[:-2].rstrip() + '\u2026'
        return text_
    proj_text, meta_text = fit(proj_text, f_meta), fit(meta_text, f_meta)
    right_w = max(d.textlength(proj_text, font=f_meta), d.textlength(meta_text, font=f_meta),
                  d.textlength(brand, font=f_brand))

    card_w = min(avail_total, int(pad * 2 + bar + left_w + gap + right_w))
    card_h = left_h + pad * 2
    x0, y1 = margin, H - margin
    x1, y0 = x0 + card_w, y1 - card_h

    d.rounded_rectangle([x0, y0, x1, y1], radius=S(12), fill=(8, 11, 16, 205))
    d.rounded_rectangle([x0, y0, x0 + bar + S(6), y1], radius=S(5), fill=accent + (255,))
    d.rectangle([x0 + bar, y0, x0 + bar + S(8), y1], fill=(8, 11, 16, 205))   # square off the bar's inner edge

    lx = x0 + bar + pad
    ty = y0 + pad
    d.rounded_rectangle([lx, ty, lx + badge_w, ty + badge_h], radius=S(6), fill=accent + (255,))
    d.text((lx + S(8), ty + (badge_h - bh) // 2 - bby), badge_text, font=f_badge, fill=(8, 11, 16))
    ty += badge_h + row_gap
    d.text((lx, ty - tby), time_text, font=f_time, fill=(255, 255, 255))
    ty += th_ + row_gap
    d.text((lx, ty - dby), date_text, font=f_date, fill=(205, 214, 224))

    # thin divider between the two blocks
    sx = lx + left_w + gap // 2
    d.line([(sx, y0 + pad), (sx, y1 - pad)], fill=(255, 255, 255, 46), width=max(1, S(1)))

    # right block, right aligned
    rx = x1 - pad
    ry = y0 + pad
    for text_, font_, fill_ in ((proj_text, f_meta, (255, 255, 255)),
                                (meta_text, f_meta, (170, 182, 196))):
        w_ = d.textlength(text_, font=font_)
        d.text((rx - w_, ry), text_, font=font_, fill=fill_)
        ry += S(21)
    bw2 = d.textlength(brand, font=f_brand)
    d.text((rx - bw2, y1 - pad - S(12) - S(2)), brand, font=f_brand, fill=accent)

    return Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')


def save_stamped_photo(file_storage, action, now, project, user, ref, save_path):
    """Read a photo taken with the phone's own camera app, stamp it and save as JPEG.
    Returns True on success."""
    try:
        img = Image.open(file_storage.stream)
        img.load()
        if min(img.size) < 240:
            return False
        stamp_work_photo(img, action, now, project, user, ref).save(save_path, 'JPEG', quality=88, optimize=True)
        return True
    except Exception:
        return False


def save_plain_photo(file_storage, save_path):
    """Save an uploaded photo as JPEG with NO date/time stamp."""
    try:
        img = Image.open(file_storage.stream)
        img.load()
        prepare_photo(img).save(save_path, 'JPEG', quality=88, optimize=True)
        return True
    except Exception:
        return False


# --- HELPERS ---
def get_accessible_projects(include_archived=False):
    if current_user.can_manage_projects():
        query = Project.query
        if not include_archived:
            query = query.filter_by(is_archived=False)
        return query.all()
    assigned_ids = [a.project_id for a in ProjectAssignment.query.filter_by(user_id=current_user.id).all()]
    query = Project.query.filter(Project.id.in_(assigned_ids))
    if not include_archived:
        query = query.filter_by(is_archived=False)
    return query.all()


def user_can_access_project(project):
    if current_user.can_manage_projects():
        return True
    return ProjectAssignment.query.filter_by(project_id=project.id, user_id=current_user.id).first() is not None


def update_project_progress(project):
    progress_map = {
        'New': 0,
        'Surveyed': 25,
        'Started': 50,
        'In Progress': 75,
        'Completed': 100
    }
    project.progress = progress_map.get(project.status, 0)


def parse_floor_area(raw):
    if not raw:
        return ('', 'sqm')
    parts = raw.split()
    if len(parts) >= 2:
        try:
            float(parts[0])
            return (parts[0], parts[1])
        except ValueError:
            pass
    return (raw, 'sqm')


SURVEY_LOCK_MSG = 'Complete the survey first. Costing, Logs and Mark as Completed are locked until then.'
NO_LOGS_MSG = 'Each team leader needs at least 2 implementation logs before this project can be marked as completed.'


def survey_gate(project):
    """Return a redirect response if the project's survey must be done first, else None."""
    if project.work_locked:
        flash(SURVEY_LOCK_MSG, 'error')
        return redirect(url_for('survey_project', project_id=project.id))
    return None


LOW_STOCK_THRESHOLD = 5     # an inventory item at or below this quantity counts as "low stock"


def notify_managers(message, link, project=None, actor=None):
    """Add a bell notification for every active Admin / Project Manager (except the person who triggered it)."""
    managers = User.query.filter(User.is_archived == False,
                                 User.role.in_([ROLE_ADMIN, ROLE_PROJECT_MANAGER])).all()
    for m in managers:
        if actor and m.id == actor.id:
            continue
        db.session.add(Notification(user_id=m.id, project_id=project.id if project else None,
                                    message=message[:300], link=link))


def project_label(project):
    return project.site_name + (f' ({project.project_code})' if project.project_code else '')


def notify_managers_of_log(project, log, poster):
    """Tell every active Admin / Project Manager (except the poster) that a new log was uploaded."""
    who = poster.display_name() if poster else 'Someone'
    notify_managers(f'{who} posted a new log on {project_label(project)}',
                    url_for('implement', project_id=project.id, tab='progress'), project, poster)


def survey_filled(project):
    """True when every survey field (area, notes, both target dates, at least one photo) is filled in."""
    return bool(project.floor_area and project.survey_note and project.target_start_date
                and project.target_completion_date and project.survey_photos)


def notify_survey_completed(project, actor):
    who = actor.display_name() if actor else 'Someone'
    notify_managers(f'{who} completed the survey for {project_label(project)}',
                    url_for('survey_project', project_id=project.id), project, actor)


def notify_project_completed(project, actor):
    who = actor.display_name() if actor else 'Someone'
    link = url_for('project_detail', project_id=project.id)
    notify_managers(f'{who} marked {project_label(project)} as completed', link, project, actor)
    notify_assigned_team_leaders(project, f'{project_label(project)} was marked as completed', link, actor)


def notify_low_stock(item, previous_qty, actor=None):
    """Notify once when an item's stock drops to the low-stock level (not on every change below it)."""
    now_qty = item.stock_quantity or 0
    if previous_qty is None or previous_qty <= LOW_STOCK_THRESHOLD or now_qty > LOW_STOCK_THRESHOLD:
        return
    if now_qty <= 0:
        msg = f'Out of stock: {item.item_name}'
    else:
        msg = f'Low stock: {item.item_name} is down to {now_qty:g} {item.unit_label or "unit"}'
    notify_managers(msg, url_for('inventory'), None, actor)


def notify_assigned_team_leaders(project, message, link, actor=None):
    """Tell the Team Leaders assigned to a project (Admin / PM get their own notifications)."""
    ids = [a.user_id for a in ProjectAssignment.query.filter_by(project_id=project.id).all()]
    if not ids:
        return
    leaders = User.query.filter(User.id.in_(ids), User.is_archived == False,
                                User.role == ROLE_TEAM_LEADER).all()
    for u in leaders:
        if actor and u.id == actor.id:
            continue
        db.session.add(Notification(user_id=u.id, project_id=project.id, message=message[:300], link=link))


def set_project_assignments(project, assigned_ids, actor=None):
    """Replace a project's assignments and notify the people who were newly assigned."""
    old_ids = {a.user_id for a in ProjectAssignment.query.filter_by(project_id=project.id).all()}
    new_ids = {int(uid) for uid in assigned_ids}
    ProjectAssignment.query.filter_by(project_id=project.id).delete()
    for uid in new_ids:
        db.session.add(ProjectAssignment(project_id=project.id, user_id=uid))
    link = url_for('project_detail', project_id=project.id)
    for uid in new_ids - old_ids:
        if actor and uid == actor.id:
            continue
        u = db.session.get(User, uid)
        if u and not u.is_archived:
            db.session.add(Notification(user_id=uid, project_id=project.id, link=link,
                                        message=f'You were assigned to {project_label(project)}'[:300]))


def valid_email(value):
    """Basic shape check: something@something.tld, no spaces, at most 100 characters (the column size)."""
    return bool(value) and len(value) <= 100 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value) is not None


# --- Name rules + username suggestions -------------------------------------------
# Names: letters and single spaces only (no numbers, no symbols). Accented letters (Ñ, é ...) are fine.
NAME_RE = re.compile(r"[^\W\d_]+(?: [^\W\d_]+)*")
SUFFIX_RE = re.compile(r"[A-Za-z]+\.?")          # Jr., Sr., II, III, IV ...


def clean_name(value):
    """Trim and collapse repeated spaces."""
    return re.sub(r'\s+', ' ', (value or '').strip())


def name_error(label, value, required=False):
    """Return an error message for a bad name part, or None when it is fine."""
    if not value:
        return f'{label} is required.' if required else None
    if len(value) > 100:
        return f'{label} can be at most 100 characters.'
    if not NAME_RE.fullmatch(value):
        return f'{label} can only contain letters and spaces. No numbers or symbols.'
    return None


def clean_suffix(value):
    """Return (suffix, error). Suffix is optional: Jr., Sr., II, III ..."""
    v = (value or '').strip()
    if not v:
        return None, None
    if len(v) > 20 or not SUFFIX_RE.fullmatch(v):
        return None, 'Suffix can only contain letters and an optional period (e.g. Jr., Sr., III).'
    return v, None


def _ascii_slug(value):
    """'Dela Cruz' -> 'delacruz', 'Peña' -> 'pena' (lowercase letters only)."""
    folded = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z]', '', folded.lower())


def suggest_usernames(first, middle='', last='', suffix='', exclude_id=None, limit=4):
    """Professional, name-based username ideas that are not taken yet.

    Order: first.last, flast, first.m.last, fmlast, last.first (+ first.last.jr when a suffix is given).
    If every idea is already taken, a number is appended to the first one so the admin still gets options.
    """
    f_tokens = [t for t in clean_name(first).split(' ') if t]
    f = _ascii_slug(f_tokens[0]) if f_tokens else ''
    f_all = _ascii_slug(first)
    l = _ascii_slug(last)
    m = _ascii_slug(middle)[:1]
    sfx = _ascii_slug(suffix)
    if not f or not l:
        return []

    ideas = [f'{f}.{l}', f'{f[0]}{l}']
    if m:
        ideas += [f'{f}.{m}.{l}', f'{f[0]}{m}{l}']
    ideas.append(f'{l}.{f}')
    if f_all and f_all != f:
        ideas.append(f'{f_all}.{l}')
    if sfx:
        ideas.insert(1, f'{f}.{l}.{sfx}')      # keeps Juan Cruz Jr. apart from Juan Cruz Sr.

    seen = set()
    ideas = [i[:50] for i in ideas if not (i in seen or seen.add(i))]

    def taken(name):
        q = User.query.filter(db.func.lower(User.username) == name.lower())
        if exclude_id:
            q = q.filter(User.id != exclude_id)
        return q.first() is not None

    out = [i for i in ideas if not taken(i)]
    if not out:                                  # everything is taken: fall back to numbered versions
        n = 2
        while len(out) < 2 and n < 100:
            cand = f'{ideas[0][:46]}{n}'
            if not taken(cand):
                out.append(cand)
            n += 1
    return out[:limit]


_COMMON_PASSWORDS = {'password', 'password1', 'password123', '12345678', '123456789', '1234567890',
                     'qwerty123', 'qwertyuiop', 'iloveyou1', 'admin123', 'welcome1', 'letmein123'}


def password_problem(pw):
    """Return why a password is too weak, or None if it is acceptable (same rule as the Users form meter)."""
    if not pw or len(pw) < 8:
        return 'Password must be at least 8 characters.'
    if pw.lower() in _COMMON_PASSWORDS:
        return 'That password is too common. Choose a different one.'
    kinds = sum(bool(re.search(r, pw)) for r in (r'[a-z]', r'[A-Z]', r'\d', r'[^A-Za-z0-9]'))
    if kinds < 2:
        return 'Mix at least two kinds of characters (letters, numbers, or symbols).'
    return None


def parse_non_negative(value):
    """Return float(value) when it is a finite number >= 0, otherwise None (rejects negatives, NaN and inf)."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and n >= 0 else None


def assign_project_code(project):
    """Give a project its permanent, unique ID (PRJ-<year>-<id>). Call after the row has an id."""
    if not project.project_code and project.id:
        year = (project.created_at or datetime.utcnow()).year
        project.project_code = f"PRJ-{year}-{project.id:04d}"


def find_duplicate_project(site_name, location, exclude_id=None):
    """Same site name at the same location (case-insensitive) counts as a duplicate project."""
    q = Project.query.filter(
        db.func.lower(Project.site_name) == site_name.strip().lower(),
        db.func.lower(Project.location) == location.strip().lower(),
    )
    if exclude_id:
        q = q.filter(Project.id != exclude_id)
    return q.first()


def ensure_schema():
    """Add the new project columns to an existing PostgreSQL database and back-fill project IDs.

    Safe to run on every start-up (everything is IF NOT EXISTS / only fills empty values).
    """
    try:
        with app.app_context():
            Notification.__table__.create(db.engine, checkfirst=True)   # new table for the bell notifications
            WorkSession.__table__.create(db.engine, checkfirst=True)    # Work Session history (START / END WORK)
            PasswordResetCode.__table__.create(db.engine, checkfirst=True)  # admin forgot-password codes
            if db.engine.dialect.name != 'postgresql':
                return
            stmts = [
                "ALTER TABLE project ADD COLUMN IF NOT EXISTS project_code VARCHAR(20)",
                "ALTER TABLE project ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP",
                "ALTER TABLE task_log ADD COLUMN IF NOT EXISTS photo_source VARCHAR(10)",
                "ALTER TABLE project ADD COLUMN IF NOT EXISTS acceptance_photo VARCHAR(200)",
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_work_session_one_open ON work_session (project_id, user_id) WHERE end_at IS NULL",
                "ALTER TABLE project ADD COLUMN IF NOT EXISTS archived_by_id INTEGER REFERENCES \"user\"(id)",
                "UPDATE project SET project_code = 'PRJ-' || to_char(COALESCE(created_at, now()), 'YYYY') || '-' || lpad(id::text, 4, '0') WHERE project_code IS NULL",
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_project_code ON project (project_code)",
                "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS profile_photo VARCHAR(200)",
                "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS suffix VARCHAR(20)",
                "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE",
            ]
            for stmt in stmts:
                db.session.execute(text(stmt))
            db.session.commit()
    except Exception as exc:  # database not reachable yet, or tables not created yet
        db.session.rollback()
        print(f'[NetSync] ensure_schema skipped: {exc}')


# --- DECORATORS ---
def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_manage_projects():
            flash('Access denied: insufficient permissions.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def user_manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_manage_users():
            flash('Access denied: insufficient permissions.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def inventory_editor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_edit_inventory():
            flash('Access denied: only Admin and Project Manager can modify inventory.', 'error')
            return redirect(url_for('inventory'))
        return f(*args, **kwargs)
    return decorated


# --- ROUTES ---
@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=(request.form.get('username') or '').strip()).first()
        if user and not user.is_archived and check_password_hash(user.password_hash, request.form.get('password') or ''):
            # The admin account is not allowed to sign in here. It must use the Admin log in page.
            # (Only shown after the password is correct, so this does not reveal which usernames are admins.)
            if user.role == ROLE_ADMIN:
                flash('Administrator accounts cannot sign in here. Please use the Admin log in page.', 'error')
                return render_template('login.html')
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- ADMIN LOGIN + FORGOT PASSWORD (email -> 6-digit code -> new password) ---
def mask_email(email):
    """admin@gmail.com -> a****@gmail.com"""
    local, _, domain = (email or '').partition('@')
    return f"{local[:1]}{'*' * max(len(local) - 1, 3)}@{domain}"


def mail_is_configured():
    return bool(app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD'])


def send_reset_code_email(to_email, code):
    """Email the 6-digit code. Returns True when sent (or, with no mail settings, printed to the server console for dev)."""
    if not mail_is_configured():
        print(f'[NetSync] Mail not configured - admin reset code for {to_email}: {code}')
        return False
    msg = EmailMessage()
    msg['Subject'] = 'NetSync admin password reset code'
    msg['From'] = app.config['MAIL_USERNAME']
    msg['To'] = to_email
    msg.set_content(
        f'Your NetSync admin password reset code is: {code}\n\n'
        f'It expires in {RESET_CODE_TTL_MINUTES} minutes. If you did not request this, ignore this email '
        f'and your password will stay the same.')
    msg.add_alternative(
        f'<div style="font-family:Arial,sans-serif;max-width:420px">'
        f'<h2 style="margin:0 0 8px">NetSync password reset</h2>'
        f'<p>Use this code to reset the admin password:</p>'
        f'<p style="font-size:32px;font-weight:700;letter-spacing:8px;margin:12px 0">{code}</p>'
        f'<p style="color:#555">It expires in {RESET_CODE_TTL_MINUTES} minutes. If you did not request this, '
        f'ignore this email and your password will stay the same.</p></div>', subtype='html')
    with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'], timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        smtp.send_message(msg)
    return True


def issue_reset_code(user):
    """Create a fresh code (voiding older ones), email it. Returns (ok, emailed)."""
    PasswordResetCode.query.filter_by(user_id=user.id, used=False).update({'used': True})
    code = f'{secrets.randbelow(10**6):06d}'
    row = PasswordResetCode(user_id=user.id, code_hash=generate_password_hash(code),
                            expires_at=datetime.utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES))
    db.session.add(row)
    db.session.commit()
    try:
        emailed = send_reset_code_email(user.email, code)
    except Exception as exc:
        print(f'[NetSync] Could not send reset email: {exc}')
        row.used = True
        db.session.commit()
        return False, False
    return True, emailed


def _reset_state(stage):
    """Return (user, state) if the session is at the given stage of the reset flow and not expired."""
    state = session.get('admin_reset')
    if not state or state.get('stage') != stage or state.get('exp', 0) < datetime.utcnow().timestamp():
        session.pop('admin_reset', None)
        return None, None
    user = db.session.get(User, state.get('uid'))
    if not user or user.role != ROLE_ADMIN or user.is_archived:
        session.pop('admin_reset', None)
        return None, None
    return user, state


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        user = User.query.filter_by(username=username).first()
        if (user and user.role == ROLE_ADMIN and not user.is_archived
                and check_password_hash(user.password_hash, request.form.get('password') or '')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid admin username or password.', 'error')
    return render_template('admin_login.html')


@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not valid_email(email):
            flash('Enter a valid email address.', 'error')
            return render_template('admin_forgot_password.html', email=email)
        admin = User.query.filter(db.func.lower(User.email) == email,
                                  User.role == ROLE_ADMIN, User.is_archived.is_(False)).first()
        if not admin:
            flash('That email address does not match the admin account.', 'error')
            return render_template('admin_forgot_password.html', email=email)
        ok, emailed = issue_reset_code(admin)
        if not ok:
            flash('We could not send the verification email. Please try again later or check the mail settings.', 'error')
            return render_template('admin_forgot_password.html', email=email)
        session['admin_reset'] = {'uid': admin.id, 'stage': 'code',
                                  'exp': (datetime.utcnow() + timedelta(minutes=30)).timestamp()}
        flash(f'We sent a 6-digit code to {mask_email(admin.email)}.' if emailed else
              'Email sending is not set up on this server yet. The code was printed in the server console.',
              'success' if emailed else 'error')
        return redirect(url_for('admin_verify_code'))
    return render_template('admin_forgot_password.html', email='')


@app.route('/admin/verify-code', methods=['GET', 'POST'])
def admin_verify_code():
    user, state = _reset_state('code')
    if not user:
        flash('Your reset session expired. Please start again.', 'error')
        return redirect(url_for('admin_forgot_password'))
    latest = (PasswordResetCode.query.filter_by(user_id=user.id, used=False)
              .order_by(PasswordResetCode.created_at.desc()).first())
    cooldown = 0
    if latest:
        cooldown = max(0, RESET_RESEND_COOLDOWN_SECONDS - int((datetime.utcnow() - latest.created_at).total_seconds()))
    if request.method == 'POST':
        entered = re.sub(r'\D', '', request.form.get('code') or '')
        if not latest or latest.expires_at < datetime.utcnow():
            flash('That code has expired. Request a new one.', 'error')
        elif latest.attempts >= RESET_CODE_MAX_ATTEMPTS:
            latest.used = True
            db.session.commit()
            flash('Too many wrong attempts. Request a new code.', 'error')
        elif len(entered) == 6 and check_password_hash(latest.code_hash, entered):
            latest.used = True
            db.session.commit()
            session['admin_reset'] = {'uid': user.id, 'stage': 'reset',
                                      'exp': (datetime.utcnow() + timedelta(minutes=15)).timestamp()}
            return redirect(url_for('admin_reset_password'))
        else:
            latest.attempts += 1
            left = RESET_CODE_MAX_ATTEMPTS - latest.attempts
            if left <= 0:
                latest.used = True
            db.session.commit()
            flash('Incorrect code.' + (f' {left} attempt(s) left.' if left > 0 else ' Request a new code.'), 'error')
    return render_template('admin_verify_code.html', masked=mask_email(user.email), cooldown=cooldown,
                           ttl=RESET_CODE_TTL_MINUTES)


@app.route('/admin/resend-code', methods=['POST'])
def admin_resend_code():
    user, state = _reset_state('code')
    if not user:
        flash('Your reset session expired. Please start again.', 'error')
        return redirect(url_for('admin_forgot_password'))
    latest = (PasswordResetCode.query.filter_by(user_id=user.id)
              .order_by(PasswordResetCode.created_at.desc()).first())
    if latest and (datetime.utcnow() - latest.created_at).total_seconds() < RESET_RESEND_COOLDOWN_SECONDS:
        flash('Please wait a moment before requesting another code.', 'error')
        return redirect(url_for('admin_verify_code'))
    ok, emailed = issue_reset_code(user)
    if not ok:
        flash('We could not send the verification email. Please try again later.', 'error')
    elif emailed:
        flash(f'A new code was sent to {mask_email(user.email)}.', 'success')
    else:
        flash('Email sending is not set up on this server yet. The code was printed in the server console.', 'error')
    return redirect(url_for('admin_verify_code'))


@app.route('/admin/reset-password', methods=['GET', 'POST'])
def admin_reset_password():
    user, state = _reset_state('reset')
    if not user:
        flash('Your reset session expired. Please start again.', 'error')
        return redirect(url_for('admin_forgot_password'))
    if request.method == 'POST':
        new_pw = request.form.get('new_password') or ''
        confirm_pw = request.form.get('confirm_password') or ''
        if len(new_pw) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif new_pw != confirm_pw:
            flash('Passwords do not match.', 'error')
        else:
            user.password_hash = generate_password_hash(new_pw)
            PasswordResetCode.query.filter_by(user_id=user.id, used=False).update({'used': True})
            db.session.commit()
            session.pop('admin_reset', None)
            flash('Password reset. Sign in with your new password.', 'success')
            return redirect(url_for('admin_login'))
    return render_template('admin_reset_password.html')


@app.route('/dashboard')
@login_required
def dashboard():
    projects = get_accessible_projects()
    archived_projects = get_accessible_projects(include_archived=True)
    archived_projects = [p for p in archived_projects if p.is_archived]
    now = datetime.utcnow()
    all_users = {u.id: u for u in User.query.filter_by(is_archived=False).all()}

    for p in projects:
        p.recent_activity = any(log.created_at > now - timedelta(hours=24) for log in p.logs)
        p.team_leader = None
        for a in p.assignments:
            u = all_users.get(a.user_id)
            if u and u.role == ROLE_TEAM_LEADER:
                p.team_leader = u
                break
        if not p.team_leader:
            creator = all_users.get(p.user_id)
            if creator and creator.role == ROLE_TEAM_LEADER:
                p.team_leader = creator

    for p in archived_projects:
        p.team_leader = None
        for a in p.assignments:
            u = all_users.get(a.user_id)
            if u and u.role == ROLE_TEAM_LEADER:
                p.team_leader = u
                break
        if not p.team_leader:
            creator = all_users.get(p.user_id)
            if creator and creator.role == ROLE_TEAM_LEADER:
                p.team_leader = creator

    status_counts = {
        'New': 0, 'Started': 0, 'Surveyed': 0,
        'In Progress': 0, 'Completed': 0, 'Total': len(projects)
    }
    for p in projects:
        if p.status in status_counts:
            status_counts[p.status] += 1

    return render_template('dashboard.html', projects=projects, status_counts=status_counts,
                           archived_projects=archived_projects, all_users=all_users)


@app.route('/project/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    all_users = {u.id: u for u in User.query.filter_by(is_archived=False).all()}

    team_leader = None
    for a in project.assignments:
        u = all_users.get(a.user_id)
        if u and u.role == ROLE_TEAM_LEADER:
            team_leader = u
            break
    if not team_leader:
        creator = all_users.get(project.user_id)
        if creator and creator.role == ROLE_TEAM_LEADER:
            team_leader = creator

    return render_template('project_detail.html', project=project, all_users=all_users, team_leader=team_leader)


@app.route('/create-project', methods=['GET', 'POST'])
@login_required
@manager_required
def create_project():
    if request.method == 'POST':
        site_name = request.form.get('site_name', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        survey_required = request.form.get('survey_required') == 'true'
        if not site_name or not location or not description:
            flash('Site Name, Location, and Project Description are required.', 'error')
            return redirect(url_for('create_project'))
        if location not in PH_LOCATION_VALUES:
            flash('Please choose a location from the list.', 'error')
            return redirect(url_for('create_project'))
        dup = find_duplicate_project(site_name, location)
        if dup:
            flash(f'This project already exists ({dup.project_code or "ID " + str(dup.id)}: {dup.site_name}, {dup.location}).', 'error')
            return redirect(url_for('create_project'))
        new_project = Project(
            site_name=site_name,
            location=location,
            description=description,
            status='New',
            user_id=current_user.id,
            survey_required=survey_required
        )
        update_project_progress(new_project)
        db.session.add(new_project)
        db.session.flush()                      # gets new_project.id
        assign_project_code(new_project)
        db.session.commit()
        set_project_assignments(new_project, request.form.getlist('assigned_users'), current_user)
        db.session.commit()
        flash(f'Project "{new_project.site_name}" ({new_project.project_code}) was created successfully.', 'success')
        return redirect(url_for('project_detail', project_id=new_project.id))
    all_users = User.query.filter_by(is_archived=False).all()
    return render_template('create.html', all_users=all_users, ph_locations=PH_LOCATIONS)


@app.route('/edit-project/<int:project_id>', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.status == 'Completed':
        flash('Completed projects cannot be edited.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    if request.method == 'POST':
        new_location = (request.form.get('location') or '').strip()
        # Allow the project's existing (older, free-text) location to stay as-is.
        if new_location not in PH_LOCATION_VALUES and new_location != project.location:
            flash('Please choose a location from the list.', 'error')
            return redirect(url_for('edit_project', project_id=project_id))
        new_site = (request.form.get('site_name') or '').strip()
        dup = find_duplicate_project(new_site, new_location, exclude_id=project.id)
        if dup:
            flash(f'Another project with the same site name and location already exists ({dup.project_code or "ID " + str(dup.id)}).', 'error')
            return redirect(url_for('edit_project', project_id=project_id))
        project.site_name = new_site
        project.location = new_location
        project.description = request.form.get('description')
        set_project_assignments(project, request.form.getlist('assigned_users'), current_user)
        db.session.commit()
        flash('Project updated successfully.', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    all_users = User.query.filter_by(is_archived=False).all()
    current_assignments = [a.user_id for a in ProjectAssignment.query.filter_by(project_id=project_id).all()]
    return render_template('edit.html', project=project, all_users=all_users,
                           current_assignments=current_assignments, ph_locations=PH_LOCATIONS,
                           legacy_location=(project.location if project.location not in PH_LOCATION_VALUES else None))


@app.route('/survey/<int:project_id>', methods=['GET', 'POST'])
@login_required
def survey_project(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    if request.method == 'POST':
        if project.status == 'Completed':
            flash('Cannot modify a completed project.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))

        files = request.files.getlist('site_photos')
        captions = request.form.getlist('photo_caption')
        notes_list = request.form.getlist('photo_notes')
        survey_was_filled = survey_filled(project)      # to notify only when the survey becomes complete
        floor_area_value = request.form.get('floor_area_value', '').strip()
        floor_area_unit = request.form.get('floor_area_unit', 'sqm').strip()
        survey_note = request.form.get('survey_note', '').strip()
        target_start = request.form.get('target_start_date', '').strip()
        target_completion = request.form.get('target_completion_date', '').strip()

        if not target_start:
            flash('Target Start Date is required.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))
        if not target_completion:
            flash('Target Completion Date is required.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))

        try:
            ts = datetime.strptime(target_start, '%Y-%m-%d').date()
            tc = datetime.strptime(target_completion, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))

        if tc <= ts:
            flash('Target Completion must be after the Target Start date.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))

        try:
            fa_num = float(floor_area_value)
            if fa_num <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash('Floor Area must be a positive number.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))

        if floor_area_unit not in ('sqm', 'm'):
            floor_area_unit = 'sqm'

        if not survey_note:
            flash('Survey Notes are required.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))

        has_new_photo = any(file and file.filename != '' for file in files)
        if not project.survey_photos and not has_new_photo:
            flash('At least one site photo is required.', 'error')
            return redirect(url_for('survey_project', project_id=project_id))

        for idx, file in enumerate(files):
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                caption = captions[idx] if idx < len(captions) else ''
                notes_val = notes_list[idx] if idx < len(notes_list) else ''
                sp = SurveyPhoto(project_id=project_id, filename=filename, caption=caption, notes=notes_val)
                db.session.add(sp)
                if not project.photo_filename:
                    project.photo_filename = filename

        project.floor_area = f"{fa_num:g} {floor_area_unit}"
        project.survey_note = survey_note
        project.target_start_date = ts
        project.target_completion_date = tc
        if project.status in ['New', 'Started', 'Surveyed']:
            project.status = 'Surveyed'
            update_project_progress(project)
        db.session.commit()
        if not survey_was_filled and survey_filled(project):
            notify_survey_completed(project, current_user)
            db.session.commit()
        flash('Survey updated successfully.', 'success')
        return redirect(url_for('survey_project', project_id=project_id))

    floor_value, floor_unit = parse_floor_area(project.floor_area)
    return render_template('survey.html', project=project,
                           floor_value=floor_value, floor_unit=floor_unit)


@app.route('/delete-survey-photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_survey_photo(photo_id):
    photo = SurveyPhoto.query.get_or_404(photo_id)
    project = Project.query.get_or_404(photo.project_id)
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo.filename))
    except:
        pass
    db.session.delete(photo)
    db.session.commit()
    flash('Photo deleted.', 'success')
    return redirect(url_for('survey_project', project_id=photo.project_id))


@app.route('/evaluate/<int:project_id>', methods=['GET', 'POST'])
@login_required
def evaluate(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    blocked = survey_gate(project)
    if blocked:
        return blocked
    if request.method == 'POST':
        if project.status == 'Completed':
            flash('Cannot add materials to a completed project.', 'error')
            return redirect(url_for('evaluate', project_id=project_id))
        item = request.form.get('item_name', '').strip()
        qty_str = request.form.get('quantity', '0')
        unit = request.form.get('unit') or 'unit'
        if not item:
            flash('Please select an item.', 'error')
            return redirect(url_for('evaluate', project_id=project_id))
        try:
            qty = float(qty_str)
        except ValueError:
            flash('Invalid quantity.', 'error')
            return redirect(url_for('evaluate', project_id=project_id))
        if qty <= 0:
            flash('Quantity must be greater than 0.', 'error')
            return redirect(url_for('evaluate', project_id=project_id))
        if qty != int(qty):
            flash('Quantity must be a whole number.', 'error')
            return redirect(url_for('evaluate', project_id=project_id))
        qty = int(qty)

        # The unit price ALWAYS comes from the inventory catalogue. Any price sent by the
        # browser is ignored, so a Team Leader cannot change it (even by editing the page).
        inventory_item = GlobalInventoryItem.query.filter_by(item_name=item).first()
        if not inventory_item:
            flash('Please select an item from the inventory.', 'error')
            return redirect(url_for('evaluate', project_id=project_id))
        price = inventory_item.unit_price
        if inventory_item.stock_quantity < qty:
            flash(f'Insufficient stock. Available: {int(inventory_item.stock_quantity)}.', 'error')
            return redirect(url_for('evaluate', project_id=project_id))

        # If this item is already in the project's costing, add to that line instead of making a new one.
        same_lines = (Material.query
                      .filter(Material.project_id == project_id,
                              db.func.lower(Material.item_name) == inventory_item.item_name.lower())
                      .order_by(Material.id).all())
        existing = same_lines[0] if same_lines else None
        if existing:
            # Fold any older duplicate lines of the same item into the first one.
            for extra in same_lines[1:]:
                existing.quantity_estimated += extra.quantity_estimated
                if extra.actual_quantity_used is not None:
                    existing.actual_quantity_used = (existing.actual_quantity_used or 0) + extra.actual_quantity_used
                db.session.delete(extra)
            existing.quantity_estimated += qty
            result_msg = f'{item} is already in the costing, so {qty} unit was added to it.'
        else:
            db.session.add(Material(
                project_id=project_id, item_name=inventory_item.item_name,
                quantity_estimated=qty, unit=unit or inventory_item.unit_label,
                unit_price=price
            ))
            result_msg = 'Material added successfully.'
        if project.status in ['New', 'Surveyed']:
            project.status = 'Started'
            update_project_progress(project)

        stock_before = inventory_item.stock_quantity
        inventory_item.stock_quantity -= qty
        notify_low_stock(inventory_item, stock_before, current_user)
        db.session.commit()
        flash(result_msg, 'success')
        return redirect(url_for('evaluate', project_id=project_id))

    inventory_items = GlobalInventoryItem.query.order_by(GlobalInventoryItem.category, GlobalInventoryItem.item_name).all()
    return render_template('quotation.html', project=project, inventory_items=inventory_items)


@app.route('/delete-material/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    mat = Material.query.get_or_404(material_id)
    project_id = mat.project_id
    project = Project.query.get_or_404(project_id)
    if project.status == 'Completed':
        flash('Cannot modify materials of a completed project.', 'error')
        return redirect(url_for('evaluate', project_id=project_id))
    inventory_item = GlobalInventoryItem.query.filter_by(item_name=mat.item_name).first()
    if inventory_item:
        inventory_item.stock_quantity += mat.quantity_estimated
    db.session.delete(mat)
    db.session.commit()
    flash('Material removed.', 'success')
    return redirect(url_for('evaluate', project_id=project_id))


@app.route('/implement/<int:project_id>')
@login_required
def implement(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    blocked = survey_gate(project)
    if blocked:
        return blocked

    is_tl = current_user.role == ROLE_TEAM_LEADER
    can_run = current_user.role in (ROLE_TEAM_LEADER, ROLE_PROJECT_MANAGER, ROLE_ADMIN)   # everyone can start / end work
    sessions_q = WorkSession.query.filter_by(project_id=project.id)
    if is_tl:                                   # Team Leaders only see their own sessions; PM / Admin see all history
        sessions_q = sessions_q.filter_by(user_id=current_user.id)
    sessions = sessions_q.order_by(WorkSession.start_at.desc()).all()
    open_session = None
    if can_run:                                 # the signed-in user's own running session
        open_session = next((x for x in sessions if x.is_open and x.user_id == current_user.id), None)

    tab = request.args.get('tab', 'work')
    if tab not in ('work', 'progress'):
        tab = 'work'
    elapsed_seconds = 0
    if open_session:
        elapsed_seconds = max(0, int((datetime.now() - open_session.start_at).total_seconds()))
    return render_template('implement.html', project=project, sessions=sessions,
                           open_session=open_session, can_run_session=can_run, active_tab=tab,
                           elapsed_seconds=elapsed_seconds)


@app.route('/work-session/<int:project_id>/<action>', methods=['POST'])
@login_required
def work_session_action(project_id, action):
    """START WORK / END WORK. Camera-only (photo arrives as a live capture), server-stamped."""
    project = Project.query.get_or_404(project_id)
    back = redirect(url_for('implement', project_id=project_id, tab='work'))
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    if action not in ('start', 'end'):
        return "Not found", 404
    if current_user.role not in (ROLE_TEAM_LEADER, ROLE_PROJECT_MANAGER, ROLE_ADMIN):
        flash('You do not have permission to start or end a work session.', 'error')
        return back
    blocked = survey_gate(project)
    if blocked:
        return blocked

    now = datetime.now()                         # one instant: used for the stamp AND the record
    photo = request.files.get('photo')
    stamp = now.strftime('%Y%m%d_%H%M%S')
    token = secrets.token_hex(3)

    if action == 'start':
        if project.status == 'Completed' or project.is_archived:
            flash('Cannot start work on a completed or archived project.', 'error')
            return back
        existing = WorkSession.query.filter_by(project_id=project_id, user_id=current_user.id, end_at=None).first()
        if existing:
            flash('You already started work. End your current work session before starting a new one.', 'error')
            return back
        filename = f'ws_p{project_id}_u{current_user.id}_{stamp}_start_{token}.jpg'
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        ref = f'NS-{project.project_code or project_id}-{now.strftime("%m%d%H%M")}'
        if not (photo and save_stamped_photo(photo, 'start', now, project, current_user, ref, save_path)):
            flash('Take a photo with your phone camera to start work.', 'error')
            return back
        session_row = WorkSession(project_id=project_id, user_id=current_user.id,
                                  start_at=now, start_photo=filename)
        db.session.add(session_row)
        try:
            db.session.flush()
        except IntegrityError:                  # a parallel request won the race
            db.session.rollback()
            _remove_upload(filename)
            flash('You already started work. End your current work session before starting a new one.', 'error')
            return back
        notify_managers(f'{current_user.display_name()} started work on {project_label(project)}',
                        url_for('implement', project_id=project.id, tab='work'), project, current_user)
        db.session.commit()
        flash('Work started. Your Start Work photo was stamped with the current date and time.', 'success')
        return back

    # ---- END WORK ----
    row = (WorkSession.query.filter_by(project_id=project_id, user_id=current_user.id)
           .order_by(WorkSession.start_at.desc()).with_for_update().first())
    if not row:
        flash('Start work first. End Work unlocks after Start Work is completed.', 'error')
        return back
    if row.end_at is not None:
        flash('This work session has already ended. Start a new work session to continue.', 'error')
        return back
    filename = f'ws_p{project_id}_u{current_user.id}_{stamp}_end_{token}.jpg'
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    ref = row.code
    if not (photo and save_stamped_photo(photo, 'end', now, project, current_user, ref, save_path)):
        db.session.rollback()
        flash('Take a photo with your phone camera to end work.', 'error')
        return back
    row.end_at = now
    row.end_photo = filename
    notify_managers(f'{current_user.display_name()} ended work on {project_label(project)} ({row.duration_label})',
                    url_for('implement', project_id=project.id, tab='work'), project, current_user)
    db.session.commit()
    flash(f'Work ended. Session length: {row.duration_label}.', 'success')
    return back


def _remove_upload(filename):
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    except OSError:
        pass


@app.route('/add-log/<int:project_id>', methods=['POST'])
@login_required
def add_log(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    blocked = survey_gate(project)
    if blocked:
        return blocked
    back = redirect(url_for('implement', project_id=project_id, tab='progress'))
    if project.status == 'Completed':
        flash('Cannot add logs to a completed project.', 'error')
        return back

    desc = request.form.get('description')
    materials_used = request.form.get('materials_used')
    photo_source = 'upload' if request.form.get('photo_source') == 'upload' else 'camera'
    file = request.files.get('log_photo')

    if not file or file.filename == '':
        flash('A progress photo is required for each progress report.', 'error')
        return back

    # Build a unique JPEG filename and save the watermarked image
    base, _ = os.path.splitext(secure_filename(file.filename))
    if not base:
        base = 'log'
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{base}_{stamp}.jpg"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if photo_source == 'camera':
        now = datetime.now()
        ref = f'NS-{project.project_code or project_id}-{now.strftime("%m%d%H%M")}'
        ok = save_stamped_photo(file, 'progress', now, project, current_user, ref, save_path)
    else:                                   # uploaded from the gallery: saved as-is, no date/time stamp
        ok = save_plain_photo(file, save_path)
    if not ok:
        flash('Could not process the uploaded photo. Please try again with a valid image.', 'error')
        return back

    new_log = TaskLog(
        project_id=project_id,
        description=desc,
        materials_used=materials_used,
        log_photo=filename,
        photo_source=photo_source,
        posted_by_id=current_user.id
    )
    if project.status not in ['Completed', 'In Progress']:
        project.status = 'In Progress'
        update_project_progress(project)
    db.session.add(new_log)
    db.session.flush()

    if not project.actual_start_date:
        project.actual_start_date = new_log.created_at.date()

    notify_managers_of_log(project, new_log, current_user)

    db.session.commit()
    flash('Progress report added successfully.', 'success')
    return back


@app.route('/complete-project/<int:project_id>', methods=['POST'])
@login_required
def complete_project(project_id):
    if not current_user.can_mark_complete():
        flash('Access denied.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    project = Project.query.get_or_404(project_id)
    if project.status == 'Completed':
        project.status = 'In Progress'
        project.actual_completion_date = None
        update_project_progress(project)
        notify_assigned_team_leaders(project, f'{project_label(project)} was reopened',
                                     url_for('project_detail', project_id=project.id), current_user)
        db.session.commit()
        flash('Project reopened.', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    else:
        if not project.can_be_completed:
            flash(project.completion_block_message, 'error')
            return redirect(url_for('project_detail', project_id=project_id))
        return redirect(url_for('closeout_project', project_id=project_id))


@app.route('/closeout/<int:project_id>', methods=['GET', 'POST'])
@login_required
def closeout_project(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project) or not current_user.can_mark_complete():
        flash('Access denied.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    if project.status == 'Completed':
        flash('Project is already completed.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    if not project.can_be_completed:
        flash(project.completion_block_message, 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    if request.method == 'POST':
        letter = request.files.get('acceptance_photo')
        if not letter or letter.filename == '':
            flash('Take a photo of the signed Acceptance Letter with your camera to complete the project.', 'error')
            return redirect(url_for('closeout_project', project_id=project_id))
        now = datetime.now()
        letter_name = f'acceptance_p{project_id}_{now.strftime("%Y%m%d_%H%M%S")}_{secrets.token_hex(3)}.jpg'
        if not save_stamped_photo(letter, 'acceptance', now, project, current_user, '',
                                  os.path.join(app.config['UPLOAD_FOLDER'], letter_name)):
            flash('Could not read the acceptance letter photo. Please take it again.', 'error')
            return redirect(url_for('closeout_project', project_id=project_id))
        project.acceptance_photo = letter_name

        for mat in project.materials:
            actual_str = request.form.get(f'actual_{mat.id}', '').strip()
            if actual_str:
                actual = parse_non_negative(actual_str)
                if actual is None:
                    flash(f'Actual quantity for {mat.item_name} must be a number that is not negative.', 'error')
                    return redirect(url_for('closeout_project', project_id=project_id))
            else:
                actual = mat.quantity_estimated
            actual = max(0, min(actual, mat.quantity_estimated))
            mat.actual_quantity_used = actual
            leftover = mat.quantity_estimated - actual
            if leftover > 0:
                inv_item = GlobalInventoryItem.query.filter_by(item_name=mat.item_name).first()
                if inv_item:
                    inv_item.stock_quantity += leftover

        project.status = 'Completed'
        project.actual_completion_date = date.today()
        update_project_progress(project)
        notify_project_completed(project, current_user)
        db.session.commit()
        flash('Project completed successfully. Leftover materials returned to inventory.', 'success')
        return redirect(url_for('project_detail', project_id=project_id))

    return render_template('closeout.html', project=project)


@app.route('/archive-project/<int:project_id>', methods=['POST'])
@login_required
def archive_project(project_id):
    if not current_user.can_archive_project():
        flash('Access denied.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    project = Project.query.get_or_404(project_id)
    project.is_archived = not project.is_archived
    who = current_user.display_name()
    if project.is_archived:
        project.archived_at = datetime.now()
        project.archived_by_id = current_user.id
        notify_managers(f'{who} archived {project_label(project)}',
                        url_for('project_detail', project_id=project.id), project, current_user)
        notify_assigned_team_leaders(project, f'{project_label(project)} was archived',
                                     url_for('dashboard'), current_user)
        flash('Project archived.', 'success')
    else:
        project.archived_at = None
        project.archived_by_id = None
        link = url_for('project_detail', project_id=project.id)
        notify_managers(f'{who} restored {project_label(project)} from the archive', link, project, current_user)
        notify_assigned_team_leaders(project, f'{project_label(project)} was restored from the archive',
                                     link, current_user)
        flash('Project unarchived.', 'success')
    db.session.commit()
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/delete-project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    if not current_user.can_delete_project():
        flash('Access denied: only the Admin can permanently delete a project.', 'error')
        return redirect(url_for('dashboard'))
    project = Project.query.get_or_404(project_id)
    if not project.is_archived:
        flash('Only archived projects can be deleted.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    try:
        Notification.query.filter_by(project_id=project.id).delete()
        db.session.delete(project)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.error('Could not delete project %s: %s', project_id, exc)
        flash('Could not delete the project. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    flash('Project permanently deleted.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update-progress/<int:project_id>', methods=['POST'])
@login_required
def update_progress(project_id):
    if not current_user.can_set_progress():
        return jsonify({'error': 'Unauthorized'}), 403
    project = Project.query.get_or_404(project_id)
    if project.status == 'Completed':
        return jsonify({'error': 'Cannot update progress of a completed project.'}), 400
    progress = int(request.form.get('progress', 0))
    progress = max(0, min(100, progress))
    project.progress = progress
    db.session.commit()
    return jsonify({'success': True, 'progress': progress})


@app.route('/report/<int:project_id>')
@login_required
def report(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project):
        return "Unauthorized Access", 403
    total_cost = sum(m.quantity_estimated * m.unit_price for m in project.materials)
    return render_template('report.html', project=project,
                           total_cost=total_cost, now=datetime.utcnow())


# --- Signed-in user's own details (header profile popover) ---------------------
@app.route('/api/me')
@login_required
def api_me():
    u = current_user
    full_name = u.full_name()
    return jsonify({
        'full_name': full_name,
        'username': u.username,
        'role': (u.role or '').replace('_', ' ').title(),
        'email': u.email or '',
        'contact_number': u.contact_number or '',
        'photo_url': u.photo_url() or '',
    })


# --- Another user's public card (name, photo, role only) - any signed-in role may view -----
@app.route('/api/users/<int:user_id>/card')
@login_required
def api_user_card(user_id):
    u = User.query.get_or_404(user_id)
    if u.is_archived:
        return jsonify({'error': 'This account is no longer active.'}), 404
    full_name = u.full_name()
    return jsonify({
        'full_name': full_name,
        'role': (u.role or '').replace('_', ' ').title(),
        'photo_url': u.photo_url() or '',
    })


# --- NOTIFICATIONS (bell icon) -------------------------------------------------
@app.route('/api/notifications')
@login_required
def api_notifications():
    base = Notification.query.filter_by(user_id=current_user.id)
    unread = base.filter_by(is_read=False).count()
    items = base.order_by(Notification.created_at.desc()).limit(15).all()
    now = datetime.utcnow()
    return jsonify({
        'enabled': True,
        'unread': unread,
        'items': [{
            'id': n.id, 'message': n.message, 'link': n.link, 'is_read': n.is_read,
            'age_seconds': int((now - n.created_at).total_seconds()),
            'when': n.created_at.strftime('%b %d, %I:%M %p')
        } for n in items]
    })


@app.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def api_notification_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def api_notifications_read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/set-new-password', methods=['GET', 'POST'])
@login_required
def force_password_change():
    """First sign-in (or after an admin reset): the user replaces the temporary password the admin set."""
    if not current_user.must_change_password:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        new_pw = request.form.get('new_password') or ''
        confirm_pw = request.form.get('confirm_password') or ''
        problem = password_problem(new_pw)
        if problem:
            flash(problem, 'error')
        elif new_pw != confirm_pw:
            flash('Passwords do not match.', 'error')
        elif check_password_hash(current_user.password_hash, new_pw):
            flash('Your new password must be different from the temporary one.', 'error')
        else:
            current_user.password_hash = generate_password_hash(new_pw)
            current_user.must_change_password = False
            db.session.commit()
            flash('Password updated. Welcome to NetSync!', 'success')
            return redirect(url_for('dashboard'))
    return render_template('force_password.html')


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if not current_user.can_change_password():
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')
        if not check_password_hash(current_user.password_hash, current_pw):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('settings'))
        if new_pw != confirm_pw:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('settings'))
        if len(new_pw) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('settings'))
        current_user.password_hash = generate_password_hash(new_pw)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('settings'))
    return render_template('change_password.html')


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        session['theme_mode'] = request.form.get('theme_mode', 'dark')
        session['theme_color'] = request.form.get('theme_color', 'purple')
        flash('Settings saved.', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html',
                           theme_mode=session.get('theme_mode', 'dark'),
                           theme_color=session.get('theme_color', 'purple'))


# --- PROFILE (name, phone, email, photo) - every user edits ONLY their own ---
PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024      # 5 MB
PROFILE_PHOTO_SIZE = 480                       # saved as a 480 x 480 square


def save_profile_photo(file_storage, user):
    """Validate, square-crop and save an uploaded profile picture. Returns (filename, error)."""
    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size == 0:
        return None, 'The selected photo is empty.'
    if size > PROFILE_PHOTO_MAX_BYTES:
        return None, 'The photo is too large. Please choose one that is 5 MB or smaller.'
    try:
        img = Image.open(stream)
        if (img.format or '').upper() not in ('JPEG', 'PNG', 'WEBP', 'GIF'):
            return None, 'Please choose a JPG, PNG, WEBP or GIF image.'
        img.load()
        img = ImageOps.exif_transpose(img)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGBA')
            flat = Image.new('RGB', img.size, (255, 255, 255))
            flat.paste(img, mask=img.split()[-1])
            img = flat
        else:
            img = img.convert('RGB')
        img = ImageOps.fit(img, (PROFILE_PHOTO_SIZE, PROFILE_PHOTO_SIZE), Image.LANCZOS)
        filename = f"avatar_{user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.jpg"
        img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'JPEG', quality=88, optimize=True)
        return filename, None
    except Exception:
        return None, 'That file is not a valid image. Please choose a JPG, PNG, WEBP or GIF photo.'


@app.route('/settings/profile', methods=['POST'])
@login_required
def update_profile():
    user = current_user
    back = url_for('settings', _anchor='account')

    first = (request.form.get('first_name') or '').strip()
    middle = (request.form.get('middle_name') or '').strip()
    last = (request.form.get('last_name') or '').strip()
    phone = (request.form.get('contact_number') or '').strip()
    email = (request.form.get('email') or '').strip().lower()

    first, middle, last = clean_name(first), clean_name(middle), clean_name(last)
    for err in (name_error('First name', first, required=True),
                name_error('Middle name', middle),
                name_error('Last name', last, required=True)):
        if err:
            flash(err, 'error')
            return redirect(back)
    if phone and not re.fullmatch(r'[0-9+()\-\s]{7,30}', phone):
        flash('Enter a valid contact number (digits, spaces, + ( ) - only).', 'error')
        return redirect(back)
    if not valid_email(email):
        flash('Enter a valid email address.', 'error')
        return redirect(back)
    if User.query.filter(db.func.lower(User.email) == email, User.id != user.id).first():
        flash('That email address is already used by another account.', 'error')
        return redirect(back)

    new_photo = None
    old_photo = user.profile_photo
    file = request.files.get('profile_photo')
    if file and file.filename:
        new_photo, err = save_profile_photo(file, user)
        if err:
            flash(err, 'error')
            return redirect(back)

    user.first_name = first
    user.middle_name = middle or None
    user.last_name = last
    user.contact_number = phone or None
    user.email = email
    if new_photo:
        user.profile_photo = new_photo
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if new_photo:
            _remove_upload(new_photo)
        flash('That email address is already used by another account.', 'error')
        return redirect(back)
    if new_photo and old_photo:
        _remove_upload(old_photo)
    flash('Your profile was updated.', 'success')
    return redirect(back)


@app.route('/settings/profile/photo/remove', methods=['POST'])
@login_required
def remove_profile_photo():
    old_photo = current_user.profile_photo
    if old_photo:
        current_user.profile_photo = None
        db.session.commit()
        _remove_upload(old_photo)
        flash('Your profile photo was removed.', 'success')
    return redirect(url_for('settings', _anchor='account'))


@app.route('/api/theme')
@login_required
def api_theme():
    return jsonify({
        'mode': session.get('theme_mode', 'dark'),
        'color': session.get('theme_color', 'purple')
    })


# ─── GLOBAL INVENTORY ───────────────────────────────────────────────────────
@app.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        if not current_user.can_edit_inventory():
            flash('Access denied: only Admin and Project Manager can modify inventory.', 'error')
            return redirect(url_for('inventory'))
        item_name = request.form.get('item_name', '').strip()
        category = request.form.get('category', 'CAT6 Cable').strip()
        description = request.form.get('description', '').strip()
        unit_price_str = request.form.get('unit_price', '0')
        stock_str = request.form.get('stock_quantity', '0')
        if not item_name or not unit_price_str:
            flash('Item name and unit price are required.', 'error')
            return redirect(url_for('inventory'))
        unit_price = parse_non_negative(unit_price_str)
        stock_val = parse_non_negative(stock_str)
        if unit_price is None or stock_val is None:
            flash('Unit price and stock quantity must be valid numbers that are not negative.', 'error')
            return redirect(url_for('inventory'))
        stock = int(round(stock_val))
        if stock < 0:
            flash('Stock quantity cannot be negative.', 'error')
            return redirect(url_for('inventory'))
        if unit_price <= 0:
            flash('Unit price must be positive.', 'error')
            return redirect(url_for('inventory'))

        existing = GlobalInventoryItem.query.filter(
            db.func.lower(GlobalInventoryItem.item_name) == item_name.lower(),
            db.func.lower(GlobalInventoryItem.category) == category.lower()
        ).first()
        if existing:
            flash('An item with the same name and category already exists.', 'error')
            return redirect(url_for('inventory'))

        item = GlobalInventoryItem(
            item_name=item_name,
            category=category,
            description=description,
            unit_price=unit_price,
            unit_label='unit',
            stock_quantity=stock
        )
        db.session.add(item)
        db.session.commit()
        flash('Item added to catalogue.', 'success')
        return redirect(url_for('inventory'))

    accessible = get_accessible_projects()
    accessible_ids = [p.id for p in accessible]
    all_project_materials = Material.query.filter(Material.project_id.in_(accessible_ids)).all()
    items = GlobalInventoryItem.query.order_by(GlobalInventoryItem.category, GlobalInventoryItem.item_name).all()
    return render_template('inventory.html', items=items, project_materials=all_project_materials)


@app.route('/inventory/edit/<int:item_id>', methods=['POST'])
@login_required
@inventory_editor_required
def edit_inventory_item(item_id):
    item = GlobalInventoryItem.query.get_or_404(item_id)
    stock_before = item.stock_quantity
    item.item_name = request.form.get('item_name', item.item_name)
    item.category = request.form.get('category', item.category)
    item.description = request.form.get('description', item.description)
    new_price = parse_non_negative(request.form.get('unit_price', item.unit_price))
    if new_price is None or new_price <= 0:
        flash('Unit price must be a number greater than 0 (no negatives).', 'error')
        return redirect(url_for('inventory'))
    new_stock = parse_non_negative(request.form.get('stock_quantity', item.stock_quantity))
    if new_stock is None:
        flash('Stock quantity must be a number that is not negative.', 'error')
        return redirect(url_for('inventory'))
    item.unit_price = new_price
    item.unit_label = request.form.get('unit_label', item.unit_label)
    item.stock_quantity = int(round(new_stock))
    notify_low_stock(item, stock_before, current_user)
    db.session.commit()
    flash('Item updated.', 'success')
    return redirect(url_for('inventory'))


@app.route('/inventory/delete/<int:item_id>', methods=['POST'])
@login_required
@inventory_editor_required
def delete_inventory_item(item_id):
    item = GlobalInventoryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted.', 'success')
    return redirect(url_for('inventory'))


@app.route('/api/inventory')
@login_required
def api_inventory():
    items = GlobalInventoryItem.query.order_by(GlobalInventoryItem.category, GlobalInventoryItem.item_name).all()
    return jsonify([{
        'id': i.id, 'item_name': i.item_name, 'category': i.category,
        'description': i.description, 'unit_price': i.unit_price, 'unit_label': i.unit_label,
        'stock_quantity': i.stock_quantity
    } for i in items])


@app.route('/api/project-materials/<int:project_id>')
@login_required
def api_project_materials(project_id):
    project = Project.query.get_or_404(project_id)
    if not user_can_access_project(project):
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify({'materials': [{
        'id': m.id, 'item_name': m.item_name,
        'quantity_estimated': m.quantity_estimated,
        'unit': m.unit, 'unit_price': m.unit_price
    } for m in project.materials]})


@app.route('/api/update-material-quantities', methods=['POST'])
@login_required
def api_update_material_quantities():
    if not current_user.can_edit_inventory():
        return jsonify({'error': 'Unauthorized'}), 403
    payload = request.get_json() or {}
    updates = payload.get('updates', [])
    for upd in updates:                       # validate everything first so a bad row saves nothing
        if parse_non_negative(upd.get('quantity')) is None:
            return jsonify({'error': 'Quantities must be numbers that are not negative.'}), 400
    for upd in updates:
        mat = Material.query.get(int(upd['id']))
        if mat and user_can_access_project(mat.project):
            mat.quantity_estimated = parse_non_negative(upd['quantity'])
    db.session.commit()
    return jsonify({'success': True})


# ─── USER MANAGEMENT (Admin only) ──────────────────────────────────────────
@app.route('/adduser', methods=['GET', 'POST'])
@login_required
@user_manager_required
def add_users():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        if not valid_email(email):
            flash('Enter a valid email address for the new user.', 'error')
            return redirect(url_for('add_users'))
        if User.query.filter(db.func.lower(User.email) == email).first():
            flash('That email address is already used by another account.', 'error')
            return redirect(url_for('add_users'))
        password = request.form.get('password')
        role = request.form.get('role', ROLE_TEAM_LEADER)
        if role not in (ROLE_ADMIN, ROLE_PROJECT_MANAGER, ROLE_TEAM_LEADER):
            role = ROLE_TEAM_LEADER
        if role == ROLE_ADMIN:
            flash('There can only be one admin. A new admin cannot be created.', 'error')
            return redirect(url_for('add_users'))
        first = clean_name(request.form.get('first_name'))
        middle = clean_name(request.form.get('middle_name'))
        last = clean_name(request.form.get('last_name'))
        suffix, sfx_err = clean_suffix(request.form.get('suffix'))
        for err in (name_error('First name', first, required=True),
                    name_error('Middle name', middle),
                    name_error('Last name', last, required=True),
                    sfx_err):
            if err:
                flash(err, 'error')
                return redirect(url_for('add_users'))
        if not username:
            flash('Username is required.', 'error')
            return redirect(url_for('add_users'))
        if User.query.filter(db.func.lower(User.username) == username.lower()).first():
            flash('That username is already taken. Please choose a different one.', 'error')
            return redirect(url_for('add_users'))
        new_user = User(
            username=username, email=email,
            password_hash=generate_password_hash(password),
            role=role,
            first_name=first,
            last_name=last,
            middle_name=middle or None,
            suffix=suffix,
            contact_number=request.form.get('contact_number', ''),
            must_change_password=True
        )
        db.session.add(new_user)
        db.session.commit()
        flash('User created successfully. They will be asked to set their own password the first time they sign in.', 'success')
        return redirect(url_for('add_users'))

    active_users = User.query.filter_by(is_archived=False).all()
    archived_users = User.query.filter_by(is_archived=True).all()
    admin_exists = any(u.role == ROLE_ADMIN for u in active_users)
    return render_template('users.html', users=active_users, archived_users=archived_users,
                           admin_exists=admin_exists)


@app.route('/api/suggest-username')
@login_required
@user_manager_required
def api_suggest_username():
    """Professional username ideas built from the name typed in the Add User form."""
    role = request.args.get('role', ROLE_TEAM_LEADER)
    if role not in (ROLE_PROJECT_MANAGER, ROLE_TEAM_LEADER):
        return jsonify({'suggestions': []})
    suggestions = suggest_usernames(
        request.args.get('first_name', ''), request.args.get('middle_name', ''),
        request.args.get('last_name', ''), request.args.get('suffix', ''),
        exclude_id=request.args.get('exclude', type=int))
    return jsonify({'suggestions': suggestions})


@app.route('/api/check-username')
@login_required
@user_manager_required
def api_check_username():
    """Live duplicate check used by the Add/Edit User forms (case-insensitive, archived accounts count)."""
    name = (request.args.get('username') or '').strip()
    exclude = request.args.get('exclude', type=int)
    q = User.query.filter(db.func.lower(User.username) == name.lower())
    if exclude:
        q = q.filter(User.id != exclude)
    match = q.first() if name else None
    return jsonify({'available': match is None, 'archived': bool(match and match.is_archived)})


@app.route('/edit-user/<int:user_id>', methods=['POST'])
@login_required
@user_manager_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', user.role)
    if new_role not in (ROLE_ADMIN, ROLE_PROJECT_MANAGER, ROLE_TEAM_LEADER):
        new_role = user.role
    if user.role == ROLE_ADMIN and new_role != ROLE_ADMIN:
        flash("The admin role can't be changed. There can only be one admin.", 'error')
        return redirect(url_for('add_users'))
    if new_role == ROLE_ADMIN and user.role != ROLE_ADMIN:
        flash('There can only be one admin. You cannot promote another user to admin.', 'error')
        return redirect(url_for('add_users'))
    first = clean_name(request.form.get('first_name', user.first_name))
    last = clean_name(request.form.get('last_name', user.last_name))
    middle = clean_name(request.form.get('middle_name', user.middle_name))
    suffix, sfx_err = clean_suffix(request.form.get('suffix'))
    for err in (name_error('First name', first), name_error('Middle name', middle),
                name_error('Last name', last), sfx_err):
        if err:
            flash(err, 'error')
            return redirect(url_for('add_users'))
    user.first_name = first
    user.last_name = last
    user.middle_name = middle or None
    user.suffix = suffix
    user.contact_number = request.form.get('contact_number', user.contact_number)
    new_username = (request.form.get('username') or user.username).strip()
    if new_username.lower() != (user.username or '').lower():
        if User.query.filter(db.func.lower(User.username) == new_username.lower(), User.id != user.id).first():
            flash('That username is already taken. Please choose a different one.', 'error')
            return redirect(url_for('add_users'))
    user.username = new_username
    new_email = (request.form.get('email') or '').strip().lower()
    if new_email and new_email != (user.email or '').lower():
        if not valid_email(new_email):
            flash('Enter a valid email address.', 'error')
            return redirect(url_for('add_users'))
        if User.query.filter(db.func.lower(User.email) == new_email, User.id != user.id).first():
            flash('That email address is already used by another account.', 'error')
            return redirect(url_for('add_users'))
        user.email = new_email
    user.role = new_role
    new_pass = request.form.get('password')
    if new_pass:
        user.password_hash = generate_password_hash(new_pass)
        if user.id != current_user.id and user.role != ROLE_ADMIN:
            user.must_change_password = True      # the admin knows this password, so the user must replace it
    db.session.commit()
    flash('User updated.', 'success')
    return redirect(url_for('add_users'))


@app.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@user_manager_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Cannot delete your own account.", 'error')
        return redirect(url_for('add_users'))
    if user.role == ROLE_ADMIN:
        flash('The admin account cannot be archived.', 'error')
        return redirect(url_for('add_users'))
    user.is_archived = True
    db.session.commit()
    flash('User archived.', 'success')
    return redirect(url_for('add_users'))


@app.route('/restore-user/<int:user_id>', methods=['POST'])
@login_required
@user_manager_required
def restore_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_archived = False
    db.session.commit()
    flash('User restored.', 'success')
    return redirect(url_for('add_users'))


@app.route('/assign-project/<int:project_id>', methods=['POST'])
@login_required
@manager_required
def assign_project(project_id):
    project = Project.query.get_or_404(project_id)
    set_project_assignments(project, request.form.getlist('assigned_users'), current_user)
    db.session.commit()
    flash('Project assignments updated.', 'success')
    return redirect(url_for('project_detail', project_id=project_id))


ensure_schema()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)