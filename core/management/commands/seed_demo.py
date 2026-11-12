"""Create fictitious interview data once, preserving all existing records."""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Announcement
from operations.models import LeaveAccount, LeaveRequest, Reservation, Vehicle
from operations.services import book_vehicle, initialize_balance, submit_leave
from wiki.models import Document, DocumentVersion, Paragraph


class Command(BaseCommand):
    help = "가상 시연 자료를 최초 한 번 생성합니다. 기존 비밀번호·권한·문서·신청·예약은 변경하지 않습니다."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        User = get_user_model()

        def user_once(username, name, manager=False):
            existing = User.objects.filter(username=username).first()
            if existing:
                return existing
            return User.objects.create_user(
                username=username, password=None, first_name=name,
                is_staff=manager, is_active=True,
            )

        staff = user_once("demo_staff", "가상 지원")
        admin = user_once("demo_admin", "가상 관리", manager=True)

        announcements = [
            ("demo-welcome", "굿모나 팀 인트라넷에 오신 것을 환영합니다", "이 공간의 계정·자료·일정은 모두 면접 시연용 가상 데이터입니다. 고객 개인정보 없이 CS 위키에서 승인된 안내를 찾고, 직원 검토 후 사용해 주세요."),
            ("demo-operation", "공용 차량과 연차 신청 안내", "연차는 1일 또는 0.5일로 신청하며 관리자 승인 후 잔여일에 반영됩니다. 공용 차량의 예약 시간은 서로 겹칠 수 없습니다. 차량 화면에 표시된 기존 예약 시간을 이용해 충돌 차단을 시연할 수 있습니다."),
        ]
        for key, title, body in announcements:
            Announcement.objects.get_or_create(seed_key=key, defaults={
                "title": title, "body": body, "created_by": admin,
            })

        def document_once(slug, kind, title, keywords, paragraphs, status="published", number=1):
            document, created = Document.objects.get_or_create(slug=slug, defaults={"kind": kind})
            # A user may have revised or archived this document since the first run.
            # Its entire version tree is left untouched on every later invocation.
            if not created:
                return document
            source = f"https://example.com/demo/{slug}"
            version = DocumentVersion.objects.create(
                document=document, number=number, title=title, keywords=keywords,
                source_url=source, revised_on=today - timedelta(days=2),
                owner="가상 운영지원 담당자", status=status, created_by=admin,
                published_at=timezone.now() if status == "published" else None,
            )
            for position, entry in enumerate(paragraphs, start=1):
                body, allowed, timestamp = entry
                Paragraph.objects.create(
                    version=version, position=position, body=body,
                    customer_allowed=allowed, timestamp=timestamp,
                    source_url=f"{source}#paragraph-{position}",
                )
            if slug == "demo-reservation-change":
                old = DocumentVersion.objects.create(
                    document=document, number=1, title="예약 변경 안내 · 이전 개정본",
                    keywords="예약 변경, 이전 안내", source_url=f"{source}?version=1",
                    revised_on=today - timedelta(days=30), owner="가상 운영지원 담당자",
                    status="archived", created_by=admin,
                )
                Paragraph.objects.create(version=old, position=1, customer_allowed=True,
                    body="이전 시연 안내입니다. LEGACY-ARCHIVED-210. 현재 안내에는 사용하지 않습니다.")
            return document

        document_once(
            "demo-reservation-change", "manual", "예약 시간 변경 안내",
            "예약 변경, 예약 시간 변경, 예약 시간을 변경, 시간 변경, 일정 변경",
            [
                ("예약 시간을 변경하려면 원하시는 날짜와 시간을 먼저 확인해 주세요. 가능한 일정인지 예약 담당자가 확인한 뒤 변경된 예약 시간을 안내드립니다. 변경이 확정되기 전에는 기존 예약이 유지된다고 설명해 주세요. 이 절차는 가상 시연용 정책입니다.", True, ""),
                ("직원 내부 처리: 예약 변경 요청은 가상 예약 담당자에게 전달하고, 변경 확정 회신을 받은 다음 안내를 마무리합니다. 내부 전달 경로는 고객 답변에 포함하지 않습니다. INTERNAL-BOOKING-731.", False, ""),
            ], number=2,
        )
        document_once(
            "demo-reservation-cancel", "manual", "예약 취소 안내",
            "예약 취소, 취소 안내, 예약을 취소",
            [("예약 취소를 원하시면 예약 담당자에게 취소 요청을 전달해 드린다고 안내해 주세요. 취소 완료 여부를 확인한 뒤 안내합니다. 취소 수수료나 환불 조건은 이 가상 문서에서 정하지 않았으므로 단정하지 않습니다.", True, "")],
        )
        document_once(
            "demo-visit-preparation", "manual", "방문 전 준비 안내",
            "방문 준비, 방문 전 준비, 예약 확인",
            [("방문 전 준비에 관한 기본 안내는 예약된 방문 일시를 다시 확인하는 것입니다. 별도 준비가 필요한지는 예약 담당자에게 확인해 안내합니다. 이 가상 매뉴얼은 진료나 시술 준비에 관한 의료 지침을 포함하지 않습니다.", True, "")],
        )
        document_once(
            "demo-wayfinding", "manual", "오시는 길 문의 안내",
            "오시는 길, 위치 안내, 주차 문의",
            [("오시는 길이나 위치 안내를 요청받으면 방문 안내 자료의 주소를 예약 담당자에게 확인한 뒤 전달합니다. 이 시연용 자료에는 실제 의원 주소·주차 가능 여부가 등록되어 있지 않습니다. 확인되지 않은 위치나 주차 조건은 안내하지 않습니다.", True, "")],
        )
        document_once(
            "demo-service-transcript", "transcript", "응대 기본 원칙 · 가상 영상 대본",
            "응대 기본 원칙, 답변 검토, 복사 전 확인",
            [
                ("응대 기본 원칙은 발행된 자료에서 확인한 내용만 안내하는 것입니다. 확인되지 않은 일정이나 정책은 담당자가 확인한 다음 안내한다고 설명해 주세요. 이 문단은 실제 영상이 없는 가상 대본이며 출처 URL도 예시입니다.", True, "00:35"),
                ("직원 답변 검토: 생성된 문장과 근거 문단을 대조하고, 불필요한 정보가 없는지 확인한 뒤 복사합니다. 고객 이름이나 연락처가 포함된 메시지를 검색창에 붙여넣지 않습니다.", False, "01:20"),
            ],
        )
        document_once(
            "demo-staff-onboarding", "onboarding", "직원 온보딩 · 내부 인수인계",
            "직원 온보딩, 신입 직원, 업무 인수인계, INTERNAL-ONLY-482",
            [("직원 온보딩 전용 가상 자료입니다. INTERNAL-ONLY-482. 신입 직원은 근무 시작 전 공지 확인, 담당 업무 인수인계, 연차·차량 예약 화면의 사용 방법을 내부 담당자와 확인합니다. 이 문단은 직원에게만 필요한 내부 운영 절차이며 고객 응대에는 사용하지 않습니다.", False, "")],
        )
        document_once(
            "demo-draft-fees", "manual", "비용 안내 정책 · 검토 중인 초안",
            "비용 안내, 비용 정책, DRAFT-ONLY-640",
            [("DRAFT-ONLY-640. 아직 승인되지 않은 가상 초안입니다. 고객에게 안내할 확정 정책이 없으며 검색 결과에 사용하지 않습니다.", True, "")], status="draft",
        )
        document_once(
            "demo-archived-hours", "manual", "과거 운영 시간 안내 · 보관 자료",
            "운영 시간, ARCHIVED-ONLY-538",
            [("ARCHIVED-ONLY-538. 과거 가상 운영 안내입니다. 현재 발행 자료가 아니므로 검색과 고객 답변에 사용하지 않습니다.", True, "")], status="archived",
        )

        for user, units in ((staff, 24), (admin, 30)):
            if not LeaveAccount.objects.filter(user=user).exists():
                initialize_balance(user, units, actor=admin)
        for user, days_ahead, units, key in (
            (staff, 3, 2, "demo-staff-pending-leave"),
            (admin, 4, 1, "demo-admin-pending-leave"),
        ):
            if LeaveRequest.objects.filter(seed_key=key).exists():
                continue
            leave_date = today + timedelta(days=days_ahead)
            if LeaveRequest.objects.filter(user=user, leave_date=leave_date, status__in=["pending", "approved"]).exists():
                self.stdout.write(f"기존 동일 날짜 신청을 보존하여 {key} 생성을 생략했습니다.")
                continue
            submit_leave(user, leave_date, units, reason="가상 시연용 개인 일정", seed_key=key)

        first, _ = Vehicle.objects.get_or_create(seed_key="demo-vehicle-1", defaults={
            "name": "공용 차량 1 · 가상 세단", "plate": "가상 01호",
        })
        second, _ = Vehicle.objects.get_or_create(seed_key="demo-vehicle-2", defaults={
            "name": "공용 차량 2 · 가상 승합차", "plate": "가상 02호",
        })
        tomorrow = today + timedelta(days=1)
        for vehicle, user, start_hour, key in (
            (first, admin, 10, "demo-reservation-1"),
            (second, staff, 14, "demo-reservation-2"),
        ):
            if Reservation.objects.filter(seed_key=key).exists():
                continue
            start = timezone.make_aware(datetime.combine(tomorrow, time(start_hour)), timezone.get_current_timezone())
            end = start + timedelta(hours=1)
            if not vehicle.active or Reservation.objects.filter(vehicle=vehicle, status="active", starts_at__lt=end, ends_at__gt=start).exists():
                self.stdout.write(f"기존 차량 상태·예약을 보존하여 {key} 생성을 생략했습니다.")
                continue
            book_vehicle(user, vehicle, start, end, purpose="가상 운영 물품 이동", seed_key=key)

        self.stdout.write(self.style.SUCCESS(
            "데모 자료 준비 완료. 기존 데이터는 변경하지 않았습니다. 계정: demo_staff / demo_admin. "
            "접속 화면에서 직원 또는 관리자 버튼을 선택하세요."
        ))
        self.stdout.write("CS 질문: 예약 시간을 변경하려면 어떻게 안내하나요?")
        self.stdout.write("내부 전용 검색어: 직원 온보딩 또는 INTERNAL-ONLY-482")
