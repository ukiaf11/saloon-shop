"""A static guard against the campaign's secrets reaching any API surface.

The per-endpoint tests check the responses that exist today. This one checks the
code, so that a serializer added next month cannot quietly expose a seed or a
winning position without failing the build.

REQUIREMENTS.md section 5, invariant 6: winning positions never leave the
server -- not in an API response, a serializer, a log line or an error message.
"""

from __future__ import annotations

import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parents[1]

FORBIDDEN_FIELDS = (
    "encrypted_seed",
    "encrypted_winning_positions",
    "winning_positions",
)

#: Files whose whole job is to handle these values.
ALLOWED = {
    "apps/promotions/lucky.py",
    "apps/promotions/models.py",
    "apps/promotions/services.py",
    "apps/promotions/migrations/0002_dailycampaign_slotreservation_and_more.py",
}


def _sources(*globs: str) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for pattern in globs:
        out.extend(
            p for p in BACKEND.glob(pattern) if ".venv" not in p.parts and "tests" not in p.parts
        )
    return out


def test_no_serializer_or_view_mentions_a_campaign_secret():
    offenders = []
    for path in _sources("apps/**/serializers.py", "apps/**/views.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel in ALLOWED:
            continue
        text = path.read_text()
        for field in FORBIDDEN_FIELDS:
            if field in text:
                offenders.append(f"{rel}: {field}")
    assert not offenders, "campaign secrets must never reach a serializer or view: " + "; ".join(
        offenders
    )


def test_only_the_promotions_service_layer_decrypts_positions():
    """Every caller of this function is a place a leak could happen, so the
    call sites are pinned down rather than left to review."""
    callers = []
    for path in _sources("apps/**/*.py", "tasks/**/*.py", "config/**/*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        text = path.read_text()
        if re.search(r"\bdecrypt_winning_positions\s*\(", text):
            callers.append(rel)

    # Phase 4 defines it; Phase 6's lucky decision will be the first real
    # caller. Anything else appearing here needs justifying.
    assert set(callers) <= {"apps/promotions/services.py"}, (
        f"unexpected caller of decrypt_winning_positions: {callers}"
    )


def test_public_progress_is_the_only_campaign_payload_builder():
    """Catches a second, ad-hoc payload builder that skips the allowlist."""
    views = BACKEND / "apps/promotions/views.py"
    text = views.read_text()
    assert "public_progress" in text
    # The view must not assemble its own dict from the model.
    assert "campaign.capacity" not in text
    assert "campaign.paid_count" not in text
