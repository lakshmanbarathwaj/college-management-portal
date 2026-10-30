from django.db import migrations, models


def set_computer_science_department(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    Profile.objects.all().update(department="B.Sc. Computer Science")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_attendance"),
    ]

    operations = [
        migrations.RenameField(
            model_name="profile",
            old_name="department_or_grade",
            new_name="department",
        ),
        migrations.AlterField(
            model_name="profile",
            name="department",
            field=models.CharField(
                choices=[("B.Sc. Computer Science", "B.Sc. Computer Science")],
                default="B.Sc. Computer Science",
                max_length=100,
            ),
        ),
        migrations.RunPython(
            set_computer_science_department,
            migrations.RunPython.noop,
        ),
    ]
