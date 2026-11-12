from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Vehicle


class LeaveForm(forms.Form):
    leave_date = forms.DateField(label="사용 날짜", widget=forms.DateInput(attrs={"type": "date"}))
    period = forms.ChoiceField(label='신청 구분', choices=[('full', '하루'), ('am', '오전 반차'), ('pm', '오후 반차')], widget=forms.RadioSelect)
    reason = forms.CharField(label="메모 (선택)", max_length=200, required=False,
                            widget=forms.TextInput(attrs={"placeholder": "개인정보 없이 간단히 입력하세요"}))

    def __init__(self, *args, **kwargs):
        # Full-day legacy posts remain valid; old unspecified half-days need explicit confirmation.
        if args and args[0] is not None and 'period' not in args[0] and str(args[0].get('units')) == '2':
            data = args[0].copy(); data['period'] = 'full'; args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        self.fields["leave_date"].widget.attrs["min"] = timezone.localdate().isoformat()


class ReservationForm(forms.Form):
    vehicle = forms.ModelChoiceField(label="차량", queryset=Vehicle.objects.none(), empty_label="차량 선택")
    starts_at = forms.DateTimeField(label="시작 시각", input_formats=["%Y-%m-%dT%H:%M"],
                                   widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}))
    ends_at = forms.DateTimeField(label="종료 시각", input_formats=["%Y-%m-%dT%H:%M"],
                                 widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}))
    purpose = forms.CharField(label="사용 메모 (선택)", required=False, max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = Vehicle.objects.filter(active=True)


class InitialBalanceForm(forms.Form):
    user = forms.ModelChoiceField(label="직원", queryset=get_user_model().objects.none())
    days = forms.DecimalField(label="시작 잔여일", min_value=0, max_value=365, decimal_places=1,
                              widget=forms.NumberInput(attrs={"step": "0.5"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = get_user_model().objects.filter(is_active=True, leave_account__isnull=True).order_by("username")

    def clean_days(self):
        value = self.cleaned_data["days"]
        if value * 2 != (value * 2).to_integral_value():
            raise forms.ValidationError("0.5일 단위로 입력하세요.")
        return value


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["name", "plate", "active"]
        labels = {"name": "차량 이름", "plate": "차량 번호 (가상)", "active": "예약 허용"}
