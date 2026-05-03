from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.db.models import Case, When
from .models import Job

def get_similar_jobs(current_job, top_n=5):
    """
    Nhận đầu vào là 1 object công việc hiện tại (Job) 
    và trả về Danh sách các công việc tương tự (QuerySet).
    """
    # Lấy tất cả các Job đang "Active"
    active_jobs = Job.objects.filter(is_approved=True, employer__isnull=False)
    
    # Góc (Corner Case): Database rỗng hoặc quá ít bài đăng
    jobs_list = list(active_jobs)
    if len(jobs_list) <= 1:
        return Job.objects.none()
        
    job_texts = []
    job_ids = []
    current_job_index = -1
    
    for idx, job in enumerate(jobs_list):
        if job.id == current_job.id:
            current_job_index = idx
            
        job_ids.append(job.id)
        # Nối chuỗi các trường quan trọng (Tiêu đề + Kỹ năng)
        title = job.title if job.title else ""
        skills = job.requirements if job.requirements else ""
        # Lỗi Unicode tiếng Việt: Python 3 và scikit-learn mặc định handle unicode khá tốt
        text = f"{title} {skills}".strip()
        job_texts.append(text)
        
    if current_job_index == -1:
        # Trong trường hợp current_job ko nằm trong list query ra
        title = current_job.title if current_job.title else ""
        skills = current_job.requirements if current_job.requirements else ""
        text = f"{title} {skills}".strip()
        job_texts.append(text)
        current_job_index = len(job_texts) - 1

    try:
        # Chạy hàm tính toán (TF-IDF)
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(job_texts)
    except ValueError:
        # Nếu thư viện không trích xuất được từ nào (tất cả chuỗi rỗng)
        return Job.objects.none()
        
    # Tính toán Cosine Similarity
    cosine_sim = cosine_similarity(tfidf_matrix[current_job_index:current_job_index+1], tfidf_matrix).flatten()
    
    # Sắp xếp điểm số từ cao xuống thấp
    similar_indices = cosine_sim.argsort()[::-1]
    
    top_similar_ids = []
    for idx in similar_indices:
        # Loại bỏ chính công việc hiện tại ra khỏi danh sách so sánh
        if idx == current_job_index:
            continue
            
        if idx < len(job_ids):
            # Chỉ gợi ý những job có độ tương đồng lớn hơn 0
            if cosine_sim[idx] > 0:
                top_similar_ids.append(job_ids[idx])
                
        if len(top_similar_ids) == top_n:
            break
            
    if not top_similar_ids:
        return Job.objects.none()
        
    # Query lại vào DB để lấy thông tin chi tiết và giữ đúng thứ tự mức độ tương đồng
    preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(top_similar_ids)])
    similar_jobs = Job.objects.filter(pk__in=top_similar_ids).order_by(preserved)
    
    return similar_jobs
