"""Compatibility entry point for database initialization.

The active database schema is defined in init_db.py. This file is kept so
older setup notes or commands that call createsqlite.py still work.
"""

from init_db import init_database


if __name__ == "__main__":
    init_database()
