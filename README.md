# HelpDesk Support Management System

A production-ready, feature-rich web-based HelpDesk and Ticketing Management System built with Flask, SQLite3, and modern UI templates.

---

## 📚 Project Documentation & Deliverables

- 📄 **[Full Project Documentation](file:///c:/Users/user/OneDrive/Desktop/HelpDesk_system/PROJECT_DOCUMENTATION.md)**: Academic project report, system architecture, ER diagrams, data dictionary, security model, and API reference.
- 📖 **[User Manual & Operating Guide](file:///c:/Users/user/OneDrive/Desktop/HelpDesk_system/USER_MANUAL.md)**: Role-based step-by-step operating instructions for Clients, Support Agents, and Administrators.
- 🖥️ **[Final Project Presentation Deck](file:///c:/Users/user/OneDrive/Desktop/HelpDesk_system/PRESENTATION.md)**: 12-slide comprehensive presentation deck for project defense and capstone evaluation.

---

## 🌟 Comprehensive Architecture & Weekly Milestones

### 1. 🚀 Final Delivery, User Manual & Production Deployment (Week 9)
- **End-to-End System Testing**: All 24 integration test cases verified with a 100% pass rate.
- **Project Documentation**: Academic-grade project report covering system goals, architecture, data dictionary, and API specs.
- **Role-Based User Manual**: Step-by-step operational handbook for end-users, support staff, and administrators.
- **Presentation Deck**: Slide-by-slide capstone presentation formatted for project review and defense.
- **Production Deployment Suite**:
  - `wsgi.py`: Production WSGI entry point.
  - `Dockerfile`: Multi-stage, minimal production image.
  - `docker-compose.yml`: Automated orchestration with persistent storage volumes.
  - `Procfile`: Ready for cloud PaaS deployments (Render, Railway, Heroku).

### 2. 🛡️ System Integration, Security & Optimization (Week 8)
- **Security Hardening**:
  - Global security HTTP response headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`).
  - Session cookie hardening: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`, 7-day expiration.
  - Upload security: Strict extension whitelist (`.png`, `.jpg`, `.pdf`, `.docx`, `.xlsx`, `.zip`, etc.), rejection of executables (`.exe`, `.sh`, `.php`, `.py`), 16MB file limit, and `secure_filename` sanitization.
- **Application Performance & Database Optimization**:
  - **SQLite WAL Mode**: Concurrent non-blocking reads and writes via Write-Ahead Logging (`PRAGMA journal_mode = WAL`).
  - **Relational & Analytical Indexes**: 9 high-speed B-Tree indexes created on `tickets(status)`, `tickets(assigned_to)`, `tickets(username)`, `tickets(priority)`, `tickets(category)`, `tickets(created_at)`, `ticket_replies(ticket_id)`, `ticket_activities(ticket_id)`, and `notifications(username, is_read)`.
  - Sub-millisecond database response times (0.6ms latency).
- **Disaster Recovery & Backup Planning**:
  - **Atomic Online Backups**: Point-in-time SQLite online backups with zero database lock via `connection.backup()`.
  - Automated retention policy maintaining the 10 most recent database snapshots in `backups/`.
  - CLI utility: [backup_manager.py](file:///c:/Users/user/OneDrive/Desktop/HelpDesk_system/backup_manager.py) (`--verify`, `--list`, automated backup).
  - Web console endpoints: `/admin/backup/create`, `/admin/backup/list`, and `/admin/backup/download/<filename>`.
- **System Health Diagnostics API**: `/api/health` providing real-time status, latency, index counts, table metrics, and backup snapshots.
- **Custom Error Handling**: Branded, responsive error templates for `404 Not Found`, `403 Forbidden`, `413 Payload Too Large`, and `500 Server Error`.

### 3. 📊 Reports & Operations Analytics (Week 7)
- **Timeframe Filtering**: Dynamically analyze operational metrics across *All Time, Last 7 Days, Last 30 Days, This Month, This Year*, or custom date ranges (`date_from`, `date_to`).
- **Ticket Status Summaries**: Detailed distribution and visual meters for Open, In Progress, Pending, Resolved, and Closed tickets with backlog sizing.
- **Category-Wise Issues**: Technical volume distribution, category resolution rates, average turnaround time (MTTR), and escalation frequency per domain.
- **Support Agent Performance & Scorecards**: Workload allocation, active queues, individual resolution efficiency (%), average resolution turnaround in hours, and workload capacity ratings.
- **Average Resolution Time (MTTR - Mean Time to Resolution)**: Turnaround tracking in hours and days, broken down by priority tiers vs defined SLA targets (Critical 2h, High 8h, Medium 24h, Low 72h).
- **Pending Tickets Deep Dive & Aging Backlog**: Backlog inspection with aging duration tiers (`< 24 Hours`, `1-3 Days`, `3-7 Days`, `> 7 Days Critical`).
- **Monthly Support Statistics**: Historical month-over-month volume comparison, resolution efficiency trends, and responsive CSS bar chart visualizations.
- **Dedicated CSV Report Exports**:
  - `/reports/export/summary`: Executive operational summary & KPIs.
  - `/reports/export/categories`: Category volume, MTTR, and resolution rates.
  - `/reports/export/agents`: Individual agent scorecards and workload metrics.
  - `/reports/export/monthly`: Monthly trend statistics and historical data.

### 4. ⚙️ Administrator Control Center (Week 6)
- **Account Management**: Create, view, edit roles (`User`, `Support`, `Admin`), department assignment, toggle active/suspended status, reset user passwords, and safely delete accounts.
- **Support Staff & Workload Balancing**: Monitor agent active queues, resolution efficiency rates, and reassign ticket workloads between staff with logged audit reasons.
- **Category Configuration**: Create, edit custom hex color codes, FontAwesome icons, toggle active states, and delete categories with usage safety checks.
- **SLA & Priority Policy Engine**: Define priority tiers, hierarchy levels, badge colors, and turnaround SLAs (e.g., 2h Critical, 8h High, 24h Medium, 72h Low).
- **Operations & Health Monitoring**: Live KPI cards, lifecycle status meters, category volume charts, and real-time audit trail feed.
- **Bulk Ticket Management**: Execute bulk status changes, bulk priority updates, and bulk reassignments.

### 5. 🎫 Ticket Lifecycle & Service Desk (Weeks 1 to 5)
- Ticket creation with attachments (PDF, images, logs, office documents up to 16MB).
- Multi-criteria filtering, search, and priority-weighted sorting.
- Discussions and internal notes on tickets with file attachments.
- Escalation workflows with tier progression (Tier 1, Tier 2, Tier 3, Leadership).
- In-app notification center with badge alerts and unread indicators.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, Flask, Werkzeug Security, Gunicorn
- **Database**: SQLite3 (automatic schema migration, WAL mode, 9 performance indexes, online backup API)
- **Frontend**: HTML5, Vanilla CSS (design system with CSS variables, responsive grid, glassmorphism), Jinja2 templates, FontAwesome icons
- **DevOps**: Docker, Docker-Compose, Procfile, WSGI

---

## 🚀 Installation & Deployment

### Option A: Local Python Environment
1. **Clone the repository**:
   ```bash
   git clone https://github.com/naveenkumarkh442004/helpdiskmanagement-system.git
   cd helpdiskmanagement-system
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python app.py
   # Or using production WSGI:
   python wsgi.py
   ```

5. **Access the application**:
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

### Option B: Docker Container Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d --build

# Inspect running container
docker ps

# Check application health
curl http://localhost:5000/api/health
```

---

## 💾 Backup & Disaster Recovery CLI

Run the automated backup manager:
```bash
# Create an atomic backup snapshot
python backup_manager.py

# List existing backups
python backup_manager.py --list

# Run integrity check and database diagnostics
python backup_manager.py --verify
```

---

## 🔐 Default Demo Accounts

When launched with a fresh database, the system automatically seeds default accounts:

| Role | Username | Password | Access / Purpose |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full control center, reports & analytics, backups, user/staff management |
| **Support Agent** | `support_agent` | `support123` | Support queue, reports & analytics, ticket response & resolution |

---

## 🧪 Comprehensive Verification Suite

Run the end-to-end automated integration test suite covering all 24 test cases:
```bash
python test_suite.py
```
> `=== ALL COMPREHENSIVE HELPDESK TEST CASES PASSED SUCCESSFULLY ===`
