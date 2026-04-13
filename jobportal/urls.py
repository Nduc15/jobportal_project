"""
URL configuration for jobportal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views  # Gọi hàm views từ app core ra

urlpatterns = [
    path('admin/user/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('admin/', admin.site.urls),
    path('', views.index, name='home'),  # Đường dẫn rỗng '' đại diện cho Trang chủ
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Thẻ Dashboard chung chung (Sử dụng router)
    path('dashboard/', views.dashboard_router, name='dashboard'),

    # Hồ sơ và CV
    path('profile/', views.profile_view, name='profile'),
    
    # Danh sách Công ty
    path('companies/', views.company_list, name='company_list'),
    path('company/<int:company_id>/', views.company_detail, name='company_detail'),

    # Ứng tuyển nhanh môt chạm (1-Click Apply)
    path('apply/<int:job_id>/', views.apply_job, name='apply_job'),

    # Dashboard Ứng viên
    path('dashboard/candidate/', views.candidate_dashboard, name='candidate_dashboard'),

    # Dashboard Nhà tuyển dụng
    path('dashboard/employer/', views.employer_dashboard, name='employer_dashboard'),

    # Dashboard Admin
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),

    # Danh sách ứng viên đã nộp CV cho 1 tin tuyển dụng
    path('dashboard/employer/job/<int:job_id>/applicants/', views.applicant_list, name='applicant_list'),

    # Cập nhật trạng thái đơn ứng tuyển (Chấp nhận / Từ chối)
    path('dashboard/employer/application/<int:app_id>/update/', views.update_application_status, name='update_application_status'),

    # Quản lý tin tuyển dụng (NTD)
    path('jobs/create/', views.create_job, name='create_job'),
    path('jobs/<int:job_id>/edit/', views.edit_job, name='edit_job'),
    path('jobs/<int:job_id>/delete/', views.delete_job, name='delete_job'),

    # Chi tiết công việc (Công khai)
    path('jobs/<int:job_id>/', views.job_detail, name='job_detail'),

    # Thao tác Admin
    path('jobs/<int:job_id>/toggle-status/', views.toggle_job_status, name='toggle_job_status'),

    # Lưu việc làm yêu thích
    path('jobs/<int:job_id>/save/', views.toggle_save_job, name='toggle_save_job'),
]

# Serve media files trong môi trường phát triển (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
