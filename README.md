# Sembon College Management System

A Django college management starter for one department: **B.Sc. Computer Science**. Administrators manage college records and student messages, staff take attendance and manage assignments, and students can monitor attendance and view assignment completion status.

## Requirements

- Python 3.10 or later
- pip

## Run locally

From this directory, open PowerShell and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to sign in. The application uses SQLite by default. Local attendance emails are printed in the development server console.

## College workflows

- **Administrator:** use the dashboard to review staff, students, and attendance totals. Open the student inbox to review messages sent by students. Manage individual records through `/django-admin/`.
- **New members:** request a staff or student account from the sign-in page using your full name, email, role, and department. Phone and an application message are optional. Requests appear in the administrator inbox. On approval, the administrator sets the initial password and shares it securely; declining removes the request.
- **Staff:** use the staff dashboard to mark attendance, review student attendance percentages, and create assignments. For each assignment, staff can mark each student's completion status. Unchecked students on the attendance form are marked absent.
- **Student:** use the student portal to review attendance percentage, assignments, and published marks. The campus assistant answers from `accounts/data/chat_knowledge.json` and current assignment/result records. Unknown or unpublished information is not guessed; students can explicitly forward the current conversation to an active staff mentor and continue chatting in the portal.
- **Mentor chats:** active staff accounts can view only conversations forwarded to their own account at `/mentor/dashboard/`, reply in the portal, and close chats. Student chat history, mentor replies, unread state, and Pending/Replied/Closed status are stored in the database. Mentor expertise can be edited in the Profile section of `/django-admin/`; active staff accounts are considered available.
- **Knowledge base:** edit `accounts/data/chat_knowledge.json` to maintain course, fee, FAQ, intent, and follow-up data. The schedule list is currently empty, so schedule questions are referred to a mentor rather than guessed. Run `python manage.py test accounts.tests.test_chat_knowledge` to check the sample question matrix.
- **Appearance:** use the header toggle to switch between light and dark themes. The choice is remembered in the browser.

Attendance is recorded once per student per date. This simple starter calculates the percentage from the attendance records entered in the system.

## Demo sign-in accounts

All seeded accounts use this demo password:

```text
CampusDemo2026!
```

| Role | Email |
|---|---|
| Administrator | admin@college.edu |
| Staff | staff1@college.edu |
| Staff | staff2@college.edu |
| Staff | staff3@college.edu |
| Staff | staff4@college.edu |
| Staff | staff5@college.edu |
| Student | student1@college.edu |
| Student | student2@college.edu |
| Student | student3@college.edu |
| Student | student4@college.edu |
| Student | student5@college.edu |

These are sample development credentials, not production credentials. Change or remove them before deployment. `seed_demo_data` updates the sample profile names and department but does not replace existing passwords.

## Configure real email delivery

The default email backend writes messages to the development server console. To send attendance inquiries through SMTP, configure these environment variables before starting Django:

```powershell
$env:DJANGO_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST = "smtp.example.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_HOST_USER = "your-smtp-user"
$env:EMAIL_HOST_PASSWORD = "your-smtp-password"
$env:EMAIL_USE_TLS = "true"
$env:DEFAULT_FROM_EMAIL = "college@example.com"
$env:COLLEGE_ADMIN_EMAIL = "admin@college.edu"
```

The first superuser email address is used as the administrator recipient; `COLLEGE_ADMIN_EMAIL` is the fallback. Use an SMTP provider's app password or credential mechanism, and keep real credentials outside source control.

## Deployment

Set `DJANGO_SECRET_KEY` to a new secret value, set `DJANGO_DEBUG=false`, and configure `DJANGO_ALLOWED_HOSTS` with the actual host names. Do not deploy the development secret or demo accounts.

## Tests

```powershell
python manage.py test
```
