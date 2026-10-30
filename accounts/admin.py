from django.contrib import admin

from .models import (
    Assignment,
    AssignmentCompletion,
    Attendance,
    ChatConversation,
    ChatMessage,
    Profile,
    StudentMessage,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "expertise", "phone")
    list_filter = ("role",)
    search_fields = ("user__first_name", "user__last_name", "user__email")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "is_present", "marked_by")
    list_filter = ("date", "is_present")
    search_fields = ("student__user__first_name", "student__user__last_name")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "due_date", "created_by", "created_at")
    search_fields = ("title", "description")
    list_filter = ("due_date",)


@admin.register(AssignmentCompletion)
class AssignmentCompletionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "is_completed", "updated_by", "updated_at")
    list_filter = ("is_completed", "assignment")
    search_fields = ("assignment__title", "student__user__first_name", "student__user__last_name")


@admin.register(StudentMessage)
class StudentMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender", "sent_at", "is_read")
    list_filter = ("is_read", "sent_at")
    search_fields = ("subject", "body", "sender__user__first_name", "sender__user__last_name")


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "forwarded_to", "status", "forwarded_at", "updated_at")
    list_filter = ("status", "forwarded_at")
    search_fields = ("student__user__first_name", "student__user__last_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender", "sent_at", "is_read")
    list_filter = ("is_read", "sent_at")
    search_fields = ("body", "conversation__student__user__first_name")
    readonly_fields = ("sent_at",)
