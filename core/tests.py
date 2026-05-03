import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .matching import compute_match
from .models import Application, ApplicationMatch, CV, InterviewInvitation, Job


User = get_user_model()


class CVBuilderTests(TestCase):
    def test_candidate_can_open_cv_builder(self):
        user = User.objects.create_user(
            username="viewer@example.com",
            email="viewer@example.com",
            password="password123",
            first_name="Nguyen Van B",
            is_candidate=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("cv_builder"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cv-form")

    def test_candidate_can_create_cv_with_ajax(self):
        user = User.objects.create_user(
            username="candidate@example.com",
            email="candidate@example.com",
            password="password123",
            first_name="Nguyen Van A",
            is_candidate=True,
        )
        self.client.force_login(user)

        payload = {
            "title": "Backend Developer CV",
            "full_name": "Nguyen Van A",
            "email": "candidate@example.com",
            "phone": "0900000000",
            "address": "Ha Noi",
            "target_major": "Backend Developer",
            "objective": "Build reliable web applications.",
            "github": "https://github.com/example",
            "linkedin": "https://linkedin.com/in/example",
            "education": json.dumps([{"school": "PTIT", "major": "IT", "time": "2022 - 2026", "desc": ""}]),
            "experience": json.dumps([{"company": "ABC", "position": "Intern", "time": "2025", "desc": "Built APIs"}]),
            "skills": json.dumps([{"name": "Django", "level": "80"}]),
        }

        response = self.client.post(
            reverse("cv_builder"),
            payload,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        cv = CV.objects.get(id=data["cv_id"])
        self.assertEqual(cv.user, user)
        self.assertEqual(cv.title, "Backend Developer CV")
        self.assertEqual(cv.skills[0]["name"], "Django")

    def test_employer_cannot_access_cv_builder(self):
        user = User.objects.create_user(
            username="employer@example.com",
            email="employer@example.com",
            password="password123",
            is_employer=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("cv_builder"))

        self.assertRedirects(response, reverse("home"))


class ApplicationMatchTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="match-employer@example.com",
            email="match-employer@example.com",
            password="password123",
            is_employer=True,
        )
        self.candidate = User.objects.create_user(
            username="match-candidate@example.com",
            email="match-candidate@example.com",
            password="password123",
            is_candidate=True,
        )
        self.job = Job.objects.create(
            title="Backend Developer Django",
            description="Build REST APIs with Django and SQL.",
            requirements="Python, Django, SQL, Docker",
            location="Ha Noi",
            employer=self.employer,
            is_approved=True,
        )
        self.cv = CV.objects.create(
            user=self.candidate,
            title="Backend CV",
            full_name="Nguyen Van C",
            email="match-candidate@example.com",
            phone="0900000000",
            target_major="Backend Developer",
            objective="I build Django REST API services.",
            skills=[
                {"name": "Python", "level": "90"},
                {"name": "Django", "level": "80"},
                {"name": "SQL", "level": "80"},
            ],
            experience=[
                {
                    "company": "ABC",
                    "position": "Backend Developer",
                    "time": "2025",
                    "desc": "Built Django APIs",
                }
            ],
        )
        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            online_cv=self.cv,
        )

    @patch("core.views.GEMINI_AVAILABLE", False)
    def test_compute_match_accepts_cv_builder_json(self):
        match = compute_match(self.application)

        self.assertGreater(match.score, 0)
        self.assertEqual(match.matched_skills, ["Python", "Django", "SQL"])
        self.assertEqual(match.missing_skills, ["Docker"])
        self.assertGreaterEqual(match.exp_score, 10)
        self.assertTrue(match.summary)
        self.assertTrue(match.interview_questions)

    @patch("core.views.GEMINI_AVAILABLE", False)
    def test_applicant_list_lazy_computes_match_for_online_cv(self):
        self.client.force_login(self.employer)

        response = self.client.get(reverse("applicant_list", args=[self.job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ApplicationMatch.objects.filter(application=self.application).exists())
        self.assertContains(response, "Python")
        self.assertContains(response, "Docker")


class InterviewInvitationTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="interview-employer@example.com",
            email="interview-employer@example.com",
            password="password123",
            is_employer=True,
            company_name="Interview Co",
        )
        self.candidate = User.objects.create_user(
            username="interview-candidate@example.com",
            email="interview-candidate@example.com",
            password="password123",
            is_candidate=True,
        )
        self.job = Job.objects.create(
            title="Java Developer",
            description="Build Spring Boot services.",
            requirements="Java, Spring Boot",
            location="Ha Noi",
            employer=self.employer,
            is_approved=True,
        )
        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            cv_file="cvs/test.pdf",
        )

    def test_employer_can_schedule_interview(self):
        self.client.force_login(self.employer)
        scheduled_at = (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")

        response = self.client.post(
            reverse("schedule_interview", args=[self.application.id]),
            {
                "scheduled_at": scheduled_at,
                "mode": "online",
                "location": "https://meet.example.com/interview",
                "note": "Prepare portfolio.",
            },
        )

        self.assertRedirects(response, reverse("applicant_list", args=[self.job.id]))
        self.application.refresh_from_db()
        invitation = InterviewInvitation.objects.get(application=self.application)
        self.assertEqual(self.application.status, "Interview")
        self.assertEqual(invitation.location, "https://meet.example.com/interview")
        self.assertEqual(invitation.created_by, self.employer)

    def test_candidate_dashboard_shows_interview(self):
        InterviewInvitation.objects.create(
            application=self.application,
            scheduled_at=timezone.now() + timezone.timedelta(days=2),
            mode="online",
            location="https://meet.example.com/interview",
            note="Prepare portfolio.",
            created_by=self.employer,
        )
        self.application.status = "Interview"
        self.application.save(update_fields=["status"])
        self.client.force_login(self.candidate)

        response = self.client.get(reverse("candidate_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lịch phỏng vấn")
        self.assertContains(response, "https://meet.example.com/interview")
