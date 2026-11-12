"""Cross-feature interview flows and non-destructive demo seeding."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from operations.models import LeaveAccount, LeaveLedger, LeaveRequest, Reservation, Vehicle
from operations.services import cancel_reservation, process_leave
from wiki.models import Document, DocumentVersion, Paragraph

from .models import Announcement


TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "SESSION_COOKIE_SECURE": False,
    "CSRF_COOKIE_SECURE": False,
    "OPENAI_API_KEY": "",
    "PASSWORD_HASHERS": ["django.contrib.auth.hashers.MD5PasswordHasher"],
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
}


def seed():
    output = StringIO()
    call_command("seed_demo", stdout=output)
    return output.getvalue()


def domain_counts():
    models = (
        get_user_model(), Announcement, Document, DocumentVersion, Paragraph,
        LeaveAccount, LeaveRequest, LeaveLedger, Vehicle, Reservation,
    )
    return {model._meta.label: model.objects.count() for model in models}


@override_settings(**TEST_SETTINGS)
class DemoSeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def test_seed_twice_has_required_data_without_duplicates(self):
        before = domain_counts()
        output = seed()
        self.assertEqual(domain_counts(), before)
        self.assertEqual(get_user_model().objects.count(), 6)
        self.assertEqual(Announcement.objects.count(), 2)
        self.assertGreaterEqual(Document.objects.count(), 6)
        self.assertGreaterEqual(DocumentVersion.objects.filter(status="published").count(), 6)
        self.assertEqual(Vehicle.objects.count(), 2)
        self.assertEqual(Reservation.objects.count(), 2)
        self.assertTrue(LeaveRequest.objects.filter(status="pending").exists())
        self.assertFalse(get_user_model().objects.get(username="demo_staff").is_staff)
        self.assertTrue(get_user_model().objects.get(username="demo_admin").is_staff)
        self.assertFalse(get_user_model().objects.get(username="demo_staff").has_usable_password())
        self.assertFalse(get_user_model().objects.get(username="demo_admin").has_usable_password())

    def test_seed_preserves_changes_password_and_cancelled_work(self):
        staff = get_user_model().objects.get(username="demo_staff")
        admin = get_user_model().objects.get(username="demo_admin")
        staff.set_password("manually-changed-fixture-password")
        staff.first_name = "수정한 가상 직원"
        staff.save(update_fields=["password", "first_name"])
        password_hash = staff.password

        document = Document.objects.get(slug="demo-reservation-change")
        version = document.versions.get(status="published")
        version.title = "관리자가 수정한 가상 문서"
        version.status = "archived"
        version.save(update_fields=["title", "status"])
        paragraph = version.paragraphs.first()
        paragraph.body = "수동 수정한 원문은 재생성하지 않습니다."
        paragraph.save(update_fields=["body"])

        notice = Announcement.objects.get(seed_key="demo-welcome")
        notice.title = "수정 후 비공개한 가상 공지"
        notice.is_active = False
        notice.save(update_fields=["title", "is_active"])
        leave = LeaveRequest.objects.get(seed_key="demo-staff-pending-leave")
        process_leave(leave.pk, staff, "cancel")
        reservation = Reservation.objects.get(seed_key="demo-reservation-1")
        cancel_reservation(reservation.pk, admin)
        vehicle = Vehicle.objects.get(seed_key="demo-vehicle-1")
        vehicle.active = False
        vehicle.save(update_fields=["active"])
        before = domain_counts()

        seed()

        self.assertEqual(domain_counts(), before)
        for obj in (staff, version, paragraph, notice, leave, reservation, vehicle):
            obj.refresh_from_db()
        self.assertEqual(staff.password, password_hash)
        self.assertTrue(staff.check_password("manually-changed-fixture-password"))
        self.assertEqual(staff.first_name, "수정한 가상 직원")
        self.assertEqual(version.title, "관리자가 수정한 가상 문서")
        self.assertEqual(version.status, "archived")
        self.assertEqual(paragraph.body, "수동 수정한 원문은 재생성하지 않습니다.")
        self.assertEqual(notice.title, "수정 후 비공개한 가상 공지")
        self.assertFalse(notice.is_active)
        self.assertEqual(leave.status, "cancelled")
        self.assertEqual(reservation.status, "cancelled")
        self.assertFalse(vehicle.active)


@override_settings(**TEST_SETTINGS)
class IntranetIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()
        cls.staff = get_user_model().objects.get(username="demo_staff")
        cls.admin = get_user_model().objects.get(username="demo_admin")

    def test_private_core_pages_require_login_and_staff_cannot_manage(self):
        for name in ("core:home", "core:manager", "core:announcements"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)

        self.client.force_login(self.staff)
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{reverse("core:manager")}"')
        self.assertFalse(response.context["is_manager"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.get(reverse("core:manager")).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:announcements")).status_code, 403)
        before = Announcement.objects.count()
        self.assertEqual(self.client.post(reverse("core:announcements"), {
            "title": "권한 없는 등록", "body": "저장되면 안 됩니다.", "is_active": "on",
        }).status_code, 403)
        self.assertEqual(Announcement.objects.count(), before)
        notice = Announcement.objects.first()
        original_title = notice.title
        self.assertEqual(self.client.post(reverse("core:announcement_edit", args=[notice.pk]), {
            "title": "권한 없는 수정", "body": "저장되면 안 됩니다.",
        }).status_code, 403)
        notice.refresh_from_db()
        self.assertEqual(notice.title, original_title)

    def test_manager_can_publish_notice_and_hide_it_from_home(self):
        self.client.force_login(self.admin)
        manager_home = self.client.get(reverse("core:home"))
        self.assertContains(manager_home, f'href="{reverse("core:manager")}"')
        self.assertEqual(self.client.get(reverse("core:manager")).status_code, 200)
        response = self.client.post(reverse("core:announcements"), {
            "title": "통합 테스트 가상 공지", "body": "직원에게 표시할 가상 내용입니다.", "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        notice = Announcement.objects.get(title="통합 테스트 가상 공지")
        self.assertEqual(notice.created_by_id, self.admin.pk)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("core:home")), notice.title)

        self.client.force_login(self.admin)
        self.client.post(reverse("core:announcement_edit", args=[notice.pk]), {
            "title": notice.title, "body": "보관할 가상 내용입니다.",
        })
        notice.refresh_from_db()
        self.assertFalse(notice.is_active)
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(reverse("core:home")), notice.title)

    def test_home_renders_zero_balance_without_missing_field_fallback(self):
        LeaveAccount.objects.filter(user=self.staff).update(balance_units=0)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account"].balance_days, Decimal(0))
        self.assertContains(response, "사용 가능한 잔여 연차")

    def test_interview_flow_login_search_apply_approve_and_block_collision(self):
        response = self.client.post(reverse("login"), {
            "role": "staff",
        })
        self.assertRedirects(response, reverse("core:home"))

        before_search = domain_counts()
        search = self.client.post(reverse("wiki:search"), {
            "mode": "customer", "question": "예약 시간을 변경하려면 어떻게 안내하나요?",
        })
        self.assertEqual(search.status_code, 200)
        self.assertTrue(search.context["result"].sufficient)
        self.assertEqual(search.context["model"]["status"], "unconfigured")
        self.assertContains(search, "예약 시간 변경 안내")
        self.assertContains(search, "등록된 출처 보기")
        for internal_marker in ("INTERNAL-BOOKING-731", "LEGACY-ARCHIVED-210", "DRAFT-ONLY-640"):
            self.assertNotContains(search, internal_marker)
        self.assertEqual(domain_counts(), before_search)

        account = LeaveAccount.objects.get(user=self.staff)
        original_units = account.balance_units
        requested_date = timezone.localdate() + timedelta(days=10)
        response = self.client.post(reverse("operations:leave"), {
            "leave_date": requested_date.isoformat(), "period": "am", "reason": "통합 시연용 가상 일정",
        })
        self.assertRedirects(response, reverse("operations:leave") + '?date=' + requested_date.isoformat())
        leave = LeaveRequest.objects.get(user=self.staff, leave_date=requested_date)
        account.refresh_from_db()
        self.assertEqual(leave.status, "pending")
        self.assertEqual(account.balance_units, original_units)

        manager_client = Client()
        response = manager_client.post(reverse("login"), {
            "role": "admin",
        })
        self.assertRedirects(response, reverse("core:home"))
        response = manager_client.post(reverse("operations:leave_process", args=[leave.pk]), {
            "action": "approve", "note": "가상 시연 승인",
        })
        self.assertRedirects(response, reverse("operations:manage"))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")
        staff_page = self.client.get(reverse("operations:leave"), {'date': requested_date.isoformat()})
        self.assertEqual(staff_page.context["account"].balance_units, original_units - 1)
        self.assertEqual(staff_page.context['calendar_data']['items'][0]['note'], '가상 시연 승인')
        ledger = LeaveLedger.objects.get(request=leave, kind="approved")
        self.assertEqual(ledger.actor_id, self.admin.pk)
        self.assertEqual(ledger.delta_units, -1)

        existing = Reservation.objects.get(seed_key="demo-reservation-1")
        before_reservations = Reservation.objects.count()
        starts_at = timezone.localtime(existing.starts_at + timedelta(minutes=10))
        ends_at = timezone.localtime(existing.ends_at - timedelta(minutes=10))
        response = self.client.post(reverse("operations:vehicles"), {
            "vehicle": existing.vehicle_id,
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": ends_at.strftime("%Y-%m-%dT%H:%M"),
            "purpose": "충돌하여 저장되면 안 되는 가상 예약",
        })
        self.assertContains(response, "이미 예약된 시간과 겹칩니다")
        self.assertEqual(Reservation.objects.count(), before_reservations)
        self.assertFalse(Reservation.objects.filter(purpose="충돌하여 저장되면 안 되는 가상 예약").exists())

    def test_role_chooser_has_two_buttons_without_credential_fields(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, '직원으로 접속')
        self.assertContains(response, '관리자로 접속')
        self.assertNotContains(response, 'name="username"')
        self.assertNotContains(response, 'name="password"')
        self.assertContains(response, '누구나 역할을 선택')

    def test_unknown_role_or_old_password_form_cannot_select_account(self):
        for payload in ({}, {'role': 'superuser'}, {'username': 'demo_admin', 'password': 'unused'}):
            with self.subTest(payload=payload):
                response = self.client.post(reverse('login'), payload)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_role_login_requires_csrf_and_switches_after_logout(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('login'))
        self.assertEqual(client.post(reverse('login'), {'role': 'staff'}).status_code, 403)
        token = client.cookies['csrftoken'].value
        response = client.post(reverse('login'), {'role': 'staff'}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session['_auth_user_id'], str(self.staff.pk))
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(reverse('logout'), HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertNotIn('_auth_user_id', client.session)
        client.get(reverse('login'))
        response = client.post(reverse('login'), {'role': 'admin'}, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session['_auth_user_id'], str(self.admin.pk))
        self.assertEqual(client.get(reverse('core:manager')).status_code, 200)

    def test_missing_or_inactive_demo_account_does_not_create_or_promote_user(self):
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        before = get_user_model().objects.count()
        self.assertEqual(self.client.post(reverse('login'), {'role': 'admin'}).status_code, 403)
        self.staff.username = 'renamed-demo-staff'
        self.staff.save(update_fields=['username'])
        self.assertEqual(self.client.post(reverse('login'), {'role': 'staff'}).status_code, 403)
        self.assertEqual(get_user_model().objects.count(), before)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_role_mismatch_never_silently_changes_permissions(self):
        self.admin.is_staff = False
        self.admin.save(update_fields=['is_staff'])
        self.assertEqual(self.client.post(reverse('login'), {'role': 'admin'}).status_code, 403)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_staff)
        self.staff.is_staff = True
        self.staff.save(update_fields=['is_staff'])
        self.assertEqual(self.client.post(reverse('login'), {'role': 'staff'}).status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_role_whitelist_ignores_arbitrary_account_and_privilege_parameters(self):
        response = self.client.post(reverse('login'), {
            'role': 'staff', 'username': 'demo_admin', 'user_id': self.admin.pk, 'is_staff': 'true',
        })
        self.assertRedirects(response, reverse('core:home'))
        self.assertEqual(self.client.session['_auth_user_id'], str(self.staff.pk))
        self.assertEqual(self.client.get(reverse('core:manager')).status_code, 403)

    def test_next_redirect_stays_on_this_site(self):
        response = self.client.post(reverse('login'), {'role': 'staff', 'next': 'https://external.example/steal'})
        self.assertRedirects(response, reverse('core:home'))
        self.client.logout()
        response = self.client.post(reverse('login'), {'role': 'staff', 'next': reverse('wiki:search')})
        self.assertRedirects(response, reverse('wiki:search'))
