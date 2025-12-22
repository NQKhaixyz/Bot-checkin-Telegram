# Telegram Attendance Bot - Project Overview

## Project Summary

A Telegram-based attendance management system for tracking employee check-ins/check-outs with GPS verification, anti-fraud measures, and comprehensive reporting.

---

## System Architecture

```
+------------------+     +-------------------+     +------------------+
|   Telegram App   |     |   Telegram Bot    |     |    Database      |
|   (Client)       |<--->|   API Server      |<--->|   SQLite/        |
|   Android/iOS    |     |   (Python)        |     |   PostgreSQL     |
+------------------+     +-------------------+     +------------------+
                                  |
                                  v
                         +------------------+
                         |   Reporting      |
                         |   Excel/Sheets   |
                         +------------------+
```

### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Client | Telegram Mobile App | User interface for employees |
| Interface | Telegram Bot API | Communication layer |
| Backend | Python (python-telegram-bot) | Business logic & processing |
| Database | SQLite / PostgreSQL | Data persistence |
| Reporting | openpyxl / Google Sheets API | Export & analytics |

---

## Tech Stack

### Required Dependencies

```txt
python-telegram-bot>=20.0
sqlalchemy>=2.0
alembic>=1.12
openpyxl>=3.1
python-dotenv>=1.0
geopy>=2.4
pytz>=2023.3
```

### Optional Dependencies

```txt
psycopg2-binary>=2.9  # For PostgreSQL
gspread>=5.12         # For Google Sheets
oauth2client>=4.1     # For Google Sheets auth
```

---

## Project Structure

```
bot_telegram/
├── blueprints/           # Implementation guides (this folder)
├── src/
│   ├── __init__.py
│   ├── main.py           # Entry point
│   ├── config.py         # Configuration management
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── start.py          # /start command
│   │   │   ├── checkin.py        # Check-in logic
│   │   │   ├── checkout.py       # Check-out logic
│   │   │   └── admin.py          # Admin commands
│   │   ├── keyboards.py          # Inline/Reply keyboards
│   │   ├── middlewares.py        # Auth & validation
│   │   └── utils.py              # Helper functions
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── session.py            # DB session management
│   │   └── migrations/           # Alembic migrations
│   ├── services/
│   │   ├── __init__.py
│   │   ├── attendance.py         # Attendance logic
│   │   ├── geolocation.py        # GPS verification
│   │   ├── anti_cheat.py         # Fraud detection
│   │   ├── user_service.py       # User management
│   │   └── export.py             # Excel/Sheets export
│   └── constants.py              # App constants
├── tests/
│   ├── __init__.py
│   ├── test_attendance.py
│   ├── test_geolocation.py
│   └── test_anti_cheat.py
├── .env.example
├── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## Core Features

### 1. User Management
- User registration with approval workflow
- Role-based access (admin/member)
- User status management (active/pending/banned)

### 2. Attendance Tracking
- GPS-verified check-in/check-out
- Late arrival detection
- Daily attendance summary

### 3. Location Management
- Multiple office locations support
- Configurable geofence radius
- Admin location setup via GPS

### 4. Anti-Cheat System
- Forward message detection
- Timestamp validation
- Location freshness check

### 5. Reporting
- Daily attendance reports
- Monthly Excel exports
- Real-time statistics

---

## User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Approve users, set locations, view reports, broadcast messages, export data |
| **Member** | Check-in, check-out, view own attendance history |

---

## Environment Variables

```env
# Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_USER_IDS=123456789,987654321

# Database
DATABASE_URL=sqlite:///./attendance.db
# DATABASE_URL=postgresql://user:pass@localhost/attendance

# Timezone
TIMEZONE=Asia/Ho_Chi_Minh

# Attendance Rules
WORK_START_TIME=09:00
LATE_THRESHOLD_MINUTES=15
GEOFENCE_DEFAULT_RADIUS=50

# Google Sheets (Optional)
GOOGLE_SHEETS_CREDENTIALS=path/to/credentials.json
SPREADSHEET_ID=your_spreadsheet_id
```

---

## Implementation Order

Follow this sequence for optimal development:

1. **Database Schema** (01_DATABASE_SCHEMA.md)
2. **Bot Core Setup** (02_BOT_CORE.md)
3. **User Management** (03_USER_MANAGEMENT.md)
4. **Attendance System** (04_ATTENDANCE_SYSTEM.md)
5. **Geolocation Service** (05_GEOLOCATION.md)
6. **Anti-Cheat Measures** (06_ANTI_CHEAT.md)
7. **Reporting System** (07_REPORTING.md)
8. **Admin Commands** (08_ADMIN_COMMANDS.md)

---

## Quick Start for LLM Agents

When implementing this project:

1. **Read TRACKER.md first** - Contains implementation status and next steps
2. **Follow blueprint order** - Each file builds on the previous
3. **Check dependencies** - Ensure previous components exist before implementing
4. **Update tracker** - Mark tasks complete as you finish them
5. **Test incrementally** - Each component should be testable independently

---

## API Reference

### Telegram Bot API Methods Used

| Method | Purpose |
|--------|---------|
| `sendMessage` | Send text responses |
| `sendDocument` | Send Excel reports |
| `getUpdates` / Webhooks | Receive user messages |
| `sendLocation` | Confirm location received |

### Key Telegram Message Properties

```python
# Location message
message.location.latitude   # User's latitude
message.location.longitude  # User's longitude
message.forward_date        # None if not forwarded
message.date               # Message timestamp
```

---

## Security Considerations

1. **Token Security**: Never commit bot token to version control
2. **Admin Validation**: Always verify admin status before privileged operations
3. **Input Sanitization**: Validate all user inputs
4. **Rate Limiting**: Implement cooldowns for check-in attempts
5. **Audit Logging**: Log all admin actions

---

## Next Steps

Proceed to `01_DATABASE_SCHEMA.md` to begin implementation.
