from django.shortcuts import render, get_object_or_404, redirect
from .forms import UserProfileForm, JobForm
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from .models import Job, Application, SavedJob
import bleach
from bleach.css_sanitizer import CSSSanitizer

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
    # Mapping các từ khóa phổ thông sang giá trị chuẩn trong DB
    mapping = {
        'junior': '1 - 3 năm',
        'senior': 'Trên 3 năm',
        'fresher': 'Thực tập / Fresher',
        'không yêu cầu kn': 'Không yêu cầu',
        'không yêu cầu kinh nghiệm': 'Không yêu cầu',
        'không kinh nghiệm': 'Không yêu cầu',
        '0 năm': 'Không yêu cầu',
        '1 năm': '1 - 3 năm',
        '2 năm': '1 - 3 năm',
        '3 năm': '1 - 3 năm',
        '4 năm': 'Trên 3 năm',
        '5 năm': 'Trên 3 năm',
    }

    if q:
        search_q = q.lower()
        # Nếu người dùng gõ từ khóa có trong mapping, dùng giá trị chuẩn để tìm kiếm
        if search_q in mapping:
            normalized_q = mapping[search_q]
        else:
            normalized_q = q

        jobs = jobs.filter(
            Q(title__icontains=normalized_q) | 
            Q(description__icontains=normalized_q) |
            Q(experience__icontains=normalized_q) |
            Q(job_type__icontains=normalized_q) |
            Q(employer__company_name__icontains=normalized_q)
        )
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
    
    # Lấy danh sách ID các việc làm đã lưu nếu là ứng viên
    saved_job_ids = []
    if request.user.is_authenticated and request.user.is_candidate:
        saved_job_ids = SavedJob.objects.filter(user=request.user).values_list('job_id', flat=True)

    context = {
        'jobs': page_obj,      
        'page_obj': page_obj,
        'saved_job_ids': saved_job_ids,
        # Giữ lại giá trị filter để hiển thị lại trên form
        'q': q,
        'selected_location': location,
        'selected_job_type': job_type,
        'selected_experience': experience,
        'selected_salary': salary,
    }
    return render(request, 'index.html', context)
def register(request):
    if request.method == 'POST':
        fullname = request.POST.get('fullname')
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone')
        password = request.POST.get('password1')
        user_type = request.POST.get('user_type')
        company_name = request.POST.get('company_name')

        if not email:
            messages.error(request, 'Email không được để trống.')
            return redirect('register')

        if User.objects.filter(Q(email=email) | Q(username=email)).exists():
            messages.error(request, 'Email hoặc Tên đăng nhập này đã được khởi tạo trên hệ thống. Vui lòng chuyển sang trang Đăng nhập.')
            return redirect('register')
            
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
        
        # Đăng ký xong thì auto login và chuyển hướng
        auth_login(request, user)
        if user.is_candidate:
            return redirect('candidate_dashboard')
        else:
            return redirect('employer_dashboard')

    return render(request, 'accounts/register.html')

def login(request):
    if request.method == 'POST':
        user_name = request.POST.get('username')
        pass_word = request.POST.get('password')
        user = authenticate(request, username=user_name, password=pass_word)
        if user is not None:
            auth_login(request, user)
            if user.is_candidate:
                return redirect('candidate_dashboard')
            elif user.is_employer or user.is_superuser:
                return redirect('employer_dashboard')
            else:
                return redirect('home')
        else:
            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không chính xác.')
            return redirect('login')
            
    return render(request, 'accounts/login.html')

def logout_view(request):
    auth_logout(request)
    return redirect('home')

# ========== DASHBOARD ỨNG VIÊN ==========
@login_required
def candidate_dashboard(request):
    """Dashboard cho ứng viên: hiển thị danh sách đơn ứng tuyển và trạng thái."""
    applications = Application.objects.filter(
        candidate=request.user
    ).select_related('job', 'job__employer').order_by('-applied_at')

    total_applications = applications.count()
    accepted_count = applications.filter(status='Accepted').count()
    pending_count = applications.filter(status='Pending').count()

    # Lấy thêm danh sách việc làm đã lưu
    saved_jobs = SavedJob.objects.filter(user=request.user).select_related('job', 'job__employer').order_by('-saved_at')

    context = {
        'applications': applications,
        'total_applications': total_applications,
        'accepted_count': accepted_count,
        'pending_count': pending_count,
        'saved_jobs': saved_jobs,
    }
    return render(request, 'dashboard/candidate_dashboard.html', context)

# ========== DASHBOARD NHÀ TUYỂN DỤNG ==========
@login_required
def employer_dashboard(request):
    """Dashboard cho NTD: hiển thị danh sách tin tuyển dụng và số CV nhận được."""
    if request.user.is_superuser:
        # Admin thấy toàn bộ tin để quản lý
        jobs = Job.objects.all().annotate(
            app_count=Count('apps')
        ).order_by('-created_at')
    else:
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

# ========== ROUTER DASHBOARD ==========
@login_required
def dashboard_router(request):
    """Router trung tâm: tự động kiểm tra role và điều hướng đến Dashboard tương ứng."""
    if request.user.is_candidate:
        return redirect('candidate_dashboard')
    elif request.user.is_employer or request.user.is_superuser:
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
    ).select_related('candidate').order_by('-applied_at')

    context = {
        'job': job,
        'applications': applications,
    }
    return render(request, 'dashboard/applicant_list.html', context)

# ========== CẬP NHẬT TRẠNG THÁI ỨNG VIÊN ==========
@login_required
def update_application_status(request, app_id):
    """NTD đổi trạng thái đơn ứng tuyển (Chấp nhận / Từ chối)."""
    if request.method == 'POST':
        if request.user.is_superuser:
            application = get_object_or_404(Application, id=app_id)
        else:
            application = get_object_or_404(Application, id=app_id, job__employer=request.user)
        new_status = request.POST.get('status')
        if new_status in ['Accepted', 'Rejected']:
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
    
    context = {
        'company': company,
        'jobs': jobs,
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

# ========== ỨNG TUYỂN CÔNG VIỆC (1-Click Apply) ==========
@login_required
def apply_job(request, job_id):
    """Tính năng nộp đơn nhanh: Lấy CV gốc của Ứng viên gửi cho NTD."""
    if not request.user.is_candidate:
        messages.error(request, "Chỉ tính khoản Ứng viên mới có thể nộp đơn tuyển dụng.")
        return redirect('home')
        
    if request.method == 'POST':
        job = get_object_or_404(Job, id=job_id, is_approved=True)

        if not request.user.default_cv:
            messages.warning(request, "Bạn chưa có CV Gốc! Hãy tải lên CV mặc định trước khi ứng tuyển.")
            return redirect('profile')

        if Application.objects.filter(job=job, candidate=request.user).exists():
            messages.info(request, "Bạn đã ứng tuyển công việc này rồi!")
            return redirect('home')

        # Nộp đơn bằng default_cv
        application = Application(job=job, candidate=request.user)
        application.cv_file.name = request.user.default_cv.name # Dùng chung file trên filesystem (tránh duplicated upload)
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

# ========== CHỈNH SỬA TIN TUYỂN DỤNG (Chỉ NTD sở hữu tin) ==========
@login_required
def edit_job(request, job_id):
    """NTD chỉnh sửa tin tuyển dụng do mình đăng."""
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
            messages.success(request, f'Cập nhật tin "{job.title}" thành công! Tin sẽ được Admin duyệt lại.')
            return redirect('employer_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = JobForm(instance=job)

    return render(request, 'jobs/edit_job.html', {'form': form, 'job': job})

# ========== XÓA TIN TUYỂN DỤNG (Chỉ NTD sở hữu tin) ==========
@login_required
def delete_job(request, job_id):
    """NTD xóa tin tuyển dụng do mình đăng."""
    job = get_object_or_404(Job, id=job_id, employer=request.user)

    if request.method == 'POST':
        title = job.title
        job.delete()
        messages.success(request, f'Đã xóa tin tuyển dụng "{title}" thành công.')
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

    context = {
        'job': job,
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
    return redirect('employer_dashboard')

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
