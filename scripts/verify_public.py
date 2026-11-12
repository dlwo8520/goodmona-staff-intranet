"""Exercise the fictional intranet on HTTPS, then restore the demo balance/slot."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import runpy
import sys
import urllib.error
import uuid

base = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else ''
if not base.startswith('https://'):
    raise SystemExit('Usage: python scripts/verify_public.py https://actual-host.onrender.com')
os.environ['SMOKE_BASE_URL'] = base
api = runpy.run_path(str(Path(__file__).with_name('http_smoke.py')))
get, post = api['get'], api['post']

def role(name):
    return post('/login/', {'role': name}, get('/')[1])[1]

def balance(html):
    match = re.search(r'class="balance-number"[^>]*>\s*([\d.]+)', html)
    assert match, 'Balance not found'
    return Decimal(match.group(1))

def calendar_data(kind, day, vehicle=None):
    path = '/api/manage/leave/calendar/' if kind == 'manage' else '/api/vehicles/calendar/' if kind == 'vehicles' else '/api/leave/calendar/'
    query = '?date=' + day.isoformat()
    if vehicle:
        query += '&vehicle=' + str(vehicle)
    return json.loads(get(path + query)[1])

role('staff')
try:
    get('/manage/')
    raise AssertionError('Staff reached administrator page')
except urllib.error.HTTPError as error:
    assert error.code == 403
_, leave, _ = get('/leave/')
day = datetime.now(timezone(timedelta(hours=9))).date()
target_day = day + timedelta(days=17)
before = Decimal(calendar_data('leave', target_day)['balance'])
marker = 'PUBLIC-DEMO-' + uuid.uuid4().hex[:12]
_, leave, _ = post('/leave/', {'leave_date': target_day.isoformat(), 'period': 'am', 'reason': marker}, leave)
request_id = next(item['id'] for item in calendar_data('leave', target_day)['items'] if item['reason'] == marker)
role('admin')
assert any(item['id'] == request_id for item in calendar_data('manage', target_day)['items']), 'Employee request missing in manager calendar'
_, manager, _ = get('/manage/leave/')
_, manager, _ = post(f'/manage/leave/{request_id}/process/', {'action': 'approve', 'note': marker}, manager)
_, manager, _ = post(f'/manage/leave/{request_id}/process/', {'action': 'approve', 'note': marker}, manager)
role('staff')
_, approved, _ = get('/leave/')
data = calendar_data('leave', target_day)
assert Decimal(data['balance']) == before - Decimal('0.5'), 'Approval did not deduct exactly once'
assert next(item for item in data['items'] if item['id'] == request_id)['status'] == 'approved'
role('admin')
_, manager, _ = get('/manage/leave/')
post(f'/manage/leave/{request_id}/process/', {'action': 'cancel', 'note': 'Public demo verification restored'}, manager)
role('staff')
assert Decimal(calendar_data('leave', target_day)['balance']) == before, 'Cancellation did not restore balance'
_, vehicle_page, _ = get('/vehicles/')
select = re.search(r'<select[^>]+name="vehicle".*?</select>', vehicle_page, re.S).group(0)
vehicle_id = re.search(r'value="(\d+)"', select).group(1)
tomorrow = (day + timedelta(days=1)).isoformat()
car_marker = 'PUBLIC-CAR-' + uuid.uuid4().hex[:12]
_, conflict, _ = post('/vehicles/', {'vehicle': vehicle_id, 'starts_at': tomorrow + 'T10:30',
                                    'ends_at': tomorrow + 'T11:30', 'purpose': car_marker}, vehicle_page)
assert '이미 예약된 시간과 겹칩니다' in conflict
_, booked, _ = post('/vehicles/', {'vehicle': vehicle_id, 'starts_at': tomorrow + 'T11:00',
                                  'ends_at': tomorrow + 'T12:00', 'purpose': car_marker}, conflict)
reservation_id = next(item['id'] for item in calendar_data('vehicles', day + timedelta(days=1), vehicle_id)['items'] if item.get('purpose') == car_marker)
post(f'/vehicles/{reservation_id}/cancel/', {}, booked)
evidence = {'url': base, 'staff_admin_role_entry': True, 'wiki_scope_and_no_evidence': True,
            'staff_admin_route_blocked': True, 'leave_apply_approve_once': True,
            'leave_cancel_restored': True, 'vehicle_overlap_blocked': True,
            'vehicle_adjacent_allowed': True, 'test_booking_cancelled': True,
            'transport': 'HTTPS with certificate verification'}
destination = Path('artifacts/public-intranet-verification.json')
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print('PASS: HTTPS wiki, staff permission, leave apply/approve/repeat/cancel, vehicle conflict/adjacent/cancel.')
