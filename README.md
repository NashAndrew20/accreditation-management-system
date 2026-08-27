# JMCFI AMS

Internal accreditation evidence management system built with Django and SQLite for development.

## Run locally

```bash
./.venv/bin/python manage.py migrate
DEMO_MODE=True ./.venv/bin/python manage.py seed_demo
DEMO_MODE=True ./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/login/>.

`seed_demo` is available only when `DEMO_MODE` is enabled (enabled by default while `DEBUG=True`). It creates internal demo accounts for Superadmin, Admin, QA, Accreditation Head, Program Head, Dean, and Area Chair. Their development password is `123`, and first-login password changes are currently disabled. Set `DJANGO_ENV=production` in production; demo seeding and demo authentication are disabled automatically.

## Production configuration

Set a real secret, explicit hosts, and `DEBUG=False` before deployment:

```bash
DJANGO_ENV=production DEBUG=False DJANGO_SECRET_KEY='replace-with-a-long-random-secret' DJANGO_ALLOWED_HOSTS='your-domain.example' ./.venv/bin/python manage.py check --deploy
```

`DJANGO_ENV=production` requires the secret key, disables demo mode, and enables HTTPS redirects, secure session/CSRF cookies, and HSTS by default. Override those settings only when the deployment architecture requires it.

## Workflow

Evidence is stored as Cycle → Level → Area → Sub-area → Requirement → Submission. Program Heads create versions and supporting files, then submissions move through Dean, Area Chair, and QA/Accreditation Head review. Revision requests retain the reviewer, remarks, files, versions, comments, notifications, and audit records.

All important workflow data is stored in the database. Browser local storage is not used for evidence, submissions, approvals, or review decisions.

## SonarQube Cloud

The `sonarqube cloud` workflow runs the Django tests with Python coverage and then sends the results to SonarQube Cloud on pushes to `main` and pull requests.

In the GitHub repository, open **Settings → Secrets and variables → Actions** and add:

- Repository secret `SONAR_TOKEN`: a token created in SonarQube Cloud.
- Repository variable `SONAR_ORGANIZATION`: the exact SonarQube Cloud organization key.
- Repository variable `SONAR_PROJECT_KEY`: the exact SonarQube Cloud project key.

The workflow has defaults based on this repository, but the values from the SonarQube Cloud project should be used when they differ. If automatic analysis is enabled for the project, disable it before using this GitHub Actions workflow so the project has one analysis method.
