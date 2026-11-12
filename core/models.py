from django.conf import settings
from django.db import models

class Announcement(models.Model):
    title = models.CharField('제목', max_length=160)
    body = models.TextField('내용')
    is_active = models.BooleanField('게시', default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    seed_key = models.CharField(max_length=80, unique=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
