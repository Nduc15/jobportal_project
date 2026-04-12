import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobportal.settings')
django.setup()

from core.models import Job

def migrate():
    print("Starting data migration for Job fields...")
    
    # Mapping definitions
    exp_mapping = {
        'Không yêu cầu': 'none',
        'Thực tập / Fresher': '0_1',
        '1 - 3 năm': '1_3',
        'Trên 3 năm': '3_5',
    }
    
    type_mapping = {
        'Toàn thời gian': 'full_time',
        'Bán thời gian': 'part_time',
        'Làm từ xa': 'remote',
    }

    # Update Experience
    for old_val, new_key in exp_mapping.items():
        count = Job.objects.filter(experience=old_val).update(experience=new_key)
        if count > 0:
            print(f"Updated jobs for experience: {count}")

    # Update Job Type
    for old_val, new_key in type_mapping.items():
        count = Job.objects.filter(job_type=old_val).update(job_type=new_key)
        if count > 0:
            print(f"Updated jobs for job_type: {count}")

    print("Data migration completed!")

if __name__ == "__main__":
    migrate()
