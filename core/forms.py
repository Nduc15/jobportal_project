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

class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'description', 'requirements', 'salary_min', 'salary_max', 'location']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: Lập trình viên Python Django',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Mô tả chi tiết công việc, quyền lợi...',
            }),
            'requirements': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: Python, Django, ReactJS (Phân cách bằng dấu phẩy)',
            }),
            'salary_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: 15',
            }),
            'salary_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: 30',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: Hà Nội',
            }),
        }
        labels = {
            'title': 'Tiêu đề công việc',
            'description': 'Mô tả công việc',
            'requirements': 'Yêu cầu kỹ năng (Tags)',
            'salary_min': 'Lương tối thiểu (Triệu VNĐ)',
            'salary_max': 'Lương tối đa (Triệu VNĐ)',
            'location': 'Địa điểm làm việc',
        }

    def clean(self):
        cleaned_data = super().clean()
        salary_min = cleaned_data.get('salary_min')
        salary_max = cleaned_data.get('salary_max')

        if salary_min and salary_max and salary_min > salary_max:
            raise ValidationError("Lương tối thiểu không thể lớn hơn lương tối đa.")
        
        return cleaned_data
