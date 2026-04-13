"""
Script tạo dữ liệu mẫu để kiểm tra Dashboard.
Chạy: python manage.py shell < create_sample_data.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobportal.settings')
django.setup()

from core.models import User, Job, Application

# === Tạo Nhà tuyển dụng ===
employer, created = User.objects.get_or_create(
    username='ntd_fpt',
    defaults={
        'email': 'ntd@fpt.vn',
        'is_employer': True,
        'is_candidate': False,
        'company_name': 'FPT Software',
    }
)
if created:
    employer.set_password('test1234')
    employer.save()
    print("[OK] Tao NTD: ntd_fpt / test1234")
else:
    print("[INFO] NTD ntd_fpt da ton tai")

# === Tạo Ứng viên ===
candidate, created = User.objects.get_or_create(
    username='ungvien01',
    defaults={
        'email': 'uv01@gmail.com',
        'is_employer': False,
        'is_candidate': True,
    }
)
if created:
    candidate.set_password('test1234')
    candidate.save()
    print("[OK] Tao UV: ungvien01 / test1234")
else:
    print("[INFO] UV ungvien01 da ton tai")

candidate2, created = User.objects.get_or_create(
    username='ungvien02',
    defaults={
        'email': 'uv02@gmail.com',
        'is_employer': False,
        'is_candidate': True,
    }
)
if created:
    candidate2.set_password('test1234')
    candidate2.save()
    print("[OK] Tao UV: ungvien02 / test1234")
else:
    print("[INFO] UV ungvien02 da ton tai")

# === Tạo Tin tuyển dụng ===
jobs_data = [
    {
        'title': 'Lập trình viên Python (Django)', 
        'description': 'Phát triển backend bằng Django', 
        'location': 'Hà Nội', 
        'salary_min': 15, 
        'salary_max': 25, 
        'is_approved': True,
        'experience': '1_3',
        'job_type': 'full_time',
        'quantity': 3
    },
    {
        'title': 'Lập trình viên Java Spring Boot', 
        'description': 'Xây dựng hệ thống microservices', 
        'location': 'TP.HCM', 
        'salary_min': 18, 
        'salary_max': 30, 
        'is_approved': True,
        'experience': '3_5',
        'job_type': 'full_time',
        'quantity': 5
    },
    {
        'title': 'Frontend Developer (React)', 
        'description': 'Phát triển giao diện người dùng', 
        'location': 'Đà Nẵng', 
        'salary_min': 12, 
        'salary_max': 22, 
        'is_approved': False,
        'experience': 'none',
        'job_type': 'remote',
        'quantity': 2
    },
    {
        'title': 'DevOps Engineer', 
        'description': 'Quản lý CI/CD và hạ tầng cloud', 
        'location': 'Hà Nội', 
        'salary_min': 20, 
        'salary_max': 35, 
        'is_approved': True,
        'experience': 'over_5',
        'job_type': 'full_time',
        'quantity': 1
    },
]

created_jobs = []
for jd in jobs_data:
    job, created = Job.objects.get_or_create(
        title=jd['title'],
        employer=employer,
        defaults=jd
    )
    created_jobs.append(job)
    if created:
        print(f"[OK] Tao Job: {job.title}")
    else:
        print(f"[INFO] Job '{job.title}' da ton tai")

# === Tạo Application (ứng viên nộp CV) ===
apps_data = [
    {'job': created_jobs[0], 'candidate': candidate, 'status': 'Pending'},
    {'job': created_jobs[1], 'candidate': candidate, 'status': 'Accepted'},
    {'job': created_jobs[2], 'candidate': candidate, 'status': 'Rejected'},
    {'job': created_jobs[3], 'candidate': candidate, 'status': 'Pending'},
    {'job': created_jobs[0], 'candidate': candidate2, 'status': 'Pending'},
    {'job': created_jobs[1], 'candidate': candidate2, 'status': 'Viewed'},
]

for ad in apps_data:
    app, created = Application.objects.get_or_create(
        job=ad['job'],
        candidate=ad['candidate'],
        defaults={'status': ad['status'], 'cv_file': 'cvs/sample.pdf'}
    )
    if created:
        print(f"[OK] Tao Application: {ad['candidate'].username} -> {ad['job'].title} ({ad['status']})")
    else:
        print(f"[INFO] Application da ton tai")

print("\nHoan tat tao du lieu mau!")
print("=" * 50)
print("Tai khoan NTD:    ntd_fpt / test1234")
print("Tai khoan UV:     ungvien01 / test1234")
print("Tai khoan UV 2:   ungvien02 / test1234")
