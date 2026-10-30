import json
import re
from difflib import SequenceMatcher
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from smtplib import SMTPException
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
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


def _is_admin(user):
    return user.is_superuser


def _redirect_for_user(user):
    if _is_admin(user):
        return redirect("home")
    return redirect("portal")


def _role_for_user(user):
    if _is_admin(user):
        return "admin"
    return Profile.objects.filter(user=user).values_list("role", flat=True).first()


def _full_name_parts(full_name):
    parts = full_name.split(maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def index(request):
    if request.user.is_authenticated:
        return _redirect_for_user(request.user)
    return render(request, "accounts/index.html")


@require_http_methods(["GET", "POST"])
def login_view(request):
    selected_role = request.POST.get("role", request.GET.get("role", "")).strip()
    valid_roles = {"admin", *Profile.Role.values}

    if selected_role and selected_role not in valid_roles:
        messages.error(request, "Choose a valid portal to sign in.")
        return redirect("index")

    if request.user.is_authenticated:
        if selected_role and selected_role in valid_roles:
            if _role_for_user(request.user) != selected_role:
                messages.error(
                    request,
                    "This account cannot use the selected portal. Choose the portal assigned to your account.",
                )
                return redirect("index")
        return _redirect_for_user(request.user)

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        users = User.objects.filter(email__iexact=email)
        if users.count() == 1:
            user = authenticate(request, username=users.first().get_username(), password=password)
            if user is not None:
                if selected_role and _role_for_user(user) != selected_role:
                    messages.error(
                        request,
                        "This account cannot use the selected portal. Choose the portal assigned to your account.",
                    )
                    return render(
                        request,
                        "accounts/login.html",
                        {"selected_role": selected_role},
                    )
                login(request, user)
                return _redirect_for_user(user)
        messages.error(request, "The email or password you entered is incorrect.")

    return render(request, "accounts/login.html", {"selected_role": selected_role})


@require_http_methods(["GET", "POST"])
def membership_request(request):
    if request.user.is_authenticated:
        return _redirect_for_user(request.user)

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "")
        department = request.POST.get("department", "")
        phone = request.POST.get("phone", "").strip()
        message = request.POST.get("message", "").strip()
        errors = []

        if not full_name:
            errors.append("Enter your full name.")
        if not email:
            errors.append("Enter your email address.")
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors.append("Enter a valid email address.")
        if len(email) > 254:
            errors.append("Email addresses must be 254 characters or fewer.")
        if len(full_name) > 150:
            errors.append("Names must be 150 characters or fewer.")
        if role not in Profile.Role.values:
            errors.append("Choose whether you are applying as staff or a student.")
        if department not in dict(Profile._meta.get_field("department").choices):
            errors.append("Choose a valid department.")
        if User.objects.filter(email__iexact=email).exists():
            errors.append("An account already uses that email address.")
        if MembershipRequest.objects.filter(email__iexact=email).exists():
            errors.append("A membership request with that email is already pending.")

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            MembershipRequest.objects.create(
                full_name=full_name,
                email=email,
                role=role,
                department=department,
                phone=phone,
                message=message,
            )
            messages.success(
                request,
                "Your membership request was sent. You can sign in after an administrator approves it and provides your password.",
            )
            return redirect("index")

    return render(request, "accounts/membership_request.html")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("index")


@login_required
def home(request):
    if not _is_admin(request.user):
        return redirect("portal")

    context = {
        "staff_count": Profile.objects.filter(role=Profile.Role.STAFF).count(),
        "student_count": Profile.objects.filter(role=Profile.Role.STUDENT).count(),
        "attendance_count": Attendance.objects.count(),
        "unread_message_count": (
            StudentMessage.objects.filter(is_read=False).count()
            + MembershipRequest.objects.count()
        ),
        "chat_count": ChatConversation.objects.filter(
            human_handoff=True,
            forwarded_to__isnull=True,
        ).count(),
        "recent_users": User.objects.filter(profile__isnull=False)
        .select_related("profile")
        .order_by("-date_joined")[:5],
    }
    return render(request, "accounts/dashboard.html", context)


@login_required
def staff_directory(request):
    if not _is_admin(request.user):
        messages.error(request, "Only administrators can access the staff directory.")
        return redirect("portal")
    staff = (
        Profile.objects.filter(role=Profile.Role.STAFF)
        .select_related("user")
        .order_by("user__last_name", "user__first_name")
    )
    return render(
        request,
        "accounts/directory.html",
        {"profiles": staff, "title": "Staff", "directory_type": "staff"},
    )


@login_required
def student_directory(request):
    if not _is_admin(request.user):
        messages.error(request, "Only administrators can access the student directory.")
        return redirect("portal")
    students = (
        Profile.objects.filter(role=Profile.Role.STUDENT)
        .select_related("user", "mentor__user")
        .order_by("user__last_name", "user__first_name")
    )
    return render(
        request,
        "accounts/directory.html",
        {
            "profiles": students,
            "title": "Students",
            "directory_type": "students",
            "available_mentors": Profile.objects.filter(
                role=Profile.Role.STAFF
            ).select_related("user").order_by("user__last_name", "user__first_name"),
        },
    )


@login_required
def portal(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned student or staff profile.")
        return redirect("login")
    if profile.role == Profile.Role.STAFF:
        return redirect("staff_dashboard")
    attendance = _attendance_summary(profile)
    completions = {
        completion.assignment_id: completion
        for completion in AssignmentCompletion.objects.filter(
            student=profile,
            assignment__in=Assignment.objects.all(),
        ).select_related("assignment")
    }
    assignments = [
        (assignment, completions.get(assignment.pk))
        for assignment in Assignment.objects.all()
    ]
    conversation = (
        ChatConversation.objects.filter(student=profile)
        .select_related("forwarded_to__user")
        .first()
    )
    if conversation:
        conversation_messages = list(conversation.messages.select_related("sender"))
        chat_suggestions = []
        chat_needs_mentor = False
        if not conversation.forwarded_to_id:
            last_question_index = next(
                (
                    index
                    for index in range(len(conversation_messages) - 1, -1, -1)
                    if conversation_messages[index].sender_id == request.user.pk
                ),
                None,
            )
            if last_question_index is not None:
                conversation_messages = conversation_messages[last_question_index:]
                if conversation_messages:
                    response_metadata = _chatbot_answer(
                        conversation_messages[0].body,
                        profile,
                    )
                    chat_suggestions = response_metadata["suggestions"]
                    chat_needs_mentor = response_metadata["needs_mentor"]
    else:
        conversation_messages = []
        chat_suggestions = []
        chat_needs_mentor = False
    student_marks = Paginator(
        StudentMark.objects.filter(student=profile).select_related("published_by"),
        3,
    ).get_page(request.GET.get("marks_page"))
    return render(
        request,
        "accounts/portal.html",
        {
            "profile": profile,
            "assignments": assignments,
            "conversation": conversation,
            "chat_messages": conversation_messages,
            "chat_suggestions": chat_suggestions,
            "chat_needs_mentor": chat_needs_mentor,
            "published_results": CourseResult.objects.all(),
            "student_marks": student_marks,
            **attendance,
        },
    )


def _attendance_summary(profile):
    summary = Attendance.objects.filter(student=profile).aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(is_present=True)),
    )
    total = summary["total"]
    present = summary["present"]
    return {
        "attendance_total": total,
        "attendance_present": present,
        "attendance_percentage": present * 100 / total if total else 0,
    }


def _load_chat_knowledge():
    knowledge_path = Path(__file__).resolve().parent / "data" / "chat_knowledge.json"
    with knowledge_path.open(encoding="utf-8") as knowledge_file:
        knowledge = json.load(knowledge_file)
    if not isinstance(knowledge.get("intents"), list):
        raise ValueError(f"{knowledge_path} must contain an intents list.")
    return knowledge


def _normalize_chat_tokens(value):
    normalized = []
    for token in re.findall(r"[a-z0-9]+", value.casefold()):
        if len(token) > 4 and token.endswith("ies"):
            token = f"{token[:-3]}y"
        elif len(token) > 4 and token.endswith("es") and token[-3] in "sxz":
            token = token[:-2]
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        normalized.append(token)
    return normalized


def _chat_alias_matches(question_tokens, alias):
    alias_tokens = _normalize_chat_tokens(alias)
    if not alias_tokens:
        return False
    for start in range(len(question_tokens) - len(alias_tokens) + 1):
        if question_tokens[start : start + len(alias_tokens)] == alias_tokens:
            return True
    if len(alias_tokens) > 1:
        return all(token in question_tokens for token in alias_tokens)
    if len(alias_tokens[0]) < 4:
        return False
    return any(
        len(token) >= 4
        and SequenceMatcher(None, token, alias_tokens[0]).ratio() >= 0.86
        for token in question_tokens
    )


def _match_chat_intents(question, knowledge=None):
    knowledge = knowledge or _load_chat_knowledge()
    question_tokens = _normalize_chat_tokens(question)
    matches = []
    for intent in knowledge["intents"]:
        if any(
            _chat_alias_matches(question_tokens, alias)
            for alias in intent["aliases"]
        ):
            matches.append(intent)
    return matches


def _format_decimal(value):
    return format(value, ".2f").rstrip("0").rstrip(".")


def _answer_chat_intent(intent_id, question, student_profile, knowledge):
    if intent_id == "fees":
        fee_items = knowledge["fees"]["items"]
        if not fee_items:
            return None
        lines = [f"• {item['name']}: {item['amount']:,}" for item in fee_items]
        total = sum(item["amount"] for item in fee_items)
        return "Current fee structure:\n" + "\n".join(lines) + f"\nTotal: {total:,}"

    if intent_id == "courses":
        courses = knowledge["courses"]
        return "Courses currently listed: " + ", ".join(courses) + "." if courses else None

    if intent_id == "assignments":
        completions = {
            completion.assignment_id: completion.is_completed
            for completion in AssignmentCompletion.objects.filter(student=student_profile)
        }
        assignments = list(Assignment.objects.all())
        normalized_question = " ".join(_normalize_chat_tokens(question))
        if "pending" in normalized_question:
            assignments = [
                assignment
                for assignment in assignments
                if not completions.get(assignment.pk, False)
            ]
            if not assignments:
                return "You have no pending assignments."
        if not assignments:
            return "No assignments have been published yet."
        lines = []
        for assignment in assignments:
            status = "Completed" if completions.get(assignment.pk, False) else "Pending"
            lines.append(
                f"• {assignment.title} — due {assignment.due_date:%d %b %Y} · {status}"
            )
        return "Your assignments:\n" + "\n".join(lines)

    if intent_id == "student_results":
        student_marks = StudentMark.objects.filter(student=student_profile)
        if student_marks.exists():
            lines = [
                f"• {result.subject}: {_format_decimal(result.mark)}/100"
                for result in student_marks
            ]
            return "Your published marks:\n" + "\n".join(lines)
        class_results = CourseResult.objects.all()
        if class_results:
            lines = [
                f"• {result.subject}: {_format_decimal(result.pass_percentage)}% pass"
                for result in class_results
            ]
            return (
                "No individual marks have been published for you yet. "
                "Latest published class pass rates:\n"
                + "\n".join(lines)
            )
        return "No individual marks have been published for you yet."

    if intent_id == "class_results":
        results = CourseResult.objects.all()
        if not results:
            return None
        lines = [
            f"• {result.subject}: {_format_decimal(result.pass_percentage)}% pass"
            for result in results
        ]
        return "Latest published class pass rates:\n" + "\n".join(lines)

    if intent_id == "attendance":
        summary = _attendance_summary(student_profile)
        return (
            f"Your attendance is {summary['attendance_percentage']:.1f}% "
            f"({summary['attendance_present']} present of "
            f"{summary['attendance_total']} recorded days). "
            f"{knowledge['faqs']['attendance']}"
        )

    if intent_id == "mentor":
        assigned_mentor = student_profile.mentor
        if assigned_mentor is None:
            return "No mentor is assigned to your account yet."
        mentor_name = assigned_mentor.user.get_full_name() or "Your assigned mentor"
        return f"Your assigned mentor is {mentor_name}. {knowledge['faqs']['mentor']}"

    if intent_id == "schedule":
        schedules = knowledge.get("schedules", [])
        if not schedules:
            return None
        return "\n".join(schedules)

    return None


def _chatbot_answer(question, student_profile):
    knowledge = _load_chat_knowledge()
    matched_intents = _match_chat_intents(question, knowledge)
    answers = []
    suggestions = []
    needs_mentor = not matched_intents
    for intent in matched_intents:
        answer = _answer_chat_intent(intent["id"], question, student_profile, knowledge)
        suggestions.extend(intent.get("suggestions", []))
        if answer:
            answers.append(answer)
        else:
            needs_mentor = True
    if needs_mentor:
        answers.append(knowledge["unknown_answer"])
    return {
        "answer": "\n\n".join(answers),
        "suggestions": (
            list(dict.fromkeys(suggestions))[:3]
            or [
                "What courses are offered?",
                "What assignments are pending?",
                "How is attendance calculated?",
            ]
        ),
        "needs_mentor": needs_mentor,
        "topic": matched_intents[0]["id"] if matched_intents else "",
    }


def _chat_message_payload(message, student_user_id):
    sender_type = (
        "assistant"
        if message.sender_id is None
        else "user"
        if message.sender_id == student_user_id
        else "mentor"
    )
    return {
        "id": message.pk,
        "sender_type": sender_type,
        "sender_name": (
            "Campus assistant"
            if message.sender_id is None
            else message.sender.get_full_name() or "Mentor"
        ),
        "body": message.body,
        "timestamp": timezone.localtime(message.sent_at).isoformat(),
    }


def _chat_thread_payload(conversation, student_user_id):
    return {
        "conversation_id": conversation.pk,
        "status": conversation.status if conversation.forwarded_to_id else "",
        "mentor_name": (
            conversation.forwarded_to.user.get_full_name()
            or "Your mentor"
            if conversation.forwarded_to_id
            else ""
        ),
        "messages": [
            _chat_message_payload(message, student_user_id)
            for message in conversation.messages.select_related("sender")
        ],
    }


@login_required
@require_POST
def student_chat_message(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned student profile.")
        return redirect("login")
    if profile.role != Profile.Role.STUDENT:
        messages.error(request, "Only students can use the student chat.")
        return redirect("portal")

    wants_json = "application/json" in request.headers.get("Accept", "")
    question = request.POST.get("question", "").strip()
    if not question or len(question) > 2000:
        if wants_json:
            return JsonResponse(
                {"error": "Enter a message of up to 2,000 characters."},
                status=400,
            )
        messages.error(request, "Enter a message of up to 2,000 characters.")
        return redirect("portal")

    conversation_id = request.POST.get("conversation_id", "").strip()
    with transaction.atomic():
        if conversation_id:
            conversation = ChatConversation.objects.select_for_update().filter(
                pk=conversation_id,
                student=profile,
            ).first()
            if conversation is None:
                if wants_json:
                    return JsonResponse({"error": "Chat not found."}, status=404)
                messages.error(request, "Chat not found.")
                return redirect("portal")
        else:
            conversation = ChatConversation.objects.create(student=profile)

        if conversation.forwarded_to_id and conversation.status == "closed":
            if wants_json:
                return JsonResponse(
                    {"error": "This mentor chat is closed. Start a new chat to continue."},
                    status=409,
                )
            messages.error(request, "This mentor chat is closed. Start a new chat to continue.")
            return redirect("portal")

        ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            body=question,
        )
        if conversation.forwarded_to_id:
            conversation.status = "pending"
            conversation.save(update_fields=("status", "updated_at"))
            if wants_json:
                return JsonResponse(
                    {
                        "question": question,
                        "answer": None,
                        "forwarded": True,
                        **_chat_thread_payload(conversation, request.user.pk),
                    }
                )
            return redirect(f"{reverse('portal')}#student-chat")

        response_data = _chatbot_answer(question, profile)
        answer_message = ChatMessage.objects.create(
            conversation=conversation,
            body=response_data["answer"],
        )
    if wants_json:
        return JsonResponse(
            {
                "question": question,
                **response_data,
                "timestamp": timezone.localtime(answer_message.sent_at).isoformat(),
                "conversation_id": conversation.pk,
            }
        )
    return redirect(f"{reverse('portal')}#student-chat")


@login_required
@require_http_methods(["GET"])
def student_chat_mentors(request):
    if _is_admin(request.user):
        return JsonResponse({"error": "Only students can contact a mentor."}, status=403)
    try:
        student_profile = request.user.profile
    except Profile.DoesNotExist:
        return JsonResponse({"error": "Your student profile could not be found."}, status=403)
    if student_profile.role != Profile.Role.STUDENT:
        return JsonResponse({"error": "Only students can contact a mentor."}, status=403)

    mentors = list(
        Profile.objects.filter(
            role=Profile.Role.STAFF,
            user__is_active=True,
        ).select_related("user").order_by("user__first_name", "user__last_name", "pk")
    )
    if not mentors:
        return JsonResponse(
            {"error": "No mentors are available right now. Please try again later."},
            status=409,
        )
    question = request.GET.get("topic", "")
    question_tokens = set(_normalize_chat_tokens(question))
    mentors.sort(
        key=lambda mentor: (
            -len(question_tokens & set(_normalize_chat_tokens(mentor.expertise))),
            -(mentor.pk == student_profile.mentor_id),
            (mentor.user.get_full_name() or mentor.user.username).casefold(),
        )
    )
    return JsonResponse(
        {
            "recommended_mentor_id": mentors[0].pk,
            "mentors": [
                {
                    "id": mentor.pk,
                    "name": mentor.user.get_full_name() or "College mentor",
                    "expertise": mentor.expertise or "Not provided",
                    "availability": "Available",
                }
                for mentor in mentors
            ],
        }
    )


@login_required
@require_POST
def student_chat_forward(request):
    wants_json = "application/json" in request.headers.get("Accept", "")
    if _is_admin(request.user):
        return JsonResponse({"error": "Only students can forward a chat."}, status=403)
    try:
        student_profile = request.user.profile
    except Profile.DoesNotExist:
        return JsonResponse({"error": "Your student profile could not be found."}, status=403)
    if student_profile.role != Profile.Role.STUDENT:
        return JsonResponse({"error": "Only students can forward a chat."}, status=403)

    conversation_id = request.POST.get("conversation_id", "").strip()
    mentor_id = request.POST.get("mentor_id", "").strip()
    if not conversation_id.isdecimal() or not mentor_id.isdecimal():
        return JsonResponse(
            {"error": "Choose a chat and an available mentor."},
            status=400,
        )
    with transaction.atomic():
        conversation = ChatConversation.objects.select_for_update().filter(
            pk=conversation_id,
            student=student_profile,
        ).first()
        if conversation is None or not conversation.messages.exists():
            return JsonResponse(
                {"error": "There is no conversation to forward yet. Ask a question first."},
                status=400,
            )
        mentor = Profile.objects.filter(
            pk=mentor_id,
            role=Profile.Role.STAFF,
            user__is_active=True,
        ).select_related("user").first()
        if mentor is None:
            return JsonResponse(
                {"error": "That mentor is not available. Please choose another mentor."},
                status=409,
            )
        if conversation.forwarded_to_id:
            if conversation.forwarded_to_id != mentor.pk:
                return JsonResponse(
                    {
                        "error": "This chat has already been forwarded to another mentor.",
                        "mentor_name": conversation.forwarded_to.user.get_full_name(),
                    },
                    status=409,
                )
            return JsonResponse(
                {
                    "message": f"Your chat is already with {mentor.user.get_full_name() or 'your mentor'}.",
                    **_chat_thread_payload(conversation, request.user.pk),
                }
            )
        if conversation.status == "closed":
            return JsonResponse(
                {"error": "This chat is closed. Start a new chat before contacting a mentor."},
                status=409,
            )

        conversation.forwarded_to = mentor
        conversation.human_handoff = True
        conversation.status = "pending"
        conversation.forwarded_at = timezone.now()
        conversation.save(
            update_fields=(
                "forwarded_to",
                "human_handoff",
                "status",
                "forwarded_at",
                "updated_at",
            )
        )
        ChatMessage.objects.create(
            conversation=conversation,
            body=f"This conversation was forwarded to {mentor.user.get_full_name() or 'your mentor'}.",
        )
    return JsonResponse(
        {
            "message": f"Your chat has been forwarded to {mentor.user.get_full_name() or 'your mentor'}.",
            **_chat_thread_payload(conversation, request.user.pk),
        }
    )


@login_required
@require_http_methods(["GET"])
def student_chat_updates(request, conversation_id):
    if _is_admin(request.user):
        return JsonResponse({"error": "Only students can view their chats."}, status=403)
    try:
        student_profile = request.user.profile
    except Profile.DoesNotExist:
        return JsonResponse({"error": "Your student profile could not be found."}, status=403)
    if student_profile.role != Profile.Role.STUDENT:
        return JsonResponse({"error": "Only students can view their chats."}, status=403)
    conversation = ChatConversation.objects.filter(
        pk=conversation_id,
        student=student_profile,
    ).select_related("forwarded_to__user").first()
    if conversation is None:
        return JsonResponse({"error": "Chat not found."}, status=404)
    if conversation.forwarded_to_id:
        conversation.messages.filter(sender__isnull=False).exclude(
            sender=request.user
        ).filter(is_read=False).update(is_read=True)
    return JsonResponse(_chat_thread_payload(conversation, request.user.pk))


@login_required
@require_http_methods(["GET", "POST"])
def staff_results(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned staff profile.")
        return redirect("login")
    if profile.role != Profile.Role.STAFF:
        messages.error(request, "Only staff can publish course results.")
        return redirect("portal")

    if request.method == "POST":
        if request.POST.get("action") == "publish_rate":
            subject = request.POST.get("rate_subject", "").strip()
            raw_percentage = request.POST.get("pass_percentage", "").strip()
            try:
                pass_percentage = Decimal(raw_percentage)
            except InvalidOperation:
                pass_percentage = None
            if not subject or len(subject) > 120 or pass_percentage is None:
                messages.error(request, "Enter a subject and a valid pass percentage.")
            elif not pass_percentage.is_finite() or not Decimal("0") <= pass_percentage <= Decimal("100"):
                messages.error(request, "Pass percentage must be between 0 and 100.")
            else:
                CourseResult.objects.update_or_create(
                    subject=subject,
                    defaults={
                        "pass_percentage": pass_percentage,
                        "published_by": request.user,
                    },
                )
                messages.success(request, f"Published the class pass rate for {subject}.")
                return redirect("staff_results")
            return render(
                request,
                "accounts/staff_results.html",
                {
                    "results": CourseResult.objects.all(),
                    "marks": StudentMark.objects.select_related("student__user", "published_by"),
                    "students": Profile.objects.filter(
                        role=Profile.Role.STUDENT
                    ).select_related("user").order_by("user__last_name", "user__first_name"),
                },
            )

        student_id = request.POST.get("student_id", "").strip()
        subject = request.POST.get("subject", "").strip()
        raw_mark = request.POST.get("mark", "").strip()
        try:
            mark = Decimal(raw_mark)
        except InvalidOperation:
            mark = None
        student = Profile.objects.filter(
            pk=student_id,
            role=Profile.Role.STUDENT,
        ).first() if student_id.isdecimal() else None
        if student is None:
            messages.error(request, "Choose a valid student.")
        elif not subject or len(subject) > 120 or mark is None or not mark.is_finite():
            messages.error(request, "Enter a subject and a valid mark.")
        elif not Decimal("0") <= mark <= Decimal("100"):
            messages.error(request, "Marks must be between 0 and 100.")
        else:
            StudentMark.objects.update_or_create(
                student=student,
                subject__iexact=subject,
                defaults={
                    "student": student,
                    "subject": subject,
                    "mark": mark,
                    "published_by": request.user,
                },
            )
            messages.success(
                request,
                f"Published {subject} mark for {student.user.get_full_name() or student.user.email}.",
            )
            return redirect("staff_results")

    return render(
        request,
        "accounts/staff_results.html",
        {
            "results": CourseResult.objects.all(),
            "marks": StudentMark.objects.select_related("student__user", "published_by"),
            "students": Profile.objects.filter(
                role=Profile.Role.STUDENT
            ).select_related("user").order_by("user__last_name", "user__first_name"),
        },
    )


@login_required
@require_POST
def admin_assign_mentor(request, student_id):
    if not _is_admin(request.user):
        messages.error(request, "Only administrators can assign student mentors.")
        return redirect("portal")
    student = Profile.objects.filter(
        pk=student_id,
        role=Profile.Role.STUDENT,
    ).first()
    if student is None:
        messages.error(request, "Student not found.")
        return redirect("student_directory")

    mentor_id = request.POST.get("mentor_id", "").strip()
    if mentor_id:
        if not mentor_id.isdecimal():
            messages.error(request, "Choose a valid staff mentor.")
            return redirect("student_directory")
        mentor = Profile.objects.filter(
            pk=mentor_id,
            role=Profile.Role.STAFF,
        ).first()
        if mentor is None:
            messages.error(request, "Choose a valid staff mentor.")
            return redirect("student_directory")
        student.mentor = mentor
    else:
        student.mentor = None
    student.save(update_fields=("mentor",))
    messages.success(request, "Student mentor assignment updated.")
    return redirect("student_directory")


@login_required
def message_center(request):
    if _is_admin(request.user):
        conversations = ChatConversation.objects.filter(
            human_handoff=True,
            forwarded_to__isnull=True,
        )
    else:
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            messages.error(request, "Your account has no assigned staff profile.")
            return redirect("login")
        if profile.role != Profile.Role.STAFF:
            messages.error(request, "Only staff and administrators can access the message center.")
            return redirect("portal")
        conversations = ChatConversation.objects.filter(
            human_handoff=True,
            forwarded_to__isnull=True,
        ).filter(
            Q(student__mentor=profile) | Q(student__mentor__isnull=True)
        )
    conversations = conversations.select_related(
        "student__user",
        "student__mentor__user",
    ).prefetch_related("messages__sender")
    return render(
        request,
        "accounts/message_center.html",
        {"conversations": conversations},
    )


@login_required
@require_POST
def staff_reply_to_chat(request, conversation_id):
    if _is_admin(request.user):
        conversation_scope = ChatConversation.objects.filter(forwarded_to__isnull=True)
    else:
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            messages.error(request, "Your account has no assigned staff profile.")
            return redirect("login")
        if profile.role != Profile.Role.STAFF:
            messages.error(request, "Only staff and administrators can reply to student chats.")
            return redirect("portal")
        conversation_scope = ChatConversation.objects.filter(
            Q(student__mentor=profile) | Q(student__mentor__isnull=True),
            forwarded_to__isnull=True,
        )

    conversation = conversation_scope.filter(
        pk=conversation_id,
        human_handoff=True,
    ).first()
    if conversation is None:
        messages.error(request, "Conversation not found or not assigned to your staff inbox.")
        return redirect("message_center")
    body = request.POST.get("body", "").strip()
    if not body or len(body) > 4000:
        messages.error(request, "Enter a reply of up to 4,000 characters.")
        return redirect("message_center")

    ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user,
        body=body,
    )
    conversation.save(update_fields=("updated_at",))
    messages.success(request, "Your reply was sent.")
    return redirect("message_center")


@login_required
def mentor_dashboard(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        mentor_profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned staff profile.")
        return redirect("login")
    if mentor_profile.role != Profile.Role.STAFF:
        messages.error(request, "Only staff mentors can access the mentor dashboard.")
        return redirect("portal")

    conversations = list(
        ChatConversation.objects.filter(forwarded_to=mentor_profile)
        .select_related("student__user", "forwarded_to__user")
        .annotate(
            unread_count=Count(
                "messages",
                filter=Q(
                    messages__sender_id=F("student__user_id"),
                    messages__is_read=False,
                ),
                distinct=True,
            )
        )
    )
    requested_id = request.GET.get("chat_id", "")
    selected_conversation = None
    if requested_id.isdecimal():
        selected_conversation = next(
            (chat for chat in conversations if chat.pk == int(requested_id)),
            None,
        )
    if selected_conversation is None:
        selected_conversation = next(
            (chat for chat in conversations if chat.status != "closed"),
            conversations[0] if conversations else None,
        )
    return render(
        request,
        "accounts/mentor_dashboard.html",
        {
            "conversations": conversations,
            "selected_conversation": selected_conversation,
        },
    )


@login_required
@require_http_methods(["GET"])
def mentor_chat_updates(request, conversation_id):
    if _is_admin(request.user):
        return JsonResponse({"error": "Only assigned staff mentors can view forwarded chats."}, status=403)
    try:
        mentor_profile = request.user.profile
    except Profile.DoesNotExist:
        return JsonResponse({"error": "Your staff profile could not be found."}, status=403)
    if mentor_profile.role != Profile.Role.STAFF:
        return JsonResponse({"error": "Only assigned staff mentors can view forwarded chats."}, status=403)

    conversation = ChatConversation.objects.filter(
        pk=conversation_id,
        forwarded_to=mentor_profile,
    ).select_related("student__user").first()
    if conversation is None:
        return JsonResponse({"error": "This chat is not assigned to your mentor account."}, status=404)
    conversation.messages.filter(
        sender=conversation.student.user,
        is_read=False,
    ).update(is_read=True)
    return JsonResponse(
        {
            **_chat_thread_payload(conversation, conversation.student.user_id),
            "student_name": (
                conversation.student.user.get_full_name() or "Student"
            ),
            "unread_count": 0,
        }
    )


@login_required
@require_POST
def mentor_chat_reply(request, conversation_id):
    wants_json = "application/json" in request.headers.get("Accept", "")
    if _is_admin(request.user):
        return JsonResponse({"error": "Only assigned staff mentors can reply to forwarded chats."}, status=403)
    try:
        mentor_profile = request.user.profile
    except Profile.DoesNotExist:
        return JsonResponse({"error": "Your staff profile could not be found."}, status=403)
    if mentor_profile.role != Profile.Role.STAFF:
        return JsonResponse({"error": "Only assigned staff mentors can reply to forwarded chats."}, status=403)

    conversation = ChatConversation.objects.filter(
        pk=conversation_id,
        forwarded_to=mentor_profile,
    ).select_related("student__user").first()
    if conversation is None:
        return JsonResponse({"error": "This chat is not assigned to your mentor account."}, status=404)
    if conversation.status == "closed":
        return JsonResponse({"error": "This chat is closed."}, status=409)

    if request.POST.get("action") == "close":
        conversation.status = "closed"
        conversation.save(update_fields=("status", "updated_at"))
        message = "Chat closed."
    else:
        body = request.POST.get("body", "").strip()
        if not body or len(body) > 4000:
            if wants_json:
                return JsonResponse(
                    {"error": "Enter a reply of up to 4,000 characters."},
                    status=400,
                )
            messages.error(request, "Enter a reply of up to 4,000 characters.")
            return redirect(f"{reverse('mentor_dashboard')}?chat_id={conversation.pk}")
        ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            body=body,
        )
        conversation.status = "replied"
        conversation.save(update_fields=("status", "updated_at"))
        message = "Your reply was sent."

    if wants_json:
        return JsonResponse(
            {
                "message": message,
                **_chat_thread_payload(conversation, conversation.student.user_id),
            }
        )
    messages.success(request, message)
    return redirect(f"{reverse('mentor_dashboard')}?chat_id={conversation.pk}")


@login_required
@require_http_methods(["GET", "POST"])
def attendance_mark(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned staff profile.")
        return redirect("login")
    if profile.role != Profile.Role.STAFF:
        messages.error(request, "Only staff can mark attendance.")
        return redirect("portal")

    selected_date = timezone.localdate()
    if request.method == "POST":
        try:
            selected_date = date.fromisoformat(request.POST.get("date", ""))
        except ValueError:
            messages.error(request, "Choose a valid attendance date.")
            students = _attendance_students(timezone.localdate())
            return render(
                request,
                "accounts/attendance.html",
                {"students": students, "selected_date": timezone.localdate()},
            )

        students = list(
            Profile.objects.filter(role=Profile.Role.STUDENT)
            .select_related("user")
            .order_by("user__last_name", "user__first_name")
        )
        present_ids = set(request.POST.getlist("present_students"))
        with transaction.atomic():
            for student in students:
                Attendance.objects.update_or_create(
                    student=student,
                    date=selected_date,
                    defaults={
                        "is_present": str(student.pk) in present_ids,
                        "marked_by": request.user,
                    },
                )
        messages.success(request, f"Attendance saved for {selected_date:%d %b %Y}.")
        return redirect(f"{request.path}?date={selected_date.isoformat()}")

    raw_date = request.GET.get("date")
    if raw_date:
        try:
            selected_date = date.fromisoformat(raw_date)
        except ValueError:
            messages.error(request, "Choose a valid attendance date.")
    students = _attendance_students(selected_date)
    return render(
        request,
        "accounts/attendance.html",
        {"students": students, "selected_date": selected_date},
    )


def _attendance_students(selected_date):
    students = list(
        Profile.objects.filter(role=Profile.Role.STUDENT)
        .select_related("user")
        .order_by("user__last_name", "user__first_name")
    )
    records = {
        record.student_id: record.is_present
        for record in Attendance.objects.filter(
            date=selected_date,
            student__in=students,
        )
    }
    for student in students:
        student.is_present_for_date = records.get(student.pk, False)
        student.has_attendance_for_date = student.pk in records
    return students


@login_required
def staff_dashboard(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned staff profile.")
        return redirect("login")
    if profile.role != Profile.Role.STAFF:
        messages.error(request, "Only staff can access the staff dashboard.")
        return redirect("portal")
    return render(
        request,
        "accounts/staff_dashboard.html",
        {
            "student_count": Profile.objects.filter(role=Profile.Role.STUDENT).count(),
            "assignment_count": Assignment.objects.count(),
            "result_count": CourseResult.objects.count(),
            "message_count": ChatConversation.objects.filter(
                human_handoff=True,
                forwarded_to__isnull=True,
            ).filter(
                Q(student__mentor=profile) | Q(student__mentor__isnull=True)
            ).count(),
        },
    )


@login_required
def staff_students(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned staff profile.")
        return redirect("login")
    if profile.role != Profile.Role.STAFF:
        messages.error(request, "Only staff can view student details.")
        return redirect("portal")

    students = Profile.objects.filter(role=Profile.Role.STUDENT).select_related("user").annotate(
        attendance_total=Count("attendance_records"),
        attendance_present=Count(
            "attendance_records",
            filter=Q(attendance_records__is_present=True),
        ),
    ).order_by("user__last_name", "user__first_name")
    for student in students:
        student.attendance_percentage = (
            student.attendance_present * 100 / student.attendance_total
            if student.attendance_total
            else 0
        )
    return render(request, "accounts/staff_students.html", {"students": students})


@login_required
@require_http_methods(["GET", "POST"])
def staff_assignments(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned staff profile.")
        return redirect("login")
    if profile.role != Profile.Role.STAFF:
        messages.error(request, "Only staff can manage assignments.")
        return redirect("portal")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        raw_due_date = request.POST.get("due_date", "")
        try:
            due_date = date.fromisoformat(raw_due_date)
        except ValueError:
            due_date = None
        if not title or not description or due_date is None:
            messages.error(request, "Enter an assignment title, description, and valid due date.")
        else:
            with transaction.atomic():
                assignment = Assignment.objects.create(
                    title=title,
                    description=description,
                    due_date=due_date,
                    created_by=request.user,
                )
                AssignmentCompletion.objects.bulk_create(
                    [
                        AssignmentCompletion(
                            assignment=assignment,
                            student=student,
                            updated_by=request.user,
                        )
                        for student in Profile.objects.filter(role=Profile.Role.STUDENT)
                    ]
                )
            messages.success(request, "Assignment created.")
            return redirect("staff_assignment_detail", assignment_id=assignment.pk)

    assignments = Assignment.objects.select_related("created_by")
    return render(
        request,
        "accounts/staff_assignments.html",
        {"assignments": assignments},
    )


@login_required
@require_http_methods(["GET", "POST"])
def staff_assignment_detail(request, assignment_id):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned staff profile.")
        return redirect("login")
    if profile.role != Profile.Role.STAFF:
        messages.error(request, "Only staff can update assignment completion.")
        return redirect("portal")

    assignment = Assignment.objects.filter(pk=assignment_id).first()
    if assignment is None:
        messages.error(request, "Assignment not found.")
        return redirect("staff_assignments")

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            assignment.delete()
            messages.success(request, "Assignment deleted.")
            return redirect("staff_assignments")

        if request.POST.get("action") == "edit_assignment":
            title = request.POST.get("title", "").strip()
            description = request.POST.get("description", "").strip()
            raw_due_date = request.POST.get("due_date", "")
            try:
                due_date = date.fromisoformat(raw_due_date)
            except ValueError:
                due_date = None
            if not title or not description or due_date is None:
                messages.error(request, "Enter an assignment title, description, and valid due date.")
            else:
                assignment.title = title
                assignment.description = description
                assignment.due_date = due_date
                assignment.save(update_fields=("title", "description", "due_date"))
                messages.success(request, "Assignment updated.")
                return redirect("staff_assignment_detail", assignment_id=assignment.pk)

        students = Profile.objects.filter(role=Profile.Role.STUDENT)
        completed_ids = set(request.POST.getlist("completed_students"))
        with transaction.atomic():
            for student in students:
                AssignmentCompletion.objects.update_or_create(
                    assignment=assignment,
                    student=student,
                    defaults={
                        "is_completed": str(student.pk) in completed_ids,
                        "updated_by": request.user,
                    },
                )
        messages.success(request, "Student completion statuses saved.")
        return redirect("staff_assignment_detail", assignment_id=assignment.pk)

    students = list(
        Profile.objects.filter(role=Profile.Role.STUDENT)
        .select_related("user")
        .order_by("user__last_name", "user__first_name")
    )
    records = {
        completion.student_id: completion.is_completed
        for completion in AssignmentCompletion.objects.filter(assignment=assignment)
    }
    for student in students:
        student.is_completed = records.get(student.pk, False)
    return render(
        request,
        "accounts/staff_assignment_detail.html",
        {"assignment": assignment, "students": students},
    )


@login_required
@require_POST
def student_send_message(request):
    if _is_admin(request.user):
        return redirect("home")
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your account has no assigned student profile.")
        return redirect("login")
    if profile.role != Profile.Role.STUDENT:
        messages.error(request, "Only students can send messages to the administrator.")
        return redirect("portal")

    subject = request.POST.get("subject", "").strip()
    body = request.POST.get("body", "").strip()
    if not subject or len(subject) > 200 or not body:
        messages.error(request, "Enter a subject (up to 200 characters) and a message.")
        return redirect("portal")

    student_message = StudentMessage.objects.create(
        sender=profile,
        subject=subject,
        body=body,
    )
    admin_email = (
        User.objects.filter(is_superuser=True)
        .exclude(email="")
        .values_list("email", flat=True)
        .first()
        or settings.COLLEGE_ADMIN_EMAIL
    )
    email_body = (
        f"From: {request.user.get_full_name() or request.user.email}\n"
        f"Email: {request.user.email}\n"
        f"Department: {profile.department}\n\n{body}"
    )
    try:
        send_mail(
            subject,
            email_body,
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
            fail_silently=False,
        )
    except (OSError, SMTPException):
        messages.warning(
            request,
            "Your message was saved in the administrator inbox, but the email notification could not be sent.",
        )
    else:
        messages.success(request, "Your message was sent to the administrator.")
    return redirect("portal")


@login_required
@require_POST
def admin_mark_message_read(request, message_id):
    if not _is_admin(request.user):
        messages.error(request, "Only administrators can access the message inbox.")
        return redirect("portal")
    message = StudentMessage.objects.filter(pk=message_id).first()
    if message is None:
        messages.error(request, "Message not found.")
    else:
        message.is_read = True
        message.save(update_fields=("is_read",))
        messages.success(request, "Message marked as read.")
    return redirect("admin_inbox")


@login_required
def admin_inbox(request):
    if not _is_admin(request.user):
        messages.error(request, "Only administrators can access the message inbox.")
        return redirect("portal")
    return render(
        request,
        "accounts/admin_inbox.html",
        {
            "student_messages": StudentMessage.objects.select_related(
                "sender__user"
            ).all(),
            "membership_requests": MembershipRequest.objects.all(),
        },
    )


@login_required
@require_POST
def admin_review_membership_request(request, request_id):
    if not _is_admin(request.user):
        messages.error(request, "Only administrators can review membership requests.")
        return redirect("portal")

    application = MembershipRequest.objects.filter(pk=request_id).first()
    if application is None:
        messages.error(request, "Membership request not found.")
        return redirect("admin_inbox")

    action = request.POST.get("action")
    if action == "decline":
        application.delete()
        messages.success(request, "Membership request declined and removed.")
        return redirect("admin_inbox")
    if action != "approve":
        messages.error(request, "Choose approve or decline for this request.")
        return redirect("admin_inbox")

    password = request.POST.get("password", "")
    if User.objects.filter(email__iexact=application.email).exists():
        messages.error(request, "An account already uses this email; the request was not approved.")
        return redirect("admin_inbox")
    first_name, last_name = _full_name_parts(application.full_name)
    candidate_user = User(
        username=f"member-{uuid4().hex}",
        email=application.email,
        first_name=first_name,
        last_name=last_name,
    )
    try:
        validate_password(password, user=candidate_user)
    except ValidationError as error:
        for validation_error in error.messages:
            messages.error(request, validation_error)
        return redirect("admin_inbox")

    with transaction.atomic():
        candidate_user.set_password(password)
        candidate_user.save()
        Profile.objects.create(
            user=candidate_user,
            role=application.role,
            department=application.department,
            phone=application.phone,
        )
        application.delete()
    messages.success(
        request,
        f"Approved {candidate_user.get_full_name()}. Provide the password you entered to the applicant securely.",
    )
    return redirect("admin_inbox")
