import os
import csv
import io
import uuid
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify, Response, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "helpdesk-secret-key-production-ready"

# Upload Configuration
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "txt", "doc", "docx", "xls", "xlsx", "csv", "zip", "log"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max limit

# Ensure uploads directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def init_db():
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'User',
            status TEXT NOT NULL DEFAULT 'Active',
            department TEXT DEFAULT 'General',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Ticket Categories Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#4f46e5',
            icon TEXT DEFAULT 'fa-ticket',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Ticket Priorities & SLA Policy Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_priorities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            level INTEGER UNIQUE NOT NULL,
            color TEXT NOT NULL,
            sla_response_hours INTEGER DEFAULT 24,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tickets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            attachment TEXT,
            attachment_name TEXT,
            status TEXT NOT NULL DEFAULT 'Open',
            assigned_to TEXT,
            resolved_at TIMESTAMP,
            closed_at TIMESTAMP,
            is_escalated INTEGER DEFAULT 0,
            escalation_level TEXT DEFAULT 'None',
            escalation_reason TEXT,
            escalated_by TEXT,
            escalated_at TIMESTAMP,
            escalation_target TEXT,
            escalation_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Ticket Replies / Discussion Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'User',
            message TEXT NOT NULL,
            is_internal INTEGER NOT NULL DEFAULT 0,
            attachment TEXT,
            attachment_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets (id) ON DELETE CASCADE
        )
    """)

    # Ticket Activities / Audit Trail Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets (id) ON DELETE CASCADE
        )
    """)

    # Notifications Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ticket_id INTEGER,
            sender TEXT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            link TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Non-destructive migrations for existing databases
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column[1] for column in cursor.fetchall()]

    if "role" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'User'")
    if "status" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")
    if "department" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN department TEXT DEFAULT 'General'")
    if "created_at" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    cursor.execute("PRAGMA table_info(tickets)")
    ticket_columns = [column[1] for column in cursor.fetchall()]

    if "attachment" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN attachment TEXT")
    if "attachment_name" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN attachment_name TEXT")
    if "updated_at" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    if "assigned_to" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN assigned_to TEXT")
    if "resolved_at" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN resolved_at TIMESTAMP")
    if "closed_at" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN closed_at TIMESTAMP")
    if "is_escalated" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN is_escalated INTEGER DEFAULT 0")
    if "escalation_level" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN escalation_level TEXT DEFAULT 'None'")
    if "escalation_reason" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN escalation_reason TEXT")
    if "escalated_by" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN escalated_by TEXT")
    if "escalated_at" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN escalated_at TIMESTAMP")
    if "escalation_target" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN escalation_target TEXT")
    if "escalation_notes" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN escalation_notes TEXT")

    cursor.execute("PRAGMA table_info(ticket_replies)")
    reply_columns = [column[1] for column in cursor.fetchall()]

    if "is_internal" not in reply_columns:
        cursor.execute("ALTER TABLE ticket_replies ADD COLUMN is_internal INTEGER NOT NULL DEFAULT 0")
    if "attachment" not in reply_columns:
        cursor.execute("ALTER TABLE ticket_replies ADD COLUMN attachment TEXT")
    if "attachment_name" not in reply_columns:
        cursor.execute("ALTER TABLE ticket_replies ADD COLUMN attachment_name TEXT")

    # Seed Default Categories if table is empty
    cursor.execute("SELECT COUNT(*) FROM ticket_categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ("Technical Issue", "System errors, stack crashes, and runtime defects", "#3b82f6", "fa-laptop-code"),
            ("Software Problem", "Application bugs, software glitches, and installer failures", "#8b5cf6", "fa-box-open"),
            ("Hardware Problem", "Physical device failures, peripherals, and server machinery", "#64748b", "fa-desktop"),
            ("Network & Connectivity", "VPN tunnels, Wi-Fi drops, routing latency, and DNS issues", "#06b6d4", "fa-wifi"),
            ("Account & Access", "Credentials, password resets, role permissions, and MFA tokens", "#f59e0b", "fa-key"),
            ("Billing & Subscription", "Invoices, payment gateway errors, and license renewals", "#10b981", "fa-credit-card"),
            ("Security & Compliance", "Vulnerability reports, phishing threats, and compliance audit", "#ef4444", "fa-shield-halved"),
            ("Feature Request", "Product suggestions, capability improvements, and user feedback", "#6366f1", "fa-lightbulb"),
            ("General Inquiry", "General IT support questions, documentation, and office assistance", "#6b7280", "fa-circle-question")
        ]
        cursor.executemany("""
            INSERT INTO ticket_categories (name, description, color, icon, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, default_categories)

    # Seed Default Priority Tiers & SLA Targets if table is empty
    cursor.execute("SELECT COUNT(*) FROM ticket_priorities")
    if cursor.fetchone()[0] == 0:
        default_priorities = [
            ("Critical", 1, "#dc2626", 2, "Emergency outage, production stop, or severe zero-day issue. SLA: 2 Hours."),
            ("High", 2, "#ea580c", 8, "Major workflow impaired, high business impact. SLA: 8 Hours."),
            ("Medium", 3, "#d97706", 24, "Standard issue with working workaround or standard request. SLA: 24 Hours."),
            ("Low", 4, "#16a34a", 72, "Cosmetic question, minor enhancement, or non-urgent request. SLA: 72 Hours.")
        ]
        cursor.executemany("""
            INSERT INTO ticket_priorities (name, level, color, sla_response_hours, description, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, default_priorities)

    connection.commit()
    connection.close()


def get_active_categories():
    """Returns list of active ticket categories ordered by name."""
    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("SELECT id, name, description, color, icon, is_active FROM ticket_categories WHERE is_active = 1 ORDER BY name ASC")
        cats = cursor.fetchall()
        connection.close()
        return cats
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return []


def get_active_priorities():
    """Returns list of active priority tiers ordered by hierarchy level."""
    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("SELECT id, name, level, color, sla_response_hours, description, is_active FROM ticket_priorities WHERE is_active = 1 ORDER BY level ASC")
        prios = cursor.fetchall()
        connection.close()
        return prios
    except Exception as e:
        print(f"Error fetching priorities: {e}")
        return []


# ==============================================================================
# Helper Functions: Notifications & Activity Logging
# ==============================================================================

def create_notification(recipient, sender, title, message, link, ticket_id=None):
    """Inserts an in-app notification for a given user."""
    if not recipient or recipient == sender:
        return
    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO notifications (username, ticket_id, sender, title, message, link, is_read)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (recipient, ticket_id, sender, title, message, link))
        connection.commit()
        connection.close()
    except Exception as e:
        print(f"Error creating notification: {e}")


def notify_all_staff(sender, title, message, link, ticket_id=None):
    """Sends notification to all active Support and Admin staff members."""
    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("SELECT username FROM users WHERE role IN ('Admin', 'Support')")
        staff_members = cursor.fetchall()
        for member in staff_members:
            if member[0] != sender:
                cursor.execute("""
                    INSERT INTO notifications (username, ticket_id, sender, title, message, link, is_read)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (member[0], ticket_id, sender, title, message, link))
        connection.commit()
        connection.close()
    except Exception as e:
        print(f"Error notifying staff: {e}")


def log_ticket_activity(ticket_id, username, activity_type, old_value=None, new_value=None, message=None):
    """Records an entry in the ticket audit trail."""
    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO ticket_activities (ticket_id, username, activity_type, old_value, new_value, message)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, username, activity_type, old_value, new_value, message))
        connection.commit()
        connection.close()
    except Exception as e:
        print(f"Error logging activity: {e}")


def get_active_staff():
    """Returns a list of all active Support and Admin staff accounts for assignment."""
    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, username, name, role, email, status, department 
            FROM users 
            WHERE role IN ('Admin', 'Support') AND (status IS NULL OR status != 'Suspended')
            ORDER BY role ASC, name ASC
        """)
        staff = cursor.fetchall()
        connection.close()
        return staff
    except Exception as e:
        print(f"Error fetching staff: {e}")
        return []


def query_tickets(filters=None, sort_by="id", sort_order="desc", limit=None):
    """
    Structured dynamic SQL query builder for tickets with multi-criteria search, filtering, and sorting.
    """
    if filters is None:
        filters = {}

    conditions = []
    params = []

    # Requester constraint (if standard User role)
    if filters.get("username") and filters.get("role") not in ["Admin", "Support"]:
        conditions.append("username = ?")
        params.append(filters["username"])
    elif filters.get("requester"):
        conditions.append("username = ?")
        params.append(filters["requester"])

    # Search Query
    q = filters.get("q", "").strip()
    if q:
        conditions.append("""(
            CAST(id AS TEXT) LIKE ? OR
            subject LIKE ? OR
            description LIKE ? OR
            category LIKE ? OR
            username LIKE ? OR
            assigned_to LIKE ? OR
            escalation_reason LIKE ? OR
            escalation_level LIKE ?
        )""")
        search_pattern = f"%{q}%"
        params.extend([search_pattern] * 8)

    # Status Filter
    status = filters.get("status", "").strip()
    if status and status.lower() != "all":
        if status.lower() == "active":
            conditions.append("status NOT IN ('Resolved', 'Closed')")
        else:
            conditions.append("LOWER(status) = LOWER(?)")
            params.append(status)

    # Priority Filter
    priority = filters.get("priority", "").strip()
    if priority and priority.lower() != "all":
        conditions.append("LOWER(priority) = LOWER(?)")
        params.append(priority)

    # Category Filter
    category = filters.get("category", "").strip()
    if category and category.lower() != "all":
        conditions.append("LOWER(category) = LOWER(?)")
        params.append(category)

    # Assigned Agent Filter
    assigned_to = filters.get("assigned_to", "").strip()
    if assigned_to and assigned_to.lower() != "all":
        if assigned_to.lower() in ["unassigned", "none", "null"]:
            conditions.append("(assigned_to IS NULL OR assigned_to = '')")
        elif assigned_to.lower() == "assigned":
            conditions.append("(assigned_to IS NOT NULL AND assigned_to != '')")
        else:
            conditions.append("assigned_to = ?")
            params.append(assigned_to)

    # Escalation Filter
    is_escalated = filters.get("is_escalated")
    if is_escalated is not None and str(is_escalated).strip() != "" and str(is_escalated).lower() != "all":
        if str(is_escalated).lower() in ["1", "true", "yes", "escalated"]:
            conditions.append("is_escalated = 1")
        elif str(is_escalated).lower() in ["0", "false", "no"]:
            conditions.append("is_escalated = 0")

    # Date Range Filters
    date_from = filters.get("date_from", "").strip()
    if date_from:
        conditions.append("created_at >= ?")
        params.append(f"{date_from} 00:00:00")

    date_to = filters.get("date_to", "").strip()
    if date_to:
        conditions.append("created_at <= ?")
        params.append(f"{date_to} 23:59:59")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Sorting Logic
    order_dir = "ASC" if str(sort_order).lower() == "asc" else "DESC"
    sort_by_lower = str(sort_by).lower().strip()

    if sort_by_lower == "priority":
        if order_dir == "DESC":
            order_clause = "ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END ASC, id DESC"
        else:
            order_clause = "ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END DESC, id ASC"
    elif sort_by_lower == "status":
        order_clause = f"ORDER BY CASE status WHEN 'Open' THEN 1 WHEN 'In Progress' THEN 2 WHEN 'Pending' THEN 3 WHEN 'Resolved' THEN 4 ELSE 5 END {order_dir}, id DESC"
    elif sort_by_lower == "created_at":
        order_clause = f"ORDER BY created_at {order_dir}, id {order_dir}"
    elif sort_by_lower == "updated_at":
        order_clause = f"ORDER BY updated_at {order_dir}, id {order_dir}"
    elif sort_by_lower == "subject":
        order_clause = f"ORDER BY subject {order_dir}"
    elif sort_by_lower == "category":
        order_clause = f"ORDER BY category {order_dir}, id DESC"
    elif sort_by_lower == "requester":
        order_clause = f"ORDER BY username {order_dir}, id DESC"
    elif sort_by_lower == "assigned_to":
        order_clause = f"ORDER BY assigned_to {order_dir}, id DESC"
    elif sort_by_lower == "escalated":
        order_clause = f"ORDER BY is_escalated {order_dir}, id DESC"
    else:
        order_clause = f"ORDER BY id {order_dir}"

    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    query_sql = f"""
        SELECT 
            id, username, category, priority, subject, description, 
            attachment, attachment_name, status, assigned_to, 
            resolved_at, closed_at, is_escalated, escalation_level, 
            escalation_reason, escalated_by, escalated_at, escalation_target, 
            escalation_notes, created_at, updated_at
        FROM tickets
        {where_clause}
        {order_clause}
        {limit_clause}
    """

    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute(query_sql, tuple(params))
        rows = cursor.fetchall()
        connection.close()
        return rows
    except Exception as e:
        print(f"Error querying tickets: {e}")
        return []


# ==============================================================================
# Context Processor: Injects Notifications to all Templates
# ==============================================================================

@app.context_processor
def inject_notifications():
    if "username" in session:
        username = session["username"]
        try:
            connection = sqlite3.connect("helpdesk.db")
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE username = ? AND is_read = 0", (username,))
            unread_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT id, title, message, link, is_read, created_at, sender, ticket_id
                FROM notifications
                WHERE username = ?
                ORDER BY id DESC LIMIT 6
            """, (username,))
            recent_notifs = cursor.fetchall()
            connection.close()

            return {
                "unread_notifications_count": unread_count,
                "navbar_notifications": recent_notifs
            }
        except Exception:
            return {
                "unread_notifications_count": 0,
                "navbar_notifications": []
            }
    return {
        "unread_notifications_count": 0,
        "navbar_notifications": []
    }


# ==============================================================================
# RBAC Access Control Decorators
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            flash("Please sign in to access administrative tools.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "Admin":
            flash("Access denied. Administrator privileges required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def support_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            flash("Please sign in to access staff tools.", "warning")
            return redirect(url_for("login"))
        if session.get("role") not in ["Admin", "Support"]:
            flash("Access denied. Support Staff or Administrator role required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# Authentication & Public Routes
# ==============================================================================

@app.route("/")
def home():
    user = session.get("username")
    role = session.get("role", "User")
    return render_template("index.html", user=user, role=role)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not username or not password:
            return render_template("register.html", error="Please fill in all required fields.")

        if len(password) < 4:
            return render_template("register.html", error="Password must be at least 4 characters long.")

        hashed_password = generate_password_hash(password)

        try:
            connection = sqlite3.connect("helpdesk.db")
            cursor = connection.cursor()

            cursor.execute("""
                INSERT INTO users (name, email, username, password, role)
                VALUES (?, ?, ?, ?, 'User')
            """, (name, email, username, hashed_password))

            connection.commit()
            connection.close()

            flash("Account registered successfully! Please sign in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username is already taken. Please choose another username.")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name, email, username, password, role, status, department FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()
        connection.close()

        if user and check_password_hash(user[4], password):
            user_status = user[6] if user[6] else "Active"
            if user_status == "Suspended":
                return render_template("login.html", error="Your account has been suspended by an administrator. Please contact IT support.")

            session["user_id"] = user[0]
            session["name"] = user[1]
            session["email"] = user[2]
            session["username"] = user[3]
            session["role"] = user[5] if user[5] else "User"
            session["status"] = user_status
            session["department"] = user[7] if user[7] else "General"

            flash(f"Welcome back, {user[1]}!", "success")
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("home"))


# ==============================================================================
# Role-Based Dashboard Routes
# ==============================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    username = session["username"]
    role = session.get("role", "User")

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    if role == "Admin":
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Admin'")
        total_admins = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Support'")
        total_support = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'User'")
        total_regular_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'Suspended'")
        suspended_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets")
        total_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Open'")
        open_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'In Progress'")
        inprogress_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Pending'")
        pending_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'")
        resolved_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Closed'")
        closed_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE priority IN ('Critical', 'High') AND status NOT IN ('Resolved', 'Closed')")
        urgent_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE (assigned_to IS NULL OR assigned_to = '') AND status NOT IN ('Resolved', 'Closed')")
        unassigned_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE is_escalated = 1 AND status NOT IN ('Resolved', 'Closed')")
        escalated_tickets = cursor.fetchone()[0]

        resolution_rate = round(((resolved_tickets + closed_tickets) / total_tickets * 100), 1) if total_tickets > 0 else 0.0

        # Fetch priority SLA mapping for SLA breach tracking
        cursor.execute("SELECT name, sla_response_hours FROM ticket_priorities")
        sla_rows = cursor.fetchall()
        sla_map = {r[0].lower(): r[1] for r in sla_rows} if sla_rows else {"critical": 2, "high": 8, "medium": 24, "low": 72}
        default_sla = 24

        # Recent global tickets with assigned_to & escalation fields
        cursor.execute("""
            SELECT id, username, category, priority, subject, status, created_at, attachment, attachment_name, assigned_to, is_escalated, escalation_level, escalation_reason, updated_at
            FROM tickets
            ORDER BY id DESC LIMIT 100
        """)
        raw_tickets = cursor.fetchall()

        now = datetime.now()
        all_tickets = []
        overdue_tickets_count = 0
        for t in raw_tickets:
            t_created_str = t[6]
            t_prio = (t[3] or "Medium").lower()
            t_status = t[5]
            sla_hours = sla_map.get(t_prio, default_sla)
            
            is_overdue = False
            hours_elapsed = 0.0
            if t_created_str and t_status not in ["Resolved", "Closed"]:
                try:
                    created_dt = datetime.strptime(str(t_created_str)[:19], "%Y-%m-%d %H:%M:%S")
                    hours_elapsed = round((now - created_dt).total_seconds() / 3600, 1)
                    if hours_elapsed > sla_hours:
                        is_overdue = True
                        overdue_tickets_count += 1
                except Exception:
                    pass

            ticket_dict = {
                "id": t[0],
                "username": t[1],
                "category": t[2],
                "priority": t[3],
                "subject": t[4],
                "status": t[5],
                "created_at": t[6],
                "attachment": t[7],
                "attachment_name": t[8],
                "assigned_to": t[9],
                "is_escalated": bool(t[10]),
                "escalation_level": t[11] or "None",
                "escalation_reason": t[12],
                "updated_at": t[13],
                "is_overdue": is_overdue,
                "hours_elapsed": hours_elapsed,
                "sla_hours": sla_hours
            }
            all_tickets.append(ticket_dict)

        # All Users with ticket count, status, and department
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.username, u.role, u.created_at,
                   COUNT(t.id) as ticket_count,
                   COALESCE(u.status, 'Active') as status,
                   COALESCE(u.department, 'General') as department
            FROM users u
            LEFT JOIN tickets t ON u.username = t.username
            GROUP BY u.id
            ORDER BY u.id DESC
        """)
        all_users = cursor.fetchall()

        # All Categories with ticket usage count
        cursor.execute("""
            SELECT c.id, c.name, c.description, c.color, c.icon, c.is_active, c.created_at,
                   COUNT(t.id) as ticket_count
            FROM ticket_categories c
            LEFT JOIN tickets t ON LOWER(c.name) = LOWER(t.category)
            GROUP BY c.id
            ORDER BY c.name ASC
        """)
        all_categories = cursor.fetchall()

        # All Priorities with ticket usage count
        cursor.execute("""
            SELECT p.id, p.name, p.level, p.color, p.sla_response_hours, p.description, p.is_active, p.created_at,
                   COUNT(t.id) as ticket_count
            FROM ticket_priorities p
            LEFT JOIN tickets t ON LOWER(p.name) = LOWER(t.priority)
            GROUP BY p.id
            ORDER BY p.level ASC
        """)
        all_priorities = cursor.fetchall()

        # Support Agents & Capacity / Workload Leaderboard
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.username, u.role, 
                   COALESCE(u.status, 'Active') as status, 
                   COALESCE(u.department, 'Support') as department,
                   COUNT(t.id) as total_assigned,
                   SUM(CASE WHEN t.status IN ('Open', 'In Progress', 'Pending') THEN 1 ELSE 0 END) as active_tickets,
                   SUM(CASE WHEN t.status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) as resolved_tickets,
                   SUM(CASE WHEN t.is_escalated = 1 THEN 1 ELSE 0 END) as escalated_tickets
            FROM users u
            LEFT JOIN tickets t ON u.username = t.assigned_to
            WHERE u.role IN ('Support', 'Admin')
            GROUP BY u.id
            ORDER BY active_tickets DESC, u.name ASC
        """)
        raw_agent_workloads = cursor.fetchall()
        agent_workloads = []
        for a in raw_agent_workloads:
            tot = a[7] or 0
            act = a[8] or 0
            res = a[9] or 0
            esc = a[10] or 0
            eff = round((res / tot * 100), 1) if tot > 0 else 100.0
            agent_workloads.append({
                "id": a[0],
                "name": a[1],
                "email": a[2],
                "username": a[3],
                "role": a[4],
                "status": a[5] or "Active",
                "department": a[6] or "Support",
                "total_assigned": tot,
                "active_tickets": act,
                "resolved_tickets": res,
                "escalated_tickets": esc,
                "efficiency": eff
            })

        # Category breakdown stats for visual chart
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM tickets 
            GROUP BY category 
            ORDER BY count DESC
        """)
        category_breakdown = cursor.fetchall()

        # Priority breakdown stats
        cursor.execute("""
            SELECT priority, COUNT(*) as count 
            FROM tickets 
            GROUP BY priority 
            ORDER BY 
                CASE priority 
                    WHEN 'Critical' THEN 1 
                    WHEN 'High' THEN 2 
                    WHEN 'Medium' THEN 3 
                    ELSE 4 
                END
        """)
        priority_breakdown = cursor.fetchall()

        # Recent system audit activities for admin live feed
        cursor.execute("""
            SELECT a.id, a.ticket_id, a.username, a.activity_type, a.old_value, a.new_value, a.message, a.created_at, t.subject
            FROM ticket_activities a
            LEFT JOIN tickets t ON a.ticket_id = t.id
            ORDER BY a.id DESC LIMIT 15
        """)
        recent_activities = cursor.fetchall()

        connection.close()

        staff_list = get_active_staff()

        stats = {
            "total_users": total_users,
            "total_admins": total_admins,
            "total_support": total_support,
            "total_regular_users": total_regular_users,
            "suspended_users": suspended_users,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "inprogress_tickets": inprogress_tickets,
            "pending_tickets": pending_tickets,
            "resolved_tickets": resolved_tickets,
            "closed_tickets": closed_tickets,
            "urgent_tickets": urgent_tickets,
            "unassigned_tickets": unassigned_tickets,
            "escalated_tickets": escalated_tickets,
            "overdue_tickets": overdue_tickets_count,
            "resolution_rate": resolution_rate
        }

        return render_template(
            "admin_dashboard.html",
            username=username,
            role=role,
            stats=stats,
            tickets=all_tickets,
            users=all_users,
            staff_list=staff_list,
            categories=all_categories,
            priorities=all_priorities,
            agent_workloads=agent_workloads,
            category_breakdown=category_breakdown,
            priority_breakdown=priority_breakdown,
            recent_activities=recent_activities
        )

    elif role == "Support":
        cursor.execute("SELECT COUNT(*) FROM tickets")
        total_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Open'")
        open_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'In Progress'")
        inprogress_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Pending'")
        pending_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE priority = 'Critical' AND status NOT IN ('Resolved', 'Closed')")
        critical_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE is_escalated = 1 AND status NOT IN ('Resolved', 'Closed')")
        escalated_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'")
        resolved_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status NOT IN ('Resolved', 'Closed')", (username,))
        my_assigned_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE (assigned_to IS NULL OR assigned_to = '') AND status NOT IN ('Resolved', 'Closed')")
        unassigned_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT id, username, category, priority, subject, status, created_at, attachment, attachment_name, assigned_to, is_escalated, escalation_level, escalation_reason, updated_at
            FROM tickets
            ORDER BY 
                is_escalated DESC,
                CASE priority 
                    WHEN 'Critical' THEN 1 
                    WHEN 'High' THEN 2 
                    WHEN 'Medium' THEN 3 
                    ELSE 4 
                END, 
                id DESC
        """)
        all_tickets = cursor.fetchall()
        connection.close()

        staff_list = get_active_staff()

        stats = {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "inprogress_tickets": inprogress_tickets,
            "pending_tickets": pending_tickets,
            "critical_tickets": critical_tickets,
            "escalated_tickets": escalated_tickets,
            "resolved_tickets": resolved_tickets,
            "my_assigned": my_assigned_count,
            "unassigned": unassigned_count
        }

        return render_template(
            "support_dashboard.html",
            username=username,
            role=role,
            stats=stats,
            tickets=all_tickets,
            staff_list=staff_list
        )

    else:
        # Standard User Dashboard
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ?", (username,))
        total_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'Open'", (username,))
        open_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'In Progress'", (username,))
        inprogress_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'Resolved'", (username,))
        resolved_tickets = cursor.fetchone()[0]

        cursor.execute("""
            SELECT id, subject, category, priority, status, created_at, attachment, attachment_name, assigned_to, is_escalated, escalation_level, escalation_reason, updated_at
            FROM tickets
            WHERE username = ?
            ORDER BY id DESC LIMIT 5
        """, (username,))
        recent_tickets = cursor.fetchall()
        connection.close()

        stats = {
            "total": total_tickets,
            "open": open_tickets,
            "inprogress": inprogress_tickets,
            "resolved": resolved_tickets
        }

        return render_template("dashboard.html", username=username, role=role, stats=stats, recent_tickets=recent_tickets)


# ==============================================================================
# Administrator User & Staff Management Endpoints
# ==============================================================================

@app.route("/admin/user/create", methods=["POST"])
@admin_required
def admin_create_user():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    target_role = request.form.get("role", "User").strip().capitalize()
    department = request.form.get("department", "General").strip()
    status = request.form.get("status", "Active").strip().capitalize()

    if target_role not in ["User", "Support", "Admin"]:
        target_role = "User"
    if status not in ["Active", "Suspended"]:
        status = "Active"

    if not name or not email or not username or not password:
        flash("All fields are required to create a new user account.", "danger")
        return redirect(url_for("dashboard"))

    if len(password) < 4:
        flash("Password must be at least 4 characters long.", "danger")
        return redirect(url_for("dashboard"))

    hashed_password = generate_password_hash(password)

    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO users (name, email, username, password, role, status, department)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, email, username, hashed_password, target_role, status, department or "General"))
        connection.commit()
        connection.close()
        flash(f"User account '{username}' created successfully with role '{target_role}'.", "success")
    except sqlite3.IntegrityError:
        flash(f"Username '{username}' already exists. Please choose a unique username.", "danger")

    return redirect(url_for("dashboard"))


@app.route("/admin/user/<int:user_id>/edit", methods=["POST"])
@admin_required
def admin_edit_user(user_id):
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    new_role = request.form.get("role", "").strip().capitalize()
    department = request.form.get("department", "").strip()
    new_status = request.form.get("status", "").strip().capitalize()

    if not name or not email:
        flash("Name and email are required fields.", "danger")
        return redirect(url_for("dashboard"))

    if new_role not in ["User", "Support", "Admin"]:
        new_role = "User"
    if new_status not in ["Active", "Suspended"]:
        new_status = "Active"

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT username, role, status FROM users WHERE id = ?", (user_id,))
    target_user = cursor.fetchone()

    if not target_user:
        connection.close()
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    # Protect self from demoting or suspending own account
    if target_user[0] == session.get("username"):
        if new_role != "Admin":
            new_role = "Admin"
            flash("Self-protection: Administrator role preserved for current session.", "warning")
        if new_status == "Suspended":
            new_status = "Active"
            flash("Self-protection: Cannot suspend your own administrator account.", "warning")

    cursor.execute("""
        UPDATE users
        SET name = ?, email = ?, role = ?, department = ?, status = ?
        WHERE id = ?
    """, (name, email, new_role, department or "General", new_status, user_id))
    connection.commit()
    connection.close()

    flash(f"Profile details and permissions updated for user '{target_user[0]}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/user/<int:user_id>/role", methods=["POST"])
@admin_required
def admin_update_user_role(user_id):
    new_role = request.form.get("role", "").strip().capitalize()
    if new_role not in ["User", "Support", "Admin"]:
        flash("Invalid role specified.", "danger")
        return redirect(url_for("dashboard"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
    target_user = cursor.fetchone()

    if not target_user:
        connection.close()
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    if target_user[0] == session.get("username") and new_role != "Admin":
        connection.close()
        flash("You cannot demote your own administrator account while logged in.", "warning")
        return redirect(url_for("dashboard"))

    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    connection.commit()
    connection.close()

    flash(f"Role for user '{target_user[0]}' updated to '{new_role}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/user/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def admin_toggle_user_status(user_id):
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT username, role, status FROM users WHERE id = ?", (user_id,))
    target_user = cursor.fetchone()

    if not target_user:
        connection.close()
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    if target_user[0] == session.get("username"):
        connection.close()
        flash("Safety Protection: You cannot suspend your own active administrator account.", "danger")
        return redirect(url_for("dashboard"))

    current_status = target_user[2] or "Active"
    next_status = "Suspended" if current_status == "Active" else "Active"

    cursor.execute("UPDATE users SET status = ? WHERE id = ?", (next_status, user_id))
    connection.commit()
    connection.close()

    flash(f"Account for '{target_user[0]}' is now marked as {next_status}.", "info" if next_status == "Suspended" else "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/user/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def admin_reset_user_password(user_id):
    new_password = request.form.get("new_password", "").strip()
    if not new_password or len(new_password) < 4:
        flash("New password must be at least 4 characters long.", "danger")
        return redirect(url_for("dashboard"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    target_user = cursor.fetchone()

    if not target_user:
        connection.close()
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    hashed = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, user_id))
    connection.commit()
    connection.close()

    flash(f"Password reset successfully for user '{target_user[0]}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
    target_user = cursor.fetchone()

    if not target_user:
        connection.close()
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    if target_user[0] == session.get("username"):
        connection.close()
        flash("Safety Protection: You cannot delete your own logged-in administrator account.", "danger")
        return redirect(url_for("dashboard"))

    if target_user[1] == "Admin":
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Admin'")
        admin_count = cursor.fetchone()[0]
        if admin_count <= 1:
            connection.close()
            flash("Safety Protection: Cannot delete the sole remaining administrator account.", "danger")
            return redirect(url_for("dashboard"))

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    connection.close()

    flash(f"Account for user '{target_user[0]}' has been deleted.", "info")
    return redirect(url_for("dashboard"))


# ==============================================================================
# Support Agent Operations & Workload Management Endpoints
# ==============================================================================

@app.route("/admin/agents/reassign-workload", methods=["POST"])
@admin_required
def admin_reassign_workload():
    source_agent = request.form.get("source_agent", "").strip()
    target_agent = request.form.get("target_agent", "").strip()
    reason = request.form.get("reason", "Administrative workload balancing").strip()

    if not source_agent or not target_agent:
        flash("Both source and destination agents must be specified.", "warning")
        return redirect(url_for("dashboard"))

    if source_agent == target_agent:
        flash("Source and destination agents cannot be identical.", "warning")
        return redirect(url_for("dashboard"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, subject FROM tickets 
        WHERE assigned_to = ? AND status NOT IN ('Resolved', 'Closed')
    """, (source_agent,))
    affected_tickets = cursor.fetchall()

    if not affected_tickets:
        connection.close()
        flash(f"No active tickets found assigned to '{source_agent}'.", "info")
        return redirect(url_for("dashboard"))

    cursor.execute("""
        UPDATE tickets
        SET assigned_to = ?, updated_at = CURRENT_TIMESTAMP
        WHERE assigned_to = ? AND status NOT IN ('Resolved', 'Closed')
    """, (target_agent, source_agent))
    connection.commit()
    connection.close()

    admin_username = session.get("username", "Admin")
    for t in affected_tickets:
        log_ticket_activity(
            ticket_id=t[0],
            username=admin_username,
            activity_type="ASSIGNMENT",
            old_value=f"@{source_agent}",
            new_value=f"@{target_agent}",
            message=f"Workload reassigned by admin {admin_username}. Reason: {reason}"
        )

    create_notification(
        recipient=target_agent,
        sender=admin_username,
        title=f"🔄 Workload Transferred: {len(affected_tickets)} Tickets Assigned",
        message=f"{len(affected_tickets)} active tickets previously assigned to @{source_agent} have been routed to you.",
        link="/dashboard"
    )

    flash(f"Successfully transferred {len(affected_tickets)} active tickets from @{source_agent} to @{target_agent}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/agents/assign-ticket", methods=["POST"])
@admin_required
def admin_assign_ticket():
    ticket_id = request.form.get("ticket_id", type=int)
    assigned_to = request.form.get("assigned_to", "").strip()

    if not ticket_id or not assigned_to:
        flash("Ticket ID and assigned staff member are required.", "danger")
        return redirect(url_for("dashboard"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT id, subject, assigned_to FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("dashboard"))

    old_assigned = ticket[2] or "Unassigned"
    cursor.execute("""
        UPDATE tickets
        SET assigned_to = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (assigned_to, ticket_id))
    connection.commit()
    connection.close()

    admin_username = session.get("username", "Admin")
    log_ticket_activity(
        ticket_id=ticket_id,
        username=admin_username,
        activity_type="ASSIGNMENT",
        old_value=old_assigned,
        new_value=assigned_to,
        message=f"Ticket assigned to @{assigned_to} by admin {admin_username}."
    )

    create_notification(
        recipient=assigned_to,
        sender=admin_username,
        title=f"📋 Ticket Assigned: #{ticket_id}",
        message=f"Ticket #{ticket_id} ('{ticket[1]}') has been assigned to you by Administrator.",
        link=f"/ticket/{ticket_id}",
        ticket_id=ticket_id
    )

    flash(f"Ticket #{ticket_id} assigned to @{assigned_to}.", "success")
    return redirect(url_for("dashboard"))


# ==============================================================================
# Ticket Category Management Endpoints
# ==============================================================================

@app.route("/admin/category/create", methods=["POST"])
@admin_required
def admin_create_category():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    color = request.form.get("color", "#4f46e5").strip()
    icon = request.form.get("icon", "fa-ticket").strip()

    if not name:
        flash("Category name is required.", "danger")
        return redirect(url_for("dashboard"))

    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO ticket_categories (name, description, color, icon, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (name, description, color, icon))
        connection.commit()
        connection.close()
        flash(f"Ticket category '{name}' created successfully.", "success")
    except sqlite3.IntegrityError:
        flash(f"Category '{name}' already exists.", "warning")

    return redirect(url_for("dashboard"))


@app.route("/admin/category/<int:category_id>/update", methods=["POST"])
@admin_required
def admin_update_category(category_id):
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    color = request.form.get("color", "#4f46e5").strip()
    icon = request.form.get("icon", "fa-ticket").strip()
    is_active = 1 if request.form.get("is_active") == "1" else 0

    if not name:
        flash("Category name is required.", "danger")
        return redirect(url_for("dashboard"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE ticket_categories
        SET name = ?, description = ?, color = ?, icon = ?, is_active = ?
        WHERE id = ?
    """, (name, description, color, icon, is_active, category_id))
    connection.commit()
    connection.close()

    flash(f"Category '{name}' updated successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/category/<int:category_id>/toggle-status", methods=["POST"])
@admin_required
def admin_toggle_category_status(category_id):
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT name, is_active FROM ticket_categories WHERE id = ?", (category_id,))
    cat = cursor.fetchone()
    if cat:
        new_status = 0 if cat[1] == 1 else 1
        cursor.execute("UPDATE ticket_categories SET is_active = ? WHERE id = ?", (new_status, category_id))
        connection.commit()
        status_text = "enabled" if new_status == 1 else "disabled"
        flash(f"Category '{cat[0]}' {status_text}.", "info")
    connection.close()
    return redirect(url_for("dashboard"))


@app.route("/admin/category/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_delete_category(category_id):
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM ticket_categories WHERE id = ?", (category_id,))
    cat = cursor.fetchone()

    if not cat:
        connection.close()
        flash("Category not found.", "danger")
        return redirect(url_for("dashboard"))

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE category = ?", (cat[0],))
    usage_count = cursor.fetchone()[0]

    if usage_count > 0:
        cursor.execute("UPDATE ticket_categories SET is_active = 0 WHERE id = ?", (category_id,))
        connection.commit()
        connection.close()
        flash(f"Category '{cat[0]}' is referenced in {usage_count} existing ticket(s). It has been deactivated instead of deleted to preserve history.", "warning")
    else:
        cursor.execute("DELETE FROM ticket_categories WHERE id = ?", (category_id,))
        connection.commit()
        connection.close()
        flash(f"Category '{cat[0]}' permanently deleted.", "info")

    return redirect(url_for("dashboard"))


# ==============================================================================
# Ticket Priority & SLA Policies Management Endpoints
# ==============================================================================

@app.route("/admin/priority/create", methods=["POST"])
@admin_required
def admin_create_priority():
    name = request.form.get("name", "").strip()
    level = request.form.get("level", type=int)
    color = request.form.get("color", "#4f46e5").strip()
    sla_response_hours = request.form.get("sla_response_hours", type=int) or 24
    description = request.form.get("description", "").strip()

    if not name or level is None:
        flash("Priority name and hierarchy level are required.", "danger")
        return redirect(url_for("dashboard"))

    try:
        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO ticket_priorities (name, level, color, sla_response_hours, description, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, level, color, sla_response_hours, description))
        connection.commit()
        connection.close()
        flash(f"Priority tier '{name}' (Level {level}, SLA {sla_response_hours}h) created.", "success")
    except sqlite3.IntegrityError:
        flash(f"Priority name or level already exists.", "warning")

    return redirect(url_for("dashboard"))


@app.route("/admin/priority/<int:priority_id>/update", methods=["POST"])
@admin_required
def admin_update_priority(priority_id):
    name = request.form.get("name", "").strip()
    level = request.form.get("level", type=int)
    color = request.form.get("color", "#4f46e5").strip()
    sla_response_hours = request.form.get("sla_response_hours", type=int) or 24
    description = request.form.get("description", "").strip()
    is_active = 1 if request.form.get("is_active") == "1" else 0

    if not name or level is None:
        flash("Priority name and level are required.", "danger")
        return redirect(url_for("dashboard"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE ticket_priorities
        SET name = ?, level = ?, color = ?, sla_response_hours = ?, description = ?, is_active = ?
        WHERE id = ?
    """, (name, level, color, sla_response_hours, description, is_active, priority_id))
    connection.commit()
    connection.close()

    flash(f"Priority tier '{name}' updated successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/priority/<int:priority_id>/toggle-status", methods=["POST"])
@admin_required
def admin_toggle_priority_status(priority_id):
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT name, is_active FROM ticket_priorities WHERE id = ?", (priority_id,))
    prio = cursor.fetchone()
    if prio:
        new_status = 0 if prio[1] == 1 else 1
        cursor.execute("UPDATE ticket_priorities SET is_active = ? WHERE id = ?", (new_status, priority_id))
        connection.commit()
        flash(f"Priority '{prio[0]}' {'enabled' if new_status == 1 else 'disabled'}.", "info")
    connection.close()
    return redirect(url_for("dashboard"))


@app.route("/admin/priority/<int:priority_id>/delete", methods=["POST"])
@admin_required
def admin_delete_priority(priority_id):
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM ticket_priorities WHERE id = ?", (priority_id,))
    prio = cursor.fetchone()

    if not prio:
        connection.close()
        flash("Priority tier not found.", "danger")
        return redirect(url_for("dashboard"))

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE priority = ?", (prio[0],))
    usage_count = cursor.fetchone()[0]

    if usage_count > 0:
        cursor.execute("UPDATE ticket_priorities SET is_active = 0 WHERE id = ?", (priority_id,))
        connection.commit()
        connection.close()
        flash(f"Priority '{prio[0]}' is currently referenced on {usage_count} ticket(s). It was deactivated instead of deleted.", "warning")
    else:
        cursor.execute("DELETE FROM ticket_priorities WHERE id = ?", (priority_id,))
        connection.commit()
        connection.close()
        flash(f"Priority '{prio[0]}' removed successfully.", "info")

    return redirect(url_for("dashboard"))


# ==============================================================================
# Help Desk Operations Console: Bulk Actions & Executive Export
# ==============================================================================

@app.route("/admin/tickets/bulk-action", methods=["POST"])
@admin_required
def admin_bulk_tickets_action():
    ticket_ids_raw = request.form.get("ticket_ids", "")
    bulk_action = request.form.get("bulk_action", "").strip()
    target_value = request.form.get("target_value", "").strip()

    if not ticket_ids_raw or not bulk_action:
        flash("Please select at least one ticket and an action to execute.", "warning")
        return redirect(url_for("dashboard"))

    ticket_ids = [int(tid.strip()) for tid in ticket_ids_raw.split(",") if tid.strip().isdigit()]
    if not ticket_ids:
        flash("No valid ticket IDs selected.", "warning")
        return redirect(url_for("dashboard"))

    admin_username = session.get("username", "Admin")
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    if bulk_action == "assign":
        if not target_value:
            flash("Target agent required for assignment.", "danger")
            connection.close()
            return redirect(url_for("dashboard"))
        
        placeholders = ",".join("?" for _ in ticket_ids)
        cursor.execute(f"UPDATE tickets SET assigned_to = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [target_value] + ticket_ids)
        connection.commit()
        for tid in ticket_ids:
            log_ticket_activity(tid, admin_username, "ASSIGNMENT", new_value=target_value, message=f"Batch assigned to @{target_value} by Admin.")
        flash(f"Batch assigned {len(ticket_ids)} tickets to @{target_value}.", "success")

    elif bulk_action == "status":
        if target_value not in ["Open", "In Progress", "Pending", "Resolved", "Closed"]:
            flash("Invalid status selected.", "danger")
            connection.close()
            return redirect(url_for("dashboard"))

        placeholders = ",".join("?" for _ in ticket_ids)
        if target_value == "Resolved":
            cursor.execute(f"UPDATE tickets SET status = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [target_value] + ticket_ids)
        elif target_value == "Closed":
            cursor.execute(f"UPDATE tickets SET status = ?, closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [target_value] + ticket_ids)
        else:
            cursor.execute(f"UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [target_value] + ticket_ids)
        
        connection.commit()
        for tid in ticket_ids:
            log_ticket_activity(tid, admin_username, "STATUS_CHANGE", new_value=target_value, message=f"Batch status updated to '{target_value}' by Admin.")
        flash(f"Batch updated status to '{target_value}' for {len(ticket_ids)} tickets.", "success")

    elif bulk_action == "priority":
        if not target_value:
            flash("Target priority required.", "danger")
            connection.close()
            return redirect(url_for("dashboard"))

        placeholders = ",".join("?" for _ in ticket_ids)
        cursor.execute(f"UPDATE tickets SET priority = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [target_value] + ticket_ids)
        connection.commit()
        for tid in ticket_ids:
            log_ticket_activity(tid, admin_username, "PRIORITY_CHANGE", new_value=target_value, message=f"Batch priority updated to '{target_value}' by Admin.")
        flash(f"Batch updated priority to '{target_value}' for {len(ticket_ids)} tickets.", "success")

    elif bulk_action == "delete":
        placeholders = ",".join("?" for _ in ticket_ids)
        cursor.execute(f"DELETE FROM tickets WHERE id IN ({placeholders})", ticket_ids)
        connection.commit()
        flash(f"Batch deleted {len(ticket_ids)} tickets.", "info")

    connection.close()
    return redirect(url_for("dashboard"))


@app.route("/admin/operations/export")
@admin_required
def admin_export_operations():
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    # Executive Overview
    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Open'")
    open_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'")
    resolved_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Closed'")
    closed_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE is_escalated = 1")
    escalated_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role IN ('Support', 'Admin')")
    total_staff = cursor.fetchone()[0]

    si = io.StringIO()
    cw = csv.writer(si)

    cw.writerow(["=== HELPDESK OPERATIONS & PERFORMANCE AUDIT REPORT ==="])
    cw.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    cw.writerow([])
    cw.writerow(["--- HIGH-LEVEL KEY PERFORMANCE INDICATORS ---"])
    cw.writerow(["Total Tickets Logged", total_tickets])
    cw.writerow(["Open Tickets Queue", open_tickets])
    cw.writerow(["Resolved Tickets", resolved_tickets])
    cw.writerow(["Closed Tickets", closed_tickets])
    cw.writerow(["Total Escalations", escalated_tickets])
    cw.writerow(["Active Support & Admin Staff", total_staff])
    cw.writerow([])

    # Support Agent Workload Section
    cw.writerow(["--- SUPPORT AGENT WORKLOAD & RESOLUTION METRICS ---"])
    cw.writerow(["Agent Username", "Full Name", "Role", "Department", "Status", "Total Assigned", "Active Queue", "Resolved Tickets", "Resolution Efficiency (%)"])
    cursor.execute("""
        SELECT u.username, u.name, u.role, u.department, u.status,
               COUNT(t.id) as total_assigned,
               SUM(CASE WHEN t.status IN ('Open', 'In Progress', 'Pending') THEN 1 ELSE 0 END) as active_tickets,
               SUM(CASE WHEN t.status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) as resolved_tickets
        FROM users u
        LEFT JOIN tickets t ON u.username = t.assigned_to
        WHERE u.role IN ('Support', 'Admin')
        GROUP BY u.id
        ORDER BY active_tickets DESC
    """)
    for row in cursor.fetchall():
        tot = row[5] or 0
        res = row[7] or 0
        eff = f"{round((res / tot * 100), 1)}%" if tot > 0 else "N/A"
        cw.writerow([row[0], row[1], row[2], row[3] or "Support", row[4] or "Active", tot, row[6] or 0, res, eff])
    cw.writerow([])

    # Category Distribution Section
    cw.writerow(["--- TICKET CATEGORY DISTRIBUTION ---"])
    cw.writerow(["Category Name", "Total Tickets Logged", "Percentage of System Total"])
    cursor.execute("SELECT category, COUNT(*) FROM tickets GROUP BY category ORDER BY COUNT(*) DESC")
    for cat_row in cursor.fetchall():
        pct = f"{round((cat_row[1] / total_tickets * 100), 1)}%" if total_tickets > 0 else "0%"
        cw.writerow([cat_row[0], cat_row[1], pct])
    cw.writerow([])

    # Priority & SLA Policy Section
    cw.writerow(["--- PRIORITY TIERS & SLA TARGETS ---"])
    cw.writerow(["Priority Tier", "Level", "SLA Target (Hours)", "Current Active Tickets"])
    cursor.execute("""
        SELECT p.name, p.level, p.sla_response_hours,
               SUM(CASE WHEN t.status NOT IN ('Resolved', 'Closed') THEN 1 ELSE 0 END)
        FROM ticket_priorities p
        LEFT JOIN tickets t ON LOWER(p.name) = LOWER(t.priority)
        GROUP BY p.id
        ORDER BY p.level ASC
    """)
    for prio_row in cursor.fetchall():
        cw.writerow([prio_row[0], prio_row[1], prio_row[2], prio_row[3] or 0])

    connection.close()

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=helpdesk_operations_executive_report.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output


# ==============================================================================
# Profile Management Routes
# ==============================================================================

@app.route("/profile")
@login_required
def profile():
    username = session["username"]
    role = session.get("role", "User")

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, email, username, role, created_at
        FROM users
        WHERE username = ?
    """, (username,))
    user = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ?", (username,))
    user_tickets_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'Resolved'", (username,))
    resolved_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'Open'", (username,))
    open_count = cursor.fetchone()[0]

    connection.close()

    if not user:
        return redirect(url_for("logout"))

    return render_template(
        "profile.html",
        name=user[1],
        email=user[2],
        username=user[3],
        role=user[4] if user[4] else role,
        created_at=user[5] if len(user) > 5 and user[5] else "Recently",
        tickets_count=user_tickets_count,
        resolved_count=resolved_count,
        open_count=open_count
    )


@app.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    username = session["username"]
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()

    if not name or not email:
        flash("Name and email are required fields.", "danger")
        return redirect(url_for("profile"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE users SET name = ?, email = ? WHERE username = ?", (name, email, username))
    connection.commit()
    connection.close()

    session["name"] = name
    session["email"] = email

    flash("Profile details updated successfully!", "success")
    return redirect(url_for("profile"))


@app.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
    username = session["username"]
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not current_password or not new_password or not confirm_password:
        flash("Please fill in all password fields.", "danger")
        return redirect(url_for("profile"))

    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
        return redirect(url_for("profile"))

    if len(new_password) < 4:
        flash("New password must be at least 4 characters long.", "danger")
        return redirect(url_for("profile"))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()

    if not row or not check_password_hash(row[0], current_password):
        connection.close()
        flash("Current password entered is incorrect.", "danger")
        return redirect(url_for("profile"))

    hashed = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE username = ?", (hashed, username))
    connection.commit()
    connection.close()

    flash("Password updated successfully!", "success")
    return redirect(url_for("profile"))


# ==============================================================================
# Ticket Lifecycle, Assignment, Tracking & Discussion Routes
# ==============================================================================

@app.route("/create-ticket", methods=["GET", "POST"])
@login_required
def create_ticket():
    username = session["username"]
    role = session.get("role", "User")
    categories = get_active_categories()
    priorities = get_active_priorities()

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "Medium").strip()
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()

        if priority not in ["Low", "Medium", "High", "Critical"]:
            priority = "Medium"

        if not category or not subject or not description:
            return render_template(
                "create_ticket.html",
                username=username,
                role=role,
                categories=categories,
                priorities=priorities,
                error="Please complete all required fields."
            )

        saved_filename = None
        original_filename = None

        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename != "":
                if allowed_file(file.filename):
                    original_filename = secure_filename(file.filename)
                    saved_filename = f"{uuid.uuid4().hex}_{original_filename}"
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)
                    file.save(file_path)
                else:
                    return render_template(
                        "create_ticket.html",
                        username=username,
                        role=role,
                        categories=categories,
                        priorities=priorities,
                        error="Invalid file type. Allowed formats: images (PNG, JPG, GIF, WEBP), documents (PDF, DOCX, TXT, CSV, XLS, XLSX), logs, and ZIP."
                    )

        connection = sqlite3.connect("helpdesk.db")
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO tickets
            (username, category, priority, subject, description, attachment, attachment_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')
        """, (
            username,
            category,
            priority,
            subject,
            description,
            saved_filename,
            original_filename
        ))

        new_ticket_id = cursor.lastrowid
        connection.commit()
        connection.close()

        # Log initial creation in activity audit trail
        log_ticket_activity(
            ticket_id=new_ticket_id,
            username=username,
            activity_type="STATUS_CHANGE",
            old_value=None,
            new_value="Open",
            message=f"Ticket #{new_ticket_id} opened with {priority} priority in '{category}'."
        )

        # Notify staff about high/critical priority tickets or new submissions
        if priority in ["Critical", "High"]:
            notify_all_staff(
                sender=username,
                title=f"🚨 New {priority} Priority Ticket #{new_ticket_id}",
                message=f"Requester {username} created: {subject}",
                link=f"/ticket/{new_ticket_id}",
                ticket_id=new_ticket_id
            )

        flash(f"Ticket #{new_ticket_id} created successfully!", "success")
        return redirect(url_for("ticket_details", ticket_id=new_ticket_id))

    return render_template(
        "create_ticket.html",
        username=username,
        role=role,
        categories=categories,
        priorities=priorities
    )


@app.route("/ticket/<int:ticket_id>")
@login_required
def ticket_details(ticket_id):
    username = session["username"]
    role = session.get("role", "User")

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT 
            id, username, category, priority, subject, description, 
            attachment, attachment_name, status, created_at, updated_at, 
            assigned_to, is_escalated, escalation_level, escalation_reason, 
            escalated_by, escalated_at, escalation_target, escalation_notes
        FROM tickets
        WHERE id = ?
    """, (ticket_id,))
    ticket_row = cursor.fetchone()

    if not ticket_row:
        connection.close()
        flash(f"Ticket #{ticket_id} not found.", "warning")
        return redirect(url_for("my_tickets"))

    # Permission check: Users can only view their own tickets; Admin and Support can view all
    if role not in ["Admin", "Support"] and ticket_row[1] != username:
        connection.close()
        flash("You do not have permission to view that ticket.", "danger")
        return redirect(url_for("my_tickets"))

    ticket = {
        "id": ticket_row[0],
        "username": ticket_row[1],
        "category": ticket_row[2],
        "priority": ticket_row[3],
        "subject": ticket_row[4],
        "description": ticket_row[5],
        "attachment": ticket_row[6],
        "attachment_name": ticket_row[7],
        "status": ticket_row[8],
        "created_at": ticket_row[9],
        "updated_at": ticket_row[10] if ticket_row[10] else ticket_row[9],
        "assigned_to": ticket_row[11] if ticket_row[11] else None,
        "is_escalated": bool(ticket_row[12]),
        "escalation_level": ticket_row[13] if ticket_row[13] else "None",
        "escalation_reason": ticket_row[14],
        "escalated_by": ticket_row[15],
        "escalated_at": ticket_row[16],
        "escalation_target": ticket_row[17],
        "escalation_notes": ticket_row[18]
    }

    # Fetch assigned agent details if exists
    assigned_staff_info = None
    if ticket["assigned_to"]:
        cursor.execute("SELECT name, role, email FROM users WHERE username = ?", (ticket["assigned_to"],))
        staff_row = cursor.fetchone()
        if staff_row:
            assigned_staff_info = {
                "name": staff_row[0],
                "role": staff_row[1],
                "email": staff_row[2]
            }

    # Requester Support History Overview
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ?", (ticket["username"],))
    requester_total_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'Resolved'", (ticket["username"],))
    requester_resolved_tickets = cursor.fetchone()[0]

    cursor.execute("""
        SELECT id, subject, status, priority, created_at
        FROM tickets 
        WHERE username = ? AND id != ?
        ORDER BY id DESC LIMIT 4
    """, (ticket["username"], ticket_id))
    requester_recent_tickets = cursor.fetchall()

    requester_history = {
        "total": requester_total_tickets,
        "resolved": requester_resolved_tickets,
        "recent_tickets": requester_recent_tickets
    }

    # Fetch replies / discussion timeline (role-based filtering for internal notes)
    if role in ["Admin", "Support"]:
        cursor.execute("""
            SELECT id, ticket_id, username, role, message, created_at, is_internal, attachment, attachment_name
            FROM ticket_replies
            WHERE ticket_id = ?
            ORDER BY id ASC
        """, (ticket_id,))
    else:
        cursor.execute("""
            SELECT id, ticket_id, username, role, message, created_at, is_internal, attachment, attachment_name
            FROM ticket_replies
            WHERE ticket_id = ? AND is_internal = 0
            ORDER BY id ASC
        """, (ticket_id,))
    replies = cursor.fetchall()

    # Fetch Activity & Audit Trail (filter internal notes from regular user view)
    if role in ["Admin", "Support"]:
        cursor.execute("""
            SELECT id, ticket_id, username, activity_type, old_value, new_value, message, created_at
            FROM ticket_activities
            WHERE ticket_id = ?
            ORDER BY id DESC
        """, (ticket_id,))
    else:
        cursor.execute("""
            SELECT id, ticket_id, username, activity_type, old_value, new_value, message, created_at
            FROM ticket_activities
            WHERE ticket_id = ? AND activity_type != 'NOTE'
            ORDER BY id DESC
        """, (ticket_id,))
    activities = cursor.fetchall()

    connection.close()

    # Staff list for assignment selector
    staff_list = get_active_staff() if role in ["Admin", "Support"] else []

    # Check if main attachment is an image
    is_image_attachment = False
    if ticket["attachment"]:
        ext = ticket["attachment"].rsplit(".", 1)[-1].lower() if "." in ticket["attachment"] else ""
        is_image_attachment = ext in {"png", "jpg", "jpeg", "gif", "webp"}

    return render_template(
        "ticket_details.html",
        username=username,
        role=role,
        ticket=ticket,
        replies=replies,
        activities=activities,
        staff_list=staff_list,
        assigned_staff_info=assigned_staff_info,
        requester_history=requester_history,
        is_image=is_image_attachment
    )


@app.route("/ticket/<int:ticket_id>/reply", methods=["POST"])
@login_required
def add_ticket_reply(ticket_id):
    username = session["username"]
    role = session.get("role", "User")
    message = request.form.get("message", "").strip()
    is_internal = 1 if (str(request.form.get("is_internal", "")).strip() in ["1", "true", "True"] and role in ["Admin", "Support"]) else 0

    if not message:
        flash("Reply message cannot be empty.", "warning")
        return redirect(url_for("ticket_details", ticket_id=ticket_id))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT username, status, assigned_to, subject FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("my_tickets"))

    ticket_owner = ticket[0]
    ticket_status = ticket[1]
    assigned_agent = ticket[2]
    ticket_subject = ticket[3]

    # Permission check: Requester or Support/Admin can reply
    if role not in ["Admin", "Support"] and ticket_owner != username:
        connection.close()
        flash("Access denied.", "danger")
        return redirect(url_for("my_tickets"))

    # Process optional attachment on reply
    saved_filename = None
    original_filename = None
    if "attachment" in request.files:
        file = request.files["attachment"]
        if file and file.filename != "":
            if allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                saved_filename = f"{uuid.uuid4().hex}_{original_filename}"
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)
                file.save(file_path)
            else:
                flash("Invalid attachment file type.", "warning")

    cursor.execute("""
        INSERT INTO ticket_replies (ticket_id, username, role, message, is_internal, attachment, attachment_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, username, role, message, is_internal, saved_filename, original_filename))

    cursor.execute("UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
    connection.commit()
    connection.close()

    # Log activity
    act_type = "NOTE" if is_internal else "REPLY"
    act_msg = f"Staff internal note added by {username}" if is_internal else f"Reply posted by {username} ({role})"
    log_ticket_activity(ticket_id, username, act_type, message=act_msg)

    # Notifications Dispatch
    if is_internal:
        # If staff posted an internal note, notify assigned agent if not self
        if assigned_agent and assigned_agent != username:
            create_notification(
                recipient=assigned_agent,
                sender=username,
                title=f"🔒 Internal Note on Ticket #{ticket_id}",
                message=f"{username} posted a private staff note: {message[:60]}...",
                link=f"/ticket/{ticket_id}",
                ticket_id=ticket_id
            )
    else:
        # Public reply:
        if role in ["Admin", "Support"]:
            # Staff replied -> notify ticket requester
            create_notification(
                recipient=ticket_owner,
                sender=username,
                title=f"💬 New Reply on Ticket #{ticket_id}",
                message=f"Support Agent {username} responded to your ticket: '{ticket_subject}'",
                link=f"/ticket/{ticket_id}",
                ticket_id=ticket_id
            )
        else:
            # User replied -> notify assigned agent or all staff
            if assigned_agent:
                create_notification(
                    recipient=assigned_agent,
                    sender=username,
                    title=f"💬 Customer Reply on Ticket #{ticket_id}",
                    message=f"{username} sent an update on Ticket #{ticket_id}",
                    link=f"/ticket/{ticket_id}",
                    ticket_id=ticket_id
                )
            else:
                notify_all_staff(
                    sender=username,
                    title=f"💬 Customer Reply on Ticket #{ticket_id}",
                    message=f"{username} updated unassigned Ticket #{ticket_id}",
                    link=f"/ticket/{ticket_id}",
                    ticket_id=ticket_id
                )

    flash("Message posted to ticket conversation successfully.", "success")
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


@app.route("/ticket/<int:ticket_id>/assign", methods=["POST"])
@support_or_admin_required
def assign_ticket(ticket_id):
    assigned_to = request.form.get("assigned_to", "").strip()
    current_user = session["username"]

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, username, subject, assigned_to, status FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("dashboard"))

    old_assigned = ticket[3] or "Unassigned"
    requester = ticket[1]
    subject = ticket[2]

    # Handle unassign or assign
    if assigned_to == "":
        new_assigned = None
        new_assigned_label = "Unassigned"
    else:
        # Verify user exists and is staff
        cursor.execute("SELECT username, name FROM users WHERE username = ? AND role IN ('Admin', 'Support')", (assigned_to,))
        target_staff = cursor.fetchone()
        if not target_staff:
            connection.close()
            flash("Invalid staff member selected.", "danger")
            return redirect(url_for("ticket_details", ticket_id=ticket_id))
        new_assigned = target_staff[0]
        new_assigned_label = target_staff[1] or target_staff[0]

    cursor.execute("""
        UPDATE tickets
        SET assigned_to = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_assigned, ticket_id))

    connection.commit()
    connection.close()

    # Log in activity audit trail
    log_ticket_activity(
        ticket_id=ticket_id,
        username=current_user,
        activity_type="ASSIGNMENT",
        old_value=old_assigned,
        new_value=new_assigned_label,
        message=f"Ticket assigned to {new_assigned_label} by {current_user}."
    )

    # Notify newly assigned staff
    if new_assigned and new_assigned != current_user:
        create_notification(
            recipient=new_assigned,
            sender=current_user,
            title=f"📋 Ticket Assigned: #{ticket_id}",
            message=f"{current_user} assigned Ticket #{ticket_id} ('{subject}') to you.",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )

    # Notify requester
    if new_assigned:
        create_notification(
            recipient=requester,
            sender=current_user,
            title=f"👤 Agent Assigned to Ticket #{ticket_id}",
            message=f"Support Agent '{new_assigned_label}' has been assigned to your ticket.",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )

    flash(f"Ticket #{ticket_id} assignment updated to: {new_assigned_label}.", "success")
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


@app.route("/ticket/<int:ticket_id>/status", methods=["POST"])
@login_required
def update_ticket_status(ticket_id):
    username = session["username"]
    role = session.get("role", "User")
    new_status = request.form.get("status", "").strip()

    valid_statuses = ["Open", "In Progress", "Pending", "Resolved", "Closed"]
    if new_status not in valid_statuses:
        flash("Invalid status specified.", "danger")
        return redirect(url_for("ticket_details", ticket_id=ticket_id))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, username, subject, status, assigned_to FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("my_tickets"))

    ticket_owner = ticket[1]
    ticket_subject = ticket[2]
    old_status = ticket[3]
    assigned_agent = ticket[4]

    # Permission check: Standard users can only mark their own tickets as Resolved/Closed or Reopen
    if role not in ["Admin", "Support"] and ticket_owner != username:
        connection.close()
        flash("Access denied.", "danger")
        return redirect(url_for("my_tickets"))

    resolved_at_clause = ""
    closed_at_clause = ""
    if new_status == "Resolved":
        resolved_at_clause = ", resolved_at = CURRENT_TIMESTAMP"
    elif new_status == "Closed":
        closed_at_clause = ", closed_at = CURRENT_TIMESTAMP"

    cursor.execute(f"""
        UPDATE tickets
        SET status = ?, updated_at = CURRENT_TIMESTAMP {resolved_at_clause} {closed_at_clause}
        WHERE id = ?
    """, (new_status, ticket_id))

    connection.commit()
    connection.close()

    # Log in activity audit trail
    log_ticket_activity(
        ticket_id=ticket_id,
        username=username,
        activity_type="STATUS_CHANGE",
        old_value=old_status,
        new_value=new_status,
        message=f"Status updated from '{old_status}' to '{new_status}' by {username}."
    )

    # Notifications
    if role in ["Admin", "Support"]:
        # Staff changed status -> notify ticket owner
        create_notification(
            recipient=ticket_owner,
            sender=username,
            title=f"🔄 Ticket #{ticket_id} Status: {new_status}",
            message=f"Your ticket '{ticket_subject}' status was updated to '{new_status}'.",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )
    else:
        # User changed status -> notify assigned agent or all staff
        if assigned_agent:
            create_notification(
                recipient=assigned_agent,
                sender=username,
                title=f"🔄 Ticket #{ticket_id} Status: {new_status}",
                message=f"Requester {username} changed ticket status to '{new_status}'.",
                link=f"/ticket/{ticket_id}",
                ticket_id=ticket_id
            )

    flash(f"Ticket #{ticket_id} status changed to '{new_status}'.", "success")
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


@app.route("/ticket/<int:ticket_id>/reopen", methods=["POST"])
@login_required
def reopen_ticket(ticket_id):
    username = session["username"]
    role = session.get("role", "User")

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, username, subject, status, assigned_to FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("my_tickets"))

    ticket_owner = ticket[1]
    ticket_subject = ticket[2]
    old_status = ticket[3]
    assigned_agent = ticket[4]

    if role not in ["Admin", "Support"] and ticket_owner != username:
        connection.close()
        flash("Access denied.", "danger")
        return redirect(url_for("my_tickets"))

    cursor.execute("""
        UPDATE tickets
        SET status = 'Open', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (ticket_id,))

    connection.commit()
    connection.close()

    log_ticket_activity(
        ticket_id=ticket_id,
        username=username,
        activity_type="STATUS_CHANGE",
        old_value=old_status,
        new_value="Open",
        message=f"Ticket reopened by {username}."
    )

    if assigned_agent and assigned_agent != username:
        create_notification(
            recipient=assigned_agent,
            sender=username,
            title=f"⚠️ Ticket #{ticket_id} Reopened",
            message=f"{username} has reopened Ticket #{ticket_id} ('{ticket_subject}').",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )

    flash(f"Ticket #{ticket_id} has been reopened.", "info")
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


@app.route("/ticket/<int:ticket_id>/close", methods=["POST"])
@login_required
def close_ticket(ticket_id):
    username = session["username"]
    role = session.get("role", "User")

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, username, subject, status, assigned_to FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("my_tickets"))

    ticket_owner = ticket[1]
    old_status = ticket[3]

    if role not in ["Admin", "Support"] and ticket_owner != username:
        connection.close()
        flash("Access denied.", "danger")
        return redirect(url_for("my_tickets"))

    cursor.execute("""
        UPDATE tickets
        SET status = 'Closed', closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (ticket_id,))

    connection.commit()
    connection.close()

    log_ticket_activity(
        ticket_id=ticket_id,
        username=username,
        activity_type="STATUS_CHANGE",
        old_value=old_status,
        new_value="Closed",
        message=f"Ticket closed and archived by {username}."
    )

    flash(f"Ticket #{ticket_id} marked as Closed.", "success")
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


# ==============================================================================
# Ticket Escalation & Metadata Controls
# ==============================================================================

@app.route("/ticket/<int:ticket_id>/escalate", methods=["POST"])
@login_required
def escalate_ticket(ticket_id):
    username = session["username"]
    role = session.get("role", "User")
    escalation_level = request.form.get("escalation_level", "Tier 2 - Senior Support").strip()
    escalation_reason = request.form.get("escalation_reason", "").strip()
    target_agent = request.form.get("target_agent", "").strip()
    bump_priority = request.form.get("bump_priority", "").strip()

    if not escalation_reason:
        flash("Please provide a reason or justification for ticket escalation.", "warning")
        return redirect(url_for("ticket_details", ticket_id=ticket_id))

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, username, subject, status, priority, assigned_to, is_escalated FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("my_tickets"))

    ticket_owner = ticket[1]
    subject = ticket[2]
    old_priority = ticket[4]
    old_assigned = ticket[5]

    # Permission check: Requester can request escalation; Support/Admin can execute escalation
    if role not in ["Admin", "Support"] and ticket_owner != username:
        connection.close()
        flash("Access denied.", "danger")
        return redirect(url_for("my_tickets"))

    # If requester requests escalation, set level to 'Customer Requested' if not specified
    if role not in ["Admin", "Support"]:
        escalation_level = "Customer Escalation Request"

    # Optional priority bump
    new_priority = old_priority
    if bump_priority in ["High", "Critical"]:
        new_priority = bump_priority
    elif role in ["Admin", "Support"] and old_priority in ["Low", "Medium"]:
        new_priority = "High"

    new_assigned = old_assigned
    if target_agent and role in ["Admin", "Support"]:
        new_assigned = target_agent

    cursor.execute("""
        UPDATE tickets
        SET is_escalated = 1,
            escalation_level = ?,
            escalation_reason = ?,
            escalated_by = ?,
            escalated_at = CURRENT_TIMESTAMP,
            escalation_target = ?,
            priority = ?,
            assigned_to = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (escalation_level, escalation_reason, username, target_agent or None, new_priority, new_assigned, ticket_id))

    connection.commit()
    connection.close()

    # Log in activity audit trail
    log_ticket_activity(
        ticket_id=ticket_id,
        username=username,
        activity_type="ESCALATION",
        old_value=f"Standard ({old_priority})",
        new_value=f"{escalation_level} ({new_priority})",
        message=f"Escalated to '{escalation_level}' by {username}. Reason: {escalation_reason}"
    )

    # Dispatch notifications
    notify_all_staff(
        sender=username,
        title=f"🚨 Ticket #{ticket_id} Escalated to {escalation_level}",
        message=f"{username} escalated '{subject}'. Reason: {escalation_reason[:80]}",
        link=f"/ticket/{ticket_id}",
        ticket_id=ticket_id
    )

    if target_agent and target_agent != username:
        create_notification(
            recipient=target_agent,
            sender=username,
            title=f"🚨 Escalated Ticket Assigned: #{ticket_id}",
            message=f"Ticket #{ticket_id} has been escalated and routed directly to you.",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )

    if role in ["Admin", "Support"] and ticket_owner != username:
        create_notification(
            recipient=ticket_owner,
            sender=username,
            title=f"⚡ Ticket #{ticket_id} Priority Escalated",
            message=f"Your ticket has been escalated to {escalation_level} for expedited resolution.",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )

    flash(f"Ticket #{ticket_id} has been escalated to {escalation_level}.", "success")
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


@app.route("/ticket/<int:ticket_id>/de-escalate", methods=["POST"])
@support_or_admin_required
def de_escalate_ticket(ticket_id):
    username = session["username"]
    de_escalation_notes = request.form.get("de_escalation_notes", "").strip()

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, username, subject, escalation_level, assigned_to FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("my_tickets"))

    ticket_owner = ticket[1]
    subject = ticket[2]
    old_level = ticket[3] or "Escalated"
    assigned_agent = ticket[4]

    cursor.execute("""
        UPDATE tickets
        SET is_escalated = 0,
            escalation_level = 'De-escalated',
            escalation_notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (de_escalation_notes or f"De-escalated by {username}", ticket_id))

    connection.commit()
    connection.close()

    # Log in activity audit trail
    log_ticket_activity(
        ticket_id=ticket_id,
        username=username,
        activity_type="DE_ESCALATION",
        old_value=old_level,
        new_value="Standard Queue",
        message=f"Ticket de-escalated by {username}. Notes: {de_escalation_notes or 'Issue normalized'}"
    )

    if ticket_owner and ticket_owner != username:
        create_notification(
            recipient=ticket_owner,
            sender=username,
            title=f"✅ Ticket #{ticket_id} Escalation Resolved",
            message=f"The escalation on Ticket #{ticket_id} has been handled.",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )

    if assigned_agent and assigned_agent != username:
        create_notification(
            recipient=assigned_agent,
            sender=username,
            title=f"✅ Ticket #{ticket_id} Escalation Resolved",
            message=f"{username} resolved the escalation on Ticket #{ticket_id}.",
            link=f"/ticket/{ticket_id}",
            ticket_id=ticket_id
        )

    flash(f"Escalation on Ticket #{ticket_id} has been resolved / de-escalated.", "info")
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


@app.route("/ticket/<int:ticket_id>/update-meta", methods=["POST"])
@support_or_admin_required
def update_ticket_meta(ticket_id):
    username = session["username"]
    new_priority = request.form.get("priority", "").strip()
    new_category = request.form.get("category", "").strip()

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, username, subject, priority, category FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        flash("Ticket not found.", "danger")
        return redirect(url_for("my_tickets"))

    old_priority = ticket[3]
    old_category = ticket[4]

    updates = []
    params = []

    if new_priority and new_priority in ["Low", "Medium", "High", "Critical"] and new_priority != old_priority:
        updates.append("priority = ?")
        params.append(new_priority)
        log_ticket_activity(
            ticket_id=ticket_id,
            username=username,
            activity_type="PRIORITY_CHANGE",
            old_value=old_priority,
            new_value=new_priority,
            message=f"Priority modified from '{old_priority}' to '{new_priority}' by {username}."
        )

    if new_category and new_category != old_category:
        updates.append("category = ?")
        params.append(new_category)
        log_ticket_activity(
            ticket_id=ticket_id,
            username=username,
            activity_type="CATEGORY_CHANGE",
            old_value=old_category,
            new_value=new_category,
            message=f"Category modified from '{old_category}' to '{new_category}' by {username}."
        )

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(ticket_id)
        cursor.execute(f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?", tuple(params))
        connection.commit()
        flash("Ticket properties updated successfully.", "success")
    else:
        flash("No changes made to ticket properties.", "info")

    connection.close()
    return redirect(url_for("ticket_details", ticket_id=ticket_id))


# ==============================================================================
# Support History & System Audit Portal Routes
# ==============================================================================

@app.route("/support-history")
@support_or_admin_required
def support_history_view():
    username = session["username"]
    role = session.get("role", "User")

    activity_type = request.args.get("type", "").strip()
    actor = request.args.get("actor", "").strip()
    ticket_id_q = request.args.get("ticket_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    search_q = request.args.get("q", "").strip()

    conditions = []
    params = []

    if activity_type and activity_type.lower() != "all":
        conditions.append("a.activity_type = ?")
        params.append(activity_type)

    if actor:
        conditions.append("a.username LIKE ?")
        params.append(f"%{actor}%")

    if ticket_id_q:
        conditions.append("CAST(a.ticket_id AS TEXT) LIKE ?")
        params.append(f"%{ticket_id_q}%")

    if date_from:
        conditions.append("a.created_at >= ?")
        params.append(f"{date_from} 00:00:00")

    if date_to:
        conditions.append("a.created_at <= ?")
        params.append(f"{date_to} 23:59:59")

    if search_q:
        conditions.append("(a.message LIKE ? OR t.subject LIKE ? OR a.old_value LIKE ? OR a.new_value LIKE ?)")
        params.extend([f"%{search_q}%"] * 4)

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT 
            a.id, a.ticket_id, a.username, a.activity_type, 
            a.old_value, a.new_value, a.message, a.created_at,
            t.subject, t.status, t.priority, t.username as requester
        FROM ticket_activities a
        LEFT JOIN tickets t ON a.ticket_id = t.id
        {where_sql}
        ORDER BY a.id DESC LIMIT 150
    """

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute(query, tuple(params))
    activities = cursor.fetchall()

    # Unique activity types for filter dropdown
    cursor.execute("SELECT DISTINCT activity_type FROM ticket_activities ORDER BY activity_type ASC")
    types_list = [r[0] for r in cursor.fetchall() if r[0]]

    # Total activities stats
    cursor.execute("SELECT COUNT(*) FROM ticket_activities")
    total_activities = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ticket_activities WHERE activity_type = 'ESCALATION'")
    total_escalations = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ticket_activities WHERE activity_type = 'STATUS_CHANGE'")
    total_status_changes = cursor.fetchone()[0]

    connection.close()

    stats = {
        "total_activities": total_activities,
        "total_escalations": total_escalations,
        "total_status_changes": total_status_changes,
        "filtered_count": len(activities)
    }

    return render_template(
        "support_history.html",
        username=username,
        role=role,
        activities=activities,
        types_list=types_list,
        stats=stats,
        current_filters={
            "type": activity_type,
            "actor": actor,
            "ticket_id": ticket_id_q,
            "date_from": date_from,
            "date_to": date_to,
            "q": search_q
        }
    )


@app.route("/support-history/export")
@support_or_admin_required
def export_support_history():
    activity_type = request.args.get("type", "").strip()
    actor = request.args.get("actor", "").strip()
    ticket_id_q = request.args.get("ticket_id", "").strip()

    conditions = []
    params = []

    if activity_type and activity_type.lower() != "all":
        conditions.append("a.activity_type = ?")
        params.append(activity_type)
    if actor:
        conditions.append("a.username LIKE ?")
        params.append(f"%{actor}%")
    if ticket_id_q:
        conditions.append("CAST(a.ticket_id AS TEXT) LIKE ?")
        params.append(f"%{ticket_id_q}%")

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT 
            a.id, a.ticket_id, t.subject, a.username, a.activity_type, 
            a.old_value, a.new_value, a.message, a.created_at
        FROM ticket_activities a
        LEFT JOIN tickets t ON a.ticket_id = t.id
        {where_sql}
        ORDER BY a.id DESC
    """

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    connection.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Audit ID", "Ticket ID", "Ticket Subject", "Actor Username", "Activity Type", "Previous Value", "New Value", "Message / Description", "Timestamp"])
    for r in rows:
        cw.writerow(list(r))

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=helpdesk_support_history_audit.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output


@app.route("/tickets/export")
@login_required
def export_tickets():
    username = session["username"]
    role = session.get("role", "User")

    filters = {
        "username": username,
        "role": role,
        "q": request.args.get("q", "").strip(),
        "status": request.args.get("status", "").strip(),
        "priority": request.args.get("priority", "").strip(),
        "category": request.args.get("category", "").strip(),
        "assigned_to": request.args.get("assigned_to", "").strip(),
        "is_escalated": request.args.get("is_escalated", "").strip(),
        "date_from": request.args.get("date_from", "").strip(),
        "date_to": request.args.get("date_to", "").strip()
    }
    sort_by = request.args.get("sort_by", "id").strip()
    sort_order = request.args.get("sort_order", "desc").strip()

    tickets = query_tickets(filters=filters, sort_by=sort_by, sort_order=sort_order)

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Ticket ID", "Requester", "Category", "Priority", "Subject", "Description",
        "Status", "Assigned Agent", "Is Escalated", "Escalation Level", "Escalation Reason",
        "Created At", "Updated At", "Resolved At", "Closed At"
    ])
    for t in tickets:
        cw.writerow([
            t[0], t[1], t[2], t[3], t[4], t[5],
            t[8], t[9] or "Unassigned", "Yes" if t[12] else "No", t[13] or "None", t[14] or "",
            t[19], t[20], t[10] or "", t[11] or ""
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=helpdesk_tickets_export_{role.lower()}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output


@app.route("/api/user/<target_username>/history")
@login_required
def api_user_support_history(target_username):
    current_user = session["username"]
    role = session.get("role", "User")

    # Safety permission: standard user can only view their own history
    if role not in ["Admin", "Support"] and target_username != current_user:
        return jsonify({"error": "Unauthorized"}), 403

    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()

    cursor.execute("SELECT id, name, email, role, created_at FROM users WHERE username = ?", (target_username,))
    u = cursor.fetchone()
    if not u:
        connection.close()
        return jsonify({"error": "User not found"}), 404

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ?", (target_username,))
    total_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'Resolved'", (target_username,))
    resolved_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND status = 'Open'", (target_username,))
    open_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE username = ? AND is_escalated = 1", (target_username,))
    escalated_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT id, subject, category, priority, status, created_at, is_escalated
        FROM tickets 
        WHERE username = ?
        ORDER BY id DESC LIMIT 10
    """, (target_username,))
    ticket_rows = cursor.fetchall()
    connection.close()

    history_list = []
    for r in ticket_rows:
        history_list.append({
            "id": r[0],
            "subject": r[1],
            "category": r[2],
            "priority": r[3],
            "status": r[4],
            "created_at": r[5],
            "is_escalated": bool(r[6])
        })

    return jsonify({
        "username": target_username,
        "name": u[1],
        "email": u[2],
        "role": u[3],
        "created_at": u[4],
        "total_tickets": total_tickets,
        "resolved_tickets": resolved_tickets,
        "open_tickets": open_tickets,
        "escalated_tickets": escalated_count,
        "recent_tickets": history_list
    })


# ==============================================================================
# Ticket Listings & Downloads
# ==============================================================================

@app.route("/download/<path:filename>")
@login_required
def download_file(filename):
    safe_filename = secure_filename(filename)
    return send_from_directory(app.config["UPLOAD_FOLDER"], safe_filename, as_attachment=True)


@app.route("/my-tickets")
@login_required
def my_tickets():
    username = session["username"]
    role = session.get("role", "User")

    # Extract all query params
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip()
    priority = request.args.get("priority", "all").strip()
    category = request.args.get("category", "all").strip()
    assigned_to = request.args.get("assigned_to", "all").strip()
    is_escalated = request.args.get("is_escalated", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort_by = request.args.get("sort_by", "id").strip()
    sort_order = request.args.get("sort_order", "desc").strip()

    filters = {
        "username": username,
        "role": role,
        "q": q,
        "status": status,
        "priority": priority,
        "category": category,
        "assigned_to": assigned_to,
        "is_escalated": is_escalated,
        "date_from": date_from,
        "date_to": date_to
    }

    tickets = query_tickets(filters=filters, sort_by=sort_by, sort_order=sort_order)

    # Categories list for filter dropdown
    connection = sqlite3.connect("helpdesk.db")
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM ticket_categories WHERE is_active = 1 UNION SELECT DISTINCT category FROM tickets ORDER BY 1 ASC")
    categories = [r[0] for r in cursor.fetchall() if r[0]]
    connection.close()

    staff_list = get_active_staff() if role in ["Admin", "Support"] else []

    current_filters = {
        "q": q,
        "status": status,
        "priority": priority,
        "category": category,
        "assigned_to": assigned_to,
        "is_escalated": is_escalated,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order
    }

    return render_template(
        "my_tickets.html",
        username=username,
        role=role,
        tickets=tickets,
        categories=categories,
        staff_list=staff_list,
        current_filters=current_filters
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
