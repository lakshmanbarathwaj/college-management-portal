from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile


DEMO_PASSWORD = "CampusDemo2026!"


class Command(BaseCommand):
    help = "Create the administrator and B.Sc. Computer Science demo accounts."

    @transaction.atomic
    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@college.edu",
                "first_name": "Kalloori",
                "last_name": "Nirvaagi",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password(DEMO_PASSWORD)
            admin.save()
        elif not admin.is_superuser:
            self.stdout.write(
                self.style.WARNING(
                    "Existing 'admin' account is not a superuser; it was left unchanged."
                )
            )
        else:
            admin.email = "admin@college.edu"
            admin.first_name = "Kalloori"
            admin.last_name = "Nirvaagi"
            admin.save(update_fields=("email", "first_name", "last_name"))

        department = "B.Sc. Computer Science"
        staff_names = [
            ("Arun", "Kumar"),
            ("Meenakshi", "Devi"),
            ("Karthik", "Raja"),
            ("Kavya", "Sri"),
            ("Murugan", "Vel"),
        ]
        for index, (first_name, last_name) in enumerate(staff_names, start=1):
            self._create_account(
                email=f"staff{index}@college.edu",
                first_name=first_name,
                last_name=last_name,
                role=Profile.Role.STAFF,
                department=department,
                username=f"staff{index}",
            )

        student_names = [
            ("Aadhavan", "Raj"),
            ("Nila", "Mani"),
            ("Yazhini", "Kumar"),
            ("Iniyan", "Selvan"),
            ("Malar", "Vizhi"),
        ]
        for index, (first_name, last_name) in enumerate(student_names, start=1):
            self._create_account(
                email=f"student{index}@college.edu",
                first_name=first_name,
                last_name=last_name,
                role=Profile.Role.STUDENT,
                department=department,
                username=f"student{index}",
            )

        self.stdout.write(self.style.SUCCESS("Demo accounts are ready."))
        self.stdout.write(f"Demo password for all demo accounts: {DEMO_PASSWORD}")
        self.stdout.write("Administrator: admin@college.edu")

    def _create_account(self, *, email, first_name, last_name, role, department, username):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        else:
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=("email", "first_name", "last_name"))

        Profile.objects.update_or_create(
            user=user,
            defaults={"role": role, "department": department},
        )
