# Local Volunteer Matcher Platform (Django)

Connects neighborhood residents with verified non-profit service opportunities.
Built from the project PPT: dual user/admin portals, automated hour tracker, verified PDF certificates.

## Run in VS Code

```bash
# 1. open this folder in VS Code, then open the terminal (Ctrl+`)
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt

python manage.py makemigrations core
python manage.py migrate
python manage.py createsuperuser # site owner, used to verify organizers
python manage.py runserver
```

Open http://127.0.0.1:8000/  (site admin: http://127.0.0.1:8000/admin/)

In VS Code: install the **Python** extension and pick the `venv` interpreter
(Ctrl+Shift+P -> "Python: Select Interpreter").

## Try the full workflow

1. **Sign up** as *Non-Profit Admin* (e.g. user `ngo1`, organization "Green Park Trust").
2. In `/admin/` (superuser) -> **Profiles** -> tick that organizer -> action **"Issue verified organizer credentials"**.
3. Log in as `ngo1` -> **Publish a drive** (set required hours + volunteer cap).
4. Sign up in a private window as a *Resident / Volunteer* -> open the drive -> **Sign up**.
5. Volunteer -> **Log hours** (after the shift).
6. `ngo1` -> **Review hours** -> **Approve**.
7. When approved hours >= required hours, the volunteer sees **Download PDF certificate**.
   The certificate has a verification code; anyone can check it at `/verify/<code>/`.

## Slide -> feature map

| Slide | Feature | Where |
|---|---|---|
| Dual User & Admin Portals / Role-Based Core | `Profile.role` + `volunteer_required` / `organizer_required` | `core/models.py`, `core/decorators.py` |
| Browse local drive postings | Drive list + search | `drive_list` |
| Create postings with hour/cap limits | `Drive.required_hours`, `Drive.capacity` | `DriveForm`, `drive_create` |
| Capacity caps prevent over-booking | Row-locked signup check | `drive_signup` |
| Log completed service hours | `HourLog` (status: pending) | `log_hours` |
| Verify & approve submitted logs | Approve / reject with note | `review_logs` |
| Issue verified organizer credentials | `Profile.is_verified` via admin action | `core/admin.py` |
| Automated signed PDF certificates | ReportLab PDF, auto-issued on approval | `core/certificates.py`, `Certificate` |

## Project layout

```
volunteer_matcher/
  manage.py
  config/        settings, urls, wsgi
  core/          models, views, forms, urls, admin, certificates, templates/
```


## Manager role (two-step approval)

Volunteer logs hours -> **Manager checks** -> **Admin gives final approval** -> certificate.

1. Sign up an account with role **Manager** (e.g. username `manager`).
2. In `/admin/` -> **Profiles** -> open the manager -> set **Reports to** = the Non-Profit Admin they work for -> Save.
3. The manager's dashboard ("Manager queue") lists volunteer logs waiting for a check. *Approve & send to admin* forwards it; *Reject* stops it.
4. The admin's "Review hours" page then shows only hours the manager already approved.
5. If an organizer has no manager assigned, the admin reviews volunteer logs directly so nothing gets stuck.

After updating the code run: `python manage.py makemigrations core` then `python manage.py migrate`.
# -volunteer-matcher
