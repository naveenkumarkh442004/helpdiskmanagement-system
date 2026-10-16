# HelpDesk Management System

A web-based HelpDesk and Ticketing Management System built with Flask, SQLite, and modern UI templates.

## Features

- **User & Admin Portals**: Dedicated dashboards for users and support agents/administrators.
- **Ticket Management**: Create, assign, track, prioritize, and resolve support tickets.
- **SLA & Escalation Policies**: Categorize tickets by severity and track resolution times with automated escalation paths.
- **Real-Time Discussions**: Comment and reply threads on tickets with file attachments support.
- **Activity Audit Trail**: Transparent logging of status changes, reassignments, and ticket updates.
- **Secure Authentication**: Password hashing with Werkzeug security and session management.

## Tech Stack

- **Backend**: Python 3, Flask
- **Database**: SQLite3
- **Frontend**: HTML5, Vanilla CSS, Jinja2 templates, FontAwesome icons

## Installation & Setup

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
