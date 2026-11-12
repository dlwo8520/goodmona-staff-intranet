from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


def days(units):
    return Decimal(units) / Decimal(2)


class LeaveAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leave_account")
    balance_units = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(balance_units__gte=0), name="leave_balance_nonnegative")]

    @property
    def balance_days(self):
        return days(self.balance_units)

    def __str__(self):
        return f"{self.user} · {self.balance_days}일"


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "승인 대기"
        APPROVED = "approved", "승인"
        REJECTED = "rejected", "반려"
        CANCELLED = "cancelled", "취소"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leave_requests")
    leave_date = models.DateField()
    units = models.PositiveSmallIntegerField(choices=[(2, "1일"), (1, "0.5일")])
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_leaves")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=200, blank=True)
    seed_key = models.CharField(max_length=100, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(condition=Q(units__in=[1, 2]), name="leave_allowed_units")]

    @property
    def amount_days(self):
        return days(self.units)


class LeaveLedger(models.Model):
    class Kind(models.TextChoices):
        INITIAL = "initial", "시작 잔여일 설정"
        APPLIED = "applied", "연차 신청"
        APPROVED = "approved", "승인 차감"
        REJECTED = "rejected", "신청 반려"
        CANCELLED = "cancelled", "신청 취소 / 복원"

    account = models.ForeignKey(LeaveAccount, on_delete=models.PROTECT, related_name="entries")
    request = models.ForeignKey(LeaveRequest, null=True, blank=True, on_delete=models.PROTECT, related_name="entries")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    delta_units = models.IntegerField()
    balance_after_units = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leave_actions")
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["request", "kind"], condition=Q(request__isnull=False), name="one_leave_event_per_kind"),
            models.UniqueConstraint(fields=["account"], condition=Q(kind="initial"), name="one_initial_leave_balance"),
        ]

    @property
    def delta_days(self):
        return days(self.delta_units)

    @property
    def balance_after_days(self):
        return days(self.balance_after_units)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("연차 이력은 수정할 수 없습니다.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("연차 이력은 삭제할 수 없습니다.")


class Vehicle(models.Model):
    name = models.CharField(max_length=80)
    plate = models.CharField(max_length=30)
    active = models.BooleanField(default=True)
    seed_key = models.CharField(max_length=100, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return f"{self.name} · {self.plate}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "예약 확정"
        CANCELLED = "cancelled", "취소"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vehicle_reservations")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="reservations")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    purpose = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="cancelled_reservations")
    seed_key = models.CharField(max_length=100, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["starts_at", "pk"]
        constraints = [models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="reservation_end_after_start")]
