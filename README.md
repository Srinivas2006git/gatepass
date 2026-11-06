# MRIT Smart Student Gate Pass & SMS System

A secure Flask/MySQL gate-pass workflow for M. R. Institute of Technology. Staff create requests, authorized approvers decide them, the approved pass is sent only to the student's registered mobile number, and security verifies the pass reference or opaque QR token before recording exit/return.

## Quick start (PowerShell)

```powershell
Copy-Item .env.example .env
C:/Python314/python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
flask --app run.py db init
flask --app run.py db migrate -m "Initial schema"
flask --app run.py db upgrade
flask --app run.py seed-admin
python run.py
```

Visit `http://127.0.0.1:5000`, then sign in as `admin` with `ChangeMe!2026`. Change that password immediately. Do not use this development account in production.

## Production / MySQL

Set `DATABASE_URL` in `.env` to a least-privileged MySQL database user, set a long random `SECRET_KEY`, and enable HTTPS. The database user must only have access to the MRIT application database. Run migrations before deploying.

Set `RATELIMIT_STORAGE_URI` to an authenticated Redis instance in production; the included `memory://` configuration is appropriate only for a single development process.

## SMS configuration

`SMS_PROVIDER=mock` is intentionally the default. It creates an auditable `SIMULATED` notification and **does not send an SMS**. A live provider must only be enabled after MRIT supplies a DLT-approved transactional template, entity/template IDs, authorization, and API credentials. The system sends gate-pass SMS only to `students.student_mobile`, records `recipient_type=STUDENT`, and rejects dispatch when the configured sender is not the authorized `CP-MRITPR-S` header.

The centralized default message is in [sms_service.py](app/services/sms_service.py); an active `sms_templates` database record named `gate_pass_approved` can replace it. The approved message contains the student name, USN, reason, IST departure time, and a unique pass reference. Security must verify that reference or QR token in the system; a screenshot or copied SMS text is not sufficient proof.

## Timezone policy (Windows and MySQL)

Windows does not provide Python with the IANA timezone database. The project therefore depends on `tzdata`, which lets `ZoneInfo("Asia/Kolkata")` work in the same virtual environment used by Flask.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Asia/Kolkata'))"
```

[timezone.py](app/utils/timezone.py) is the single timezone boundary: application datetimes are aware, MySQL `DATETIME` values are persisted as UTC, and they are restored as aware UTC values. The user interface, PDF passes, and student SMS convert explicitly to `Asia/Kolkata`. This avoids relying on the Windows local-time setting and prevents an accidental second +05:30 conversion. No database schema migration is required because the on-disk column representation remains UTC `DATETIME`.

## Test

```powershell
pytest -q
```

## Roles

`SUPER_ADMIN` manages users/students; `STAFF` submits requests; `APPROVER` decides them; `SECURITY` verifies QR/pass IDs and records student movement.

## Database

The principal relationships are Role ↔ User, Department → Student → GatePass, and GatePass → Approval / SMSNotification / SecurityVerificationLog. Database-level unique constraints protect USNs, pass numbers, QR tokens, and approval SMS duplication.
