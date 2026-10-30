from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import (
    Assignment,
    AssignmentCompletion,
    Attendance,
    ChatConversation,
    ChatMessage,
    CourseResult,
    MembershipRequest,
    Profile,
    StudentMark,
    StudentMessage,
)


class StudentManagementViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="admin",
            email="admin@school.edu",
            password="AdminPass!234",
        )
        cls.staff_user = User.objects.create_user(
            username="staff1",
            email="staff1@school.edu",
            password="StaffPass!234",
            first_name="Ava",
        )
        Profile.objects.create(
            user=cls.staff_user,
            role=Profile.Role.STAFF,
            department="B.Sc. Computer Science",
        )
        cls.student_user = User.objects.create_user(
            username="student1",
            email="student1@school.edu",
            password="StudentPass!234",
            first_name="Aria",
        )
        Profile.objects.create(
            user=cls.student_user,
            role=Profile.Role.STUDENT,
            department="B.Sc. Computer Science",
        )

    def test_admin_can_sign_in_with_email_and_view_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"email": "ADMIN@school.edu", "password": "AdminPass!234"},
        )
        self.assertRedirects(response, reverse("home"))
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin dashboard")
        self.assertContains(response, "staff1@school.edu")

    def test_index_offers_separate_role_portals(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator")
        self.assertContains(response, "Staff")
        self.assertContains(response, "Student")
        self.assertContains(response, 'name="role" value="admin"')
        self.assertContains(response, 'name="role" value="staff"')
        self.assertContains(response, 'name="role" value="student"')
        self.assertContains(response, 'type="submit"')
        self.assertNotContains(response, f'href="{reverse("login")}?role=')

    def test_selected_portal_only_accepts_accounts_with_matching_role(self):
        portal_cases = (
            ("admin", "admin@school.edu", "AdminPass!234", "home"),
            ("staff", "staff1@school.edu", "StaffPass!234", "portal"),
            ("student", "student1@school.edu", "StudentPass!234", "portal"),
        )
        for selected_role, email, password, destination in portal_cases:
            with self.subTest(role=selected_role):
                response = self.client.get(
                    reverse("login"),
                    {"role": selected_role},
                )
                self.assertContains(response, f"Sign in as {selected_role}")
                response = self.client.post(
                    reverse("login"),
                    {"role": selected_role, "email": email, "password": password},
                )
                self.assertRedirects(
                    response,
                    reverse(destination),
                    fetch_redirect_response=False,
                )
                self.client.logout()

        rejected_cases = (
            ("staff", "student1@school.edu", "StudentPass!234"),
            ("student", "staff1@school.edu", "StaffPass!234"),
            ("admin", "staff1@school.edu", "StaffPass!234"),
            ("staff", "admin@school.edu", "AdminPass!234"),
        )
        for selected_role, email, password in rejected_cases:
            with self.subTest(rejected_role=selected_role, email=email):
                response = self.client.post(
                    reverse("login"),
                    {"role": selected_role, "email": email, "password": password},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "cannot use the selected portal")
                self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_invalid_portal_selection_cannot_fall_back_to_generic_login(self):
        response = self.client.post(
            reverse("login"),
            {
                "role": "unknown",
                "email": "student1@school.edu",
                "password": "StudentPass!234",
            },
        )
        self.assertRedirects(response, reverse("index"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_staff_login_redirects_to_portal_and_cannot_view_admin_directory(self):
        response = self.client.post(
            reverse("login"),
            {"email": "staff1@school.edu", "password": "StaffPass!234"},
        )
        self.assertRedirects(
            response,
            reverse("portal"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(self.client.get(reverse("portal")), reverse("staff_dashboard"))
        self.assertEqual(self.client.get(reverse("staff_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("attendance_mark")).status_code, 200)
        self.assertEqual(self.client.get(reverse("attendance_mark")).status_code, 200)
        response = self.client.get(reverse("staff_directory"))
        self.assertRedirects(
            response,
            reverse("portal"),
            fetch_redirect_response=False,
        )

    def test_student_login_redirects_to_portal(self):
        response = self.client.post(
            reverse("login"),
            {"email": "student1@school.edu", "password": "StudentPass!234"},
        )
        self.assertRedirects(response, reverse("portal"))
        self.assertContains(self.client.get(reverse("portal")), "B.Sc. Computer Science")

    def test_student_can_expand_assigned_mentor_contact_details(self):
        student_profile = self.student_user.profile
        student_profile.mentor = self.staff_user.profile
        student_profile.save(update_fields=("mentor",))
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("portal"))

        self.assertContains(response, "Contact your mentor")
        self.assertContains(response, "<details class=\"mt-1\">", html=False)
        self.assertContains(response, "Ava")
        self.assertContains(response, 'href="mailto:staff1@school.edu"')
        self.assertContains(response, "staff1@school.edu")

    def test_admin_can_view_staff_and_student_directories(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("staff_directory")), "staff1@school.edu")
        self.assertContains(self.client.get(reverse("student_directory")), "student1@school.edu")

    def test_invalid_login_does_not_authenticate(self):
        response = self.client.post(
            reverse("login"),
            {"email": "staff1@school.edu", "password": "incorrect"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "incorrect")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_public_membership_request_is_held_for_admin_review(self):
        self.assertEqual(self.client.get(reverse("membership_request")).status_code, 200)
        response = self.client.post(
            reverse("membership_request"),
            {
                "full_name": "Priya Devi",
                "email": "priya@school.edu",
                "role": "student",
                "department": "B.Sc. Computer Science",
                "phone": "1234567890",
                "message": "I would like to join.",
            },
        )
        self.assertRedirects(response, reverse("index"))
        application = MembershipRequest.objects.get(email="priya@school.edu")
        self.assertEqual(application.role, Profile.Role.STUDENT)
        self.assertFalse(User.objects.filter(email__iexact="priya@school.edu").exists())

    def test_admin_approval_creates_user_and_profile_with_admin_password(self):
        application = MembershipRequest.objects.create(
            full_name="Priya Devi",
            email="priya@school.edu",
            role=Profile.Role.STUDENT,
            department="B.Sc. Computer Science",
            phone="1234567890",
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_review_membership_request", args=[application.pk]),
            {"action": "approve", "password": "StrongPass!234"},
        )
        self.assertRedirects(response, reverse("admin_inbox"))
        user = User.objects.get(email="priya@school.edu")
        self.assertEqual(user.get_full_name(), "Priya Devi")
        self.assertTrue(user.check_password("StrongPass!234"))
        self.assertEqual(user.profile.role, Profile.Role.STUDENT)
        self.assertEqual(user.profile.phone, "1234567890")
        self.assertFalse(MembershipRequest.objects.filter(pk=application.pk).exists())
        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"email": "priya@school.edu", "password": "StrongPass!234"},
        )
        self.assertRedirects(response, reverse("portal"))

    def test_invalid_admin_password_does_not_approve_request(self):
        application = MembershipRequest.objects.create(
            full_name="Priya Devi",
            email="priya@school.edu",
            role=Profile.Role.STUDENT,
            department="B.Sc. Computer Science",
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_review_membership_request", args=[application.pk]),
            {"action": "approve", "password": "short"},
        )
        self.assertRedirects(response, reverse("admin_inbox"))
        self.assertTrue(MembershipRequest.objects.filter(pk=application.pk).exists())
        self.assertFalse(User.objects.filter(email="priya@school.edu").exists())

    def test_admin_decline_removes_membership_request(self):
        application = MembershipRequest.objects.create(
            full_name="Priya Devi",
            email="priya@school.edu",
            role=Profile.Role.STUDENT,
            department="B.Sc. Computer Science",
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_review_membership_request", args=[application.pk]),
            {"action": "decline"},
        )
        self.assertRedirects(response, reverse("admin_inbox"))
        self.assertFalse(MembershipRequest.objects.filter(pk=application.pk).exists())
        self.assertFalse(User.objects.filter(email="priya@school.edu").exists())

    def test_staff_cannot_review_membership_requests(self):
        application = MembershipRequest.objects.create(
            full_name="Priya Devi",
            email="priya@school.edu",
            role=Profile.Role.STUDENT,
            department="B.Sc. Computer Science",
        )
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("admin_review_membership_request", args=[application.pk]),
            {"action": "approve", "password": "StrongPass!234"},
        )
        self.assertRedirects(response, reverse("portal"), fetch_redirect_response=False)
        self.assertTrue(MembershipRequest.objects.filter(pk=application.pk).exists())

    def test_staff_can_mark_daily_attendance(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("attendance_mark"),
            {
                "date": "2026-10-28",
                "present_students": [str(self.student_user.profile.pk)],
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('attendance_mark')}?date=2026-10-28",
        )
        record = Attendance.objects.get(student=self.student_user.profile)
        self.assertTrue(record.is_present)
        self.assertEqual(record.marked_by, self.staff_user)

    def test_staff_student_details_show_attendance_percentage(self):
        Attendance.objects.create(
            student=self.student_user.profile,
            date="2026-10-26",
            is_present=True,
            marked_by=self.staff_user,
        )
        Attendance.objects.create(
            student=self.student_user.profile,
            date="2026-10-27",
            is_present=False,
            marked_by=self.staff_user,
        )
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("staff_students"))
        self.assertContains(response, "Aria")
        self.assertContains(response, "50.0%")

    def test_student_can_view_attendance_and_send_manual_message_to_admin(self):
        Attendance.objects.create(
            student=self.student_user.profile,
            date="2026-10-27",
            is_present=False,
            marked_by=self.staff_user,
        )
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("portal"))
        self.assertContains(response, "0.0%")
        self.assertContains(response, "Campus assistant")

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            response = self.client.post(
                reverse("student_send_message"),
                {"subject": "Attendance help", "body": "Please advise me."},
            )

        self.assertRedirects(response, reverse("portal"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@school.edu"])
        self.assertEqual(mail.outbox[0].subject, "Attendance help")
        self.assertIn("Please advise me.", mail.outbox[0].body)
        self.assertEqual(StudentMessage.objects.count(), 1)
        self.assertEqual(StudentMessage.objects.get().sender, self.student_user.profile)

    def test_student_can_send_message_even_when_attendance_is_at_70_percent(self):
        for day in range(10):
            Attendance.objects.create(
                student=self.student_user.profile,
                date=f"2026-10-{day + 1:02}",
                is_present=day < 7,
                marked_by=self.staff_user,
            )
        self.client.force_login(self.student_user)

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            response = self.client.post(
                reverse("student_send_message"),
                {"subject": "Attendance update", "body": "I am asking for help."},
            )

        self.assertRedirects(response, reverse("portal"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(StudentMessage.objects.count(), 1)

    def test_student_chat_answers_faqs_with_live_assignment_and_result_data(self):
        pending_assignment = Assignment.objects.create(
            title="Pending Python lab",
            description="Finish the lab.",
            due_date="2026-11-15",
            created_by=self.staff_user,
        )
        completed_assignment = Assignment.objects.create(
            title="Completed English essay",
            description="Essay submitted.",
            due_date="2026-11-10",
            created_by=self.staff_user,
        )
        AssignmentCompletion.objects.create(
            assignment=completed_assignment,
            student=self.student_user.profile,
            is_completed=True,
            updated_by=self.staff_user,
        )
        CourseResult.objects.create(
            subject="Tamil",
            pass_percentage="90.00",
            published_by=self.staff_user,
        )
        self.client.force_login(self.student_user)

        response = self.client.post(
            reverse("student_chat_message"),
            {"question": "What assignments are pending?"},
        )
        self.assertRedirects(response, f"{reverse('portal')}#student-chat")
        self.assertContains(
            self.client.get(reverse("portal")),
            pending_assignment.title,
        )
        self.assertNotIn(
            completed_assignment.title,
            ChatMessage.objects.filter(
                conversation__student=self.student_user.profile,
                sender__isnull=True,
            ).first().body,
        )
        self.assertFalse(
            ChatConversation.objects.get(student=self.student_user.profile).human_handoff
        )

        self.client.post(
            reverse("student_chat_message"),
            {"question": "Tell me the fee structure"},
        )
        response = self.client.get(reverse("portal"))
        self.assertContains(response, "Term fee: 10,000")
        self.assertContains(response, "Total: 35,000")
        self.assertEqual(
            [message.body for message in response.context["chat_messages"]],
            ["Tell me the fee structure", "Current fee structure:\n• Term fee: 10,000\n• Exam fee: 5,000\n• Maintenance fee: 5,000\n• Transport fee: 15,000\nTotal: 35,000"],
        )

        self.client.post(
            reverse("student_chat_message"),
            {"question": "Show the published results"},
        )
        result_answer = ChatMessage.objects.filter(
            conversation__student=self.student_user.profile,
            sender__isnull=True,
        ).order_by("sent_at", "pk").last().body
        self.assertIn("Tamil", result_answer)
        self.assertIn("90%", result_answer)
        response = self.client.get(reverse("portal"))
        self.assertContains(response, "Tamil")
        self.assertContains(response, "90%")
        self.assertEqual(
            [message.body for message in response.context["chat_messages"]],
            ["Show the published results", result_answer],
        )

    def test_student_chat_returns_json_for_async_requests_and_validates_input(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("student_chat_message"),
            {"question": "What assignments are pending?"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["question"], "What assignments are pending?")
        self.assertEqual(response.json()["answer"], "You have no pending assignments.")
        self.assertIn("timestamp", response.json())
        self.assertEqual(ChatMessage.objects.count(), 2)

        invalid_response = self.client.post(
            reverse("student_chat_message"),
            {"question": " "},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("2,000 characters", invalid_response.json()["error"])
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_unknown_chat_can_be_forwarded_and_replied_to_in_mentor_dashboard(self):
        staff_two = User.objects.create_user(
            username="staff2",
            email="staff2@school.edu",
            password="StaffPass!234",
        )
        Profile.objects.create(
            user=staff_two,
            role=Profile.Role.STAFF,
            department="B.Sc. Computer Science",
        )
        self.student_user.profile.mentor = self.staff_user.profile
        self.student_user.profile.save(update_fields=("mentor",))
        self.client.force_login(self.student_user)

        response = self.client.post(
            reverse("student_chat_message"),
            {"question": "Can I discuss my academic plans?"},
            HTTP_ACCEPT="application/json",
        )
        self.assertTrue(response.json()["needs_mentor"])
        conversation = ChatConversation.objects.get(student=self.student_user.profile)
        self.assertFalse(conversation.human_handoff)
        self.assertEqual(conversation.messages.count(), 2)
        mentors_response = self.client.get(
            reverse("student_chat_mentors"),
            {"topic": "Can I discuss my academic plans?"},
        )
        self.assertEqual(
            mentors_response.json()["recommended_mentor_id"],
            self.student_user.profile.mentor_id,
        )

        forward_response = self.client.post(
            reverse("student_chat_forward"),
            {
                "conversation_id": conversation.pk,
                "mentor_id": self.student_user.profile.mentor_id,
            },
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(forward_response.status_code, 200)
        self.assertIn("forwarded to", forward_response.json()["message"])
        conversation.refresh_from_db()
        self.assertEqual(conversation.forwarded_to_id, self.student_user.profile.mentor_id)
        self.assertEqual(conversation.status, "pending")
        message_count = conversation.messages.count()
        duplicate_response = self.client.post(
            reverse("student_chat_forward"),
            {
                "conversation_id": conversation.pk,
                "mentor_id": self.student_user.profile.mentor_id,
            },
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(conversation.messages.count(), message_count)
        conflicting_response = self.client.post(
            reverse("student_chat_forward"),
            {
                "conversation_id": conversation.pk,
                "mentor_id": staff_two.profile.pk,
            },
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(conflicting_response.status_code, 409)
        self.assertEqual(conversation.messages.count(), message_count)

        self.client.force_login(staff_two)
        self.assertNotContains(
            self.client.get(reverse("mentor_dashboard")),
            "Can I discuss my academic plans?",
        )
        self.client.force_login(self.student_user.profile.mentor.user)
        self.assertContains(self.client.get(reverse("mentor_dashboard")), "Can I discuss my academic plans?")
        self.assertEqual(
            self.client.get(
                reverse("mentor_chat_updates", args=[conversation.pk]),
                HTTP_ACCEPT="application/json",
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("mentor_chat_reply", args=[conversation.pk]),
            {"body": "Let's discuss this after class."},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.json()["status"], "replied")
        self.client.force_login(self.student_user)
        student_update = self.client.get(
            reverse("student_chat_updates", args=[conversation.pk]),
            HTTP_ACCEPT="application/json",
        )
        self.assertIn(
            "Let's discuss this after class.",
            [message["body"] for message in student_update.json()["messages"]],
        )
        self.client.force_login(self.student_user.profile.mentor.user)
        close_response = self.client.post(
            reverse("mentor_chat_reply", args=[conversation.pk]),
            {"action": "close"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(close_response.json()["status"], "closed")

    def test_no_active_mentor_returns_friendly_error(self):
        User.objects.filter(profile__role=Profile.Role.STAFF).update(is_active=False)
        self.client.force_login(self.student_user)
        response = self.client.get(
            reverse("student_chat_mentors"),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("No mentors are available", response.json()["error"])

    def test_staff_can_publish_results_and_students_can_see_them(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("staff_results"),
            {"action": "publish_rate", "rate_subject": "Invalid", "pass_percentage": "NaN"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CourseResult.objects.filter(subject="Invalid").exists())
        response = self.client.post(
            reverse("staff_results"),
            {
                "action": "publish_rate",
                "rate_subject": "Python Lab",
                "pass_percentage": "100",
            },
        )
        self.assertRedirects(response, reverse("staff_results"))
        result = CourseResult.objects.get(subject="Python Lab")
        self.assertEqual(result.published_by, self.staff_user)
        self.client.force_login(self.student_user)
        self.assertContains(self.client.get(reverse("portal")), "Python Lab")

    def test_staff_publish_student_marks_and_only_that_student_can_see_them(self):
        another_student = User.objects.create_user(
            username="student2",
            email="student2@school.edu",
            password="StudentPass!234",
        )
        another_profile = Profile.objects.create(
            user=another_student,
            role=Profile.Role.STUDENT,
            department="B.Sc. Computer Science",
        )
        self.client.force_login(self.staff_user)
        for subject, mark in (("Tamil", "90"), ("English", "70"), ("Maths", "99"), ("Python", "75")):
            response = self.client.post(
                reverse("staff_results"),
                {
                    "student_id": self.student_user.profile.pk,
                    "subject": subject,
                    "mark": mark,
                },
            )
            self.assertRedirects(response, reverse("staff_results"))
        self.client.post(
            reverse("staff_results"),
            {
                "student_id": self.student_user.profile.pk,
                "subject": "Tamil",
                "mark": "95",
            },
        )
        self.assertEqual(StudentMark.objects.filter(student=self.student_user.profile).count(), 4)
        self.assertEqual(
            StudentMark.objects.get(student=self.student_user.profile, subject="Tamil").mark,
            Decimal("95"),
        )
        self.assertContains(self.client.get(reverse("staff_results")), "Aria")

        self.client.force_login(self.student_user)
        first_page = self.client.get(reverse("portal"))
        self.assertEqual(len(first_page.context["student_marks"]), 3)
        second_page = self.client.get(reverse("portal"), {"marks_page": 2})
        self.assertEqual(len(second_page.context["student_marks"]), 1)
        rendered_marks = first_page.content.decode() + second_page.content.decode()
        for subject in ("Tamil", "English", "Maths", "Python"):
            self.assertIn(subject, rendered_marks)
        self.client.post(
            reverse("student_chat_message"),
            {"question": "Can I see my results?"},
        )
        self.assertContains(
            self.client.get(reverse("portal")),
            "Tamil: 95/100",
        )

        self.client.force_login(another_student)
        response = self.client.get(reverse("portal"))
        self.assertContains(response, "Your marks")
        self.assertNotContains(response, "Tamil")
        self.assertNotContains(response, "90")

    def test_admin_can_assign_student_mentor_and_students_cannot(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_assign_mentor", args=[self.student_user.profile.pk]),
            {"mentor_id": "invalid"},
        )
        self.assertRedirects(response, reverse("student_directory"))
        self.student_user.profile.refresh_from_db()
        self.assertIsNone(self.student_user.profile.mentor)

        response = self.client.post(
            reverse("admin_assign_mentor", args=[self.student_user.profile.pk]),
            {"mentor_id": self.staff_user.profile.pk},
        )
        self.assertRedirects(response, reverse("student_directory"))
        self.student_user.profile.refresh_from_db()
        self.assertEqual(self.student_user.profile.mentor, self.staff_user.profile)

        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("admin_assign_mentor", args=[self.student_user.profile.pk]),
            {"mentor_id": ""},
        )
        self.assertRedirects(response, reverse("portal"), fetch_redirect_response=False)
        self.student_user.profile.refresh_from_db()
        self.assertEqual(self.student_user.profile.mentor, self.staff_user.profile)

    def test_staff_can_create_assignment_and_track_student_completion(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("staff_assignments"),
            {
                "title": "Python project",
                "description": "Submit the project.",
                "due_date": "2026-11-15",
            },
        )
        assignment = Assignment.objects.get(title="Python project")
        self.assertRedirects(
            response,
            reverse("staff_assignment_detail", args=[assignment.pk]),
        )
        self.assertFalse(AssignmentCompletion.objects.get(assignment=assignment).is_completed)

        response = self.client.post(
            reverse("staff_assignment_detail", args=[assignment.pk]),
            {
                "action": "edit_assignment",
                "title": "Revised Python project",
                "description": "Submit the revised project.",
                "due_date": "2026-11-20",
            },
        )
        self.assertRedirects(
            response,
            reverse("staff_assignment_detail", args=[assignment.pk]),
        )
        assignment.refresh_from_db()
        self.assertEqual(assignment.title, "Revised Python project")

        response = self.client.post(
            reverse("staff_assignment_detail", args=[assignment.pk]),
            {"completed_students": [str(self.student_user.profile.pk)], "action": "save"},
        )
        self.assertRedirects(
            response,
            reverse("staff_assignment_detail", args=[assignment.pk]),
        )
        completion = AssignmentCompletion.objects.get(assignment=assignment)
        self.assertTrue(completion.is_completed)
        self.assertEqual(completion.updated_by, self.staff_user)

        self.client.force_login(self.student_user)
        self.assertContains(self.client.get(reverse("portal")), "Revised Python project")
        self.assertContains(self.client.get(reverse("portal")), "Completed")

    def test_student_cannot_change_assignment_completion_or_view_admin_inbox(self):
        assignment = Assignment.objects.create(
            title="Python project",
            description="Submit the project.",
            due_date="2026-11-15",
            created_by=self.staff_user,
        )
        completion = AssignmentCompletion.objects.create(
            assignment=assignment,
            student=self.student_user.profile,
            updated_by=self.staff_user,
        )
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("staff_assignment_detail", args=[assignment.pk]),
            {"completed_students": [str(self.student_user.profile.pk)], "action": "save"},
        )
        self.assertRedirects(response, reverse("portal"), fetch_redirect_response=False)
        completion.refresh_from_db()
        self.assertFalse(completion.is_completed)
        self.assertRedirects(
            self.client.get(reverse("admin_inbox")),
            reverse("portal"),
            fetch_redirect_response=False,
        )

    def test_admin_can_review_student_messages(self):
        student_message = StudentMessage.objects.create(
            sender=self.student_user.profile,
            subject="A question",
            body="My message",
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_inbox"))
        self.assertContains(response, "A question")
        response = self.client.post(
            reverse("admin_mark_message_read", args=[student_message.pk])
        )
        self.assertRedirects(response, reverse("admin_inbox"))
        student_message.refresh_from_db()
        self.assertTrue(student_message.is_read)
