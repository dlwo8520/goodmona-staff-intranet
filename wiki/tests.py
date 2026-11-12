import json
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import SearchForm
from .models import Document, DocumentVersion, Paragraph
from .services import create_revision, generate_draft, publish_version, search_paragraphs


@override_settings(SECURE_SSL_REDIRECT=False, OPENAI_API_KEY="", STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class WikiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.employee = users.objects.create_user("wiki-employee", password="test-only-password")
        cls.manager = users.objects.create_user("wiki-manager", password="test-only-password", is_staff=True)
        cls.document = Document.objects.create(slug="reservation-guide", kind="manual")
        cls.version = DocumentVersion.objects.create(document=cls.document, number=1, title="예약 변경 안내", source_url="https://example.com/reservations", revised_on=date(2026, 10, 1), owner="가상 담당자", keywords="예약 변경, 시간 변경, 일정 변경", status="published")
        cls.public = Paragraph.objects.create(version=cls.version, position=1, body="예약 시간 변경은 가능한 시간을 확인한 뒤 새로운 일정으로 안내합니다.", customer_allowed=True)
        cls.private = Paragraph.objects.create(version=cls.version, position=2, body="직원 비공개 교육 자료: 인수인계 암호는 데모 전용입니다.", customer_allowed=False)
        cls.old = DocumentVersion.objects.create(document=cls.document, number=2, title="과거 예약 지침", revised_on=date(2026, 9, 1), owner="가상", status="archived", keywords="예약 변경")
        cls.old_p = Paragraph.objects.create(version=cls.old, position=1, body="과거 폐기 문구 예약 변경", customer_allowed=True)
        cls.draft = DocumentVersion.objects.create(document=cls.document, number=3, title="초안 예약 변경", revised_on=date(2026, 11, 1), owner="가상", keywords="예약 변경")
        cls.draft_p = Paragraph.objects.create(version=cls.draft, position=1, body="발행 전 비밀 예약 변경 초안", customer_allowed=True)

    def test_customer_scope_only_current_approved_paragraphs(self):
        result = search_paragraphs("예약 시간을 변경하려면 어떻게 안내하나요?")
        self.assertTrue(result.sufficient)
        self.assertEqual([p.pk for p in result.paragraphs], [self.public.pk])

    def test_registered_synonym_query(self):
        result = search_paragraphs("일정 변경은 어떻게 안내하나요?")
        self.assertTrue(result.sufficient)
        self.assertIn(self.public.pk, [p.pk for p in result.paragraphs])

    def test_internal_search_finds_employee_only_content(self):
        result = search_paragraphs("인수인계", "internal")
        self.assertEqual([p.pk for p in result.paragraphs], [self.private.pk])
        self.assertEqual(search_paragraphs("인수인계", "customer").paragraphs, [])

    def test_unrelated_question_needs_confirmation(self):
        result = search_paragraphs("헬리콥터 착륙장을 이용할 수 있나요?")
        self.assertFalse(result.sufficient)
        self.assertEqual(result.paragraphs, [])
        self.assertEqual(result.retrieval_label, "담당자 확인 필요")

    def test_uncertain_source_does_not_generate(self):
        self.public.body = "예약 시간 변경에 대한 정책 확인 필요"
        self.public.save()
        self.assertFalse(search_paragraphs("예약 시간 변경").sufficient)

    def test_matching_topic_with_unanswered_detail_requires_confirmation(self):
        for question in [
            "예약 변경 위약금은 어떻게 안내하나요?",
            "예약 변경 수수료 100만원?",
            "예약 변경 지구 궤도 관련",
            "예약 변경은 무료인가요?",
            "예약 변경 의료사고 보상은 어떻게 하나요?",
            "예약 시간 변경 담당자 연락처",
        ]:
            with self.subTest(question=question):
                result = search_paragraphs(question)
                self.assertTrue(result.paragraphs)
                self.assertFalse(result.sufficient)

    def test_missing_key_preserves_sources(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("wiki:search"), {"question": "예약 시간을 변경하려면 어떻게 안내하나요?", "mode": "customer"})
        self.assertContains(response, "모델 미연결")
        self.assertContains(response, self.public.body)
        self.assertNotContains(response, self.private.body)
        self.assertNotContains(response, self.draft_p.body)
        self.assertNotContains(response, self.old_p.body)

    @patch("wiki.views.generate_draft")
    def test_internal_mode_never_calls_model(self, generate):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("wiki:search"), {"question": "인수인계", "mode": "internal"})
        generate.assert_not_called()
        self.assertContains(response, self.private.body)
        self.assertContains(response, "직원 전용")

    @patch("wiki.views.generate_draft")
    def test_no_evidence_never_calls_model(self, generate):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("wiki:search"), {"question": "헬리콥터 착륙장", "mode": "customer"})
        generate.assert_not_called()
        self.assertContains(response, "담당자 확인 필요")

    @override_settings(OPENAI_API_KEY="fake-test-key")
    @patch("wiki.services.urllib.request.urlopen")
    def test_model_receives_only_rechecked_current_approved_paragraphs(self, urlopen):
        response_mock = MagicMock()
        response_mock.__enter__.return_value.read.return_value = json.dumps({"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps({"answer": "가능한 시간을 확인한 뒤 변경을 도와드리겠습니다.", "needs_review": False}, ensure_ascii=False)}]}]}).encode()
        urlopen.return_value = response_mock
        result = generate_draft("예약 시간 변경", [self.public, self.private, self.old_p, self.draft_p])
        sent = json.loads(urlopen.call_args.args[0].data)
        content = json.loads(sent["input"])
        self.assertFalse(sent["store"])
        self.assertEqual([p["id"] for p in content["evidence"]], [self.public.pk])
        self.assertEqual(result["status"], "success")

    @override_settings(OPENAI_API_KEY="fake-test-key")
    @patch("wiki.services.urllib.request.urlopen", side_effect=TimeoutError("not logged"))
    def test_model_failure_is_graceful(self, _urlopen):
        result = generate_draft("예약 시간 변경", [self.public])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["answer"], "")

    @override_settings(OPENAI_API_KEY="fake-test-key")
    @patch("wiki.services.urllib.request.urlopen")
    def test_model_generated_links_are_rejected(self, urlopen):
        mock = MagicMock()
        mock.__enter__.return_value.read.return_value = json.dumps({"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps({"answer": "안내 https://invented.example", "needs_review": False})}]}]}).encode()
        urlopen.return_value = mock
        self.assertEqual(generate_draft("예약 변경", [self.public])["status"], "review")

    def test_publish_archives_previous_version_atomically(self):
        publish_version(self.draft.pk, self.manager)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "archived")
        result = search_paragraphs("예약 시간 변경")
        self.assertEqual([p.pk for p in result.paragraphs], [self.draft_p.pk])
        with self.assertRaises(ValidationError):
            publish_version(self.draft.pk, self.manager)

    def test_database_enforces_one_published_version(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DocumentVersion.objects.filter(pk=self.draft.pk).update(status="published")

    def test_revision_reuses_existing_draft(self):
        self.assertEqual(create_revision(self.document.pk, self.manager).pk, self.draft.pk)

    def test_revision_copies_publication_scope(self):
        DocumentVersion.objects.filter(pk=self.draft.pk).update(status="archived")
        revised = create_revision(self.document.pk, self.manager)
        self.assertEqual(revised.status, "draft")
        self.assertEqual(revised.number, 4)
        self.assertEqual(list(revised.paragraphs.values_list("customer_allowed", flat=True)), [True, False])

    def test_manager_routes_reject_employee_get_and_post(self):
        self.client.force_login(self.employee)
        for route, kwargs in [("manage", {}), ("new", {}), ("edit", {"pk": self.version.pk}), ("publish", {"pk": self.draft.pk}), ("archive", {"pk": self.version.pk}), ("revise", {"pk": self.document.pk})]:
            url = reverse(f"wiki:{route}", kwargs=kwargs)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url).status_code, 403)

    def test_published_version_cannot_be_edited(self):
        self.client.force_login(self.manager)
        self.client.post(reverse("wiki:edit", kwargs={"pk": self.version.pk}), {"title": "hacked"})
        self.version.refresh_from_db()
        self.assertEqual(self.version.title, "예약 변경 안내")

    def test_source_link_uses_registered_data(self):
        self.assertEqual(self.public.source_link, "https://example.com/reservations")
        self.public.source_url = "javascript:alert(1)"
        self.assertEqual(self.public.source_link, "")
        self.public.source_url = "https://www.youtube.com/watch?v=demo"
        self.public.timestamp = "02:15"
        self.assertIn("t=135", self.public.source_link)

    def test_sensitive_contact_input_rejected_before_search(self):
        for question in ["연락처 010-1234-5678 변경", "test@example.com 예약", "901010-1234567 예약"]:
            self.assertFalse(SearchForm({"question": question, "mode": "customer"}).is_valid())

    def test_search_requires_login_and_does_not_read_query_url(self):
        self.assertEqual(self.client.get(reverse("wiki:search")).status_code, 302)
        self.client.force_login(self.employee)
        response = self.client.get(reverse("wiki:search"), {"question": "do-not-echo"})
        self.assertNotContains(response, "do-not-echo")
