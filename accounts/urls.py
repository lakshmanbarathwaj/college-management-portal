from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("join/", views.membership_request, name="membership_request"),
    path("logout/", views.logout_view, name="logout"),
    path("staff/", views.staff_directory, name="staff_directory"),
    path("students/", views.student_directory, name="student_directory"),
    path("portal/", views.portal, name="portal"),
    path("staff/dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("staff/results/", views.staff_results, name="staff_results"),
    path("message-center/", views.message_center, name="message_center"),
    path(
        "message-center/<int:conversation_id>/reply/",
        views.staff_reply_to_chat,
        name="staff_reply_to_chat",
    ),
    path("mentor/dashboard/", views.mentor_dashboard, name="mentor_dashboard"),
    path(
        "mentor/chats/<int:conversation_id>/updates/",
        views.mentor_chat_updates,
        name="mentor_chat_updates",
    ),
    path(
        "mentor/chats/<int:conversation_id>/reply/",
        views.mentor_chat_reply,
        name="mentor_chat_reply",
    ),
    path(
        "admin/students/<int:student_id>/mentor/",
        views.admin_assign_mentor,
        name="admin_assign_mentor",
    ),
    path("chat/send/", views.student_chat_message, name="student_chat_message"),
    path("chat/mentors/", views.student_chat_mentors, name="student_chat_mentors"),
    path("chat/forward/", views.student_chat_forward, name="student_chat_forward"),
    path(
        "chat/<int:conversation_id>/updates/",
        views.student_chat_updates,
        name="student_chat_updates",
    ),
    path("staff/students/", views.staff_students, name="staff_students"),
    path("staff/assignments/", views.staff_assignments, name="staff_assignments"),
    path(
        "staff/assignments/<int:assignment_id>/",
        views.staff_assignment_detail,
        name="staff_assignment_detail",
    ),
    path("attendance/", views.attendance_mark, name="attendance_mark"),
    path("messages/send/", views.student_send_message, name="student_send_message"),
    path("admin/inbox/", views.admin_inbox, name="admin_inbox"),
    path(
        "admin/inbox/<int:message_id>/read/",
        views.admin_mark_message_read,
        name="admin_mark_message_read",
    ),
    path(
        "admin/inbox/membership/<int:request_id>/",
        views.admin_review_membership_request,
        name="admin_review_membership_request",
    ),
]
