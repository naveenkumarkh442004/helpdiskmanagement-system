# HelpDesk Management System

A production-ready, feature-rich web-based HelpDesk and Ticketing Management System built with Flask, SQLite3, and modern UI templates.

---

## 🌟 Key Modules & Features

### 1. 🛡️ Administrator Control Center (Week 6)
- **Account Management**: Create, view, edit roles (`User`, `Support`, `Admin`), department assignment, toggle active/suspended status, reset user passwords, and safely delete accounts.
- **Support Staff & Workload Balancing**: Monitor agent active queues, resolution efficiency rates, and reassign ticket workloads between staff with logged audit reasons.
- **Category Configuration**: Create, edit custom hex color codes, FontAwesome icons, toggle active states, and delete categories with usage safety checks.
- **SLA & Priority Policy Engine**: Define priority tiers, hierarchy levels, badge colors, and turnaround SLAs (e.g., 2h Critical, 8h High, 24h Medium, 72h Low).
- **Operations & Health Monitoring**:
  - Live KPI cards: Total accounts, escalated tickets (🚨), overdue SLA queue (⏳), total tickets, unassigned tickets, and global resolution rate.
  - Lifecycle meters for status distribution (Open, In Progress, Pending, Resolved, Closed).
  - Category and priority volume charts.
  - Real-time audit trail feed logging all actions and status transitions.
- **Bulk Ticket Management**: Execute bulk status changes, bulk priority updates, and bulk reassignments.
- **Executive Operations Export**: Generate and download comprehensive CSV reports of help desk operations.

### 2. 🎫 Ticket Lifecycle & Service Desk
- Ticket creation with attachments (PDF, images, logs, office documents up to 16MB).
- Multi-criteria filtering, search, and priority-weighted sorting.
- Discussions and internal notes on tickets with file attachments.
- Escalation workflows with tier progression (Tier 1, Tier 2, Tier 3, Leadership).

### 3. 👥 User & Support Portals
- Dedicated User Dashboard to create and track personal tickets.
- Dedicated Support Dashboard to manage assigned queues and respond to users.
- In-app notification center with badge alerts and unread indicators.

---

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask, Werkzeug Security
- **Database**: SQLite3 (automatic schema migration & seeding)
- **Frontend**: HTML5, Vanilla CSS (design system with CSS variables, responsive grid, glassmorphism), Jinja2 templates, FontAwesome icons

---

## 🚀 Installation & Setup

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
   ```

5. **Access the application**:
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🔐 Default Demo Accounts

When launched with a fresh database, the system automatically seeds default accounts:

| Role | Username | Password | Access / Purpose |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full control center, user/staff management, SLA policies, and monitoring |
| **Support Agent** | `support_agent` | `support123` | Support dashboard, assigned ticket queue, and ticket resolution |

---

## 🧪 Running the Verification Suite

Run the automated end-to-end test suite covering all 14 integration test cases:
```bash
python test_suite.py
```
