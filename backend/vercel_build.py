"""Vercel build hook: migrate the production database before the new code serves.

Runs via [tool.vercel.scripts] build, inside the build's venv, after
`uv sync --no-dev` and before Vercel's Django hook.

Production only. vercel.json's git.deploymentEnabled already stops branches
other than main from deploying, but this refuses on its own too, because a
preview migrating the production database would be a silent, shared-state
disaster.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    if os.environ.get("VERCEL_ENV") != "production":
        print("vercel_build: not a production build, skipping database steps")
        return 0
    if os.environ.get("VERCEL_BUILD_SKIP_DB") == "1":
        print("vercel_build: VERCEL_BUILD_SKIP_DB=1, skipping database steps")
        return 0

    # DDL goes over the DIRECT connection. The pooled URL routes through
    # PgBouncer in transaction mode, which Neon warns is error-prone for
    # migrations.
    if os.environ.get("DATABASE_URL_UNPOOLED"):
        os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_UNPOOLED"]
    if not os.environ.get("DATABASE_URL"):
        # Fail closed: deploying code whose schema was never applied is worse
        # than not deploying.
        print("vercel_build: DATABASE_URL is missing", file=sys.stderr)
        return 1

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
    import django

    django.setup()
    from django.core.management import call_command

    call_command("migrate", interactive=False)
    # Not a migration: the DatabaseCache table. A no-op when it already exists.
    call_command("createcachetable")

    # One-off, switched on by env vars that are deleted after the first deploy.
    # Every seed command uses get_or_create, so a repeat run is harmless.
    if os.environ.get("SEED_ON_BUILD") == "1":
        call_command(
            "seed_salon", owner_email=os.environ.get("SEED_OWNER_EMAIL", "owner@example.com")
        )
        for command in ("seed_catalog", "seed_content", "seed_campaign_config"):
            call_command(command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
