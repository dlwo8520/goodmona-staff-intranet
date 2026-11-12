from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from io import StringIO
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Department, EmployeeProfile, LeaveAccount, LeaveLedger, LeavePeriodAudit, LeaveRequest, StaffingOverride, Vehicle
from .services import book_vehicle, confirm_leave_period, initialize_balance, process_leave, submit_leave
from .staffing import availability


class CalendarTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.admin = users.create_user('calendar-manager', is_staff=True)
        self.people = [users.create_user(f'calendar-person-{i}', first_name=f'가상 직원 {i}') for i in range(5)]
        for person in self.people:
            initialize_balance(person, 20, self.admin)
        self.department = self.people[0].staff_profile.department
        self.day = timezone.localdate() + timedelta(days=20)

    def request(self, person=0, period='full', day=None):
        return submit_leave(self.people[person], day or self.day, period=period, reason='동료 비공개 사유')

    def approve(self, person=0, period='full'):
        item = self.request(person, period)
        process_leave(item.pk, self.admin, 'approve')
        return item

    def test_two_approved_block_third_at_form_and_service(self):
        self.approve(0)
        self.approve(1)
        check = availability(self.people[2], self.day)
        self.assertFalse(check['allowed'])
        self.assertEqual([(r['scheduled'], r['approved'], r['remaining'], r['minimum']) for r in check['slots']], [(5, 2, 2, 3)] * 2)
        with self.assertRaisesMessage(ValidationError, '최소 필요'):
            self.request(2)
        self.client.force_login(self.people[2])
        response = self.client.post(reverse('operations:leave'), {'leave_date': self.day.isoformat(), 'period': 'full'})
        self.assertContains(response, '최소 필요')
        self.assertEqual(LeaveRequest.objects.count(), 2)

    def test_pending_requests_compete_only_when_approved(self):
        self.approve(0)
        first, second = self.request(1), self.request(2)
        process_leave(first.pk, self.admin, 'approve')
        with self.assertRaisesMessage(ValidationError, '최소 필요'):
            process_leave(second.pk, self.admin, 'approve')
        second.refresh_from_db()
        self.assertEqual(second.status, 'pending')
        self.assertEqual(LeaveAccount.objects.get(user=self.people[2]).balance_units, 20)
        self.assertFalse(LeaveLedger.objects.filter(request=second, kind='approved').exists())

    def test_period_capacity_and_full_day_check_both_slots(self):
        self.approve(0, 'am')
        self.approve(1, 'am')
        self.assertFalse(availability(self.people[2], self.day, 'am')['allowed'])
        self.assertFalse(availability(self.people[2], self.day, 'full')['allowed'])
        self.assertTrue(availability(self.people[2], self.day, 'pm')['allowed'])
        self.request(2, 'pm')

    def test_two_non_overlapping_half_days_allowed_full_and_same_half_blocked(self):
        self.request(0, 'am')
        self.request(0, 'pm')
        for period in ('full', 'am', 'pm'):
            with self.assertRaisesMessage(ValidationError, '같은 시간대'):
                self.request(0, period)

    def test_approved_cancel_restores_balance_and_capacity_once(self):
        first = self.approve(0)
        self.approve(1)
        before = availability(self.people[2], self.day)
        self.assertFalse(before['allowed'])
        process_leave(first.pk, self.admin, 'cancel')
        process_leave(first.pk, self.admin, 'cancel')
        self.assertTrue(availability(self.people[2], self.day)['allowed'])
        self.assertEqual(LeaveAccount.objects.get(user=self.people[0]).balance_units, 20)
        self.assertEqual(LeaveLedger.objects.filter(request=first, kind='cancelled').count(), 1)

    def test_staff_and_manager_read_same_request_and_result_on_json_refresh(self):
        self.client.force_login(self.people[0])
        created = self.client.post(reverse('operations:leave'), {'leave_date': self.day.isoformat(), 'period': 'am'})
        self.assertEqual(created.status_code, 302)
        item = LeaveRequest.objects.get(user=self.people[0])
        self.client.force_login(self.admin)
        response = self.client.get(reverse('operations:manage_calendar'), {'date': self.day.isoformat()})
        self.assertEqual(response.json()['items'][0]['id'], item.pk)
        self.assertEqual(response.json()['events'][self.day.isoformat()]['pending'], 1)
        self.client.post(reverse('operations:leave_process', args=[item.pk]), {'action': 'approve'})
        self.client.force_login(self.people[0])
        payload = self.client.get(reverse('operations:leave_calendar'), {'date': self.day.isoformat()}).json()
        self.assertEqual(payload['items'][0]['status_label'], '승인 완료')
        self.assertEqual(payload['balance'], '9.5')

    def test_staff_only_sees_counts_and_own_requests_and_cannot_set_staffing(self):
        self.approve(0)
        self.client.force_login(self.people[2])
        response = self.client.get(reverse('operations:leave_calendar'), {'date': self.day.isoformat()})
        self.assertNotContains(response, '동료 비공개 사유')
        self.assertNotContains(response, self.people[0].username)
        self.assertEqual(response.json()['items'], [])
        self.assertEqual(response.json()['availability']['am']['slots'][0]['approved'], 1)
        for name in ('operations:staffing', 'operations:manage_calendar'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
            self.assertEqual(self.client.post(reverse(name), {}).status_code, 403)

    def test_staffing_override_affects_selected_slot_and_latest_approval(self):
        item = self.request()
        StaffingOverride.objects.create(department=self.department, date=self.day, period='am', scheduled=3, minimum=3, updated_by=self.admin)
        self.assertTrue(availability(self.people[1], self.day, 'pm')['allowed'])
        with self.assertRaisesMessage(ValidationError, '오전'):
            process_leave(item.pk, self.admin, 'approve')
        self.client.force_login(self.admin)
        response = self.client.post(reverse('operations:staffing'), {'action': 'override', 'department': self.department.pk,
            'date': self.day.isoformat(), 'period': 'am', 'scheduled': 5, 'minimum': 3})
        self.assertEqual(response.status_code, 302)
        process_leave(item.pk, self.admin, 'approve')

    def test_manager_department_and_pending_filters(self):
        first = self.approve(0)
        pending = self.request(1)
        other = Department.objects.create(name='다른 부서', scheduled=5, minimum=3)
        EmployeeProfile.objects.filter(user=self.people[2]).update(department=other)
        self.request(2)
        self.client.force_login(self.admin)
        payload = self.client.get(reverse('operations:manage_calendar'), {'date': self.day.isoformat(), 'department': self.department.pk, 'pending': '1'}).json()
        self.assertEqual([item['id'] for item in payload['items']], [pending.pk])
        self.assertNotIn('approved', payload['events'][self.day.isoformat()])

    def test_legacy_unknown_half_needs_confirmation_and_conservatively_counts_both(self):
        unknown = LeaveRequest.objects.create(user=self.people[0], department=self.department, leave_date=self.day, units=1, period='unknown')
        with self.assertRaisesMessage(ValidationError, '오전·오후'):
            process_leave(unknown.pk, self.admin, 'approve')
        confirm_leave_period(unknown.pk, self.admin, 'am')
        process_leave(unknown.pk, self.admin, 'approve')
        self.assertEqual(LeavePeriodAudit.objects.get(request=unknown).actor, self.admin)
        self.assertEqual(availability(self.people[1], self.day, 'am')['slots'][0]['approved'], 1)
        self.assertEqual(availability(self.people[1], self.day, 'pm')['slots'][0]['approved'], 0)

    def test_waiting_request_outside_month_is_not_silently_hidden(self):
        next_month = (self.day.replace(day=28) + timedelta(days=4)).replace(day=1)
        item = self.request(day=next_month)
        self.client.force_login(self.admin)
        payload = self.client.get(reverse('operations:manage_calendar'), {'date': self.day.isoformat()}).json()
        self.assertEqual(payload['pending_total'], 1)
        self.assertEqual(payload['outside_pending'], 1)
        self.assertEqual(payload['outside_date'], item.leave_date.isoformat())

    def test_duplicate_department_name_returns_form_error_without_changing_defaults(self):
        other = Department.objects.create(name='이미 있는 부서', scheduled=7, minimum=4)
        self.client.force_login(self.admin)
        response = self.client.post(reverse('operations:staffing'), {'action': 'department', 'id': self.department.pk,
            'name': other.name, 'scheduled': 5, 'minimum': 3})
        self.assertContains(response, '이미 있는 부서 이름')
        self.department.refresh_from_db()
        self.assertNotEqual(self.department.name, other.name)

    def test_vehicle_calendar_scopes_car_date_and_hides_coworker_fields(self):
        car = Vehicle.objects.create(name='테스트 차량', plate='가상')
        other = Vehicle.objects.create(name='다른 차량', plate='가상')
        begin = timezone.make_aware(datetime.combine(self.day, time(10)))
        end = begin + timedelta(hours=1)
        booking = book_vehicle(self.people[0], car, begin, end, '비공개 차량 메모')
        book_vehicle(self.people[1], other, begin, end)
        self.client.force_login(self.people[2])
        response = self.client.get(reverse('operations:vehicle_calendar'), {'date': self.day.isoformat(), 'vehicle': car.pk})
        data = response.json()
        self.assertEqual(data['events'][self.day.isoformat()], 1)
        self.assertEqual(data['items'], [{'start': 600, 'end': 660, 'mine': False}])
        self.assertNotContains(response, '비공개 차량 메모')
        self.assertEqual(data['gaps'], [{'start': 0, 'end': 600}, {'start': 660, 'end': 1440}])
        self.client.force_login(self.people[0])
        own = self.client.get(reverse('operations:vehicle_calendar'), {'date': self.day.isoformat(), 'vehicle': car.pk}).json()['items'][0]
        self.assertEqual(own['id'], booking.pk)
        self.assertTrue(own['mine'])

    def test_all_calendar_pages_render_and_seed_does_not_duplicate(self):
        self.client.force_login(self.people[0])
        for name in ('operations:leave', 'operations:vehicles'):
            response = self.client.get(reverse(name))
            self.assertContains(response, 'month-calendar')
            self.assertRegex(response.content.decode(), r'<script defer src="/static/calendar(?:\.[0-9a-f]+)?\.js"')
        self.client.force_login(self.admin)
        for name in ('operations:manage', 'operations:staffing'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)


class CapacityConcurrencyTests(TransactionTestCase):
    def test_two_pending_approvals_cannot_take_same_last_seat(self):
        if 'memory' in str(connection.settings_dict['NAME']):
            self.skipTest('Requires file SQLite')
        users = get_user_model().objects
        admin = users.create_user('capacity-admin', is_staff=True)
        people = [users.create_user(f'capacity-{i}') for i in range(3)]
        for person in people:
            initialize_balance(person, 20, admin)
        day = timezone.localdate() + timedelta(days=30)
        requests = [submit_leave(person, day, period='full') for person in people]
        process_leave(requests[0].pk, admin, 'approve')
        barrier = Barrier(2)
        def approve(pk):
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                process_leave(pk, admin, 'approve')
                return 'approved'
            except ValidationError:
                return 'blocked'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(approve, [requests[1].pk, requests[2].pk]))
        self.assertCountEqual(result, ['approved', 'blocked'])
        self.assertEqual(LeaveRequest.objects.filter(status='approved').count(), 2)
        self.assertEqual(LeaveRequest.objects.filter(status='pending').count(), 1)


class PreserveMigrationTests(TransactionTestCase):
    def test_existing_half_day_stays_unknown_and_balance_history_and_reservation_survive(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('operations', '0001_initial')])
        old = executor.loader.project_state([('operations', '0001_initial')]).apps
        try:
            User = old.get_model('auth', 'User')
            user = User.objects.create(username='migration-staff')
            account = old.get_model('operations', 'LeaveAccount').objects.create(user_id=user.pk, balance_units=17)
            leave = old.get_model('operations', 'LeaveRequest').objects.create(user_id=user.pk, units=1, leave_date=timezone.localdate(), status='approved', reason='기존 신청 보존')
            full = old.get_model('operations', 'LeaveRequest').objects.create(user_id=user.pk, units=2, leave_date=timezone.localdate() + timedelta(days=1))
            ledger = old.get_model('operations', 'LeaveLedger').objects.create(account_id=account.pk, request_id=leave.pk, kind='approved', delta_units=-1, balance_after_units=17, actor_id=user.pk)
            car = old.get_model('operations', 'Vehicle').objects.create(name='기존 차량', plate='기존')
            reservation = old.get_model('operations', 'Reservation').objects.create(user_id=user.pk, vehicle_id=car.pk, starts_at=timezone.now(), ends_at=timezone.now()+timedelta(hours=1), purpose='기존 예약 보존')
            executor = MigrationExecutor(connection)
            executor.migrate([('operations', '0002_department_calendar')])
            self.assertEqual(LeaveRequest.objects.get(pk=leave.pk).period, 'unknown')
            self.assertEqual(LeaveRequest.objects.get(pk=full.pk).period, 'full')
            self.assertEqual(LeaveAccount.objects.get(pk=account.pk).balance_units, 17)
            self.assertEqual(LeaveLedger.objects.get(pk=ledger.pk).delta_units, -1)
            from .models import Reservation
            self.assertEqual(Reservation.objects.get(pk=reservation.pk).purpose, '기존 예약 보존')
        finally:
            MigrationExecutor(connection).migrate([('operations', '0002_department_calendar')])
