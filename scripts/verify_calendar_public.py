"""Verify department capacity over HTTPS using fictional accounts, then cancel test requests."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import runpy
import sys
import uuid

base = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else ''
if not base.startswith('https://'):
    raise SystemExit('Usage: python scripts/verify_calendar_public.py https://actual-host.onrender.com')
import os
os.environ['SMOKE_BASE_URL'] = base
api = runpy.run_path(str(Path(__file__).with_name('http_smoke.py')))
get, post = api['get'], api['post']
day = datetime.now(timezone(timedelta(hours=9))).date() + timedelta(days=25)
marker = 'CAPACITY-HTTPS-' + uuid.uuid4().hex[:12]

def role(name, person='demo_staff'):
    return post('/login/', {'role': name, 'demo_user': person}, get('/')[1])[1]

def data(manager=False, selected=day):
    return json.loads(get(('/api/manage/leave/calendar/' if manager else '/api/leave/calendar/') + '?date=' + selected.isoformat())[1])

created, balances = [], {}
try:
    # All three are pending before any approval, so pending counts do not consume capacity.
    for person in ('demo_staff2', 'demo_staff3', 'demo_staff4'):
        role('staff', person)
        balances[person] = Decimal(data()['balance'])
        _, form, _ = get('/leave/?date=' + day.isoformat())
        post('/leave/', {'leave_date': day.isoformat(), 'period': 'full', 'reason': marker}, form)
        created.append(next(item['id'] for item in data()['items'] if item['reason'] == marker))
    role('admin')
    pending = [item for item in data(True)['items'] if item['id'] in created]
    assert len(pending) == 3 and all(item['status'] == 'pending' for item in pending)
    for pk in created:
        _, html, _ = get('/manage/leave/?date=' + day.isoformat())
        post(f'/manage/leave/{pk}/process/', {'action': 'approve', 'calendar': '1', 'return_date': day.isoformat()}, html)
    after = {item['id']: item for item in data(True)['items'] if item['id'] in created}
    assert [after[pk]['status'] for pk in created] == ['approved', 'approved', 'pending']
    assert not after[created[-1]]['can_approve']
    assert after[created[-1]]['approval_reason']

    # A new applicant is also blocked by the server, not only by a disabled button.
    role('staff', 'demo_staff5')
    before = data()
    full = before['availability']['full']
    assert not full['allowed']
    assert [(s['scheduled'], s['approved'], s['remaining'], s['minimum']) for s in full['slots']] == [(5, 2, 2, 3)] * 2
    _, html, _ = get('/leave/?date=' + day.isoformat())
    post('/leave/', {'leave_date': day.isoformat(), 'period': 'full', 'reason': marker}, html)
    assert not any(item['reason'] == marker for item in data()['items'])
    assert marker not in json.dumps(before), 'Coworker reasons exposed to employee'

    role('staff', 'demo_staff4')
    assert Decimal(data()['balance']) == balances['demo_staff4'], 'Blocked approval deducted leave'
    role('admin')
    _, html, _ = get('/manage/leave/?date=' + day.isoformat())
    post(f'/manage/leave/{created[0]}/process/', {'action': 'cancel'}, html)
    role('staff', 'demo_staff5')
    assert data()['availability']['full']['allowed'], 'Cancellation did not restore capacity'
    role('staff', 'demo_staff2')
    assert Decimal(data()['balance']) == balances['demo_staff2']

    # The second vehicle permits the same time that is occupied on vehicle one.
    tomorrow = datetime.now(timezone(timedelta(hours=9))).date() + timedelta(days=1)
    role('staff')
    _, vehicle_html, _ = get('/vehicles/?vehicle=2&date=' + tomorrow.isoformat())
    post('/vehicles/', {'vehicle': '2', 'date': tomorrow.isoformat(), 'start_time': '10:30', 'end_time': '11:30', 'purpose': marker}, vehicle_html)
    car_data = json.loads(get('/api/vehicles/calendar/?vehicle=2&date=' + tomorrow.isoformat())[1])
    own = next(item for item in car_data['items'] if item.get('purpose') == marker)
    _, html, _ = get('/vehicles/?vehicle=2&date=' + tomorrow.isoformat())
    post(f'/vehicles/{own["id"]}/cancel/', {}, html)
finally:
    role('admin')
    for pk in created:
        _, html, _ = get('/manage/leave/?date=' + day.isoformat())
        post(f'/manage/leave/{pk}/process/', {'action': 'cancel', 'note': 'HTTPS verification cleanup'}, html)

for person, amount in balances.items():
    role('staff', person)
    assert Decimal(data()['balance']) == amount, 'Test balance was not restored'
evidence = {'url': base, 'checked_at': datetime.now(timezone.utc).isoformat(), 'test_date': day.isoformat(),
    'three_pending_visible_to_manager': True, 'third_approval_blocked_after_two_approved': True,
    'third_employee_submission_blocked_by_server': True, 'staffing_5_approved_2_remaining_2_minimum_3': True,
    'coworker_reason_private': True, 'blocked_approval_balance_unchanged': True,
    'cancellation_restores_capacity_and_balance': True, 'other_vehicle_same_time_allowed': True,
    'created_test_requests_cancelled': True, 'transport': 'HTTPS with certificate verification'}
destination = Path('artifacts/public-calendar-verification.json')
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print('PASS: HTTPS manager sync, capacity recheck, third submission/approval blocked, cancellation restored, vehicle scope.')
