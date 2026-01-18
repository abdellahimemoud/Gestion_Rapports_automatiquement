from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("app_rapports", "0017_reportemail_remove_report_cc_emails_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE APP_RAPPORTS_REPORT_TO_EMAILS CASCADE CONSTRAINTS",
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[],
            hints={"ignore_errors": True},
        ),
    ]
