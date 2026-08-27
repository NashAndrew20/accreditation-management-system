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

## JWT API

The website continues to use Django session authentication. API clients use
JSON Web Tokens (JWT) through Django REST Framework and SimpleJWT.

Endpoints:

- `POST /api/auth/token/` — exchange an approved user's username or email and password for an access token and refresh token.
- `POST /api/auth/token/refresh/` — exchange a refresh token for a new access token.
- `GET /api/auth/me/` — protected current-user and active-role information.
- `GET /api/evidence/` — protected evidence submissions limited by the user's existing role and department access.

Access tokens last 15 minutes by default and refresh tokens last 1 day. Set
`JWT_ACCESS_TOKEN_MINUTES` or `JWT_REFRESH_TOKEN_DAYS` in the environment to
change those lifetimes. JWT signing uses Django's `SECRET_KEY`; production
deployments must provide it through `DJANGO_SECRET_KEY`.

Example local request:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"qa","password":"123"}'
```

Use the returned access token with a protected endpoint:

```bash
curl http://127.0.0.1:8000/api/auth/me/ \
  -H 'Authorization: Bearer <access-token>'
```

## Redis caching

Redis runs in Docker; it does not need to be installed directly on the host.
The project uses Django's built-in Redis cache backend and caches only the
active accreditation cycle structure used by the Levels &amp; Areas page. This
configuration data is not user-specific or sensitive, and it expires after
five minutes.

Start Redis for Django running directly on the host:

```bash
docker compose up -d redis
REDIS_URL=redis://127.0.0.1:6379/1 ./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

If port 6379 is already in use, choose another host port for this Compose
service and use the same URL for Django:

```bash
REDIS_PORT=6380 docker compose up -d redis
REDIS_URL=redis://127.0.0.1:6380/1 ./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

When Django runs inside Docker, set `REDIS_URL=redis://redis:6379/1` in the
Django service because `redis` is the Compose service hostname.

Check the container and connection:

```bash
docker compose ps redis
docker compose exec redis redis-cli ping
```

To prove Django is writing to Redis, run this while the Redis service is up:

```bash
./.venv/bin/python manage.py shell -c "from django.core.cache import cache; cache.set('d2-cache-check', 'redis-ok', 300); print(cache.get('d2-cache-check'))"
docker compose exec redis redis-cli -n 1 --scan --pattern '*d2-cache-check*'
```

Open the PACUCOA Levels &amp; Areas page once, then inspect the cached structure:

```bash
docker compose exec redis redis-cli -n 1 --scan --pattern '*accreditation:active-structure*'
```

Stop Redis with `docker compose stop redis` and restart it with
`docker compose start redis`. `docker compose down` removes the container and
network but keeps the named Redis volume; `docker compose down -v` also removes
the cached Redis data.

## Login rate limiting

The normal website login (`POST /login/`) and the API token endpoint
(`POST /api/auth/token/`) allow 5 attempts per client IP in a one-minute
window. The website returns the login page with HTTP 429 after the limit; the
API returns HTTP 429 JSON with a `Retry-After` header. The counter expires
automatically, so legitimate users are not permanently blocked. The project
uses Django's cache for the website limiter and DRF's `AnonRateThrottle` for
the API limiter.

## SonarQube Cloud

The `sonarqube cloud` workflow runs the Django tests with Python coverage and then sends the results to SonarQube Cloud on pushes to `main` and pull requests.

In the GitHub repository, open **Settings → Secrets and variables → Actions** and add:

- Repository secret `SONAR_TOKEN`: a token created in SonarQube Cloud.
- Repository variable `SONAR_ORGANIZATION`: the exact SonarQube Cloud organization key.
- Repository variable `SONAR_PROJECT_KEY`: the exact SonarQube Cloud project key.

The workflow has defaults based on this repository, but the values from the SonarQube Cloud project should be used when they differ. If automatic analysis is enabled for the project, disable it before using this GitHub Actions workflow so the project has one analysis method.
