from django import forms
from .models import Announcement

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'body', 'is_active']
        widgets = {'body': forms.Textarea(attrs={'rows': 5})}
