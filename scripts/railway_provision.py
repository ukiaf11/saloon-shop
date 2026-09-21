#!/usr/bin/env python3
"""Provision the whole stack on Railway in one run.

    RAILWAY_API_KEY=... python scripts/railway_provision.py            # do it
    RAILWAY_API_KEY=... python scripts/railway_provision.py --dry-run  # show the plan

Creates one project with seven services:

    Postgres   official Railway template
    Redis      official Railway template
    backend    Django API        (backend/, Dockerfile, gunicorn)
    worker     Celery worker     (same image, different start command)
    beat       Celery Beat       (same image; exactly ONE replica, ever)
    frontend   Next.js           (frontend/, Dockerfile)
    + a volume on backend for uploaded media

Every mutation and input field used here was checked against Railway's live
GraphQL schema by introspection before this file was written.

PREREQUISITE, one-time and manual: Railway builds from the GitHub repo, so its
GitHub app must be allowed to read `ukiaf11/saloon-shop`
(Railway dashboard -> Account -> Integrations -> GitHub). An API token cannot
grant that itself.

Secrets are generated here and sent straight to Railway. They are never printed
in full and never written to disk.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import urllib.request

API = "https://backboard.railway.com/graphql/v2"

REPO = "ukiaf11/saloon-shop"
BRANCH = "main"
PROJECT_NAME = "saloon-shop"

TEMPLATE_POSTGRES = "postgres"
TEMPLATE_REDIS = "redis"

MEDIA_MOUNT = "/app/media"


# --- transport -------------------------------------------------------------


class RailwayError(RuntimeError):
    pass


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    if payload.get("errors"):
        raise RailwayError("; ".join(e.get("message", "?") for e in payload["errors"]))
    return payload["data"]


# --- secrets ---------------------------------------------------------------


def fernet_key() -> str:
    """A Fernet key without importing cryptography: 32 random bytes, url-safe b64."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def masked(value: str) -> str:
    return value[:4] + "…" + f"({len(value)} chars)"


# --- steps -----------------------------------------------------------------


def workspace_id(token: str) -> str:
    data = gql(token, "{ projects { edges { node { workspace { id name } } } } }")
    edges = data["projects"]["edges"]
    if not edges:
        raise RailwayError("No workspace visible to this token.")
    ws = edges[0]["node"]["workspace"]
    print(f"  workspace: {ws['name']}")
    return ws["id"]


def create_project(token: str, ws: str) -> tuple[str, str]:
    data = gql(
        token,
        """mutation($i: ProjectCreateInput!) {
             projectCreate(input: $i) { id environments { edges { node { id name } } } }
           }""",
        {"i": {"name": PROJECT_NAME, "workspaceId": ws,
               "description": "Salon Lucky Customer Platform"}},
    )["projectCreate"]
    env = data["environments"]["edges"][0]["node"]
    print(f"  project {PROJECT_NAME}: {data['id']} (env {env['name']})")
    return data["id"], env["id"]


def deploy_template(token: str, code: str, project: str, env: str, ws: str) -> None:
    tpl = gql(token, "query($c:String!){ template(code:$c){ id serializedConfig } }",
              {"c": code})["template"]
    gql(
        token,
        """mutation($i: TemplateDeployV2Input!) { templateDeployV2(input: $i) { projectId } }""",
        {"i": {"templateId": tpl["id"], "serializedConfig": tpl["serializedConfig"],
               "projectId": project, "environmentId": env, "workspaceId": ws}},
    )
    print(f"  {code}: deployed from official template")


def create_service(token: str, project: str, env: str, name: str) -> str:
    sid = gql(
        token,
        """mutation($i: ServiceCreateInput!) { serviceCreate(input: $i) { id } }""",
        {"i": {"projectId": project, "environmentId": env, "name": name,
               "branch": BRANCH, "source": {"repo": REPO}}},
    )["serviceCreate"]["id"]
    print(f"  service {name}: {sid}")
    return sid


def configure(token: str, sid: str, env: str, **fields) -> None:
    gql(
        token,
        """mutation($s:String!,$e:String!,$i:ServiceInstanceUpdateInput!) {
             serviceInstanceUpdate(serviceId:$s, environmentId:$e, input:$i) }""",
        {"s": sid, "e": env, "i": fields},
    )


def set_vars(token: str, project: str, env: str, sid: str, variables: dict) -> None:
    gql(
        token,
        """mutation($i: VariableCollectionUpsertInput!) { variableCollectionUpsert(input: $i) }""",
        {"i": {"projectId": project, "environmentId": env, "serviceId": sid,
               "variables": variables, "skipDeploys": True}},
    )


def add_volume(token: str, project: str, env: str, sid: str) -> None:
    gql(
        token,
        """mutation($i: VolumeCreateInput!) { volumeCreate(input: $i) { id } }""",
        {"i": {"projectId": project, "environmentId": env, "serviceId": sid,
               "mountPath": MEDIA_MOUNT}},
    )
    print(f"  volume mounted at {MEDIA_MOUNT}")


def add_domain(token: str, env: str, sid: str, port: int) -> str:
    return gql(
        token,
        """mutation($i: ServiceDomainCreateInput!) { serviceDomainCreate(input: $i) { domain } }""",
        {"i": {"environmentId": env, "serviceId": sid, "targetPort": port}},
    )["serviceDomainCreate"]["domain"]


def redeploy(token: str, sid: str, env: str) -> None:
    gql(token, "mutation($s:String!,$e:String!){ serviceInstanceRedeploy(serviceId:$s, environmentId:$e) }",
        {"s": sid, "e": env})


# --- main ------------------------------------------------------------------


PLAN = """
  1. create project '{name}'
  2. Postgres + Redis from official templates
  3. backend  : backend/  Dockerfile, gunicorn, healthcheck /healthz,
                pre-deploy `migrate`, media volume at {mount}
  4. worker   : same image, `celery -A config worker`
  5. beat     : same image, `celery -A config beat`, exactly 1 replica
  6. frontend : frontend/ Dockerfile, NEXT_PUBLIC_* passed as build args
  7. generate DJANGO_SECRET_KEY and FIELD_ENCRYPTION_KEY
  8. public domains for backend + frontend, then cross-wire CORS/CSRF/hosts
  9. redeploy everything with the final variables
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("Plan:" + PLAN.format(name=PROJECT_NAME, mount=MEDIA_MOUNT))
    if args.dry_run:
        return 0

    token = os.environ.get("RAILWAY_API_KEY") or os.environ.get("RAILWAY_API_TOKEN")
    if not token:
        print("Set RAILWAY_API_KEY.", file=sys.stderr)
        return 2

    try:
        ws = workspace_id(token)
        project, env = create_project(token, ws)

        deploy_template(token, TEMPLATE_POSTGRES, project, env, ws)
        deploy_template(token, TEMPLATE_REDIS, project, env, ws)

        backend = create_service(token, project, env, "backend")
        worker = create_service(token, project, env, "worker")
        beat = create_service(token, project, env, "beat")
        frontend = create_service(token, project, env, "frontend")

        django_secret = secrets.token_urlsafe(50)
        field_key = fernet_key()
        print(f"  DJANGO_SECRET_KEY     {masked(django_secret)}")
        print(f"  FIELD_ENCRYPTION_KEY  {masked(field_key)}")

        # Railway resolves ${{Service.VAR}} references at deploy time, so the
        # database credentials never pass through this script.
        shared = {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": django_secret,
            "FIELD_ENCRYPTION_KEY": field_key,
            "DATABASE_URL": "${{Postgres.DATABASE_URL}}",
            "REDIS_URL": "${{Redis.REDIS_URL}}",
            "CELERY_BROKER_URL": "${{Redis.REDIS_URL}}",
            "CELERY_RESULT_BACKEND": "${{Redis.REDIS_URL}}",
            "SALON_TIMEZONE": "Asia/Kolkata",
            "PAYMENT_GATEWAY_MODE": "test",
            "ENVIRONMENT": "production",
            "MEDIA_ROOT": MEDIA_MOUNT,
        }

        for sid, start in (
            (backend, None),
            (worker, "celery -A config worker -l info --concurrency 2"),
            (beat, "celery -A config beat -l info "
                   "--scheduler django_celery_beat.schedulers:DatabaseScheduler"),
        ):
            fields = {"rootDirectory": "backend", "dockerfilePath": "Dockerfile",
                      "builder": "DOCKERFILE"}
            if start:
                fields["startCommand"] = start
            else:
                fields.update(healthcheckPath="/healthz", healthcheckTimeout=120,
                              preDeployCommand=["python manage.py migrate --noinput"])
            if sid == beat:
                # Two Beat processes would fire every scheduled task twice.
                fields["numReplicas"] = 1
            configure(token, sid, env, **fields)

        configure(token, frontend, env, rootDirectory="frontend",
                  dockerfilePath="Dockerfile", builder="DOCKERFILE",
                  healthcheckPath="/", healthcheckTimeout=120)

        add_volume(token, project, env, backend)

        api_host = add_domain(token, env, backend, 8000)
        web_host = add_domain(token, env, frontend, 3000)
        api, web = f"https://{api_host}", f"https://{web_host}"
        print(f"  backend  -> {api}")
        print(f"  frontend -> {web}")

        backend_vars = {
            **shared,
            "PORT": "8000",
            "DJANGO_ALLOWED_HOSTS": api_host,
            "CORS_ALLOWED_ORIGINS": web,
            "CSRF_TRUSTED_ORIGINS": web,
        }
        set_vars(token, project, env, backend, backend_vars)
        set_vars(token, project, env, worker, {**backend_vars})
        set_vars(token, project, env, beat, {**backend_vars})
        set_vars(token, project, env, frontend, {
            "PORT": "3000",
            # Read as Docker build args -- see the ARGs in frontend/Dockerfile.
            "NEXT_PUBLIC_API_BASE_URL": f"{api}/api/v1",
            "NEXT_PUBLIC_SITE_URL": web,
            "NEXT_PUBLIC_MEDIA_HOSTNAME": api_host,
            # Stays unindexed until checkout genuinely works.
            "NEXT_PUBLIC_NOINDEX": "1",
        })

        for sid in (backend, worker, beat, frontend):
            redeploy(token, sid, env)

    except RailwayError as exc:
        print(f"\nRailway refused: {exc}", file=sys.stderr)
        if "limit" in str(exc).lower() or "upgrade" in str(exc).lower():
            print("The account plan does not allow more resources. Add credits "
                  "or upgrade, then re-run.", file=sys.stderr)
        return 1

    print(f"""
Provisioned. Once the first deploy is green, seed the live database:

  railway run --service backend python manage.py seed_salon
  railway run --service backend python manage.py seed_catalog
  railway run --service backend python manage.py seed_content
  railway run --service backend python manage.py seed_campaign_config

Site: {web}
API:  {api}/api/v1/readiness
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
