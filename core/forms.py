from django import forms
from django.core.exceptions import ValidationError
from .models import User, Job, Application

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar', 'phone_number', 'skills', 'default_cv']
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 0912345678'}),
            'skills': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ví dụ: Python, Django, ReactJS...'}),
            'avatar': forms.FileInput(attrs={'class': 'd-none', 'id': 'avatar_upload', 'accept': 'image/*'}),
            'default_cv': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
        }
