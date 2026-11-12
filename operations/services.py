from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.permissions import is_manager
from .models import LeaveAccount, LeaveLedger, LeaveRequest, Reservation, Vehicle


def require_manager(actor):
    if not is_manager(actor):
        raise PermissionDenied


@transaction.atomic
def initialize_balance(user, units, actor):
    require_manager(actor)
    if isinstance(units, bool) or not isinstance(units, int) or units < 0 or units > 730:
        raise ValidationError("시작 잔여일은 0~365일 범위의 0.5일 단위로 입력하세요.")
    # Serialize even on databases where a missing account cannot be row-locked.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    account, created = LeaveAccount.objects.get_or_create(user=user, defaults={"balance_units": units})
    if created:
        LeaveLedger.objects.create(account=account, kind=LeaveLedger.Kind.INITIAL,
                                   delta_units=units, balance_after_units=units, actor=actor)
    return account, created


@transaction.atomic
def submit_leave(user, leave_date, units, reason="", seed_key=None):
    if units not in (1, 2) or isinstance(units, bool):
        raise ValidationError("사용량은 1일 또는 0.5일만 선택할 수 있습니다.")
    if leave_date < timezone.localdate():
        raise ValidationError("지난 날짜에는 연차를 신청할 수 없습니다.")
    account = LeaveAccount.objects.select_for_update().filter(user=user).first()
    if account is None:
        raise ValidationError("관리자에게 시작 잔여일 설정을 요청하세요.")
    if LeaveRequest.objects.filter(user=user, leave_date=leave_date, status__in=["pending", "approved"]).exists():
        raise ValidationError("해당 날짜에 이미 대기 또는 승인된 연차가 있습니다.")
    request = LeaveRequest.objects.create(user=user, leave_date=leave_date, units=units,
                                          reason=reason[:200], seed_key=seed_key)
    LeaveLedger.objects.create(account=account, request=request, kind=LeaveLedger.Kind.APPLIED,
                               delta_units=0, balance_after_units=account.balance_units, actor=user)
    return request


@transaction.atomic
def process_leave(request_id, actor, action, note=""):
    request = LeaveRequest.objects.select_for_update().get(pk=request_id)
    if action not in ("approve", "reject", "cancel"):
        raise ValidationError("지원하지 않는 처리입니다.")
    manager = is_manager(actor)
    if action in ("approve", "reject"):
        require_manager(actor)
    elif not manager and request.user_id != actor.pk:
        raise PermissionDenied
    if action == "cancel" and request.status == LeaveRequest.Status.APPROVED:
        require_manager(actor)
    target = {"approve": "approved", "reject": "rejected", "cancel": "cancelled"}[action]
    if request.status == target:
        return request, False
    allowed = ["pending", "approved"] if action == "cancel" else ["pending"]
    if request.status not in allowed:
        raise ValidationError("이미 처리된 신청입니다. 현재 상태를 확인하세요.")
    account = LeaveAccount.objects.select_for_update().get(user_id=request.user_id)
    delta = -request.units if action == "approve" else request.units if action == "cancel" and request.status == "approved" else 0
    if delta < 0:
        changed = LeaveAccount.objects.filter(pk=account.pk, balance_units__gte=-delta).update(balance_units=F("balance_units") + delta)
        if not changed:
            raise ValidationError("잔여 연차가 부족하여 승인할 수 없습니다.")
    elif delta:
        LeaveAccount.objects.filter(pk=account.pk).update(balance_units=F("balance_units") + delta)
    account.refresh_from_db()
    request.status = target
    request.reviewed_by = actor
    request.reviewed_at = timezone.now()
    request.review_note = note[:200]
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    kind = {"approve": LeaveLedger.Kind.APPROVED, "reject": LeaveLedger.Kind.REJECTED, "cancel": LeaveLedger.Kind.CANCELLED}[action]
    LeaveLedger.objects.create(account=account, request=request, kind=kind, delta_units=delta,
                               balance_after_units=account.balance_units, actor=actor, note=note[:200])
    return request, True


@transaction.atomic
def book_vehicle(user, vehicle, starts_at, ends_at, purpose="", seed_key=None):
    vehicle = Vehicle.objects.select_for_update().get(pk=vehicle.pk)
    if not vehicle.active:
        raise ValidationError("현재 예약할 수 없는 차량입니다.")
    if ends_at <= starts_at:
        raise ValidationError("종료 시각은 시작 시각보다 늦어야 합니다.")
    if starts_at <= timezone.now():
        raise ValidationError("시작 시각은 현재보다 이후여야 합니다.")
    # Half-open intervals: [start, end). An adjacent booking is valid.
    if Reservation.objects.filter(vehicle=vehicle, status="active", starts_at__lt=ends_at, ends_at__gt=starts_at).exists():
        raise ValidationError("이미 예약된 시간과 겹칩니다. 다른 시간이나 차량을 선택하세요.")
    return Reservation.objects.create(user=user, vehicle=vehicle, starts_at=starts_at, ends_at=ends_at,
                                       purpose=purpose[:200], seed_key=seed_key)


@transaction.atomic
def cancel_reservation(reservation_id, actor):
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id)
    if reservation.user_id != actor.pk and not is_manager(actor):
        raise PermissionDenied
    if reservation.status == "cancelled":
        return reservation, False
    reservation.status = "cancelled"
    reservation.cancelled_at = timezone.now()
    reservation.cancelled_by = actor
    reservation.save(update_fields=["status", "cancelled_at", "cancelled_by"])
    return reservation, True
