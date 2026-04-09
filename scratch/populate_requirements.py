import os
import sys
import django

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobportal.settings')
django.setup()

from core.models import Job

# Cập nhật một số job có sẵn để test tags và logo
jobs = Job.objects.all()

requirements_data = [
    "Python, Django, ReactJS",
    "Java, Spring Boot, MySQL",
    "HTML, CSS, JavaScript, VueJS",
    "AWS, Docker, Kubernetes, DevOps",
    "PHP, Laravel, MariaDB",
    "Node.js, Express, MongoDB",
]

for i, job in enumerate(jobs):
    req = requirements_data[i % len(requirements_data)]
    job.requirements = req
    job.save()
    print(f"Updated job '{job.title}' with requirements: {req}")

print("\nDone! Data updated successfully.")
