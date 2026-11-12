import calendar
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.permissions import manager_required
from .models import Department, EmployeeProfile, LeaveAccount, LeaveLedger, LeaveRequest, Reservation, StaffingOverride, Vehicle
from .forms import LeaveForm
from .services import book_vehicle, confirm_leave_period, submit_leave
from .staffing import availability, department_for


def selection(request):
    today = timezone.localdate()
    try:
        selected = date.fromisoformat(request.POST.get('leave_date') or request.POST.get('date') or request.GET.get('date', today.isoformat()))
    except (ValueError, TypeError):
        selected = today
    try:
        year, month = map(int, request.GET.get('month', selected.strftime('%Y-%m')).split('-'))
        first = date(year, month, 1)
        if not 2000 <= year <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        first = today.replace(day=1)
    if (selected.year, selected.month) != (first.year, first.month):
        selected = first
    end = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return selected, first, end


def calendar_context(request, title, api_name, extra=None):
    selected, first, end = selection(request)
    params = request.GET.dict()
    def month_url(day):
        query = {**params, 'month': day.strftime('%Y-%m'), 'date': day.isoformat()}
        return '?' + urlencode(query)
    return {'calendar_title': title, 'selected_date': selected, 'month': first.strftime('%Y-%m'),
        'month_label': first.strftime('%Y년 %m월'), 'weeks': calendar.Calendar(firstweekday=0).monthdayscalendar(first.year, first.month),
        'previous_month': month_url(first - timedelta(days=1)), 'next_month': month_url(end),
        'api_url': reverse(api_name), 'today': timezone.localdate(), **(extra or {})}


def request_item(item, manager=False):
    result = {'id': item.pk, 'date': item.leave_date.isoformat(), 'period': item.period,
        'period_label': item.get_period_display(), 'status': item.status, 'status_label': item.get_status_display(),
        'reason': item.reason, 'note': item.review_note, 'amount': str(item.amount_days)}
    if manager:
        result.update(employee=item.user.get_full_name() or item.user.username,
                      department=item.department.name if item.department else '부서 확인 필요')
        if item.status == 'pending':
            check = availability(item.user, item.leave_date, item.period, item.department, exclude_request=item.pk)
            result['can_approve'] = item.period != 'unknown' and check['allowed']
            result['approval_reason'] = '이전 반차의 오전·오후 확인이 필요합니다.' if item.period == 'unknown' else check['reason']
    return result


def leave_payload(request, manager=False):
    selected, first, end = selection(request)
    query = LeaveRequest.objects.filter(leave_date__gte=first, leave_date__lt=end).select_related('user', 'department')
    if manager:
        if request.GET.get('department', '').isdigit():
            query = query.filter(department_id=int(request.GET['department']))
        if request.GET.get('pending') == '1':
            query = query.filter(status='pending')
    else:
        query = query.filter(user=request.user)
    items = [request_item(item, manager) for item in query.order_by('leave_date', 'created_at', 'pk')]
    events = defaultdict(lambda: defaultdict(int))
    for item in items:
        events[item['date']][item['status']] += 1
    result = {'date': selected.isoformat(), 'month': first.strftime('%Y-%m'), 'events': dict(events),
              'items': [item for item in items if item['date'] == selected.isoformat()], 'manager': manager}
    if manager:
        waiting = LeaveRequest.objects.filter(status='pending')
        if request.GET.get('department', '').isdigit():
            waiting = waiting.filter(department_id=int(request.GET['department']))
        result['pending_total'] = waiting.count()
        outside = waiting.exclude(leave_date__gte=first, leave_date__lt=end).order_by('leave_date')
        result['outside_pending'] = outside.count()
        result['outside_date'] = outside.values_list('leave_date', flat=True).first()
        if result['outside_date']:
            result['outside_date'] = result['outside_date'].isoformat()
    if not manager:
        result['availability'] = {period: availability(request.user, selected, period) for period in ('full', 'am', 'pm')}
        account = LeaveAccount.objects.filter(user=request.user).first()
        result['balance'] = str(account.balance_days) if account else '미설정'
    return result


@login_required
def leave(request):
    selected, _, _ = selection(request)
    form = LeaveForm(request.POST if request.method == 'POST' else None, initial={'leave_date': selected, 'period': 'full'})
    if request.method == 'POST' and form.is_valid():
        try:
            submit_leave(request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error.messages)
        else:
            messages.success(request, '연차 신청을 보냈습니다. 관리자 달력에도 반영됩니다.')
            return redirect(reverse('operations:leave') + '?' + urlencode({'date': form.cleaned_data['leave_date'].isoformat()}))
    payload = leave_payload(request)
    return render(request, 'operations/calendar_leave.html', calendar_context(request, '내 연차', 'operations:leave_calendar', {
        'form': form, 'calendar_data': payload, 'calendar_mode': 'leave',
        'initial_availability': payload['availability'].get(form['period'].value() or 'full', payload['availability']['full']),
        'account': LeaveAccount.objects.filter(user=request.user).first(),
        'requests': LeaveRequest.objects.filter(user=request.user).select_related('reviewed_by'),
        'ledger': LeaveLedger.objects.filter(account__user=request.user).select_related('actor', 'request')[:40]}))


@manager_required
def manage(request):
    return render(request, 'operations/calendar_manage.html', calendar_context(request, '연차 승인', 'operations:manage_calendar', {
        'calendar_data': leave_payload(request, True), 'calendar_mode': 'manage',
        'departments': Department.objects.all(), 'department_filter': request.GET.get('department', ''),
        'pending_only': request.GET.get('pending') == '1'}))


@login_required
@require_GET
def leave_calendar(request):
    return JsonResponse(leave_payload(request))


@manager_required
@require_GET
def manage_calendar(request):
    return JsonResponse(leave_payload(request, True))


def vehicle_payload(request, vehicle):
    selected, first, end = selection(request)
    zone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(first, time.min), zone)
    stop = timezone.make_aware(datetime.combine(end, time.min), zone)
    bookings = Reservation.objects.filter(vehicle=vehicle, status='active', starts_at__lt=stop, ends_at__gt=start).order_by('starts_at') if vehicle else []
    events = defaultdict(int)
    items = []
    for item in bookings:
        begin, finish = timezone.localtime(item.starts_at), timezone.localtime(item.ends_at)
        day = max(first, begin.date())
        while day < end and timezone.make_aware(datetime.combine(day, time.min), zone) < item.ends_at:
            events[day.isoformat()] += 1
            day += timedelta(days=1)
        day_start = timezone.make_aware(datetime.combine(selected, time.min), zone)
        day_end = day_start + timedelta(days=1)
        if item.starts_at < day_end and item.ends_at > day_start:
            begin_min = max(0, int((item.starts_at - day_start).total_seconds() // 60))
            end_min = min(1440, math.ceil((item.ends_at - day_start).total_seconds() / 60))
            record = {'start': begin_min, 'end': end_min, 'mine': item.user_id == request.user.pk}
            if record['mine']:
                record.update(id=item.pk, purpose=item.purpose)
            items.append(record)
    gaps, cursor = [], 0
    for item in items:
        if item['start'] > cursor:
            gaps.append({'start': cursor, 'end': item['start']})
        cursor = max(cursor, item['end'])
    if cursor < 1440 and vehicle:
        gaps.append({'start': cursor, 'end': 1440})
    return {'date': selected.isoformat(), 'events': dict(events), 'items': items, 'gaps': gaps,
            'vehicle': vehicle.pk if vehicle else None, 'month': first.strftime('%Y-%m')}


def selected_vehicle(request):
    vehicle_id = request.POST.get('vehicle') or request.GET.get('vehicle')
    cars = Vehicle.objects.filter(active=True)
    return cars.filter(pk=vehicle_id).first() if str(vehicle_id).isdigit() else cars.first()


@login_required
def vehicles(request):
    vehicle = selected_vehicle(request)
    selected, _, _ = selection(request)
    error = ''
    if request.method == 'POST':
        try:
            if not vehicle:
                raise ValidationError('예약할 차량을 선택해 주세요.')
            # Retain compatibility with old datetime-local form posts.
            if request.POST.get('starts_at'):
                begin = datetime.fromisoformat(request.POST['starts_at'])
                finish = datetime.fromisoformat(request.POST['ends_at'])
            else:
                begin = datetime.combine(date.fromisoformat(request.POST['date']), time.fromisoformat(request.POST['start_time']))
                finish = datetime.combine(begin.date(), time.fromisoformat(request.POST['end_time']))
            zone = timezone.get_current_timezone()
            begin = timezone.make_aware(begin, zone) if timezone.is_naive(begin) else begin
            finish = timezone.make_aware(finish, zone) if timezone.is_naive(finish) else finish
            book_vehicle(request.user, vehicle, begin, finish, request.POST.get('purpose', ''))
        except (ValidationError, ValueError, KeyError, TypeError) as issue:
            error = ' '.join(issue.messages) if isinstance(issue, ValidationError) else '날짜와 시작·종료 시간을 확인해 주세요.'
        else:
            messages.success(request, '차량 예약이 확정되었습니다.')
            return redirect(reverse('operations:vehicles') + '?' + urlencode({'vehicle': vehicle.pk, 'date': timezone.localtime(begin).date().isoformat()}))
    busy = Reservation.objects.filter(status='active', ends_at__gt=timezone.now()).order_by('starts_at').values('vehicle__name', 'starts_at', 'ends_at')[:100]
    return render(request, 'operations/calendar_vehicles.html', calendar_context(request, '차량 예약', 'operations:vehicle_calendar', {
        'calendar_data': vehicle_payload(request, vehicle), 'calendar_mode': 'vehicles', 'vehicle': vehicle,
        'vehicles': Vehicle.objects.filter(active=True), 'booking_error': error, 'busy': busy}))


@login_required
@require_GET
def vehicle_calendar(request):
    return JsonResponse(vehicle_payload(request, selected_vehicle(request)))


@manager_required
@require_POST
def confirm_period(request, pk):
    item = get_object_or_404(LeaveRequest, pk=pk)
    try:
        confirm_leave_period(pk, request.user, request.POST.get('period'))
        messages.success(request, '기존 반차 시간을 확인했습니다. 잔여일은 바뀌지 않습니다.')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    return redirect(reverse('operations:manage') + '?' + urlencode({'date': item.leave_date.isoformat()}))


@manager_required
def staffing(request):
    error = ''
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            with transaction.atomic():
                if action == 'department':
                    name = request.POST.get('name', '').strip()
                    if not name or len(name) > 80:
                        raise ValidationError('부서 이름을 입력해 주세요.')
                    scheduled, minimum = int(request.POST['scheduled']), int(request.POST['minimum'])
                    if not 0 <= scheduled <= 1000 or not 0 <= minimum <= 1000:
                        raise ValidationError('인원은 0~1000명 범위로 입력하세요.')
                    if request.POST.get('id'):
                        department = get_object_or_404(Department, pk=request.POST['id'])
                        department.name, department.scheduled, department.minimum = name, scheduled, minimum
                        department.save()
                    else:
                        if Department.objects.filter(name=name).exists():
                            raise ValidationError('이미 있는 부서입니다.')
                        Department.objects.create(name=name, scheduled=scheduled, minimum=minimum)
                elif action == 'assignment':
                    user = get_object_or_404(get_user_model(), pk=request.POST['user'])
                    department = get_object_or_404(Department, pk=request.POST['department'])
                    EmployeeProfile.objects.update_or_create(user=user, defaults={'department': department})
                elif action in ('override', 'clear_override'):
                    department = get_object_or_404(Department, pk=request.POST['department'])
                    day = date.fromisoformat(request.POST['date'])
                    slot = request.POST['period']
                    if slot not in ('both', 'am', 'pm'):
                        raise ValidationError('오전·오후 구분을 선택해 주세요.')
                    slots = ('am', 'pm') if slot == 'both' else (slot,)
                    if action == 'clear_override':
                        StaffingOverride.objects.filter(department=department, date=day, period__in=slots).delete()
                    else:
                        scheduled, minimum = int(request.POST['scheduled']), int(request.POST['minimum'])
                        if not 0 <= scheduled <= 1000 or not 0 <= minimum <= 1000:
                            raise ValidationError('인원은 0~1000명 범위로 입력하세요.')
                        for period in slots:
                            StaffingOverride.objects.update_or_create(department=department, date=day, period=period,
                                defaults={'scheduled': scheduled, 'minimum': minimum, 'updated_by': request.user})
                else:
                    raise ValidationError('지원하지 않는 설정입니다.')
            messages.success(request, '부서·근무 인원 설정을 저장했습니다.')
            return redirect('operations:staffing')
        except (ValidationError, ValueError, KeyError, TypeError, IntegrityError) as issue:
            error = (' '.join(issue.messages) if isinstance(issue, ValidationError)
                     else '이미 있는 부서 이름입니다.' if isinstance(issue, IntegrityError)
                     else '설정 값을 확인해 주세요.')
    return render(request, 'operations/staffing.html', {'departments': Department.objects.all(),
        'employees': get_user_model().objects.filter(is_active=True).select_related('staff_profile__department').order_by('username'),
        'overrides': StaffingOverride.objects.select_related('department').order_by('date', 'department__name', 'period'), 'error': error})
