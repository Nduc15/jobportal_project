from django import forms
from django.core.exceptions import ValidationError
from .models import User, Job, Application

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar', 'first_name', 'company_name', 'phone_number', 'skills', 'default_cv', 'company_description']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập họ và tên đầy đủ'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên công ty'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 0912345678'}),
            'skills': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ví dụ: Python, Django, ReactJS...'}),
            'avatar': forms.FileInput(attrs={'class': 'd-none', 'id': 'avatar_upload', 'accept': 'image/*'}),
            'default_cv': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
            'company_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Giới thiệu ngắn gọn về công ty của bạn...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            if self.instance.is_superuser:
                # Nếu là Admin (Superuser): Xóa các trường đặc thù của cả NTD và Ứng viên
                fields_to_remove = ['company_name', 'skills', 'default_cv', 'company_description']
                for field in fields_to_remove:
                    if field in self.fields:
                        del self.fields[field]
            elif self.instance.is_employer:
                # Nếu là Nhà tuyển dụng: Giữ Tên công ty, Xóa Họ tên và các trường Ứng viên
                if 'first_name' in self.fields:
                    del self.fields['first_name']
                if 'skills' in self.fields:
                    del self.fields['skills']
                if 'default_cv' in self.fields:
                    del self.fields['default_cv']
            else:
                # Nếu là Ứng viên: Giữ Họ tên, Xóa Tên công ty và Mô tả công ty
                if 'company_name' in self.fields:
                    del self.fields['company_name']
                if 'company_description' in self.fields:
                    del self.fields['company_description']

class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'experience', 'job_type', 'quantity', 'description', 'requirements', 'salary_min', 'salary_max', 'location']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: Lập trình viên Python Django',
            }),
            'experience': forms.Select(choices=Job.EXPERIENCE_CHOICES, attrs={
                'class': 'form-select',
            }),
            'job_type': forms.Select(choices=Job.JOB_TYPE_CHOICES, attrs={
                'class': 'form-select',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: 5',
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
            'experience': 'Kinh nghiệm yêu cầu',
            'job_type': 'Hình thức làm việc',
            'quantity': 'Số lượng tuyển',
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
