from datetime import time

from django.db import migrations, models


def copy_existing_window(apps, schema_editor):
    AgentSettings = apps.get_model("agent", "AgentSettings")
    for settings in AgentSettings.objects.all():
        start = settings.session_window_start
        end = settings.session_window_end
        settings.window_one_start = start
        settings.window_one_end = end
        settings.window_two_start = time(hour=13, minute=0)
        settings.window_two_end = time(hour=17, minute=0)
        settings.window_three_start = time(hour=18, minute=0)
        settings.window_three_end = time(hour=22, minute=0)
        settings.save(
            update_fields=[
                "window_one_start",
                "window_one_end",
                "window_two_start",
                "window_two_end",
                "window_three_start",
                "window_three_end",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentsettings",
            name="window_one_end",
            field=models.TimeField(help_text="Daily window #1 end time", null=True),
        ),
        migrations.AddField(
            model_name="agentsettings",
            name="window_one_start",
            field=models.TimeField(help_text="Daily window #1 start time", null=True),
        ),
        migrations.AddField(
            model_name="agentsettings",
            name="window_three_end",
            field=models.TimeField(help_text="Daily window #3 end time", null=True),
        ),
        migrations.AddField(
            model_name="agentsettings",
            name="window_three_start",
            field=models.TimeField(help_text="Daily window #3 start time", null=True),
        ),
        migrations.AddField(
            model_name="agentsettings",
            name="window_two_end",
            field=models.TimeField(help_text="Daily window #2 end time", null=True),
        ),
        migrations.AddField(
            model_name="agentsettings",
            name="window_two_start",
            field=models.TimeField(help_text="Daily window #2 start time", null=True),
        ),
        migrations.RunPython(copy_existing_window, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="agentsettings",
            name="window_one_end",
            field=models.TimeField(help_text="Daily window #1 end time"),
        ),
        migrations.AlterField(
            model_name="agentsettings",
            name="window_one_start",
            field=models.TimeField(help_text="Daily window #1 start time"),
        ),
        migrations.AlterField(
            model_name="agentsettings",
            name="window_three_end",
            field=models.TimeField(help_text="Daily window #3 end time"),
        ),
        migrations.AlterField(
            model_name="agentsettings",
            name="window_three_start",
            field=models.TimeField(help_text="Daily window #3 start time"),
        ),
        migrations.AlterField(
            model_name="agentsettings",
            name="window_two_end",
            field=models.TimeField(help_text="Daily window #2 end time"),
        ),
        migrations.AlterField(
            model_name="agentsettings",
            name="window_two_start",
            field=models.TimeField(help_text="Daily window #2 start time"),
        ),
        migrations.RemoveField(
            model_name="agentsettings",
            name="session_window_end",
        ),
        migrations.RemoveField(
            model_name="agentsettings",
            name="session_window_start",
        ),
    ]
