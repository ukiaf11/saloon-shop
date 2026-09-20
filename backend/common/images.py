"""Uploaded image validation.

Applied to every admin-uploaded image (service photos, gallery images, logo).
Validation happens before the file reaches storage: an oversized or
wrong-format upload is rejected, not resized silently, so the owner gets a
clear error instead of a degraded image.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB -- multi-megabyte hero images are a
# mobile performance problem (Doc 3 section 33)
MIN_DIMENSION = 200
MAX_DIMENSION = 6000

ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"})
ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".avif"})


def validate_image_file(file) -> None:
    """Validate an uploaded image. Raises ValidationError on any failure."""
    size = getattr(file, "size", None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"Image must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.")

    name = (getattr(file, "name", "") or "").lower()
    if name:
        dot = name.rfind(".")
        extension = name[dot:] if dot != -1 else ""
        if extension not in ALLOWED_EXTENSIONS:
            raise ValidationError("Image must be a JPEG, PNG, WebP or AVIF file.")

    content_type = getattr(file, "content_type", None)
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("Image must be a JPEG, PNG, WebP or AVIF file.")

    # Verify the bytes really are an image, rather than trusting the extension
    # or the client-supplied content type.
    width, height = _read_dimensions(file)
    if width is None or height is None:
        return

    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise ValidationError(f"Image must be at least {MIN_DIMENSION}x{MIN_DIMENSION} pixels.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValidationError(f"Image must be at most {MAX_DIMENSION}x{MAX_DIMENSION} pixels.")


def _read_dimensions(file) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        return (None, None)

    position = file.tell() if hasattr(file, "tell") else None
    try:
        if hasattr(file, "seek"):
            file.seek(0)
        with Image.open(file) as image:
            image.verify()
            return image.size
    except Exception as exc:
        raise ValidationError("File is not a readable image.") from exc
    finally:
        if position is not None and hasattr(file, "seek"):
            file.seek(position)
