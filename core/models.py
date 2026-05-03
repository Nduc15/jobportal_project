import os
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.core.files.storage import FileSystemStorage
from django.conf import settings

class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        # Nếu file đã tồn tại, xóa file cũ đi để ghi đè (giữ nguyên tên gốc tuyệt đối)
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name

def user_directory_path(instance, filename):
    # Lưu mỗi người dùng vào một thư mục riêng để không đụng hàng tên file
    return f'cvs/defaults/user_{instance.id}/{filename}'

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
    default_cv = models.FileField(
        upload_to=user_directory_path, 
        storage=OverwriteStorage(),
        null=True, 
        blank=True, 
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx']), validate_file_size]
    )
    company_description = models.TextField(blank=True, null=True, verbose_name="Mô tả công ty")
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="Địa chỉ công ty")
    
    def clean(self):
        if self.is_employer and self.is_candidate:
            raise ValidationError("Một tài khoản không thể vừa là Nhà tuyển dụng vừa là Ứng viên.")

    @property
    def cv_filename(self):
        # Dùng regex để làm đẹp ngay lập tức các file đã bị lưu dính mã trước đây
        if self.default_cv:
            import os
            import re
            base = os.path.basename(self.default_cv.name)
            return re.sub(r'_[a-zA-Z0-9]{7}(\.[a-zA-Z0-9]+)$', r'\1', base)
        return ""

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class Job(models.Model):
    EXPERIENCE_CHOICES = [
        ('none', 'Không yêu cầu'),
        ('0_1', 'Dưới 1 năm'),
        ('1_3', '1 - 3 năm'),
        ('3_5', '3 - 5 năm'),
        ('over_5', 'Trên 5 năm'),
    ]
    
    JOB_TYPE_CHOICES = [
        ('full_time', 'Toàn thời gian'),
        ('part_time', 'Bán thời gian'),
        ('remote', 'Làm từ xa'),
        ('hybrid', 'Hybrid (Kết hợp)'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    location = models.CharField(max_length=200, db_index=True)
    
    employer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='jobs')
    is_approved = models.BooleanField(default=False, db_index=True)
    requirements = models.CharField(max_length=500, blank=True, null=True, verbose_name="Yêu cầu kỹ năng")
    
    # Các trường đã được chuẩn hóa
    experience = models.CharField(max_length=50, choices=EXPERIENCE_CHOICES, default='none', verbose_name="Kinh nghiệm")
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES, default='full_time', verbose_name="Hình thức làm việc")
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Số lượng tuyển")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def requirements_list(self):
        """Trả về danh sách các tag từ chuỗi requirements (ví dụ: 'Python, Django' -> ['Python', 'Django'])"""
        if self.requirements:
            return [tag.strip() for tag in self.requirements.split(',') if tag.strip()]
        return []

    @property
    def time_ago_vn(self):
        from django.utils import timezone
        diff = timezone.now() - self.updated_at
        seconds = diff.total_seconds()
        if seconds < 60:
            return "Vừa xong"
        elif seconds < 3600:
            return f"{int(seconds // 60)} phút trước"
        elif seconds < 86400:
            return f"{int(seconds // 3600)} giờ trước"
        elif seconds < 604800:
            return f"{int(seconds // 86400)} ngày trước"
        elif seconds < 2592000:
            return f"{int(seconds // 604800)} tuần trước"
        elif seconds < 31536000:
            return f"{int(seconds // 2592000)} tháng trước"
        return f"{int(seconds // 31536000)} năm trước"

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
        ('Interview', 'Mời phỏng vấn'),
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
        ],
        null=True,
        blank=True
    )
    online_cv = models.ForeignKey('CV', on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    applied_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True)
    employer_note = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('job', 'candidate')

    @property
    def filename(self):
        if self.cv_file:
            return os.path.basename(self.cv_file.name)
        return ""

    def clean(self):
        if not self.cv_file and not self.online_cv:
            raise ValidationError("Phải cung cấp File CV hoặc chọn CV trực tuyến.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidate.username} nộp {self.job.title}"

class InterviewInvitation(models.Model):
    MODE_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Tại văn phòng'),
        ('phone', 'Gọi điện'),
    ]

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='interview')
    scheduled_at = models.DateTimeField()
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='online')
    location = models.CharField(max_length=500, verbose_name="Link hoặc địa điểm phỏng vấn")
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_interviews')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_at']

    def __str__(self):
        return f"Interview: {self.application.candidate.username} - {self.application.job.title}"

class SavedJob(models.Model):
    """Lưu trữ các công việc mà ứng viên đã đánh dấu yêu thích."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'job')

    def __str__(self):
        return f"{self.user.username} đã lưu {self.job.title}"

class CV(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cvs')
    title = models.CharField(max_length=200, default="CV Không Tên")
    
    # Personal Info
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    address = models.CharField(max_length=255, blank=True, null=True)
    target_major = models.CharField(max_length=255, blank=True, null=True, verbose_name="Vị trí ứng tuyển")
    objective = models.TextField(blank=True, null=True, verbose_name="Mục tiêu nghề nghiệp")
    avatar = models.ImageField(upload_to='cv_avatars/', null=True, blank=True)
    github = models.URLField(max_length=255, blank=True, null=True)
    linkedin = models.URLField(max_length=255, blank=True, null=True)
    
    # Complex fields stored as JSON
    education = models.JSONField(default=list, blank=True, null=True)
    experience = models.JSONField(default=list, blank=True, null=True)
    skills = models.JSONField(default=list, blank=True, null=True)
    projects = models.JSONField(default=list, blank=True, null=True)
    certifications = models.JSONField(default=list, blank=True, null=True)
    
    # Template name
    template_name = models.CharField(max_length=50, default='default')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CV: {self.title} - {self.user.username}"

class ApplicationMatch(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='match')
    
    # Điểm tổng & từng phần
    score = models.IntegerField(default=0)         # 0–100
    skill_score = models.IntegerField(default=0)   # /50
    exp_score = models.IntegerField(default=0)     # /20
    desc_score = models.IntegerField(default=0)    # /15
    project_score = models.IntegerField(default=0) # /10
    bonus_score = models.IntegerField(default=0)   # /5
    
    # Dữ liệu giải thích
    matched_skills = models.JSONField(default=list)   # ['Python', 'Django']
    missing_skills = models.JSONField(default=list)   # ['Docker', 'AWS']
    matched_keywords = models.JSONField(default=list) # keywords chung
    
    # AI summary & questions
    summary = models.TextField(blank=True, null=True)
    interview_questions = models.JSONField(default=list, blank=True, null=True) # 2-3 câu hỏi gợi ý
    ai_generated = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Match: {self.score}% - {self.application.candidate.username}"
