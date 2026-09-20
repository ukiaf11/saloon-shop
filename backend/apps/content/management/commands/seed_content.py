"""Seed the editable website content for a development or staging salon.

Idempotent by design: it only creates rows that are missing, so re-running it
after the owner has edited copy in the admin never overwrites their words.

The legal pages are seeded as *drafts* with placeholder bodies. Binding legal
text is the owner's and their counsel's to write (REQUIREMENTS.md section 1,
"Legal copy"); inventing it here would put words in their mouth and the public
endpoint would happily serve them, so the placeholders say so loudly and
``published_at`` stays null until someone publishes real copy.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.content.models import FaqItem, LegalPage, SiteContent, Testimonial
from apps.salons.models import Salon

# Keys and value shapes are fixed by API_CONTRACT_PHASE2.md (GET /api/v1/salon).
# The "Har Din 5 Lucky Slots" wording is the recommendation still awaiting owner
# sign-off (memory.md section 6) -- seeded so the page is testable, not settled.
SITE_CONTENT = {
    "hero_eyebrow": "Premium grooming. Daily rewards.",
    "hero_heading": "Har Din 5 Lucky Slots",
    "hero_subheading": ("Hair Cutting + Shaving + Face Massage free for the day's lucky slots."),
    "why_choose_us": [
        {
            "title": "Trained stylists",
            "body": "Every stylist is trained on current cuts, fades and beard work.",
        },
        {
            "title": "Hygiene first",
            "body": "Fresh linen for every client and tools sterilised between appointments.",
        },
        {
            "title": "Honest pricing",
            "body": "The price you see is the price you pay. No surprise add-ons at the chair.",
        },
        {
            "title": "A reason to come back",
            "body": "Book two or more services and the 10% discount applies automatically.",
        },
    ],
    # Real handles come from the owner (REQUIREMENTS.md section 1, "Salon
    # content"). null, not "", is how the contract represents an absent link.
    "social_links": {"instagram": None, "facebook": None},
}

FAQS = [
    (
        "How do the daily lucky slots work?",
        "A fixed number of lucky slots is generated for each day before the first "
        "customer of that day pays. Every paid booking takes the next position in "
        "the day's queue, and if that position is one of the lucky ones you win. "
        "The slots are decided in advance and cannot be changed once the day has "
        "started, so nobody -- including us -- can move them around afterwards.",
    ),
    (
        "When do I find out whether I won?",
        "Immediately. The result appears on the confirmation screen as soon as your "
        "payment is confirmed. There is no draw to wait for and no separate "
        "announcement.",
    ),
    (
        "What does a winner actually get?",
        "The reward package is Hair Cutting + Shaving + Face Massage. You are "
        "refunded what you paid for the package services you booked, and the "
        "package services you did not book are added to your coupon as free "
        "services. Anything outside the package stays paid for as normal.",
    ),
    (
        "Are all the lucky slots won every day?",
        "Not necessarily. The lucky positions are spread across the whole day's "
        "capacity, so on a quiet day some of them are simply never reached. Fewer "
        "bookings than capacity means fewer winners that day.",
    ),
    (
        "How does the 10% discount work?",
        "Pick two or more different services and 10% comes off the total "
        "automatically -- there is no code to enter. Booking the same service "
        "twice does not count: the discount is for combining different services.",
    ),
    (
        "How do I use my coupon?",
        "Every booking gets a QR coupon. Show it at the salon and we scan it. Each "
        "coupon can be redeemed once, within the validity period printed on it.",
    ),
]

TESTIMONIALS = [
    (
        "Rahul S.",
        5,
        "Clean place, no waiting and the fade was exactly what I asked for. "
        "Booked the haircut and beard trim together and the discount came off "
        "on its own.",
    ),
    (
        "Imran K.",
        5,
        "Won a lucky slot on my second visit and the refund was back in my "
        "account the same week. Genuinely did not expect it to be that simple.",
    ),
    (
        "Deepak V.",
        4,
        "Good haircut and fair prices. Saturday evening gets busy, so I book "
        "earlier in the day now.",
    ),
    (
        "Sanjay M.",
        5,
        "Been going for months. Same stylist every time and he remembers how I "
        "like it. The face massage is worth it on its own.",
    ),
]

PLACEHOLDER_BODY = """## AWAITING LEGAL SIGN-OFF

**This is placeholder text. It is not a policy and it is not binding.**

The real wording for this page has to be written and approved by the salon
owner and their legal adviser before launch. Until that happens this page is a
draft and is not served by the public API.
"""

LEGAL_PAGES = [
    (LegalPage.Slug.TERMS, "Terms of Service"),
    (LegalPage.Slug.PRIVACY, "Privacy Policy"),
    (LegalPage.Slug.REFUNDS, "Refund Policy"),
    (LegalPage.Slug.PROMOTION_RULES, "Promotion Rules"),
]


class Command(BaseCommand):
    help = "Create the editable site content, FAQs, testimonials and draft legal pages."

    def add_arguments(self, parser):
        parser.add_argument(
            "--salon-slug",
            default=None,
            help="Salon to seed. Defaults to the only active salon.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        salon = self._resolve_salon(options["salon_slug"])
        self.stdout.write(f"seeding content for: {salon.name}")

        for key, value in SITE_CONTENT.items():
            _, created = SiteContent.objects.get_or_create(
                salon=salon, key=key, defaults={"value": value}
            )
            self._report(created, f"site content {key}")

        for order, (question, answer) in enumerate(FAQS, start=1):
            _, created = FaqItem.objects.get_or_create(
                salon=salon,
                question=question,
                defaults={"answer": answer, "is_published": True, "display_order": order},
            )
            self._report(created, f"faq #{order}")

        for order, (author, rating, body) in enumerate(TESTIMONIALS, start=1):
            _, created = Testimonial.objects.get_or_create(
                salon=salon,
                author_name=author,
                defaults={
                    "rating": rating,
                    "body": body,
                    "is_published": True,
                    "display_order": order,
                },
            )
            self._report(created, f"testimonial {author}")

        for slug, title in LEGAL_PAGES:
            _, created = LegalPage.objects.get_or_create(
                salon=salon,
                slug=slug,
                version=1,
                defaults={
                    "title": title,
                    "body_markdown": PLACEHOLDER_BODY,
                    "published_at": None,
                },
            )
            self._report(created, f"legal draft {slug}")

        self.stdout.write(
            self.style.WARNING(
                "Legal pages are drafts and will 404 until real copy is published "
                "via content.services.publish_legal_page."
            )
        )

    def _resolve_salon(self, slug: str | None) -> Salon:
        if slug:
            try:
                return Salon.objects.get(slug=slug)
            except Salon.DoesNotExist as exc:
                raise CommandError(f"No salon with slug {slug!r}.") from exc

        salons = list(Salon.objects.filter(status=Salon.Status.ACTIVE).order_by("created_at")[:2])
        if not salons:
            raise CommandError("No active salon found. Run seed_salon first.")
        if len(salons) > 1:
            raise CommandError("More than one active salon; pass --salon-slug.")
        return salons[0]

    def _report(self, created: bool, what: str) -> None:
        self.stdout.write(f"{'created' if created else 'exists'}: {what}")
