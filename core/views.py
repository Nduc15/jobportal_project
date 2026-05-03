from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import os
import json
import time
from django.core.files.base import ContentFile
from .forms import UserProfileForm, JobForm
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Job, Application, SavedJob, CV, ApplicationMatch, InterviewInvitation
from .utils import get_similar_jobs
from .matching import compute_match
import bleach
from bleach.css_sanitizer import CSSSanitizer
try:
    from google import genai as google_genai
    GEMINI_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: Gemini SDK Import Error: {e}")
    GEMINI_AVAILABLE = False
except Exception as e:
    print(f"DEBUG: Gemini SDK Unexpected Error: {e}")
    GEMINI_AVAILABLE = False

# Cấu hình các thẻ HTML được phép cho bộ soạn thảo Rich Text
ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'strong', 'em', 'u', 's',
    'ul', 'ol', 'li', 'blockquote', 'code', 'pre',
    'a', 'span', 'img'
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'span': ['class', 'style'],
    'p': ['class', 'style'],
    'img': ['src', 'alt', 'width', 'height', 'style'],
}
ALLOWED_STYLES = ['color', 'background-color', 'font-size', 'text-align']

User = get_user_model()
def index(request):
    # Lấy các công việc đã được duyệt và có nhà tuyển dụng
    jobs = Job.objects.filter(is_approved=True, employer__isnull=False).order_by('-updated_at')
    
    # 1. Bắt dữ liệu tìm kiếm từ tất cả các bộ lọc
    q         = request.GET.get('q', '').strip()
    location  = request.GET.get('location', '').strip()
    job_type  = request.GET.get('job_type', '').strip()
    experience = request.GET.get('experience', '').strip()
    salary = request.GET.get('salary', '').strip()
    
    # 2. Chuẩn hóa dữ liệu (Normalization) & Áp dụng bộ lọc
    # Mapping các từ khóa phổ thông sang giá trị chuẩn trong DB (Keys)
    mapping = {
        'junior': '1_3',
        'senior': 'over_5',
        'fresher': '0_1',
        'không yêu cầu': 'none',
        'không yêu cầu kn': 'none',
        'không yêu cầu kinh nghiệm': 'none',
        'không kinh nghiệm': 'none',
        'ko yêu cầu': 'none',
        'ko kn': 'none',
        '0 năm': 'none',
        '1 năm': '1_3',
        '2 năm': '1_3',
        '3 năm': '1_3',
        '4 năm': '3_5',
        '5 năm': '3_5',
        '6 năm': 'over_5',
    }

    if q:
        processed_q = q.lower()
        # 2. Chuẩn hóa theo cụm từ (Normalization)
        # Sắp xếp các key theo chiều dài giảm dần để ưu tiên khớp cụm từ dài trước
        sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in processed_q:
                processed_q = processed_q.replace(key, mapping[key])

        # 3. Tách từ và tìm kiếm (Word Splitting + AND logic)
        words = processed_q.split()
        q_obj = Q()
        for word in words:
            word_q = (
                Q(title__icontains=word) |
                Q(employer__company_name__icontains=word) |
                Q(requirements__icontains=word) |
                Q(experience__icontains=word) |
                Q(job_type__icontains=word) |
                Q(description__icontains=word)
            )
            q_obj &= word_q
        
        jobs = jobs.filter(q_obj)
    if location:
        jobs = jobs.filter(location__icontains=location)
    # job_type và experience lọc theo các trường chuyên biệt (dùng icontains để linh hoạt hơn với dữ liệu cũ)
    if job_type:
        jobs = jobs.filter(job_type__icontains=job_type)
    if experience:
        jobs = jobs.filter(experience__icontains=experience)
        
    # 3. Lọc theo mức lương
    if salary == '0_10':
        jobs = jobs.filter(salary_max__lte=10)
    elif salary == '10_20':
        jobs = jobs.filter(salary_min__gte=10, salary_max__lte=20)
    elif salary == '20_50':
        jobs = jobs.filter(salary_min__gte=20, salary_max__lte=50)
    elif salary == '50_plus':
        jobs = jobs.filter(salary_min__gte=50)
        
    # 4. Phân trang
    paginator = Paginator(jobs, 9)  # 9 jobs / trang (3x3 grid)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Lấy danh sách ID các việc làm đã lưu và đã ứng tuyển nếu là ứng viên
    saved_job_ids = []
    applied_job_ids = []
    if request.user.is_authenticated and request.user.is_candidate:
        saved_job_ids = SavedJob.objects.filter(user=request.user).values_list('job_id', flat=True)
        applied_job_ids = Application.objects.filter(candidate=request.user).values_list('job_id', flat=True)

    context = {
        'jobs': page_obj,      
        'page_obj': page_obj,
        'saved_job_ids': saved_job_ids,
        'applied_job_ids': applied_job_ids,
        # Giữ lại giá trị filter để hiển thị lại trên form
        'q': q,
        'selected_location': location,
        'selected_job_type': job_type,
        'selected_experience': experience,
        'selected_salary': salary,
    }
    return render(request, 'index.html', context)
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        fullname = request.POST.get('fullname')
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone')
        password = request.POST.get('password1')
        password_confirm = request.POST.get('password2')
        user_type = request.POST.get('user_type')
        company_name = request.POST.get('company_name')

        if not email:
            messages.error(request, 'Email không được để trống.')
            return render(request, 'accounts/register.html', request.POST)

        if password != password_confirm:
            messages.error(request, 'Mật khẩu xác nhận không khớp.')
            return render(request, 'accounts/register.html', request.POST)

        if User.objects.filter(Q(email=email) | Q(username=email)).exists():
            messages.error(request, 'Email hoặc Tên đăng nhập này đã được khởi tạo trên hệ thống. Vui lòng chuyển sang trang Đăng nhập.')
            return render(request, 'accounts/register.html', request.POST)
            
        # Dùng luôn email làm cột username (để đăng nhập)
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=fullname,
        )
        user.phone_number = phone
        
        if user_type == 'ntd':
            user.is_employer = True
            user.company_name = company_name
        else:
            user.is_candidate = True
            
        user.save()
        
        # Đăng ký xong thì auto login và chuyển hướng qua Router trung tâm
        auth_login(request, user)
        return redirect('dashboard')

    return render(request, 'accounts/register.html')

def login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        user_name = request.POST.get('username', '').strip().lower()
        pass_word = request.POST.get('password')
        user = authenticate(request, username=user_name, password=pass_word)
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không chính xác.')
            # Trả về template với username để user ko phải gõ lại
            return render(request, 'accounts/login.html', {'username': user_name})
            
    return render(request, 'accounts/login.html')

def logout_view(request):
    auth_logout(request)
    return redirect('home')

# ========== DASHBOARD ỨNG VIÊN ==========
@login_required
def candidate_dashboard(request):
    """Dashboard cho ứng viên: hiển thị danh sách đơn ứng tuyển và trạng thái."""
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    
    applications = Application.objects.filter(
        candidate=request.user
    ).select_related('job', 'job__employer', 'interview').order_by('-applied_at')

    total_applications = applications.count()
    accepted_count = applications.filter(status='Accepted').count()
    pending_count = applications.filter(status='Pending').count()
    interview_count = applications.filter(status='Interview').count()

    upcoming_interviews = InterviewInvitation.objects.filter(
        application__candidate=request.user,
        scheduled_at__gte=timezone.now(),
    ).select_related(
        'application',
        'application__job',
        'application__job__employer',
    ).order_by('scheduled_at')

    # Lấy thêm danh sách việc làm đã lưu
    saved_jobs = SavedJob.objects.filter(user=request.user).select_related('job', 'job__employer').order_by('-saved_at')

    context = {
        'applications': applications,
        'total_applications': total_applications,
        'accepted_count': accepted_count,
        'pending_count': pending_count,
        'interview_count': interview_count,
        'upcoming_interviews': upcoming_interviews,
        'saved_jobs': saved_jobs,
    }
    return render(request, 'dashboard/candidate_dashboard.html', context)

# ========== DASHBOARD NHÀ TUYỂN DỤNG ==========
@login_required
def employer_dashboard(request):
    """Dashboard cho NTD: hiển thị danh sách tin tuyển dụng và số CV nhận được."""
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    
    # NTD chỉ thấy bài của mình
    jobs = Job.objects.filter(
        employer=request.user
    ).annotate(
        app_count=Count('apps')
    ).order_by('-created_at')

    total_jobs = jobs.count()
    approved_jobs = jobs.filter(is_approved=True).count()
    pending_jobs = jobs.filter(is_approved=False).count()
    total_cvs = Application.objects.filter(job__employer=request.user).count()

    context = {
        'jobs': jobs,
        'total_jobs': total_jobs,
        'approved_jobs': approved_jobs,
        'pending_jobs': pending_jobs,
        'total_cvs': total_cvs,
    }
    return render(request, 'dashboard/employer_dashboard.html', context)

# ========== DASHBOARD ADMIN (Chỉ Superuser) ==========
@login_required
def admin_dashboard(request):
    """Dashboard cho Admin: quản lý toàn bộ hệ thống."""
    if not request.user.is_superuser:
        return redirect('home')

    # Thống kê toàn cục
    jobs = Job.objects.all().annotate(app_count=Count('apps')).order_by('-created_at')
    total_jobs = jobs.count()
    approved_jobs = jobs.filter(is_approved=True).count()
    pending_jobs = jobs.filter(is_approved=False).count()
    
    total_companies = User.objects.filter(is_employer=True).count()
    total_candidates = User.objects.filter(is_candidate=True).count()
    total_cvs = Application.objects.count()

    # Lấy danh sách để quản lý
    companies = User.objects.filter(is_employer=True).order_by('-date_joined')
    candidates = User.objects.filter(is_candidate=True).order_by('-date_joined')

    context = {
        'jobs': jobs,
        'total_jobs': total_jobs,
        'approved_jobs': approved_jobs,
        'pending_jobs': pending_jobs,
        'total_companies': total_companies,
        'total_candidates': total_candidates,
        'total_cvs': total_cvs,
        'companies': companies,
        'candidates': candidates,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
def delete_user(request, user_id):
    """Admin xóa người dùng khỏi hệ thống."""
    if not request.user.is_superuser:
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")
        return redirect('home')
        
    user_to_delete = get_object_or_404(User, id=user_id)
    
    if user_to_delete == request.user:
        messages.warning(request, "Bạn không thể tự xóa tài khoản của chính mình!")
        return redirect('admin_dashboard')
        
    username = user_to_delete.username
    user_to_delete.delete()
    
    messages.success(request, f'Đã xóa người dùng "{username}" và toàn bộ dữ liệu liên quan thành công.')
    return redirect('admin_dashboard')

# ========== ROUTER DASHBOARD ==========
@login_required
def dashboard_router(request):
    """Router trung tâm: tự động kiểm tra role và điều hướng đến Dashboard tương ứng."""
    if request.user.is_candidate:
        return redirect('candidate_dashboard')
    elif request.user.is_superuser:
        return redirect('admin_dashboard')
    elif request.user.is_employer:
        return redirect('employer_dashboard')
    return redirect('home')

# ========== DANH SÁCH ỨNG VIÊN (Trang con) ==========
@login_required
def applicant_list(request, job_id):
    """Trang con: hiển thị danh sách ứng viên đã nộp CV cho một tin tuyển dụng cụ thể."""
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, employer=request.user)

    applications = Application.objects.filter(
        job=job
    ).select_related('candidate', 'online_cv', 'match', 'interview')

    # Lazy compute matching for online CVs that don't have a match record yet
    for app in applications:
        if app.online_cv and not hasattr(app, 'match'):
            app.match = compute_match(app, skip_ai=True)
    
    # Sorting logic
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'match':
        applications = applications.order_by('-match__score', '-applied_at')
    elif sort_by == 'oldest':
        applications = applications.order_by('applied_at')
    else: # newest
        applications = applications.order_by('-applied_at')

    # Filter by score if requested
    min_score = request.GET.get('min_score')
    if min_score and min_score.isdigit():
        applications = applications.filter(match__score__gte=int(min_score))

    context = {
        'job': job,
        'applications': applications,
        'current_sort': sort_by,
        'current_min_score': min_score,
    }
    return render(request, 'dashboard/applicant_list.html', context)

@login_required
@require_POST
def recalculate_match(request, app_id):
    """Tính lại điểm matching cho một application cụ thể (AJAX)."""
    if request.user.is_superuser:
        application = get_object_or_404(Application, id=app_id)
    else:
        application = get_object_or_404(Application, id=app_id, job__employer=request.user)
    
    if not application.online_cv:
        return JsonResponse({'status': 'error', 'message': 'Ứng viên nộp CV file, không hỗ trợ AI Matching.'}, status=400)
    
    match_obj = compute_match(application, skip_ai=False)
    
    return JsonResponse({
        'status': 'success',
        'score': match_obj.score,
        'skill_score': match_obj.skill_score,
        'exp_score': match_obj.exp_score,
        'desc_score': match_obj.desc_score,
        'project_score': match_obj.project_score,
        'bonus_score': match_obj.bonus_score,
        'summary': match_obj.summary,
        'matched_skills': match_obj.matched_skills,
        'missing_skills': match_obj.missing_skills,
        'interview_questions': match_obj.interview_questions,
    })

# ========== CẬP NHẬT TRẠNG THÁI ỨNG VIÊN ==========
@login_required
@require_POST
def schedule_interview(request, app_id):
    """Employer/Admin tạo hoặc cập nhật lịch phỏng vấn cho một application."""
    if request.user.is_superuser:
        application = get_object_or_404(Application, id=app_id)
    else:
        application = get_object_or_404(Application, id=app_id, job__employer=request.user)

    scheduled_at_raw = request.POST.get('scheduled_at', '').strip()
    mode = request.POST.get('mode', 'online')
    location = request.POST.get('location', '').strip()
    note = request.POST.get('note', '').strip()

    scheduled_at = parse_datetime(scheduled_at_raw)
    if not scheduled_at:
        messages.error(request, "Thời gian phỏng vấn không hợp lệ.")
        return redirect('applicant_list', job_id=application.job.id)

    if timezone.is_naive(scheduled_at):
        scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())

    if scheduled_at < timezone.now():
        messages.error(request, "Thời gian phỏng vấn phải ở tương lai.")
        return redirect('applicant_list', job_id=application.job.id)

    if mode not in dict(InterviewInvitation.MODE_CHOICES):
        messages.error(request, "Hình thức phỏng vấn không hợp lệ.")
        return redirect('applicant_list', job_id=application.job.id)

    if not location:
        messages.error(request, "Vui lòng nhập link hoặc địa điểm phỏng vấn.")
        return redirect('applicant_list', job_id=application.job.id)

    InterviewInvitation.objects.update_or_create(
        application=application,
        defaults={
            'scheduled_at': scheduled_at,
            'mode': mode,
            'location': location,
            'note': note,
            'created_by': request.user,
        },
    )
    application.status = 'Interview'
    application.save(update_fields=['status'])

    messages.success(request, f"Đã gửi lịch phỏng vấn cho {application.candidate.email}.")
    return redirect('applicant_list', job_id=application.job.id)

@login_required
def update_application_status(request, app_id):
    """NTD đổi trạng thái đơn ứng tuyển (Chấp nhận / Từ chối)."""
    if request.method == 'POST':
        if request.user.is_superuser:
            application = get_object_or_404(Application, id=app_id)
        else:
            application = get_object_or_404(Application, id=app_id, job__employer=request.user)
        new_status = request.POST.get('status')
        if new_status in ['Accepted', 'Rejected', 'Viewed']:
            application.status = new_status
            application.save()
        return redirect('applicant_list', job_id=application.job.id)
    return redirect('employer_dashboard')

# ========== DANH SÁCH CÔNG TY ==========
def company_list(request):
    """Hiển thị danh sách các nhà tuyển dụng."""
    # Lấy các user là employer và đếm số lượng tin tuyển dụng (có is_approved=True)
    companies = User.objects.filter(is_employer=True).annotate(
        job_count=Count('jobs', filter=Q(jobs__is_approved=True))
    ).order_by('-date_joined')
    
    return render(request, 'company_list.html', {'companies': companies})

# ========== CHI TIẾT CÔNG TY ==========
def company_detail(request, company_id):
    """Trang chi tiết hồ sơ công ty và danh sách việc làm đang tuyển."""
    company = get_object_or_404(User, id=company_id, is_employer=True)
    # Chỉ lấy các job đã được admin duyệt
    jobs = company.jobs.filter(is_approved=True).order_by('-created_at')
    
    applied_job_ids = []
    if request.user.is_authenticated and request.user.is_candidate:
        applied_job_ids = Application.objects.filter(candidate=request.user).values_list('job_id', flat=True)
        
    context = {
        'company': company,
        'jobs': jobs,
        'applied_job_ids': applied_job_ids,
    }
    return render(request, 'company_detail.html', context)

# ========== QUẢN LÝ HỒ SƠ ỨNG VIÊN ==========
@login_required
def profile_view(request):
    """Trang quản lý hồ sơ ứng viên (Cập nhật Avatar, Điện thoại, Kỹ năng, CV gốc)."""
    user = request.user
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Hồ sơ của bạn đã được cập nhật thành công!")
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = UserProfileForm(instance=user)

    # Dùng user_db để hiển thị Avatar an toàn (tránh vỡ ảnh khi form bị lỗi và user.avatar chứa file rác trên RAM)
    user_db = User.objects.get(pk=user.pk)

    return render(request, 'accounts/profile.html', {'user': user, 'user_db': user_db, 'form': form})

# ========== ỨNG TUYỂN CÔNG VIỆC ==========
@login_required
def apply_job(request, job_id):
    """Tính năng nộp đơn: Hỗ trợ dùng CV gốc hoặc tải CV mới lên."""
    if not request.user.is_candidate:
        messages.error(request, "Chỉ tài khoản Ứng viên mới có thể nộp đơn tuyển dụng.")
        return redirect('home')
        
    if request.method == 'POST':
        job = get_object_or_404(Job, id=job_id, is_approved=True)

        if Application.objects.filter(job=job, candidate=request.user).exists():
            messages.info(request, "Bạn đã ứng tuyển công việc này rồi!")
            return redirect('home')

        cv_option = request.POST.get('cv_option')
        application = Application(job=job, candidate=request.user)

        if cv_option == 'default':
            if not request.user.default_cv:
                messages.warning(request, "Bạn chưa có CV Gốc! Vui lòng tải lên CV gốc trong Hồ sơ hoặc chọn tải CV mới.")
                return redirect('job_detail', job_id=job.id)
                
            # Nhân bản file vật lý
            file_ext = os.path.splitext(request.user.default_cv.name)[1]
            new_file_name = f"CV_{request.user.id}_{job.id}{file_ext}"
            application.cv_file.save(new_file_name, ContentFile(request.user.default_cv.read()), save=False)
            
        elif cv_option == 'new':
            new_cv = request.FILES.get('new_cv')
            if not new_cv:
                messages.error(request, "Bạn chưa chọn file CV mới để tải lên.")
                return redirect('job_detail', job_id=job.id)
                
            # Validation định dạng và dung lượng
            if new_cv.size > 5242880: # 5MB
                messages.error(request, "Kích thước CV tối đa là 5MB.")
                return redirect('job_detail', job_id=job.id)
                
            ext = os.path.splitext(new_cv.name)[1].lower()
            if ext not in ['.pdf', '.docx']:
                messages.error(request, "Chỉ chấp nhận file định dạng PDF hoặc DOCX.")
                return redirect('job_detail', job_id=job.id)
                
            new_file_name = f"CV_{request.user.id}_{job.id}{ext}"
            new_cv.name = new_file_name
            application.cv_file = new_cv
            
        elif cv_option == 'online':
            online_cv_id = request.POST.get('online_cv_id')
            if not online_cv_id:
                messages.error(request, "Vui lòng chọn một CV trên hệ thống.")
                return redirect('job_detail', job_id=job.id)
            cv_obj = get_object_or_404(CV, id=online_cv_id, user=request.user)
            application.online_cv = cv_obj
            
            
        else:
            messages.error(request, "Lựa chọn không hợp lệ.")
            return redirect('job_detail', job_id=job.id)

        application.save()
        messages.success(request, f"Nộp đơn thành công vị trí: {job.title}")
        return redirect('candidate_dashboard')

    return redirect('home')

# ========== ĐĂNG TIN TUYỂN DỤNG MỚI (Chỉ NTD) ==========
@login_required
def create_job(request):
    """NTD tạo tin tuyển dụng mới. Tin sẽ ở trạng thái chờ duyệt (is_approved=False)."""
    if not request.user.is_employer:
        messages.error(request, "Chỉ Nhà tuyển dụng mới có thể đăng tin.")
        return redirect('home')

    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.employer = request.user
            job.is_approved = False
            
            # Làm sạch dữ liệu description (XSS Protection)
            raw_description = form.cleaned_data.get('description', '')
            # Khởi tạo bộ lọc CSS (cho phép đổi màu chữ, căn lề...)
            css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)
            
            job.description = bleach.clean(
                raw_description,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                css_sanitizer=css_sanitizer,
                strip=True
            )
            
            job.save()
            messages.success(request, f'Đăng tin "{job.title}" thành công! Tin đang chờ Admin duyệt.')
            return redirect('employer_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = JobForm()

    return render(request, 'jobs/create_job.html', {'form': form})

# ========== CHỈNH SỬA TIN TUYỂN DỤNG (Cả Admin và NTD) ==========
@login_required
def edit_job(request, job_id):
    """Admin hoặc NTD chỉnh sửa tin tuyển dụng."""
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, employer=request.user)

    if request.method == 'POST':
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            job = form.save(commit=False)
            job.is_approved = False  # Reset về chờ duyệt khi sửa

            # Làm sạch dữ liệu description (XSS Protection)
            raw_description = form.cleaned_data.get('description', '')
            # Khởi tạo bộ lọc CSS (cho phép đổi màu chữ, căn lề...)
            css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)
            
            job.description = bleach.clean(
                raw_description,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                css_sanitizer=css_sanitizer,
                strip=True
            )
            
            job.save()
            if request.user.is_superuser:
                messages.success(request, f'Admin cập nhật tin "{job.title}" thành công!')
                return redirect('admin_dashboard')
            else:
                messages.success(request, f'Cập nhật tin "{job.title}" thành công! Tin sẽ được Admin duyệt lại.')
                return redirect('employer_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = JobForm(instance=job)

    return render(request, 'jobs/edit_job.html', {'form': form, 'job': job})

# ========== XÓA TIN TUYỂN DỤNG (Cả Admin và NTD) ==========
@login_required
def delete_job(request, job_id):
    """Admin hoặc NTD xóa tin tuyển dụng."""
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, employer=request.user)

    if request.method == 'POST':
        title = job.title
        job.delete()
        messages.success(request, f'Đã xóa tin tuyển dụng "{title}" thành công.')
        if request.user.is_superuser:
            return redirect('admin_dashboard')
        return redirect('employer_dashboard')

    return render(request, 'jobs/delete_job.html', {'job': job})

# ========== CHI TIẾT CÔNG VIỆC (Công khai) ==========
def job_detail(request, job_id):
    """Trang chi tiết công việc. Hiện nút Apply nếu user là ứng viên."""
    job = get_object_or_404(Job, id=job_id)
    
    # Kiểm tra xem ứng viên đã apply chưa
    has_applied = False
    if request.user.is_authenticated and request.user.is_candidate:
        has_applied = Application.objects.filter(job=job, candidate=request.user).exists()

    # Kiểm tra xem đã lưu việc này chưa
    is_saved = False
    if request.user.is_authenticated and request.user.is_candidate:
        is_saved = SavedJob.objects.filter(user=request.user, job=job).exists()

    # Nhận gợi ý các công việc tương tự
    similar_jobs = get_similar_jobs(job)

    context = {
        'job': job,
        'similar_jobs': similar_jobs,
        'has_applied': has_applied,
        'is_saved': is_saved,
    }
    return render(request, 'jobs/job_detail.html', context)

# ========== DUYỆT TIN TUYỂN DỤNG (Chỉ Admin) ==========
@login_required
def toggle_job_status(request, job_id):
    """Admin bật/tắt trạng thái duyệt của một tin tuyển dụng."""
    if not request.user.is_superuser:
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")
        return redirect('home')
        
    job = get_object_or_404(Job, id=job_id)
    job.is_approved = not job.is_approved
    job.save()
    
    status_text = "Đã duyệt" if job.is_approved else "Đã hủy duyệt"
    messages.success(request, f'Đã cập nhật trạng thái tin "{job.title}" thành: {status_text}')
    return redirect('admin_dashboard')

# ========== LƯU VIỆC LÀM (Toggle Save) ==========
@login_required
def toggle_save_job(request, job_id):
    """Bật/tắt trạng thái lưu việc làm của ứng viên."""
    if not request.user.is_candidate:
        messages.error(request, "Chỉ tài khoản Ứng viên mới có thể lưu việc làm.")
        return redirect('home')

    job = get_object_or_404(Job, id=job_id)
    saved_item = SavedJob.objects.filter(user=request.user, job=job)

    if saved_item.exists():
        saved_item.delete()
        messages.info(request, f'Đã bỏ lưu: {job.title}')
    else:
        SavedJob.objects.create(user=request.user, job=job)
        messages.success(request, f'Đã lưu thành công: {job.title}')

    # Quay lại trang trước đó hoặc trang chủ
    return redirect(request.META.get('HTTP_REFERER', 'home'))

# ========== XÓA CV GỐC (API AJAX) ==========
@login_required
@require_POST
def delete_cv(request):
    """API độc lập cho phép xóa CV thông qua AJAX."""
    if not request.user.is_candidate:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        
    if request.user.default_cv:
        # Xóa file vật lý và clear trường default_cv
        request.user.default_cv.delete(save=True)
        return JsonResponse({'status': 'success', 'message': 'CV đã được xóa.'})
        
    return JsonResponse({'status': 'error', 'message': 'Không tìm thấy CV nào để xóa.'}, status=400)

# ========== TẠO CV GIỐNG TOPCV ==========
import json

@login_required
def cv_list(request):
    """Danh sách CV đã tạo trên hệ thống của ứng viên"""
    if not request.user.is_candidate:
        messages.error(request, "Chỉ Ứng viên mới có thể quản lý CV trực tuyến.")
        return redirect('home')
        
    cvs = CV.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'cv/cv_list.html', {'cvs': cvs})

@login_required
def cv_builder(request, cv_id=None):
    """Giao diện tạo và chỉnh sửa CV"""
    if not request.user.is_candidate:
        messages.error(request, "Chỉ Ứng viên mới có thể tạo CV trực tuyến.")
        return redirect('home')
        
    cv = None
    if cv_id:
        cv = get_object_or_404(CV, id=cv_id, user=request.user)
        
    if request.method == 'POST':
        if not cv:
            cv = CV(user=request.user)
            
        cv.title = request.POST.get('title', 'CV Không Tên')
        cv.full_name = request.POST.get('full_name', '')
        cv.email = request.POST.get('email', '')
        cv.phone = request.POST.get('phone', '')
        cv.address = request.POST.get('address', '')
        cv.target_major = request.POST.get('target_major', '')
        cv.objective = request.POST.get('objective', '')
        cv.github = request.POST.get('github', '')
        cv.linkedin = request.POST.get('linkedin', '')
        
        # Xử lý avatar
        if 'avatar' in request.FILES:
            cv.avatar = request.FILES['avatar']
            
        # Parse các trường JSON
        try:
            cv.education = json.loads(request.POST.get('education', '[]'))
            cv.experience = json.loads(request.POST.get('experience', '[]'))
            cv.skills = json.loads(request.POST.get('skills', '[]'))
            cv.projects = json.loads(request.POST.get('projects', '[]'))
            cv.certifications = json.loads(request.POST.get('certifications', '[]'))
        except json.JSONDecodeError:
            pass
            
        cv.save()
        messages.success(request, "Lưu CV thành công!")
        
        # Xử lý ajax save (lưu ngầm)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'cv_id': cv.id})
            
        return redirect('cv_builder_edit', cv_id=cv.id)

    # Nếu tạo mới, điền sẵn thông tin từ User Profile
    if not cv:
        initial_data = {
            'full_name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'phone': request.user.phone_number or '',
        }
    else:
        initial_data = None

    return render(request, 'cv/cv_builder.html', {'cv': cv, 'initial_data': initial_data})

@login_required
def cv_delete(request, cv_id):
    """Xóa CV"""
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    if request.method == 'POST':
        cv.delete()
        messages.success(request, "Đã xóa CV thành công!")
    return redirect('cv_list')

@login_required
def cv_view(request, cv_id):
    """Xem CV / In ra PDF"""
    # Nếu là ứng viên, có thể xem CV của chính mình
    # Nếu là NTD, có thể xem CV của người đã nộp vào công ty mình
    cv = get_object_or_404(CV, id=cv_id)
    
    # Kiểm tra quyền (đơn giản hoá, ứng viên xem của ứng viên, admin xem được hết, NTD xem nếu có application)
    if request.user.is_superuser or request.user == cv.user:
        pass
    elif request.user.is_employer:
        if not Application.objects.filter(online_cv=cv, job__employer=request.user).exists():
            messages.error(request, "Bạn không có quyền xem CV này.")
            return redirect('home')
    else:
        messages.error(request, "Bạn không có quyền xem CV này.")
        return redirect('home')
        
    return render(request, f'cv/templates/{cv.template_name}.html', {'cv': cv})


# =============================================================================
# AI: TẠO GỢI Ý MỤC TIÊU NGHỀ NGHIỆP (GEMINI API)
# AI: TRỢ LÝ AI ĐA NĂNG
# =============================================================================
@login_required
@require_POST
def ai_assistant(request):
    """
    Trợ lý AI đa năng: Objective, Experience, Skills.
    """
    now = time.time()
    call_history = request.session.get('ai_call_history', [])
    call_history = [t for t in call_history if now - t < 60]
    
    if len(call_history) >= 10: # Tăng hạn mức lên 10 lần/phút cho trợ lý đa năng
        return JsonResponse({'status': 'error', 'message': 'Bạn thao tác quá nhanh. Vui lòng chờ 1 phút.'}, status=429)
    
    call_history.append(now)
    request.session['ai_call_history'] = call_history
    
    if not GEMINI_AVAILABLE:
        return JsonResponse({'status': 'error', 'message': 'AI SDK not installed.'}, status=503)
    
    from django.conf import settings
    api_key = settings.GEMINI_API_KEY
    
    try:
        data = json.loads(request.body)
        task_type = data.get('task_type', 'objective') # objective, experience, skills
        position = data.get('position', '').strip()
        context = data.get('context', '').strip() # context cho exp hoặc skills
        
        if not position:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập Vị trí ứng tuyển.'}, status=400)

        # Xây dựng Prompt dựa trên Task
        if task_type == 'objective':
            prompt = f'Tạo 3 đoạn mục tiêu nghề nghiệp ấn tượng cho vị trí "{position}" với các kỹ năng "{context}". Mỗi đoạn 2-3 câu, viết ngôi thứ nhất. Trả về JSON: {{"suggestions": ["...", "...", "..."]}}'
        
        elif task_type == 'experience':
            prompt = f'Viết 4-5 gạch đầu dòng mô tả công việc chuyên nghiệp cho vị trí "{context}" (tại công ty {position}). Sử dụng các động từ mạnh, tập trung vào kết quả. Trả về JSON: {{"suggestions": ["...", "...", "..."]}}'
            
        elif task_type == 'skills':
            prompt = f'Gợi ý 8 kỹ năng chuyên môn quan trọng nhất cho vị trí "{position}". Trả về JSON: {{"suggestions": ["Skill 1", "Skill 2", ...]}}'
        
        else:
            return JsonResponse({'status': 'error', 'message': 'Task không hợp lệ.'}, status=400)

        client = google_genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'temperature': 0.8,
            }
        )
        
        raw_text = response.text.strip()
        # Removed print - Windows charmap can't encode Vietnamese
        
        # --- KIỂM DUYỆT & BÓC TÁCH JSON ---
        result = json.loads(raw_text)
        suggestions = result.get('suggestions', [])
        
        if not isinstance(suggestions, list) or len(suggestions) == 0:
            raise ValueError('AI trả về định dạng không đúng')
        
        return JsonResponse({'status': 'success', 'suggestions': suggestions[:3]})
    
    except json.JSONDecodeError as e:
        return JsonResponse({
            'status': 'error',
            'message': 'AI trả về định dạng không đúng. Vui lòng thử lại.'
        }, status=500)
    except Exception as e:
        err_msg = str(e).encode('ascii', errors='replace').decode('ascii')
        error_str = err_msg.lower()
        if 'quota' in error_str or 'rate' in error_str or '429' in error_str:
            message = 'Hệ thống AI đang bận (Hết lượt dùng miễn phí). Vui lòng thử lại sau 1 phút.'
        elif 'api_key' in error_str or 'invalid' in error_str:
            message = 'Cấu hình API Key không hợp lệ. Vui lòng kiểm tra file .env.'
        elif 'charmap' in error_str or 'encode' in error_str or 'codec' in error_str:
            message = 'Có lỗi encoding nội bộ. Vui lòng thử lại.'
        else:
            message = f'Lỗi AI: {err_msg[:100]}'
        return JsonResponse({'status': 'error', 'message': message}, status=500)
