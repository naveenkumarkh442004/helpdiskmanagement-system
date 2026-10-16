# HelpDesk Management System

A production-ready, feature-rich web-based HelpDesk and Ticketing Management System built with Flask, SQLite3, and modern UI templates.

---

## 🌟 Key Modules & Features

### 1. 📊 Reports & Operations Analytics (Week 7)
- **Timeframe Filtering**: Dynamically analyze operational metrics across *All Time, Last 7 Days, Last 30 Days, This Month, This Year*, or custom date ranges (`date_from`, `date_to`).
- **Ticket Status Summaries**: Detailed distribution and visual meters for Open, In Progress, Pending, Resolved, and Closed tickets with backlog sizing.
- **Category-Wise Issues**: Technical volume distribution, category resolution rates, average turnaround time (MTTR), and escalation frequency per domain.
- **Support Agent Performance & Scorecards**: Workload allocation, active queues, individual resolution efficiency (%), average resolution turnaround in hours, and workload capacity ratings.
- **Average Resolution Time (MTTR - Mean Time to Resolution)**: Accurate turnaround tracking in hours and days, broken down by priority tiers vs defined SLA targets (Critical 2h, High 8h, Medium 24h, Low 72h).
- **Pending Tickets Deep Dive & Aging Backlog**: Backlog inspection with aging duration tiers (`< 24 Hours`, `1-3 Days`, `3-7 Days`, `> 7 Days Critical`) and individual ticket inspection.
- **Monthly Support Statistics**: Historical month-over-month created vs resolved volume trends, monthly resolution efficiency, and responsive CSS bar chart visualizations.
- **Dedicated CSV Report Exports**:
  - `/reports/export/summary`: Executive operational summary & KPIs.
  - `/reports/export/categories`: Category volume, MTTR, and resolution rates.
  - `/reports/export/agents`: Individual agent scorecards, workload, and performance.
  - `/reports/export/monthly`: Monthly trend statistics and historical data.
- **Print / PDF Ready**: Clean print stylesheet (`window.print()`) formatted for executive reports.
- **JSON Analytics API**: Accessible at `/api/reports/stats`.

### 2. 🛡️ Administrator Control Center (Week 6)
- **Account Management**: Create, view, edit roles (`User`, `Support`, `Admin`), department assignment, toggle active/suspended status, reset user passwords, and safely delete accounts.
- **Support Staff & Workload Balancing**: Monitor agent active queues, resolution efficiency rates, and reassign ticket workloads between staff with logged audit reasons.
- **Category Configuration**: Create, edit custom hex color codes, FontAwesome icons, toggle active states, and delete categories with usage safety checks.
- **SLA & Priority Policy Engine**: Define priority tiers, hierarchy levels, badge colors, and turnaround SLAs (e.g., 2h Critical, 8h High, 24h Medium, 72h Low).
- **Operations & Health Monitoring**:
  - Live KPI cards: Total accounts, escalated tickets (🚨), overdue SLA queue (⏳), total tickets, unassigned tickets, and global resolution rate.
  - Lifecycle meters for status distribution (Open, In Progress, Pending, Resolved, Closed).
  - Real-time audit trail feed logging all actions and status transitions.
- **Bulk Ticket Management**: Execute bulk status changes, bulk priority updates, and bulk reassignments.

### 3. 🎫 Ticket Lifecycle & Service Desk
- Ticket creation with attachments (PDF, images, logs, office documents up to 16MB).
- Multi-criteria filtering, search, and priority-weighted sorting.
- Discussions and internal notes on tickets with file attachments.
- Escalation workflows with tier progression (Tier 1, Tier 2, Tier 3, Leadership).

### 4. 👥 User & Support Portals
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
| **Administrator** | `admin` | `admin123` | Full control center, reports & analytics, user/staff management, SLA policies |
| **Support Agent** | `support_agent` | `support123` | Support dashboard, reports & analytics, assigned queue, ticket resolution |

---

## 🧪 Running the Verification Suite

Run the automated end-to-end test suite covering all 18 integration test cases:
```bash
python test_suite.py
```
