from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from operations.models import LeaveRequest
from operations.services import process_leave, submit_leave


class Command(BaseCommand):
    help = '현재 자료를 유지하면서 부서 5명/최소3명 인원 검증용 가상 신청을 추가합니다.'

    @transaction.atomic
    def handle(self, *args, **options):
        call_command('seed_demo', stdout=self.stdout)
        users = get_user_model().objects
        admin = users.get(username='demo_admin')
        today = timezone.localdate()
        entries = [(2, 7, True, 'capacity-two-first'), (3, 7, True, 'capacity-two-second'),
                   (2, 8, True, 'capacity-race-approved'), (3, 8, False, 'capacity-race-pending-one'),
                   (4, 8, False, 'capacity-race-pending-two')]
        for number, offset, approve, key in entries:
            request = LeaveRequest.objects.filter(seed_key=key).first()
            if request is None:
                request = submit_leave(users.get(username=f'demo_staff{number}'), today + timedelta(days=offset),
                                       period='full', reason='부서 인원 검증용 가상 신청', seed_key=key)
                if approve:
                    process_leave(request.pk, admin, 'approve')
                request.refresh_from_db()
            self.stdout.write(f'{request.leave_date} · demo_staff{number} · {request.get_status_display()}')
