import json
import re
from django.conf import settings
from .models import ApplicationMatch, Application, CV, Job

# Synonym mapping for normalization
SYNONYMS = {
    'js': 'javascript', 'reactjs': 'react', 'vuejs': 'vue',
    'nodejs': 'node', 'postgres': 'postgresql',
    'rest api': 'api', 'restful': 'api',
    'mysql': 'sql', 'mssql': 'sql', 'postgres sql': 'postgresql',
    'golang': 'go', 'net core': '.net', 'asp.net': '.net'
}

def normalize_text(text):
    if not text:
        return ""
    text = str(text)
    text = text.lower().strip()
    # Remove special chars but keep spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    # Basic synonym replacement
    for k, v in SYNONYMS.items():
        text = re.sub(r'\b' + re.escape(k) + r'\b', v, text)
    return text

def extract_skills_list(data):
    """Return normalized skill names from job text or CV Builder JSON."""
    if isinstance(data, list):
        skills = []
        for item in data:
            if isinstance(item, dict):
                value = item.get('name') or item.get('skill') or item.get('title')
            else:
                value = item
            normalized = normalize_text(value)
            if normalized:
                skills.append(normalized)
        return skills
    if isinstance(data, str):
        return [normalize_text(s.strip()) for s in data.split(',') if s.strip()]
    return []

def entry_to_text(entry):
    """Flatten a CV Builder JSON item without depending on one field name."""
    if isinstance(entry, dict):
        return " ".join(str(value) for value in entry.values() if value)
    return str(entry or "")

def has_text_match(needle, haystack):
    """Match by phrase first, then by meaningful token overlap."""
    needle = normalize_text(needle)
    haystack = normalize_text(haystack)
    if not needle or not haystack:
        return False
    if needle in haystack or haystack in needle:
        return True

    needle_tokens = {token for token in needle.split() if len(token) > 2}
    haystack_tokens = {token for token in haystack.split() if len(token) > 2}
    if not needle_tokens:
        return False

    return len(needle_tokens & haystack_tokens) >= max(1, len(needle_tokens) // 2)

def compute_match(application, skip_ai=False):
    """
    Computes matching score for an application.
    Phase 1: Online CV only.
    """
    if not application.online_cv:
        return None
    
    cv = application.online_cv
    job = application.job
    
    # Initialize scores
    skill_score = 0
    exp_score = 0
    desc_score = 0
    project_score = 0
    bonus_score = 0
    
    # 1. SKILLS MATCH (50 pts)
    job_skills = extract_skills_list(job.requirements)
    cv_skills = extract_skills_list(cv.skills)
    
    matched_skills_orig = []
    missing_skills_orig = []
    
    # We use original names for display but normalized for matching
    job_skills_raw = [s.strip() for s in job.requirements.split(',') if s.strip()] if job.requirements else []
    
    matched_count = 0
    if job_skills:
        for i, js_norm in enumerate(job_skills):
            found = False
            for cs_norm in cv_skills:
                if js_norm in cs_norm or cs_norm in js_norm:
                    found = True
                    break
            
            if found:
                matched_count += 1
                if i < len(job_skills_raw):
                    matched_skills_orig.append(job_skills_raw[i])
            else:
                if i < len(job_skills_raw):
                    missing_skills_orig.append(job_skills_raw[i])
        
        skill_score = int((matched_count / len(job_skills)) * 50)
    else:
        skill_score = 50 # If job has no skills required, everyone matches
    
    # 2. EXPERIENCE / TITLE MATCH (20 pts)
    # Match title
    job_title_norm = normalize_text(job.title)
    cv_major_norm = normalize_text(cv.target_major)
    
    if has_text_match(job_title_norm, cv_major_norm):
        exp_score += 10
    
    # Match experience entries
    cv_exp = cv.experience if isinstance(cv.experience, list) else []
    exp_matched = False
    for entry in cv_exp:
        entry_text = entry_to_text(entry)
        if has_text_match(job_title_norm, entry_text):
            exp_matched = True
            break
    if exp_matched:
        exp_score += 10
    
    # 3. DESCRIPTION RELEVANCE (15 pts)
    # Extract some keywords from job description (very basic for phase 1)
    important_keywords = job_skills + [job_title_norm]
    cv_full_text = normalize_text(f"{cv.objective} {' '.join(entry_to_text(e) for e in cv_exp)}")
    
    desc_hits = 0
    for kw in important_keywords:
        if kw and kw in cv_full_text:
            desc_hits += 1
    
    if important_keywords:
        desc_score = int(min(15, (desc_hits / len(important_keywords)) * 30)) # Boosted weight
    
    # 4. PROJECTS (10 pts)
    cv_projects = cv.projects if isinstance(cv.projects, list) else []
    proj_hits = 0
    for proj in cv_projects:
        proj_text = normalize_text(entry_to_text(proj))
        for kw in important_keywords:
            if kw and kw in proj_text:
                proj_hits += 1
                break
    if cv_projects:
        project_score = min(10, proj_hits * 5)
    
    # 5. BONUS (5 pts)
    if cv.github or cv.linkedin:
        bonus_score += 2
    if len(cv_exp) > 1:
        bonus_score += 2
    if len(cv_projects) > 0:
        bonus_score += 1
        
    total_score = skill_score + exp_score + desc_score + project_score + bonus_score
    total_score = min(100, total_score)
    
    # Save to DB
    match_obj, created = ApplicationMatch.objects.get_or_create(application=application)
    match_obj.score = total_score
    match_obj.skill_score = skill_score
    match_obj.exp_score = exp_score
    match_obj.desc_score = desc_score
    match_obj.project_score = project_score
    match_obj.bonus_score = bonus_score
    match_obj.matched_skills = matched_skills_orig
    match_obj.missing_skills = missing_skills_orig
    
    # Generate AI summary if Gemini is available and not skipped
    if skip_ai:
        summary, questions = generate_fallback_feedback(match_obj)
        is_ai = False
    else:
        summary, questions, is_ai = generate_match_feedback(match_obj)
        
    match_obj.summary = summary
    match_obj.interview_questions = questions
    match_obj.ai_generated = is_ai
    
    match_obj.save()
    return match_obj

def generate_match_feedback(match):
    """Calls Gemini to write a summary and questions based on scores. Returns (summary, questions, success_bool)"""
    try:
        from core.views import GEMINI_AVAILABLE
        if not GEMINI_AVAILABLE:
            s, q = generate_fallback_feedback(match)
            return s, q, False
        
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        prompt = f"""
        Phân tích mức độ phù hợp của ứng viên cho vị trí "{match.application.job.title}".
        Dữ liệu đã tính toán:
        - Điểm tổng: {match.score}/100
        - Kỹ năng khớp: {', '.join(match.matched_skills)}
        - Kỹ năng thiếu: {', '.join(match.missing_skills)}
        - Điểm kinh nghiệm: {match.exp_score}/20
        
        Yêu cầu:
        1. Viết 1 đoạn nhận xét ngắn (2-3 câu) về ứng viên này (ngôn ngữ chuyên nghiệp, tiếng Việt).
        2. Gợi ý 2-3 câu hỏi phỏng vấn tập trung vào các kỹ năng còn thiếu hoặc điểm yếu.
        
        Trả về định dạng JSON:
        {{
            "summary": "...",
            "questions": ["...", "...", "..."]
        }}
        """
        
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        # Clean JSON if AI adds markdown backticks
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].strip()
            
        data = json.loads(raw_text)
        return data.get('summary', ''), data.get('questions', []), True
        
    except Exception as e:
        print(f"AI Match Feedback Error: {e}")
        s, q = generate_fallback_feedback(match)
        return s, q, False

def generate_fallback_feedback(match):
    """Fallback when AI is not available."""
    summary = f"Ứng viên đạt {match.score}% độ tương đồng. "
    if match.matched_skills:
        summary += f"Phù hợp các kỹ năng: {', '.join(match.matched_skills[:3])}. "
    if match.missing_skills:
        summary += f"Cần cải thiện: {', '.join(match.missing_skills[:3])}."
    
    questions = []
    for skill in match.missing_skills[:3]:
        questions.append(f"Bạn đã có kinh nghiệm thực tế hay dự án nào sử dụng {skill} chưa?")
    if not questions:
        questions = ["Bạn có thể chia sẻ thêm về kinh nghiệm làm việc gần đây nhất của mình không?"]
        
    return summary, questions
