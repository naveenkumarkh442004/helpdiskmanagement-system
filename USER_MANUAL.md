# HelpDesk Support Management System - User Manual & Operating Guide

A comprehensive, role-based manual for End-Users, Support Engineers, and System Administrators.

---

## 1. Getting Started & Account Access

### 1.1 Accessing the Application
Open your web browser and navigate to the application address:
- **Local Development**: `http://127.0.0.1:5000`
- **Containerized / Cloud**: `http://<your-host>:5000`

### 1.2 User Roles & Pre-configured Credentials
The system comes pre-seeded with default demo accounts:

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **System Administrator** | `admin` | `admin123` | Complete system oversight, user/staff management, categories, SLAs, backups |
| **Support Staff** | `support_agent` | `support123` | Queue triage, ticket replies, internal notes, escalations, and resolution |
| **Standard User** | *Register new* | *Your password* | Ticket submission, discussions, and personal status tracking |

### 1.3 User Registration
1. On the login screen, click **"Create an account"** or navigate to `/register`.
2. Fill in your **Full Name**, **Email Address**, desired **Username**, and **Password** (min 4 characters).
3. Click **"Register Account"** to access your personal dashboard.

---

## 2. End-User Guide (Clients & Requesters)

### 2.1 Submitting a Support Ticket
1. From the top navigation bar, click **"New Ticket"** or **"Create Ticket"** (`/create-ticket`).
2. Fill out the ticket intake form:
   - **Category**: Select the issue domain (e.g., *Technical Issue, Software Problem, Billing & Subscription*).
   - **Priority**: Select initial urgency (*Critical, High, Medium, Low*).
   - **Subject**: Enter a concise summary of the issue.
   - **Description**: Provide thorough details, reproduction steps, or error codes.
   - **File Attachment (Optional)**: Attach screenshots, PDFs, logs, or diagnostic archives (up to 16 MB).
3. Click **"Submit Ticket"**. You will receive an immediate confirmation with your Ticket ID number.

### 2.2 Tracking Your Tickets
- Navigate to **"My Tickets"** (`/my-tickets`) to view all tickets you have submitted.
- Use the quick filters to view **Open**, **In Progress**, **Resolved**, or **Closed** tickets.
- Use the search bar to find tickets by keyword or reference ID.

### 2.3 Participating in Discussion Threads
1. Click on any ticket subject to open the **Ticket Details** page (`/ticket/<id>`).
2. Read replies and updates posted by support engineers.
3. Type your response in the **"Post a Reply"** box, attach additional files if required, and click **"Send Reply"**.

### 2.4 Notifications
- The notification bell icon in the top header lights up with a badge count whenever support staff reply, change your ticket status, or resolve your request.
- Click the bell to view recent alerts, or navigate to `/notifications` to manage all notifications.

---

## 3. Support Staff Guide (Help Desk Agents)

### 3.1 Working the Support Queue
1. Log in with a **Support** account (`support_agent` / `support123`).
2. Your home dashboard (`/dashboard`) displays:
   - **Assigned to Me**: Tickets specifically routed to you.
   - **Unassigned Queue**: Fresh incoming tickets awaiting triage.
   - **🚨 Escalated Queue**: Urgent incidents requiring immediate senior attention.
3. Click on any ticket to open its investigation workspace.

### 3.2 Updating Ticket Metadata & Status
On the ticket details page:
- **Change Status**: Move ticket between `Open`, `In Progress`, `Pending` (awaiting user/vendor feedback), `Resolved`, or `Closed`.
- **Assign Agent**: Assign the ticket to yourself or reassign to a colleague.
- **Adjust Priority**: Upgrade or downgrade priority based on business impact.

### 3.3 Adding Public Replies vs. Internal Staff Notes
- **Public Reply**: Visible to both the requester and all support staff. Used to communicate solutions or request user clarifications.
- **Internal Note**: Visible **only** to Support and Admin staff. Check the **"Internal Note (Staff Only)"** box before submitting. Use internal notes to record diagnostic findings, vendor ticket IDs, or handover comments.

### 3.4 Multi-Tier Ticket Escalation
If an issue cannot be resolved within standard SLA or requires engineering/leadership intervention:
1. In the ticket details sidebar, locate the **Escalation Management** card.
2. Select the **Target Escalation Tier**:
   - *Tier 1 - Help Desk Lead*
   - *Tier 2 - Senior Support Engineer*
   - *Tier 3 - Systems / Engineering Specialist*
   - *Tier 4 - Leadership / Management Escalation*
3. Enter a mandatory **Escalation Reason & Context**.
4. Check **"Bump Priority to Critical"** if immediate emergency response is required.
5. Click **"Trigger Escalation"**. All staff and the target tier receive automated alerts, and the ticket enters the high-priority Escalated Queue.

---

## 4. Administrator Guide (System Admins)

### 4.1 Accessing the Administrator Control Center
Log in with an **Admin** account (`admin` / `admin123`) to access `/dashboard`.

### 4.2 User & Staff Account Management
Under the **"Users & Staff"** tab:
- **Add New Account**: Click **"Add Account"** in the top banner to create Users, Support Agents, or Administrators with specified departments.
- **Edit User**: Click **Edit** next to any user to change their full name, email, department, or role clearance.
- **Suspend / Activate**: Click **Suspend** to immediately block a compromised or departed account from logging in.
- **Reset Password**: Click **Reset Password** to assign a new temporary or permanent password directly.
- **Delete Account**: Safe deletion safeguards prevent admins from accidentally deleting themselves or leaving zero admins.

### 4.3 Support Agent Workload Balancing
Under the **"Support Agents"** tab:
- Review the **Agent Workload Leaderboard** showing active tickets, resolution counts, and efficiency ratings.
- Click **"Reassign Agent Workload"** to bulk-transfer active tickets from an overloaded agent or agent on leave to a designated colleague with an audit log reason.

### 4.4 Category & SLA Priority Configuration
- **Categories Tab**: Create and modify categories, select custom hex colors, choose FontAwesome icons, and toggle active/inactive states.
- **Priorities & SLA Tab**: Define priority tiers, hierarchy levels, badge colors, and turnaround SLAs (e.g., 2h Critical, 8h High, 24h Medium, 72h Low).

### 4.5 Performing Database Backups
- **Web Console**: Click the **"Backup DB"** button in the top administrator banner to immediately generate an atomic point-in-time snapshot.
- **CLI Utility**: From the project directory, run:
  ```bash
  python backup_manager.py           # Immediate online backup
  python backup_manager.py --list    # List backup files and sizes
  python backup_manager.py --verify  # Run SQLite integrity checks
  ```

---

## 5. Reports & Analytics Guide

Accessible to Admins and Support staff at `/reports` (or `/analytics`):
1. **Timeframe Selection**: Choose between *All Time*, *Last 7 Days*, *Last 30 Days*, *This Month*, *This Year*, or specify a custom *Date Range*.
2. **Key Metric Panels**:
   - **Ticket Status Summaries**: Proportional distribution across Open, In Progress, Pending, Resolved, and Closed.
   - **Mean Time to Resolution (MTTR)**: Average resolution hours and days, with priority SLA breakdown.
   - **Category-Wise Issues**: Technical volume and resolution rates per domain.
   - **Agent Scorecards**: Workload efficiency, MTTR, and capacity ratings (*Available, Balanced, Heavy Load*).
   - **Pending Aging Analysis**: Backlog aging breakdown (*< 24h, 1-3d, 3-7d, > 7d Critical*).
   - **Monthly Trends**: Historical volume bar chart and month-by-month table.
3. **Exporting Data**: Click the **"Export CSV"** dropdown to download:
   - *Executive Summary CSV*
   - *Category Breakdown CSV*
   - *Agent Performance CSV*
   - *Monthly Statistics CSV*
4. **Printing**: Click **"Print / PDF"** to generate an executive-ready hardcopy or PDF report.

---

## 6. Frequently Asked Questions (FAQ)

**Q: What is the maximum file upload size?**  
A: The system allows attachments up to 16 MB. Supported formats include `.png`, `.jpg`, `.pdf`, `.docx`, `.xlsx`, `.zip`, `.csv`, `.log`.

**Q: Can a standard user see internal staff notes?**  
A: No. Internal notes are strictly restricted to accounts with Support or Admin roles.

**Q: How does the system detect SLA breaches?**  
A: The system continuously calculates the elapsed time from ticket creation against the priority tier's configured SLA response hours. When exceeded, the ticket displays an alert tag (`⏳ Overdue SLA`).

**Q: Where are database backups stored?**  
A: Database snapshots are stored in the `backups/` directory in `.db` format with automated 10-file rotation.
