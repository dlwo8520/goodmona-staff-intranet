"""Exercise startup twice on an isolated SQLite file, never the live/demo DB."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

with tempfile.TemporaryDirectory(prefix='goodmona-persistence-') as directory:
    os.environ.update({
        'DJANGO_SETTINGS_MODULE': 'intranet.settings', 'DJANGO_DEBUG': 'False',
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(60), 'SQLITE_PATH': str(Path(directory) / 'intranet.sqlite3'),
        'SEED_DEMO': 'true', 'PYTHONIOENCODING': 'utf-8',
    })
    os.environ.pop('RENDER', None)
    def startup():
        subprocess.run([sys.executable, str(root / 'scripts' / 'prepare_runtime.py')],
                       cwd=root, env=os.environ, check=True, stdout=subprocess.DEVNULL)
    startup()
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection
    from operations.models import LeaveAccount, LeaveRequest, Reservation
    from operations.services import process_leave, cancel_reservation
    from wiki.models import DocumentVersion
    admin = get_user_model().objects.get(username='demo_admin')
    request = LeaveRequest.objects.get(seed_key='demo-staff-pending-leave')
    process_leave(request.pk, admin, 'approve')
    booking = Reservation.objects.get(seed_key='demo-reservation-1')
    cancel_reservation(booking.pk, admin)
    draft = DocumentVersion.objects.get(document__slug='demo-draft-fees')
    draft.title = 'Persistence verification edited draft'
    draft.save(update_fields=['title'])
    expected = LeaveAccount.objects.get(user=request.user).balance_units
    counts = (LeaveRequest.objects.count(), Reservation.objects.count(), DocumentVersion.objects.count())
    connection.close()
    startup()
    assert LeaveRequest.objects.get(pk=request.pk).status == 'approved'
    assert LeaveAccount.objects.get(user=request.user).balance_units == expected
    assert Reservation.objects.get(pk=booking.pk).status == 'cancelled'
    assert DocumentVersion.objects.get(pk=draft.pk).title == 'Persistence verification edited draft'
    assert counts == (LeaveRequest.objects.count(), Reservation.objects.count(), DocumentVersion.objects.count())
    connection.close()
print('PASS: separate startup processes retained edited wiki, approved leave balance, cancelled reservation and row counts.')
