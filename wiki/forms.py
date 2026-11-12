import re

from django import forms
from django.forms import inlineformset_factory

from .models import Document, DocumentVersion, Paragraph


class SearchForm(forms.Form):
    mode = forms.ChoiceField(choices=[("customer", "고객 답변 찾기"), ("internal", "내부 문서 찾기")], widget=forms.RadioSelect, initial="customer")
    question = forms.CharField(label="질문 또는 검색어", max_length=400, widget=forms.TextInput(attrs={"placeholder": "예약 시간을 변경하려면 어떻게 안내하나요?", "autocomplete": "off"}))

    def clean_question(self):
        question = self.cleaned_data["question"].strip()
        if re.search(r"\b01[016789][\s-]?\d{3,4}[\s-]?\d{4}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\d{6}[- ]?[1-4]\d{6}", question):
            raise forms.ValidationError("연락처·이메일 등 개인정보를 지우고 일반적인 질문만 입력해 주세요.")
        return question


class VersionForm(forms.ModelForm):
    class Meta:
        model = DocumentVersion
        fields = ["title", "source_url", "revised_on", "owner", "keywords"]
        labels = {"title": "문서 제목", "source_url": "출처 URL", "revised_on": "개정일", "owner": "담당자", "keywords": "검색 키워드 · 동의어"}
        widgets = {"revised_on": forms.DateInput(attrs={"type": "date"}), "keywords": forms.Textarea(attrs={"rows": 2, "placeholder": "예약 변경, 시간 변경, 일정 변경"})}


class NewDocumentForm(VersionForm):
    kind = forms.ChoiceField(label="자료 유형", choices=Document.Kind.choices)
    body = forms.CharField(label="본문 붙여넣기", widget=forms.Textarea(attrs={"rows": 12}), help_text="빈 줄로 문단을 나눕니다. [02:15]처럼 시작하는 타임스탬프는 따로 저장됩니다.")


class ParagraphForm(forms.ModelForm):
    class Meta:
        model = Paragraph
        fields = ["body", "customer_allowed", "timestamp", "source_url"]
        labels = {"body": "원문 문단", "customer_allowed": "고객 응대에 사용 가능", "timestamp": "타임스탬프", "source_url": "문단 출처 URL (없으면 문서 출처 사용)"}
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}

    def clean_timestamp(self):
        value = self.cleaned_data["timestamp"].strip()
        if value and not re.fullmatch(r"\d{1,3}:\d{2}(?::\d{2})?", value):
            raise forms.ValidationError("02:15 또는 01:02:15 형식으로 입력해 주세요.")
        return value


ParagraphFormSet = inlineformset_factory(DocumentVersion, Paragraph, form=ParagraphForm, extra=1, can_delete=True)
