import os
import sqlite3
import json
from app import app, init_db, query_tickets, create_database_backup, allowed_file
from werkzeug.security import generate_password_hash

def run_tests():
    print("=== STARTING COMPREHENSIVE HELPDESK SUITE VERIFICATION ===")
    init_db()
    client = app.test_client()

    conn = sqlite3.connect("helpdesk.db")
    c = conn.cursor()

    pwd = generate_password_hash("password123")

    c.execute("INSERT OR IGNORE INTO users (name, email, username, password, role) VALUES ('Admin Master', 'admin@helpdesk.local', 'admin_tester', ?, 'Admin')", (pwd,))
    c.execute("INSERT OR IGNORE INTO users (name, email, username, password, role) VALUES ('Support Agent Joe', 'joe@helpdesk.local', 'joe_support', ?, 'Support')", (pwd,))
    c.execute("INSERT OR IGNORE INTO users (name, email, username, password, role) VALUES ('Senior Dev Lead', 'lead@helpdesk.local', 'lead_specialist', ?, 'Support')", (pwd,))
    c.execute("INSERT OR IGNORE INTO users (name, email, username, password, role) VALUES ('Client Alice', 'alice@company.local', 'alice_client', ?, 'User')", (pwd,))
    c.execute("INSERT OR IGNORE INTO users (name, email, username, password, role) VALUES ('Client Bob', 'bob@company.local', 'bob_client', ?, 'User')", (pwd,))
    conn.commit()

    print("[PASS] Test users verified in database.")

    # -------------------------------------------------------------
    # Test 1: Ticket Creation with various categories & priorities
    # -------------------------------------------------------------
    with client.session_transaction() as sess:
        sess["username"] = "alice_client"
        sess["name"] = "Client Alice"
        sess["role"] = "User"
        sess["user_id"] = 101

    res1 = client.post("/create-ticket", data={
        "category": "Software Bug",
        "priority": "High",
        "subject": "Payment Gateway Timeout",
        "description": "Getting timeout error 504 when attempting checkout in payment portal."
    }, follow_redirects=True)
    assert res1.status_code == 200

    res2 = client.post("/create-ticket", data={
        "category": "Billing Issue",
        "priority": "Low",
        "subject": "Invoice PDF download missing VAT",
        "description": "The downloaded PDF invoice does not contain the European VAT tax ID."
    }, follow_redirects=True)
    assert res2.status_code == 200

    res3 = client.post("/create-ticket", data={
        "category": "Network & Access",
        "priority": "Critical",
        "subject": "Database connection pool exhausted",
        "description": "Production database rejects new connections due to max limit."
    }, follow_redirects=True)
    assert res3.status_code == 200

    c.execute("SELECT id, subject, priority, category FROM tickets WHERE username = 'alice_client' ORDER BY id DESC")
    user_tickets = c.fetchall()
    assert len(user_tickets) >= 3
    ticket_crit = user_tickets[0][0] # Critical ticket
    ticket_bill = user_tickets[1][0] # Billing ticket
    ticket_pay = user_tickets[2][0]  # Payment ticket
    print(f"[PASS] Created 3 test tickets: IDs #{ticket_crit} (Critical), #{ticket_bill} (Low), #{ticket_pay} (High).")

    # -------------------------------------------------------------
    # Test 2: Search, Multi-Filter & Sorting Queries
    # -------------------------------------------------------------
    # Direct query_tickets tests
    q_res = query_tickets(filters={"q": "Payment", "username": "alice_client", "role": "User"})
    assert any(t[0] == ticket_pay for t in q_res)
    assert not any(t[0] == ticket_bill for t in q_res)
    print("[PASS] query_tickets: keyword search (?q=Payment) matches only relevant tickets.")

    cat_query_res = query_tickets(filters={"category": "Billing Issue", "username": "alice_client", "role": "User"})
    assert any(t[0] == ticket_bill for t in cat_query_res)
    assert not any(t[0] == ticket_pay for t in cat_query_res)
    print("[PASS] query_tickets: category filter (?category=Billing Issue) verified.")

    prio_query_res = query_tickets(filters={"priority": "Critical", "username": "alice_client", "role": "User"})
    assert any(t[0] == ticket_crit for t in prio_query_res)
    assert not any(t[0] == ticket_bill for t in prio_query_res)
    print("[PASS] query_tickets: priority filter (?priority=Critical) verified.")

    # Sort by priority query test
    sort_query_res = query_tickets(filters={"username": "alice_client", "role": "User"}, sort_by="priority", sort_order="desc")
    # In DESC priority sort, Critical comes before High and Low
    crit_idx = next(i for i, t in enumerate(sort_query_res) if t[0] == ticket_crit)
    bill_idx = next(i for i, t in enumerate(sort_query_res) if t[0] == ticket_bill)
    assert crit_idx < bill_idx
    print("[PASS] query_tickets: priority-weighted sorting (Critical > High > Medium > Low) verified.")

    # Web endpoints for search and filter
    search_res = client.get("/my-tickets?q=Payment")
    assert search_res.status_code == 200
    assert f"#{ticket_pay}".encode() in search_res.data
    print("[PASS] Endpoint /my-tickets?q=Payment rendered ticket successfully.")

    cat_res = client.get("/my-tickets?category=Billing+Issue")
    assert cat_res.status_code == 200
    assert f"#{ticket_bill}".encode() in cat_res.data
    print("[PASS] Endpoint /my-tickets?category=Billing+Issue rendered ticket successfully.")

    # -------------------------------------------------------------
    # Test 3: Escalation Workflow (Trigger, Route, Priority Bump)
    # -------------------------------------------------------------
    with client.session_transaction() as sess:
        sess["username"] = "joe_support"
        sess["name"] = "Support Agent Joe"
        sess["role"] = "Support"
        sess["user_id"] = 102

    # Escalate Ticket #ticket_pay to Tier 2 with re-routing to lead_specialist and priority bump to Critical
    esc_res = client.post(f"/ticket/{ticket_pay}/escalate", data={
        "escalation_level": "Tier 2 - Senior Support",
        "escalation_reason": "Production impact reported by multiple users. Needs DB cache inspection.",
        "bump_priority": "Critical",
        "target_agent": "lead_specialist",
        "notes": "Escalated for immediate triage by lead engineer."
    }, follow_redirects=True)
    assert esc_res.status_code == 200

    c.execute("SELECT is_escalated, escalation_level, priority, assigned_to, escalated_by FROM tickets WHERE id = ?", (ticket_pay,))
    esc_row = c.fetchone()
    assert esc_row[0] == 1
    assert esc_row[1] == "Tier 2 - Senior Support"
    assert esc_row[2] == "Critical"
    assert esc_row[3] == "lead_specialist"
    assert esc_row[4] == "joe_support"
    print(f"[PASS] Ticket #{ticket_pay} successfully escalated: Level='{esc_row[1]}', Priority='{esc_row[2]}', AssignedTo='{esc_row[3]}'.")

    # Verify Escalation Notification sent to assigned specialist and admin
    c.execute("SELECT username, title FROM notifications WHERE ticket_id = ? AND title LIKE '%Escalat%'", (ticket_pay,))
    notifs = c.fetchall()
    assert len(notifs) >= 1
    print(f"[PASS] Escalation notifications generated: {[n[0] for n in notifs]}")

    # Check query_tickets for escalated filter
    esc_tickets = query_tickets(filters={"is_escalated": "1", "role": "Support", "username": "joe_support"})
    assert any(t[0] == ticket_pay for t in esc_tickets)
    print("[PASS] Filter '?is_escalated=1' correctly contains escalated ticket.")

    # -------------------------------------------------------------
    # Test 4: Ticket Metadata Quick Update Endpoint
    # -------------------------------------------------------------
    meta_res = client.post(f"/ticket/{ticket_bill}/update-meta", data={
        "priority": "Medium",
        "category": "Hardware & Devices"
    }, follow_redirects=True)
    assert meta_res.status_code == 200

    c.execute("SELECT priority, category FROM tickets WHERE id = ?", (ticket_bill,))
    meta_row = c.fetchone()
    assert meta_row[0] == "Medium"
    assert meta_row[1] == "Hardware & Devices"
    print(f"[PASS] Quick metadata update verified on Ticket #{ticket_bill}: Priority={meta_row[0]}, Category={meta_row[1]}.")

    # -------------------------------------------------------------
    # Test 5: De-escalation Workflow
    # -------------------------------------------------------------
    with client.session_transaction() as sess:
        sess["username"] = "admin_tester"
        sess["name"] = "Admin Master"
        sess["role"] = "Admin"
        sess["user_id"] = 103

    de_res = client.post(f"/ticket/{ticket_pay}/de-escalate", data={
        "resolution_summary": "Root cause identified and hotfix deployed. Escalation resolved."
    }, follow_redirects=True)
    assert de_res.status_code == 200

    c.execute("SELECT is_escalated FROM tickets WHERE id = ?", (ticket_pay,))
    assert c.fetchone()[0] == 0
    print(f"[PASS] Ticket #{ticket_pay} successfully de-escalated (is_escalated=0).")

    # -------------------------------------------------------------
    # Test 6: Support History & Audit Trail Portal & API
    # -------------------------------------------------------------
    # View Support History Portal
    hist_portal_res = client.get("/support-history")
    assert hist_portal_res.status_code == 200
    assert b"Support History" in hist_portal_res.data
    print("[PASS] Support History & Audit Trail portal rendered successfully.")

    # Filter Support History by event_type=ESCALATION
    hist_filter_res = client.get("/support-history?type=ESCALATION")
    assert hist_filter_res.status_code == 200
    assert b"ESCALATION" in hist_filter_res.data
    print("[PASS] Support History filtered by 'ESCALATION' event type.")

    # Customer History JSON API
    api_res = client.get("/api/user/alice_client/history")
    assert api_res.status_code == 200
    api_data = json.loads(api_res.data)
    assert api_data["username"] == "alice_client"
    assert api_data["total_tickets"] >= 3
    print(f"[PASS] JSON API /api/user/alice_client/history returned {api_data['total_tickets']} tickets and summary stats.")

    # -------------------------------------------------------------
    # Test 7: CSV Exports
    # -------------------------------------------------------------
    csv_tickets_res = client.get("/tickets/export?is_escalated=&sort_by=id&sort_order=desc")
    assert csv_tickets_res.status_code == 200
    assert csv_tickets_res.headers.get("Content-Type", "").startswith("text/csv")
    assert b"Ticket ID,Requester,Category,Priority,Subject" in csv_tickets_res.data
    print("[PASS] Tickets CSV export (/tickets/export) validated with proper CSV headers and rows.")

    csv_audit_res = client.get("/support-history/export?type=ESCALATION")
    assert csv_audit_res.status_code == 200
    assert csv_audit_res.headers.get("Content-Type", "").startswith("text/csv")
    assert b"Audit ID,Ticket ID,Ticket Subject,Actor Username,Activity Type" in csv_audit_res.data
    print("[PASS] Support History CSV export (/support-history/export) validated.")

    # -------------------------------------------------------------
    # Test 8: Dashboard Escalation Queues & Activity Feeds
    # -------------------------------------------------------------
    # Support Dashboard
    with client.session_transaction() as sess:
        sess["username"] = "joe_support"
        sess["name"] = "Support Agent Joe"
        sess["role"] = "Support"
        sess["user_id"] = 102

    sup_dash_res = client.get("/dashboard")
    assert sup_dash_res.status_code == 200
    assert b"Escalated Queue" in sup_dash_res.data
    print("[PASS] Support Dashboard includes Escalated Queue metrics.")

    # Admin Dashboard
    with client.session_transaction() as sess:
        sess["username"] = "admin_tester"
        sess["name"] = "Admin Master"
        sess["role"] = "Admin"
        sess["user_id"] = 103

    admin_dash_res = client.get("/dashboard")
    assert admin_dash_res.status_code == 200
    assert b"Escalated Tickets" in admin_dash_res.data
    assert b"Audit Trail Live Feed" in admin_dash_res.data
    assert b"Operations & Monitoring" in admin_dash_res.data
    assert b"Support Agents" in admin_dash_res.data
    assert b"Ticket Categories" in admin_dash_res.data
    assert b"Priorities & SLA" in admin_dash_res.data
    print("[PASS] Admin Dashboard includes Escalated Tickets metrics, Audit Trail Live Feed, and all management sections.")

    # -------------------------------------------------------------
    # Test 9: Admin User Management (Create, Edit, Toggle Status, Reset Password)
    # -------------------------------------------------------------
    c.execute("DELETE FROM users WHERE username = 'david_ops'")
    c.execute("DELETE FROM ticket_categories WHERE name LIKE 'Database &%'")
    c.execute("DELETE FROM ticket_priorities WHERE name LIKE '%Blocker%'")
    conn.commit()

    # 9a. Create new user via admin endpoint
    create_u_res = client.post("/admin/user/create", data={
        "name": "David Operations",
        "email": "david@helpdesk.local",
        "username": "david_ops",
        "password": "initialPassword123",
        "role": "Support",
        "department": "Infrastructure",
        "status": "Active"
    }, follow_redirects=True)
    assert create_u_res.status_code == 200

    c.execute("SELECT id, name, role, status, department FROM users WHERE username = 'david_ops'")
    d_user = c.fetchone()
    assert d_user is not None
    assert d_user[1] == "David Operations"
    assert d_user[2] == "Support"
    assert d_user[3] == "Active"
    assert d_user[4] == "Infrastructure"
    d_user_id = d_user[0]
    print(f"[PASS] Admin created user 'david_ops' (ID #{d_user_id}) with Support role.")

    # 9b. Edit user
    edit_u_res = client.post(f"/admin/user/{d_user_id}/edit", data={
        "name": "David Senior Ops",
        "email": "david_senior@helpdesk.local",
        "role": "Support",
        "department": "Cloud Operations",
        "status": "Active"
    }, follow_redirects=True)
    assert edit_u_res.status_code == 200

    c.execute("SELECT name, department FROM users WHERE id = ?", (d_user_id,))
    assert c.fetchone() == ("David Senior Ops", "Cloud Operations")
    print("[PASS] Admin successfully edited user details.")

    # 9c. Toggle Status (Suspend / Activate)
    toggle_status_res = client.post(f"/admin/user/{d_user_id}/toggle-status", follow_redirects=True)
    assert toggle_status_res.status_code == 200
    c.execute("SELECT status FROM users WHERE id = ?", (d_user_id,))
    assert c.fetchone()[0] == "Suspended"
    print("[PASS] Admin toggled user status to 'Suspended'.")

    # Verify suspended user cannot log in
    client.get("/logout")
    bad_login_res = client.post("/login", data={"username": "david_ops", "password": "initialPassword123"})
    assert b"account has been suspended" in bad_login_res.data
    print("[PASS] Suspended user successfully blocked from signing in.")

    # Restore session as admin
    with client.session_transaction() as sess:
        sess["username"] = "admin_tester"
        sess["name"] = "Admin Master"
        sess["role"] = "Admin"
        sess["user_id"] = 103

    client.post(f"/admin/user/{d_user_id}/toggle-status", follow_redirects=True)
    c.execute("SELECT status FROM users WHERE id = ?", (d_user_id,))
    assert c.fetchone()[0] == "Active"

    # 9d. Reset password
    pwd_reset_res = client.post(f"/admin/user/{d_user_id}/reset-password", data={"new_password": "NewSecretPassword99"}, follow_redirects=True)
    assert pwd_reset_res.status_code == 200
    c.execute("SELECT password FROM users WHERE id = ?", (d_user_id,))
    from werkzeug.security import check_password_hash
    assert check_password_hash(c.fetchone()[0], "NewSecretPassword99")
    print("[PASS] Admin successfully reset user password.")

    # -------------------------------------------------------------
    # Test 10: Category Management (Create, Update, Toggle Status, Delete)
    # -------------------------------------------------------------
    cat_create_res = client.post("/admin/category/create", data={
        "name": "Database & Storage",
        "description": "SQL errors, indexing, storage volumes, and backup restore",
        "color": "#0ea5e9",
        "icon": "fa-database"
    }, follow_redirects=True)
    assert cat_create_res.status_code == 200

    c.execute("SELECT id, name, color, icon, is_active FROM ticket_categories WHERE name = 'Database & Storage'")
    db_cat = c.fetchone()
    assert db_cat is not None
    db_cat_id = db_cat[0]
    print(f"[PASS] Category '{db_cat[1]}' created successfully.")

    # Update category
    cat_update_res = client.post(f"/admin/category/{db_cat_id}/update", data={
        "name": "Database & Cloud Storage",
        "description": "SQL and NoSQL cloud clusters",
        "color": "#0284c7",
        "icon": "fa-server",
        "is_active": "1"
    }, follow_redirects=True)
    assert cat_update_res.status_code == 200
    c.execute("SELECT name, icon FROM ticket_categories WHERE id = ?", (db_cat_id,))
    assert c.fetchone() == ("Database & Cloud Storage", "fa-server")
    print("[PASS] Category updated successfully.")

    # Toggle category active state
    client.post(f"/admin/category/{db_cat_id}/toggle-status", follow_redirects=True)
    c.execute("SELECT is_active FROM ticket_categories WHERE id = ?", (db_cat_id,))
    assert c.fetchone()[0] == 0
    client.post(f"/admin/category/{db_cat_id}/toggle-status", follow_redirects=True)
    c.execute("SELECT is_active FROM ticket_categories WHERE id = ?", (db_cat_id,))
    assert c.fetchone()[0] == 1
    print("[PASS] Category active/inactive toggle verified.")

    # -------------------------------------------------------------
    # Test 11: Priority & SLA Policy Management
    # -------------------------------------------------------------
    prio_create_res = client.post("/admin/priority/create", data={
        "name": "Blocker",
        "level": 0,
        "color": "#991b1b",
        "sla_response_hours": 1,
        "description": "Complete production halt. 1-hour executive SLA."
    }, follow_redirects=True)
    assert prio_create_res.status_code == 200

    c.execute("SELECT id, name, level, sla_response_hours FROM ticket_priorities WHERE name = 'Blocker'")
    blocker_prio = c.fetchone()
    assert blocker_prio is not None
    blocker_prio_id = blocker_prio[0]
    assert blocker_prio[3] == 1
    print(f"[PASS] Priority Tier '{blocker_prio[1]}' (Level 0, 1h SLA) created.")

    # Update priority
    client.post(f"/admin/priority/{blocker_prio_id}/update", data={
        "name": "P0 - Emergency Blocker",
        "level": 0,
        "color": "#7f1d1d",
        "sla_response_hours": 1,
        "description": "Emergency Blocker updated",
        "is_active": "1"
    }, follow_redirects=True)
    c.execute("SELECT name FROM ticket_priorities WHERE id = ?", (blocker_prio_id,))
    assert c.fetchone()[0] == "P0 - Emergency Blocker"
    print("[PASS] Priority tier updated successfully.")

    # -------------------------------------------------------------
    # Test 12: Support Agent Workload Balancing
    # -------------------------------------------------------------
    # Assign tickets to joe_support
    c.execute("UPDATE tickets SET assigned_to = 'joe_support', status = 'In Progress' WHERE id IN (?, ?)", (ticket_pay, ticket_bill))
    conn.commit()

    reassign_res = client.post("/admin/agents/reassign-workload", data={
        "source_agent": "joe_support",
        "target_agent": "david_ops",
        "reason": "On-call rotation shift change"
    }, follow_redirects=True)
    assert reassign_res.status_code == 200

    c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = 'david_ops' AND status NOT IN ('Resolved', 'Closed')")
    assert c.fetchone()[0] >= 2
    print("[PASS] Reassigned open tickets from 'joe_support' to 'david_ops' via workload console.")

    # -------------------------------------------------------------
    # Test 13: Bulk Operations Console
    # -------------------------------------------------------------
    bulk_res = client.post("/admin/tickets/bulk-action", data={
        "ticket_ids": f"{ticket_pay},{ticket_bill}",
        "bulk_action": "status",
        "target_value": "Resolved"
    }, follow_redirects=True)
    assert bulk_res.status_code == 200

    c.execute("SELECT status FROM tickets WHERE id IN (?, ?)", (ticket_pay, ticket_bill))
    assert all(r[0] == "Resolved" for r in c.fetchall())
    print(f"[PASS] Bulk status change to 'Resolved' executed on tickets #{ticket_pay} and #{ticket_bill}.")

    # -------------------------------------------------------------
    # Test 14: Help Desk Operations Report CSV Export
    # -------------------------------------------------------------
    ops_csv_res = client.get("/admin/operations/export")
    assert ops_csv_res.status_code == 200
    assert ops_csv_res.headers.get("Content-Type", "").startswith("text/csv")
    assert b"HELPDESK OPERATIONS & PERFORMANCE AUDIT REPORT" in ops_csv_res.data
    assert b"SUPPORT AGENT WORKLOAD & RESOLUTION METRICS" in ops_csv_res.data
    assert b"TICKET CATEGORY DISTRIBUTION" in ops_csv_res.data
    assert b"PRIORITY TIERS & SLA TARGETS" in ops_csv_res.data
    print("[PASS] Help Desk Operations executive report CSV export verified.")

    # -------------------------------------------------------------
    # Test 15: Week 7 Reports & Analytics Portal & Period Filters
    # -------------------------------------------------------------
    with client.session_transaction() as sess:
        sess["username"] = "admin_tester"
        sess["role"] = "Admin"
        sess["name"] = "Admin Master"

    rep_res = client.get("/reports")
    assert rep_res.status_code == 200
    assert b"Help Desk Reports & Analytics" in rep_res.data
    assert b"Ticket Status Summaries" in rep_res.data
    assert b"Monthly Support Statistics" in rep_res.data
    assert b"Category-Wise Issues" in rep_res.data
    assert b"Support Agent Performance" in rep_res.data
    assert b"Pending Tickets & Aging Backlog" in rep_res.data

    # Period filters
    assert client.get("/reports?period=7d").status_code == 200
    assert client.get("/reports?period=30d").status_code == 200
    assert client.get("/reports?period=month").status_code == 200
    assert client.get("/reports?period=year").status_code == 200
    assert client.get("/analytics").status_code == 200
    print("[PASS] Week 7 Reports & Analytics portal rendered with all sections and period filters.")

    # Authorization verification: non-staff user blocked
    with client.session_transaction() as sess:
        sess["username"] = "alice_client"
        sess["role"] = "User"
    user_blocked_res = client.get("/reports", follow_redirects=True)
    assert user_blocked_res.status_code == 200
    assert b"Access denied" in user_blocked_res.data
    print("[PASS] Access control verified: standard Users blocked from staff analytics.")

    # -------------------------------------------------------------
    # Test 16: Week 7 JSON Analytics API (/api/reports/stats)
    # -------------------------------------------------------------
    with client.session_transaction() as sess:
        sess["username"] = "admin_tester"
        sess["role"] = "Admin"

    api_res = client.get("/api/reports/stats")
    assert api_res.status_code == 200
    api_json = json.loads(api_res.data)
    assert api_json["success"] is True
    data_payload = api_json["data"]
    assert "kpis" in data_payload
    assert "priority_stats" in data_payload
    assert "category_stats" in data_payload
    assert "agent_stats" in data_payload
    assert "pending_tickets_list" in data_payload
    assert "monthly_stats" in data_payload
    assert data_payload["kpis"]["total_tickets"] > 0
    assert "avg_resolution_hours" in data_payload["kpis"]
    print(f"[PASS] JSON Analytics API validated: {data_payload['kpis']['total_tickets']} tickets, MTTR: {data_payload['kpis']['avg_resolution_hours']}h.")

    # -------------------------------------------------------------
    # Test 17: Week 7 Dedicated CSV Reports Exports
    # -------------------------------------------------------------
    exp_summary = client.get("/reports/export/summary?period=all")
    assert exp_summary.status_code == 200
    assert exp_summary.headers.get("Content-Type", "").startswith("text/csv")
    assert b"EXECUTIVE OPERATIONS & KPI REPORT" in exp_summary.data
    assert b"Average Resolution Time" in exp_summary.data

    exp_cats = client.get("/reports/export/categories?period=all")
    assert exp_cats.status_code == 200
    assert exp_cats.headers.get("Content-Type", "").startswith("text/csv")
    assert b"CATEGORY-WISE ISSUES & RESOLUTION REPORT" in exp_cats.data

    exp_agents = client.get("/reports/export/agents?period=all")
    assert exp_agents.status_code == 200
    assert exp_agents.headers.get("Content-Type", "").startswith("text/csv")
    assert b"SUPPORT AGENT PERFORMANCE SCORECARDS" in exp_agents.data

    exp_monthly = client.get("/reports/export/monthly")
    assert exp_monthly.status_code == 200
    assert exp_monthly.headers.get("Content-Type", "").startswith("text/csv")
    assert b"MONTHLY SUPPORT STATISTICS & HISTORICAL TRENDS" in exp_monthly.data
    print("[PASS] All 4 dedicated Week 7 CSV report exports verified.")

    # -------------------------------------------------------------
    # Test 18: Pending Tickets & Aging Backlog Analysis
    # -------------------------------------------------------------
    c.execute("""
        INSERT INTO tickets (username, category, priority, subject, description, status)
        VALUES ('alice_client', 'Technical Issue', 'Medium', 'Pending Vendor Clarification', 'Awaiting API token response from external provider.', 'Pending')
    """)
    conn.commit()
    pending_ticket_id = c.lastrowid

    p_check_res = client.get("/api/reports/stats")
    p_check_json = json.loads(p_check_res.data)["data"]
    assert p_check_json["kpis"]["pending_tickets"] >= 1
    assert any(pt["id"] == pending_ticket_id for pt in p_check_json["pending_tickets_list"])
    assert p_check_json["pending_aging"]["under_24h"] >= 1
    print(f"[PASS] Pending ticket #{pending_ticket_id} verified in aging backlog analysis.")

    # Clean up pending test ticket
    c.execute("DELETE FROM tickets WHERE id = ?", (pending_ticket_id,))
    conn.commit()

    # -------------------------------------------------------------
    # Test 19: Security Implementation (HTTP Response Headers & Session Cookies)
    # -------------------------------------------------------------
    sec_res = client.get("/")
    assert sec_res.headers.get("X-Content-Type-Options") == "nosniff"
    assert sec_res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert sec_res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert sec_res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert app.config.get("SESSION_COOKIE_HTTPONLY") is True
    assert app.config.get("SESSION_COOKIE_SAMESITE") == "Lax"
    print("[PASS] Security headers (nosniff, SAMEORIGIN, XSS, Referrer) and session flags validated.")

    # -------------------------------------------------------------
    # Test 20: Application Optimization & Database Performance Indexes
    # -------------------------------------------------------------
    c.execute("PRAGMA journal_mode")
    j_mode = c.fetchone()[0]
    assert j_mode.lower() == "wal"

    c.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    active_indexes = [r[0] for r in c.fetchall() if not r[0].startswith("sqlite_autoindex")]
    required_indexes = [
        "idx_tickets_status", "idx_tickets_assigned_to", "idx_tickets_username",
        "idx_tickets_priority", "idx_tickets_category", "idx_tickets_created_at",
        "idx_replies_ticket_id", "idx_activities_ticket_id", "idx_notifications_user_read"
    ]
    for req_idx in required_indexes:
        assert req_idx in active_indexes, f"Missing required index: {req_idx}"
    print(f"[PASS] Performance optimization verified: SQLite WAL mode and {len(active_indexes)} active indexes.")

    # -------------------------------------------------------------
    # Test 21: Disaster Recovery & Online Database Backup Engine
    # -------------------------------------------------------------
    b_filename, b_filepath, b_size = create_database_backup()
    assert os.path.exists(b_filepath)
    assert b_size > 0
    assert b_filename.startswith("helpdesk_backup_") and b_filename.endswith(".db")

    # Verify backup integrity by opening in sqlite
    b_conn = sqlite3.connect(b_filepath)
    b_cur = b_conn.cursor()
    b_cur.execute("PRAGMA integrity_check")
    assert b_cur.fetchone()[0] == "ok"
    b_cur.execute("SELECT COUNT(*) FROM tickets")
    assert b_cur.fetchone()[0] > 0
    b_conn.close()

    # Test Admin backup endpoints
    with client.session_transaction() as sess:
        sess["username"] = "admin_tester"
        sess["role"] = "Admin"

    b_list_res = client.get("/admin/backup/list")
    assert b_list_res.status_code == 200
    b_list_json = json.loads(b_list_res.data)
    assert b_list_json["success"] is True
    assert b_list_json["count"] >= 1

    b_create_res = client.post("/admin/backup/create", headers={"Accept": "application/json"})
    assert b_create_res.status_code == 200
    assert json.loads(b_create_res.data)["success"] is True

    # Authorization: standard user forbidden from backup list
    with client.session_transaction() as sess:
        sess["username"] = "alice_client"
        sess["role"] = "User"
    user_b_res = client.get("/admin/backup/list", follow_redirects=True)
    assert user_b_res.status_code == 200
    assert b"Access denied" in user_b_res.data
    print("[PASS] Disaster recovery engine verified: atomic snapshot, integrity check, and RBAC security.")

    # -------------------------------------------------------------
    # Test 22: Custom Error Handlers & Boundary Validation
    # -------------------------------------------------------------
    err404 = client.get("/non-existent-route-for-testing-404")
    assert err404.status_code == 404
    assert b"404" in err404.data
    assert b"Page Not Found" in err404.data
    assert b"Return to Dashboard" in err404.data
    print("[PASS] Custom 404 error handler validated with branded template.")

    # -------------------------------------------------------------
    # Test 23: Data Validation & Malicious File Upload Prevention
    # -------------------------------------------------------------
    assert allowed_file("malware.exe") is False
    assert allowed_file("script.py") is False
    assert allowed_file("attack.sh") is False
    assert allowed_file("hack.php") is False
    assert allowed_file("document.pdf") is True
    assert allowed_file("screenshot.png") is True
    assert allowed_file("data.xlsx") is True
    assert allowed_file("archive.zip") is True
    assert app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024
    print("[PASS] Data validation and secure file upload whitelist verified.")

    # -------------------------------------------------------------
    # Test 24: System Diagnostics & Health Check API (/api/health)
    # -------------------------------------------------------------
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    health_json = json.loads(health_res.data)
    assert health_json["status"] == "healthy"
    assert health_json["database"]["connected"] is True
    assert health_json["database"]["journal_mode"] == "wal"
    assert health_json["database"]["indexes_active"] >= 9
    assert health_json["backups"]["snapshots_available"] >= 1
    print(f"[PASS] System Health API verified: status='{health_json['status']}', latency={health_json['latency_ms']}ms.")

    conn.close()
    print("\n=== ALL COMPREHENSIVE HELPDESK TEST CASES PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_tests()
