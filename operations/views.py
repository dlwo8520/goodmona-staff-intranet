from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import manager_required
from .forms import InitialBalanceForm, LeaveForm, ReservationForm, VehicleForm
from .models import LeaveAccount, LeaveLedger, LeaveRequest, Reservation, Vehicle
from .services import book_vehicle, cancel_reservation, initialize_balance, process_leave, submit_leave


def add_errors(form, error):
    for message in error.messages:
        form.add_error(None, message)


@login_required
def leave(request):
    form = LeaveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            submit_leave(request.user, **form.cleaned_data)
        except ValidationError as exc:
            add_errors(form, exc)
        else:
            messages.success(request, "연차 신청을 보냈습니다. 승인되면 잔여일에 반영됩니다.")
            return redirect("operations:leave")
    account = LeaveAccount.objects.filter(user=request.user).first()
    return render(request, "operations/leave.html", {
        "form": form, "account": account,
        "requests": LeaveRequest.objects.filter(user=request.user).select_related("reviewed_by"),
        "ledger": LeaveLedger.objects.filter(account__user=request.user).select_related("actor", "request")[:40],
    })


@login_required
@require_POST
def leave_cancel(request, pk):
    # Ownership is checked before status handling, including repeated requests.
    get_object_or_404(LeaveRequest, pk=pk, user=request.user)
    try:
        _, changed = process_leave(pk, request.user, "cancel")
        messages.success(request, "신청을 취소했습니다." if changed else "이미 취소된 신청입니다.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("operations:leave")


@manager_required
def manage(request):
    return render(request, "operations/manage.html", {
        "pending": LeaveRequest.objects.filter(status="pending").select_related("user", "user__leave_account"),
        "processed": LeaveRequest.objects.exclude(status="pending").select_related("user", "reviewed_by")[:60],
        "accounts": LeaveAccount.objects.select_related("user").order_by("user__username"),
        "ledger": LeaveLedger.objects.select_related("account__user", "actor").all()[:60],
    })


@manager_required
@require_POST
def leave_process(request, pk):
    get_object_or_404(LeaveRequest, pk=pk)
    action = request.POST.get("action")
    if action not in ("approve", "reject", "cancel"):
        return HttpResponseBadRequest("지원하지 않는 처리입니다.")
    try:
        _, changed = process_leave(pk, request.user, action, request.POST.get("note", ""))
        messages.success(request, "처리 결과와 증감 이력을 저장했습니다." if changed else "이미 처리되었습니다. 잔여일은 다시 차감되지 않습니다.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("operations:manage")


@manager_required
def balances(request):
    form = InitialBalanceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        _, created = initialize_balance(form.cleaned_data["user"], int(form.cleaned_data["days"] * 2), request.user)
        messages.success(request, "시작 잔여일과 설정 이력을 저장했습니다." if created else "이미 시작 잔여일이 설정된 직원입니다.")
        return redirect("operations:manage")
    return render(request, "operations/balances.html", {"form": form})


@login_required
def vehicles(request):
    form = ReservationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            book_vehicle(request.user, **form.cleaned_data)
        except ValidationError as exc:
            add_errors(form, exc)
        else:
            messages.success(request, "차량 예약이 확정되었습니다.")
            return redirect("operations:vehicles")
    # Only vehicle and occupied time are exposed for other staff bookings.
    busy = Reservation.objects.filter(status="active", ends_at__gt=timezone.now()).order_by("starts_at").values("vehicle__name", "starts_at", "ends_at")[:100]
    return render(request, "operations/vehicles.html", {
        "form": form, "busy": busy,
        "reservations": Reservation.objects.filter(user=request.user).select_related("vehicle")[:60],
    })


@login_required
@require_POST
def reservation_cancel(request, pk):
    get_object_or_404(Reservation, pk=pk, user=request.user)
    _, changed = cancel_reservation(pk, request.user)
    messages.success(request, "차량 예약을 취소했습니다." if changed else "이미 취소된 예약입니다.")
    return redirect("operations:vehicles")


@manager_required
def vehicle_manage(request, pk=None):
    vehicle = get_object_or_404(Vehicle, pk=pk) if pk is not None else None
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "차량 정보를 저장했습니다.")
        return redirect("operations:vehicle_manage")
    return render(request, "operations/vehicle_manage.html", {"form": form, "vehicles": Vehicle.objects.all(), "editing": vehicle})
