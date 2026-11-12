import re
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from core.permissions import manager_required
from .forms import NewDocumentForm, ParagraphFormSet, SearchForm, VersionForm
from .models import Document, DocumentVersion, Paragraph
from .services import create_revision, generate_draft, publish_version, search_paragraphs


@login_required
@never_cache
@sensitive_post_parameters("question")
def search(request):
    form = SearchForm(request.POST if request.method == "POST" else None)
    result = None
    model = {"status": "idle", "label": "모델 대기", "answer": "", "needs_review": False}
    mode = "customer"
    if request.method == "POST" and form.is_valid():
        question = form.cleaned_data["question"]
        mode = form.cleaned_data["mode"]
        result = search_paragraphs(question, mode)
        if mode == "internal":
            model = {"status": "skipped", "label": "내부 검색 · 모델 호출 안 함", "answer": "", "needs_review": False}
        elif result.sufficient:
            model = generate_draft(question, result.paragraphs)
        else:
            model = {"status": "skipped", "label": "호출 안 함 · 근거 확인 필요", "answer": "", "needs_review": True}
    return render(request, "wiki/search.html", {"form": form, "result": result, "model": model, "mode": mode})


@manager_required
def manage(request):
    documents = Document.objects.prefetch_related("versions").order_by("-created_at")
    return render(request, "wiki/manage.html", {"documents": documents})


@manager_required
def new_document(request):
    form = NewDocumentForm(request.POST or None, initial={"revised_on": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            document = Document.objects.create(slug=f"document-{uuid.uuid4().hex[:12]}", kind=form.cleaned_data["kind"])
            version = form.save(commit=False)
            version.document = document
            version.created_by = request.user
            version.save()
            for position, body in enumerate(re.split(r"\n\s*\n", form.cleaned_data["body"].strip()), 1):
                match = re.match(r"^\s*\[?(\d{1,3}:\d{2}(?::\d{2})?)\]?\s+", body)
                Paragraph.objects.create(version=version, position=position, body=body[match.end():] if match else body,
                                         timestamp=match.group(1) if match else "", customer_allowed=False)
        messages.success(request, "초안을 저장했습니다. 각 문단의 응대 허용 여부를 확인한 뒤 발행하세요.")
        return redirect("wiki:edit", pk=version.pk)
    return render(request, "wiki/new.html", {"form": form})


@manager_required
def edit(request, pk):
    version = get_object_or_404(DocumentVersion.objects.select_related("document"), pk=pk)
    if version.status != "draft":
        return render(request, "wiki/version.html", {"version": version})
    form = VersionForm(request.POST or None, instance=version)
    formset = ParagraphFormSet(request.POST or None, instance=version)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        # Atomic check keeps a concurrently published version immutable.
        with transaction.atomic():
            current = DocumentVersion.objects.select_for_update().get(pk=pk)
            if current.status != "draft":
                return HttpResponseBadRequest("발행된 버전은 수정할 수 없습니다.")
            form.save()
            position = max([p.position for p in version.paragraphs.all()] or [0])
            for obj in formset.save(commit=False):
                if not obj.pk:
                    position += 1
                    obj.position = position
                obj.save()
            for obj in formset.deleted_objects:
                obj.delete()
        messages.success(request, "초안을 저장했습니다.")
        return redirect("wiki:edit", pk=pk)
    return render(request, "wiki/edit.html", {"version": version, "form": form, "formset": formset})


@manager_required
@require_POST
def publish(request, pk):
    get_object_or_404(DocumentVersion, pk=pk)
    try:
        publish_version(pk, request.user)
        messages.success(request, "새 버전을 발행했습니다. 이전 발행본은 보관되며 검색에서 제외됩니다.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("wiki:edit", pk=pk)


@manager_required
@require_POST
def revise(request, pk):
    get_object_or_404(Document, pk=pk)
    version = create_revision(pk, request.user)
    return redirect("wiki:edit", pk=version.pk)


@manager_required
@require_POST
def archive(request, pk):
    version = get_object_or_404(DocumentVersion, pk=pk)
    DocumentVersion.objects.filter(pk=version.pk).update(status="archived")
    messages.success(request, "문서를 보관했습니다. 검색에 사용되지 않습니다.")
    return redirect("wiki:manage")
