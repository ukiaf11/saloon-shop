"""The owner's QR and UPI details, and what the public sees of them."""

from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.audit.models import AuditLog
from apps.payments.models import PaymentSettings
from apps.payments.services import PaymentMethod

from .conftest import OWNER_PASSWORD, png_bytes, png_upload

pytestmark = pytest.mark.django_db

URL = "/api/v1/owner/payment-settings"


def put(client, auth, **fields):
    fields.setdefault("password", OWNER_PASSWORD)
    return client.put(URL, data=_multipart(fields), content_type=_BOUNDARY_CT, **auth)


_BOUNDARY = "testboundary"
_BOUNDARY_CT = f"multipart/form-data; boundary={_BOUNDARY}"


def _multipart(fields) -> bytes:
    """Django's test client only encodes multipart for POST, so build it."""
    from django.test.client import encode_multipart

    return encode_multipart(_BOUNDARY, fields)


def stored_image() -> Image.Image:
    row = PaymentSettings.objects.get()
    return Image.open(io.BytesIO(bytes(row.qr_image)))


def test_owner_uploads_a_qr_and_payments_switch_to_upi(client, salon, owner_auth):
    assert client.get("/api/v1/payments/options").json() == {
        "method": "unavailable",
        "upi_qr": None,
    }

    r = put(client, owner_auth, qr_image=png_upload(), upi_id="salon@okaxis", payee_name="Salon")
    assert r.status_code == 200, r.content
    assert r.json()["method"] == "upi_qr"
    assert r.json()["qr"]["width"] == 300

    options = client.get("/api/v1/payments/options").json()
    assert options["method"] == "upi_qr"
    assert options["upi_qr"]["upi_id"] == "salon@okaxis"
    assert options["upi_qr"]["payee_name"] == "Salon"
    assert len(options["upi_qr"]["qr_image_version"]) == 16


def test_the_change_is_audited_without_the_image(client, salon, owner_auth):
    put(client, owner_auth, qr_image=png_upload())
    entry = AuditLog.objects.get(action="payment_settings.updated")
    assert entry.actor_email == "owner@test.example"
    assert entry.before["qr_sha256"] == ""
    assert len(entry.after["qr_sha256"]) == 64
    assert "qr_image" not in entry.after


def test_the_password_is_required_again(client, salon, owner_auth):
    r = put(client, owner_auth, qr_image=png_upload(), password="not it")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "reauth_failed"
    assert not PaymentSettings.objects.filter(qr_sha256__gt="").exists()


def test_only_the_owner_may_change_it(client, salon, manager_auth):
    r = put(client, manager_auth, qr_image=png_upload())
    assert r.status_code == 403
    assert client.get(URL, **manager_auth).status_code == 403


def test_signed_out_callers_are_refused(client, salon):
    assert client.get(URL).status_code == 401


def test_a_transparent_qr_is_flattened_onto_white(client, salon, owner_auth):
    """convert("RGB") alone turns transparency black, and a QR on black does
    not scan."""
    upload = SimpleUploadedFile(
        "qr.png", png_bytes(mode="RGBA", colour=(0, 0, 0, 0)), content_type="image/png"
    )
    assert put(client, owner_auth, qr_image=upload).status_code == 200
    image = stored_image()
    assert image.mode == "RGB"
    assert image.getpixel((5, 5)) == (255, 255, 255)
    assert image.getpixel((0, 0)) == (0, 0, 0)


def test_metadata_is_stripped_by_re_encoding(client, salon, owner_auth):
    source = Image.new("RGB", (400, 400), "white")
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # camera make
    buffer = io.BytesIO()
    source.save(buffer, format="JPEG", exif=exif)
    upload = SimpleUploadedFile("qr.jpg", buffer.getvalue(), content_type="image/jpeg")

    assert put(client, owner_auth, qr_image=upload).status_code == 200
    row = PaymentSettings.objects.get()
    assert row.qr_content_type == "image/png"
    assert b"PhoneMaker" not in bytes(row.qr_image)
    assert not stored_image().getexif()


def test_a_huge_image_is_scaled_down(client, salon, owner_auth):
    assert put(client, owner_auth, qr_image=png_upload(size=(3000, 3000))).status_code == 200
    assert stored_image().size == (1200, 1200)


@pytest.mark.parametrize(
    ("name", "content", "content_type"),
    [
        ("qr.png", b"definitely not an image", "image/png"),
        ("qr.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml"),
    ],
)
def test_non_images_are_rejected(client, salon, owner_auth, name, content, content_type):
    upload = SimpleUploadedFile(name, content, content_type=content_type)
    r = put(client, owner_auth, qr_image=upload)
    assert r.status_code == 400
    assert not PaymentSettings.objects.filter(qr_sha256__gt="").exists()


def test_an_image_over_4_mb_is_rejected_before_decoding(client, salon, owner_auth):
    """Vercel drops bodies over 4.5 MB before Django sees them, so the limit is
    4 MB and says why, rather than failing later with a bare 413."""
    oversized = SimpleUploadedFile(
        "qr.png", b"\0" * (4 * 1024 * 1024 + 1), content_type="image/png"
    )
    r = put(client, owner_auth, qr_image=oversized)
    assert r.status_code == 400
    assert "4 MB" in r.json()["error"]["message"]


def test_a_tiny_image_is_rejected(client, salon, owner_auth):
    assert put(client, owner_auth, qr_image=png_upload(size=(50, 50))).status_code == 400


@pytest.mark.parametrize("upi_id", ["no-at-sign", "a@b", "spaces here@okaxis", "x@1bank"])
def test_malformed_upi_ids_are_rejected(client, salon, owner_auth, upi_id):
    r = put(client, owner_auth, upi_id=upi_id)
    assert r.status_code == 400


def test_the_upi_id_can_be_cleared(client, salon, owner_auth, qr_on_file):
    r = put(client, owner_auth, upi_id="")
    assert r.status_code == 200
    assert r.json()["upi_id"] == ""
    assert client.get("/api/v1/payments/options").json()["upi_qr"]["upi_id"] is None


def test_removing_the_qr_turns_upi_payments_off(client, salon, owner_auth, qr_on_file):
    r = put(client, owner_auth, remove_qr="true")
    assert r.status_code == 200
    assert r.json()["method"] == PaymentMethod.UNAVAILABLE
    assert client.get("/api/v1/payments/qr-image").status_code == 404


def test_upload_and_remove_together_is_ambiguous(client, salon, owner_auth):
    assert put(client, owner_auth, qr_image=png_upload(), remove_qr="true").status_code == 400


def test_a_configured_gateway_takes_over_from_the_qr(client, salon, qr_on_file, monkeypatch):
    """When Phase 5's gateway is configured, the fallback switches itself off."""
    monkeypatch.setattr("apps.payments.services.gateway_configured", lambda salon: True)
    assert client.get("/api/v1/payments/options").json() == {"method": "gateway", "upi_qr": None}


def test_the_qr_image_is_served_with_caching(client, salon, qr_on_file):
    r = client.get("/api/v1/payments/qr-image")
    assert r.status_code == 200
    assert r["Content-Type"] == "image/png"
    assert r["Cache-Control"] == "public, max-age=60"
    etag = r["ETag"]

    assert client.get("/api/v1/payments/qr-image", HTTP_IF_NONE_MATCH=etag).status_code == 304

    version = client.get("/api/v1/payments/options").json()["upi_qr"]["qr_image_version"]
    versioned = client.get(f"/api/v1/payments/qr-image?v={version}")
    assert versioned["Cache-Control"] == "public, max-age=31536000, s-maxage=31536000, immutable"
    assert Image.open(io.BytesIO(versioned.content)).format == "PNG"


def test_no_qr_means_no_image(client, salon):
    assert client.get("/api/v1/payments/qr-image").status_code == 404


def test_the_qr_image_is_rate_limited_like_other_public_reads(client, salon, qr_on_file):
    from unittest import mock

    with mock.patch(
        "common.throttling.ResilientScopedRateThrottle.allow_request", return_value=False
    ):
        assert client.get("/api/v1/payments/qr-image?v=bust").status_code == 429


def test_wrong_passwords_on_the_qr_form_lock_a_stolen_session_out(client, salon, owner, owner_auth):
    for _ in range(5):
        assert put(client, owner_auth, upi_id="x@okaxis", password="guess").status_code == 403
    owner.refresh_from_db()
    assert owner.is_locked
    assert client.get(URL, **owner_auth).status_code == 401
