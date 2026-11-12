from django.utils import timezone

from .models import EmployeeProfile, LeaveRequest, StaffingOverride

SLOTS = {'full': ('am', 'pm'), 'am': ('am',), 'pm': ('pm',), 'unknown': ('am', 'pm')}


def department_for(user):
    profile = EmployeeProfile.objects.select_related('department').filter(user=user).first()
    return profile.department if profile else None


def availability(user, date, period='full', department=None, exclude_request=None):
    department = department or department_for(user)
    if not department:
        return {'allowed': False, 'reason': '소속 부서 설정이 필요합니다.', 'slots': [], 'department': ''}
    # Read counts fresh: this function is also called inside approval's write transaction.
    approved = LeaveRequest.objects.filter(department=department, leave_date=date, status='approved')
    own = LeaveRequest.objects.filter(user=user, leave_date=date, status__in=['pending', 'approved'])
    if exclude_request:
        own = own.exclude(pk=exclude_request)
        approved = approved.exclude(pk=exclude_request)
    overlap = [item for item in own if set(SLOTS[item.period]) & set(SLOTS.get(period, ('am', 'pm')))]
    overrides = {item.period: item for item in StaffingOverride.objects.filter(department=department, date=date)}
    rows = []
    for slot in SLOTS.get(period, ('am', 'pm')):
        override = overrides.get(slot)
        scheduled = override.scheduled if override else department.scheduled
        minimum = override.minimum if override else department.minimum
        people = set(approved.filter(period__in=['full', slot, 'unknown']).values_list('user_id', flat=True))
        remaining = scheduled - len(people) - (0 if user.pk in people else 1)
        rows.append({'period': slot, 'label': '오전' if slot == 'am' else '오후', 'scheduled': scheduled,
                     'approved': len(people), 'available': scheduled - len(people),
                     'remaining': remaining, 'minimum': minimum})
    reason = ''
    if date < timezone.localdate():
        reason = '지난 날짜에는 신청할 수 없습니다.'
    elif overlap:
        reason = '같은 시간대에 승인 대기 또는 승인 완료인 내 신청이 있습니다.'
    elif any(row['remaining'] < row['minimum'] for row in rows):
        reason = ' · '.join(f"{row['label']} 승인 시 {row['remaining']}명으로 최소 필요 {row['minimum']}명에 미달합니다."
                            for row in rows if row['remaining'] < row['minimum'])
    return {'allowed': not bool(reason), 'reason': reason, 'slots': rows, 'department': department.name}
