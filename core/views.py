from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from .forms import AnnouncementForm
from .models import Announcement
from .permissions import is_manager, manager_required

class DemoRoleLoginView(View):
    template_name = 'registration/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')
        return render(request, self.template_name, {'next': request.GET.get('next', '')})

    def post(self, request, *args, **kwargs):
        # Deliberately open role selection for this fictional interview demo.
        # Never accept a user ID, arbitrary username or privilege flag from POST.
        role = request.POST.get('role')
        username = {'staff': 'demo_staff', 'admin': 'demo_admin'}.get(role)
        if username is None:
            return render(request, self.template_name, {'error': '접속할 역할을 선택해 주세요.'}, status=400)
        account = get_user_model().objects.filter(username=username, is_active=True).first()
        if account is None or is_manager(account) != (role == 'admin'):
            return render(request, self.template_name, {
                'error': '선택한 데모 계정이 준비되지 않았습니다. 데모 데이터와 계정 상태를 확인해 주세요.',
            }, status=403)
        login(request, account, backend='django.contrib.auth.backends.ModelBackend')
        target = request.POST.get('next', '')
        if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(target)
        return redirect('core:home')

@login_required
def home(request):
    from operations.models import LeaveAccount, LeaveRequest, Reservation
    from wiki.models import DocumentVersion
    return render(request, 'core/home.html', {
        'announcements': Announcement.objects.filter(is_active=True)[:4],
        'account': LeaveAccount.objects.filter(user=request.user).first(),
        'leaves': LeaveRequest.objects.filter(user=request.user).order_by('-created_at')[:3],
        'reservations': Reservation.objects.filter(user=request.user, status='active', ends_at__gte=timezone.now()).select_related('vehicle').order_by('starts_at')[:3],
        'published_count': DocumentVersion.objects.filter(status='published').count(),
        'today': timezone.localdate(),
    })

@manager_required
def manager(request):
    from operations.models import LeaveRequest
    from wiki.models import DocumentVersion
    return render(request, 'core/manager.html', {
        'pending_count': LeaveRequest.objects.filter(status='pending').count(),
        'draft_count': DocumentVersion.objects.filter(status='draft').count(),
    })

@manager_required
def announcements(request, pk=None):
    item = get_object_or_404(Announcement, pk=pk) if pk else None
    form = AnnouncementForm(request.POST or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        notice = form.save(commit=False)
        if not notice.pk:
            notice.created_by = request.user
        notice.save()
        messages.success(request, '공지를 저장했습니다.')
        return redirect('core:announcements')
    return render(request, 'core/announcements.html', {'form': form, 'items': Announcement.objects.all(), 'editing': item})

def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()
    return JsonResponse({'status': 'ok'})
