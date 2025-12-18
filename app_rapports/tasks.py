from celery import shared_task
from .models import SqlQuery
from .utils import execute_sql_on_remote, df_to_excel_bytes, send_report_email

@shared_task(bind=True)
def execute_sql_query_task(self, query_id):
    query = SqlQuery.objects.get(id=query_id)

    # 1. Exécuter la requête
    df = execute_sql_on_remote(query.database, query.sql_text)

    # 2. Convertir en Excel
    excel_bytes = df_to_excel_bytes(df)

    # 3. Emails sélectionnés
    to_emails = [e.email for e in query.emails.all()]

    if not to_emails:
        raise ValueError("Aucun email sélectionné")

    # 4. Envoyer email
    send_report_email(
        subject=query.subject,
        body=query.message or "Veuillez trouver le rapport en pièce jointe.",
        to_emails=to_emails,
        excel_bytes=excel_bytes,
        filename=f"{query.name}.xlsx"
    )

    return "Email envoyé avec succès"
