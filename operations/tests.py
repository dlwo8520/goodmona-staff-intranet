from datetime import timedelta
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import LeaveAccount, LeaveLedger, LeaveRequest, Reservation, Vehicle
from .services import book_vehicle, cancel_reservation, initialize_balance, process_leave, submit_leave


class OperationsTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.staff = users.create_user("ops-staff", password="test-only-password")
        self.other = users.create_user("ops-other", password="test-only-password", first_name="숨겨진예약자")
        self.manager = users.create_user("ops-manager", password="test-only-password", is_staff=True)
        self.account, _ = initialize_balance(self.staff, 20, self.manager)
        initialize_balance(self.other, 20, self.manager)
        self.day = timezone.localdate() + timedelta(days=20)
        self.start = timezone.now() + timedelta(days=20)
        self.end = self.start + timedelta(hours=2)
        self.vehicle = Vehicle.objects.create(name="가상 1호", plate="데모-001")
        self.vehicle2 = Vehicle.objects.create(name="가상 2호", plate="데모-002")

    def apply(self, units=2, user=None):
        return submit_leave(user or self.staff, self.day, units)

    def test_initial_balance_once_and_immutable_audit(self):
        account, created = initialize_balance(self.staff, 100, self.manager)
        self.assertFalse(created)
        self.assertEqual(account.balance_units, 20)
        ledger = account.entries.get()
        self.assertEqual(ledger.kind, "initial")
        self.assertEqual(ledger.actor_id, self.manager.pk)
        ledger.delta_units = 500
        with self.assertRaises(ValidationError):
            ledger.save()
        with self.assertRaises(ValidationError):
            ledger.delete()

    def test_staff_cannot_set_balance(self):
        with self.assertRaises(PermissionDenied):
            initialize_balance(self.staff, 200, self.staff)

    def test_half_day_units_only_and_no_past(self):
        for amount in (0, 3, -1, True):
            with self.assertRaises(ValidationError):
                self.apply(amount)
        with self.assertRaises(ValidationError):
            submit_leave(self.staff, timezone.localdate() - timedelta(days=1), 1)

    def test_apply_does_not_deduct_and_duplicate_date_blocked(self):
        request = self.apply()
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance_units, 20)
        self.assertEqual(request.entries.get().delta_units, 0)
        with self.assertRaises(ValidationError):
            self.apply()

    def test_approve_is_atomic_and_idempotent(self):
        request = self.apply()
        _, changed = process_leave(request.pk, self.manager, "approve")
        self.assertTrue(changed)
        _, changed = process_leave(request.pk, self.manager, "approve")
        self.assertFalse(changed)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance_units, 18)
        entry = request.entries.get(kind="approved")
        self.assertEqual(entry.delta_units, -2)
        self.assertEqual(entry.balance_after_units, 18)
        self.assertEqual(entry.actor_id, self.manager.pk)

    def test_insufficient_balance_keeps_pending_and_no_deduction(self):
        LeaveAccount.objects.filter(pk=self.account.pk).update(balance_units=1)
        request = self.apply()
        with self.assertRaises(ValidationError):
            process_leave(request.pk, self.manager, "approve")
        request.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(request.status, "pending")
        self.assertEqual(self.account.balance_units, 1)
        self.assertFalse(request.entries.filter(kind="approved").exists())

    def test_approved_cancel_restores_once_and_staff_cannot_restore(self):
        request = self.apply(1)
        process_leave(request.pk, self.manager, "approve")
        with self.assertRaises(PermissionDenied):
            process_leave(request.pk, self.staff, "cancel")
        process_leave(request.pk, self.manager, "cancel")
        _, changed = process_leave(request.pk, self.manager, "cancel")
        self.assertFalse(changed)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance_units, 20)
        self.assertEqual(request.entries.get(kind="cancelled").delta_units, 1)
        with self.assertRaises(ValidationError):
            process_leave(request.pk, self.manager, "approve")

    def test_pending_cancel_and_reject_do_not_change_balance(self):
        request = self.apply()
        process_leave(request.pk, self.staff, "cancel")
        self.assertEqual(request.entries.get(kind="cancelled").delta_units, 0)
        replacement = self.apply()
        process_leave(replacement.pk, self.manager, "reject", "일정 확인 요청")
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance_units, 20)
        self.assertEqual(replacement.entries.get(kind="rejected").note, "일정 확인 요청")

    def test_staff_cannot_approve_or_cancel_other_leave(self):
        request = self.apply(user=self.other)
        for action in ("approve", "reject", "cancel"):
            with self.assertRaises(PermissionDenied):
                process_leave(request.pk, self.staff, action)

    def test_manager_routes_enforce_server_role(self):
        request = self.apply()
        self.client.force_login(self.staff)
        for name in ("operations:manage", "operations:balances", "operations:vehicle_manage"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
            self.assertEqual(self.client.post(reverse(name), {"name": "침입"}).status_code, 403)
        response = self.client.post(reverse("operations:leave_process", args=[request.pk]), {"action": "approve"})
        self.assertEqual(response.status_code, 403)
        request.refresh_from_db()
        self.assertEqual(request.status, "pending")

    def test_staff_leave_visibility_and_owner_cancel(self):
        mine = self.apply()
        other = submit_leave(self.other, self.day, 2, reason="다른직원전용메모")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations:leave"))
        self.assertContains(response, "내 연차")
        self.assertNotContains(response, "다른직원전용메모")
        self.assertEqual([item.pk for item in response.context["requests"]], [mine.pk])
        self.assertEqual(self.client.post(reverse("operations:leave_cancel", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("operations:leave_cancel", args=[mine.pk])).status_code, 405)

    def test_booking_collision_including_enclosing_and_exact(self):
        book_vehicle(self.other, self.vehicle, self.start, self.end)
        for start, end in (
            (self.start, self.end),
            (self.start + timedelta(minutes=5), self.end - timedelta(minutes=5)),
            (self.start - timedelta(minutes=5), self.end + timedelta(minutes=5)),
            (self.start - timedelta(minutes=5), self.start + timedelta(minutes=5)),
            (self.end - timedelta(minutes=5), self.end + timedelta(minutes=5)),
        ):
            with self.assertRaises(ValidationError):
                book_vehicle(self.staff, self.vehicle, start, end)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_adjacent_and_other_vehicle_bookings_allowed(self):
        book_vehicle(self.other, self.vehicle, self.start, self.end)
        book_vehicle(self.staff, self.vehicle, self.end, self.end + timedelta(hours=1))
        book_vehicle(self.staff, self.vehicle2, self.start, self.end)
        book_vehicle(self.staff, self.vehicle, self.start - timedelta(hours=1), self.start)
        self.assertEqual(Reservation.objects.count(), 4)

    def test_cancel_booking_once_and_reuse_slot(self):
        reservation = book_vehicle(self.staff, self.vehicle, self.start, self.end)
        with self.assertRaises(PermissionDenied):
            cancel_reservation(reservation.pk, self.other)
        cancel_reservation(reservation.pk, self.staff)
        _, changed = cancel_reservation(reservation.pk, self.staff)
        self.assertFalse(changed)
        reservation.refresh_from_db()
        self.assertEqual(reservation.cancelled_by_id, self.staff.pk)
        book_vehicle(self.other, self.vehicle, self.start, self.end)

    def test_booking_validates_time_and_active_vehicle(self):
        for start, end in ((self.end, self.start), (self.start, self.start), (timezone.now() - timedelta(hours=1), self.end)):
            with self.assertRaises(ValidationError):
                book_vehicle(self.staff, self.vehicle, start, end)
        self.vehicle.active = False
        self.vehicle.save()
        with self.assertRaises(ValidationError):
            book_vehicle(self.staff, self.vehicle, self.start, self.end)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(user=self.staff, vehicle=self.vehicle, starts_at=self.end, ends_at=self.start)

    def test_other_booking_exposes_only_occupied_time(self):
        other = book_vehicle(self.other, self.vehicle, self.start, self.end, "다른직원예약비공개메모")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations:vehicles"))
        self.assertNotContains(response, self.other.username)
        self.assertNotContains(response, self.other.first_name)
        self.assertNotContains(response, "다른직원예약비공개메모")
        rows = list(response.context["busy"])
        self.assertEqual(set(rows[0]), {"vehicle__name", "starts_at", "ends_at"})
        self.assertEqual(self.client.post(reverse("operations:reservation_cancel", args=[other.pk])).status_code, 404)

    def test_booking_collision_is_visible_form_error(self):
        book_vehicle(self.other, self.vehicle, self.start, self.end)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("operations:vehicles"), {
            "vehicle": self.vehicle.pk,
            "starts_at": timezone.localtime(self.start).strftime("%Y-%m-%dT%H:%M"),
            "ends_at": timezone.localtime(self.end).strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertContains(response, "이미 예약된 시간과 겹칩니다")
        self.assertEqual(Reservation.objects.count(), 1)

    def test_public_views_require_login(self):
        for name in ("operations:leave", "operations:vehicles", "operations:manage"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn("login", response.url)


class SQLiteConcurrencyTests(TransactionTestCase):
    """Use a file-backed test DB: shared-cache memory SQLite does not wait for locks."""
    def setUp(self):
        if connection.vendor != "sqlite" or "memory" in str(connection.settings_dict["NAME"]):
            self.skipTest("파일 SQLite 테스트 DB에서 동시 요청 잠금을 검증합니다.")
        if connection.settings_dict.get("OPTIONS", {}).get("transaction_mode") != "IMMEDIATE":
            self.skipTest("IMMEDIATE 트랜잭션 설정이 필요합니다.")
        users = get_user_model().objects
        self.manager = users.create_user("parallel-manager", is_staff=True)
        self.staff = users.create_user("parallel-staff")
        initialize_balance(self.staff, 20, self.manager)
        self.vehicle = Vehicle.objects.create(name="동시성 차량", plate="테스트")
        self.start = timezone.now() + timedelta(days=30)

    def run_parallel(self, operation):
        barrier = Barrier(2)

        def task():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                return operation()
            except ValidationError:
                return "blocked"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(lambda _: task(), range(2)))

    def test_simultaneous_approvals_deduct_once(self):
        request = submit_leave(self.staff, timezone.localdate() + timedelta(days=30), 2)
        results = self.run_parallel(lambda: process_leave(request.pk, self.manager, "approve")[1])
        self.assertCountEqual(results, [True, False])
        self.assertEqual(LeaveAccount.objects.get(user=self.staff).balance_units, 18)
        self.assertEqual(LeaveLedger.objects.filter(request=request, kind="approved").count(), 1)

    def test_simultaneous_overlapping_bookings_save_one(self):
        results = self.run_parallel(lambda: book_vehicle(self.staff, self.vehicle, self.start, self.start + timedelta(hours=1)).pk)
        self.assertEqual(results.count("blocked"), 1)
        self.assertEqual(Reservation.objects.filter(status="active").count(), 1)
