from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

def validate_file_size(value):
    filesize = value.size
    if filesize > 5242880: # 5MB
        raise ValidationError("Kích thước file tối đa là 5MB")

class User(AbstractUser):
    email = models.EmailField(unique=True)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    phone_number = models.CharField(max_length=30, null=True, blank=True)
    is_employer = models.BooleanField(default=False)
    is_candidate = models.BooleanField(default=False)
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    skills = models.CharField(max_length=500, blank=True, null=True)
    default_cv = models.FileField(upload_to='cvs/defaults/', null=True, blank=True, validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx']), validate_file_size])
    
    def clean(self):
        if self.is_employer and self.is_candidate:
            raise ValidationError("Một tài khoản không thể vừa là Nhà tuyển dụng vừa là Ứng viên.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class Job(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    location = models.CharField(max_length=200, db_index=True)
    
    employer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='jobs')
    is_approved = models.BooleanField(default=False, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.salary_min and self.salary_max and self.salary_min > self.salary_max:
            raise ValidationError("Lương tối thiểu không thể lớn hơn lương tối đa.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class Application(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Chờ duyệt'),
        ('Viewed', 'Đã xem'),
        ('Accepted', 'Chấp nhận'),
        ('Rejected', 'Từ chối'),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='apps')
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_apps')
    cv_file = models.FileField(
        upload_to='cvs/', 
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'docx']),
            validate_file_size
        ]
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True)
    employer_note = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('job', 'candidate')

    def __str__(self):
        return f"{self.candidate.username} nộp {self.job.title}"