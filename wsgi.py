"""
Production WSGI Entrypoint for HelpDesk Management System.
Used by Gunicorn, uWSGI, Waitress, or Apache/Nginx mod_wsgi.
"""

from app import app, init_db

# Initialize database schema, default credentials, performance indexes, and pragmas
init_db()

if __name__ == "__main__":
    app.run()
