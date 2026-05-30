# ThutoTrack

**Parent-Teacher-Student Progress Tracker for Botswana Schools**

## About

ThutoTrack helps schools in Botswana digitize student marks and behavior records, and lets parents track progress in real-time.

The goal is to make it easy for teachers to record results and for parents to see how their children are doing during the term, without waiting for end-of-term report cards.

## Why This Matters

- Most schools still use paper or Excel for marks
- Parents only see results once per term
- Rural parents have no way to track performance or behavior
- Botswana's SmartBots and BETP programs are pushing for digital education solutions

## Features

**For Teachers**
- Record marks, attendance, and behavior notes per term
- Bulk-import students and marks from Excel
- Generate per-student term report PDFs
- Send enquiries to school admin / HR
- Manage classes and subjects

**For School Admins**
- Manage students, teachers, classes, subjects, and school calendar
- View teacher performance based on student outcomes
- Manage parent web/WhatsApp accounts and PINs
- Export data for Ministry submissions

**For Parents**
- WhatsApp bot: text the school number to get marks / attendance / behavior
- Web portal: log in with phone number + PIN to view a child's full record

## Tech Stack

- **Backend**: Python 3.13 + Django 6.0
- **Frontend**: Server-rendered Django templates + HTMX + Tailwind (CDN)
- **Database**: SQLite (default for dev); Postgres-compatible via `DATABASE_URL`
- **PDFs**: ReportLab
- **Excel**: openpyxl
- **WhatsApp**: Twilio webhook (TwiML response)

## Local Development

**Prerequisites**: Python 3.13+

```powershell
# Clone and enter the repo
git clone https://github.com/kgosipako419-oss/THUTO-TRACK.git
cd THUTO-TRACK

# Create venv and install deps
py -3.13 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Apply migrations and seed demo data
python manage.py migrate
python manage.py seed_demo

# Run the dev server
python manage.py runserver
```

Then open http://127.0.0.1:8000 and log in with one of the seeded accounts (printed by `seed_demo`):

| Portal | Username | Password |
|---|---|---|
| Teacher | `mr_kgosi` | `teacher123` |
| School admin | `mma_pula` | `admin123` |
| Django admin | `admin` | `admin123` |
| Parent web | `+267 71 222 001` | `1234` |

## Tests

```powershell
python manage.py test
```

## Engineering Report

A full engineering project report (abstract, methodology, design, testing, results, etc.) is available in [`docs/report.tex`](docs/report.tex). See [`docs/README.md`](docs/README.md) for compile instructions.

## Contributing

Ideas and feedback welcome — open an issue to share thoughts.

## Author

Pako Kgosi Kgosintwa
