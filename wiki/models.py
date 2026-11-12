from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def validate_source(value):
    if value and urlsplit(value).scheme not in ("http", "https"):
        raise ValidationError("출처는 http 또는 https 주소만 사용할 수 있습니다.")


class Document(models.Model):
    class Kind(models.TextChoices):
        TRANSCRIPT = "transcript", "유튜브 대본"
        ONBOARDING = "onboarding", "온보딩 자료"
        MANUAL = "manual", "매뉴얼"

    slug = models.SlugField(unique=True, max_length=160)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.slug


class DocumentVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "초안"
        PUBLISHED = "published", "발행"
        ARCHIVED = "archived", "보관"

    document = models.ForeignKey(Document, related_name="versions", on_delete=models.CASCADE)
    number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=240)
    source_url = models.URLField(max_length=1000, blank=True, validators=[validate_source])
    revised_on = models.DateField()
    owner = models.CharField(max_length=100)
    keywords = models.TextField(blank=True, help_text="쉼표로 구분한 검색어와 동의어")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["document", "number"], name="wiki_document_version_number"),
            models.UniqueConstraint(fields=["document"], condition=models.Q(status="published"), name="wiki_one_published_version"),
        ]

    def __str__(self):
        return f"{self.title} · v{self.number}"


class Paragraph(models.Model):
    version = models.ForeignKey(DocumentVersion, related_name="paragraphs", on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    body = models.TextField()
    customer_allowed = models.BooleanField(default=False)
    timestamp = models.CharField(max_length=24, blank=True, help_text="예: 02:15")
    source_url = models.URLField(max_length=1000, blank=True, validators=[validate_source])

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["version", "position"], name="wiki_paragraph_position")]

    @property
    def source_link(self):
        url = self.source_url or self.version.source_url
        if not url or urlsplit(url).scheme not in ("http", "https"):
            return ""
        parts = urlsplit(url)
        if self.timestamp and parts.hostname in ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"):
            try:
                seconds = 0
                for number in self.timestamp.split(":"):
                    seconds = seconds * 60 + int(number)
                query = dict(parse_qsl(parts.query))
                query["t"] = str(seconds)
                return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
            except ValueError:
                pass
        return url
