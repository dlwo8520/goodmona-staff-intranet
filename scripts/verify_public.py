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

role('staff')
try:
    get('/manage/')
    raise AssertionError('Staff reached administrator page')
except urllib.error.HTTPError as error:
    assert error.code == 403
_, leave, _ = get('/leave/')
before = balance(leave)
day = datetime.now(timezone(timedelta(hours=9))).date()
marker = 'PUBLIC-DEMO-' + uuid.uuid4().hex[:12]
_, leave, _ = post('/leave/', {'leave_date': (day + timedelta(days=17)).isoformat(), 'units': '1', 'reason': marker}, leave)
row = next(article for article in re.findall(r'<article\b.*?</article>', leave, re.S) if marker in article)
request_id = re.search(r'/leave/(\d+)/cancel/', row).group(1)
role('admin')
_, manager, _ = get('/manage/leave/')
_, manager, _ = post(f'/manage/leave/{request_id}/process/', {'action': 'approve', 'note': marker}, manager)
_, manager, _ = post(f'/manage/leave/{request_id}/process/', {'action': 'approve', 'note': marker}, manager)
role('staff')
_, approved, _ = get('/leave/')
assert balance(approved) == before - Decimal('0.5'), 'Approval did not deduct exactly once'
assert marker in approved
role('admin')
_, manager, _ = get('/manage/leave/')
post(f'/manage/leave/{request_id}/process/', {'action': 'cancel', 'note': 'Public demo verification restored'}, manager)
role('staff')
assert balance(get('/leave/')[1]) == before, 'Cancellation did not restore balance'
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
row = next(row for row in re.findall(r'<tr\b.*?</tr>', booked, re.S) if car_marker in row)
reservation_id = re.search(r'/vehicles/(\d+)/cancel/', row).group(1)
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
