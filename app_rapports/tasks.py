from celery import shared_task
from django.utils import timezone
from io import BytesIO
import pandas as pd

from .models import (
    SqlQuery,
    Report,
    ReportExecutionLog,
    ReportQueryParameter,
    ReportEmail,   # ✅ NOUVEAU
)
from .utils import execute_sql_on_remote, send_report_email


# =====================================================
# 🔹 Exécution d'une requête SQL simple (SANS paramètres)
# =====================================================
# @shared_task(
#     bind=True,
#     autoretry_for=(Exception,),
#     retry_kwargs={"countdown": 15, "max_retries": 3},
# )
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={
        "countdown": 1800,  #  30 minutes
        "max_retries": 3,   #  3 tentatives
    },
)
def execute_sql_query_task(self, query_id):
    query = SqlQuery.objects.get(id=query_id)

    try:
        df = execute_sql_on_remote(
            query.database,
            query.sql_text
        )

        if df.empty:
            raise ValueError("La requête SQL n'a retourné aucune donnée.")

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Résultats")
        output.seek(0)

        attachments = [{
            "filename": f"{query.name}.xlsx",
            "content": output.getvalue(),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }]


        raise ValueError(
            "Aucun destinataire TO défini pour l’exécution de requête seule."
        )

    except Exception as e:
        ReportExecutionLog.objects.create(
            report=None,
            query=query,
            status="error",
            message=str(e),
        )
        raise


# =====================================================
# 🔹 Exécution d’un RAPPORT (PLUSIEURS REQUÊTES + PARAMÈTRES)
# =====================================================
# @shared_task(
#     bind=True,
#     autoretry_for=(Exception,),
#     retry_kwargs={"countdown": 30, "max_retries": 3},
# )

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={
        "countdown": 1800,  #  30 minutes
        "max_retries": 3,   #  3 tentatives
    },
)
def execute_report_task(self, report_id):

    report = Report.objects.get(id=report_id)

    # 🔥 LOG GLOBAL : DÉMARRAGE
    ReportExecutionLog.objects.create(
        report=report,
        query=None,
        status="success",
        message="Démarrage de l’exécution du rapport",
    )

    if not report.queries.exists():
        ReportExecutionLog.objects.create(
            report=report,
            query=None,
            status="error",
            message="Aucune requête associée au rapport",
        )
        return

    attachments = []
    has_error = False

    # =================================================
    # 1️⃣ Exécution des requêtes
    # =================================================
    for query in report.queries.all():
        try:
            # ✅ PARAMÈTRES LIÉS AU RAPPORT + REQUÊTE
            params = {
                p.name: p.value
                for p in ReportQueryParameter.objects.filter(
                    report=report,
                    query=query
                )
            }

            df = execute_sql_on_remote(
                query.database,
                query.sql_text,
                params
            )

            if df.empty:
                df = pd.DataFrame({
                    "INFO": [f"Aucune donnée retournée pour la requête : {query.name}"]
                })

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Résultats")
            output.seek(0)

            attachments.append({
                "filename": f"{query.name}.xlsx",
                "content": output.getvalue(),
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            })

            # ✅ LOG REQUÊTE OK
            ReportExecutionLog.objects.create(
                report=report,
                query=query,
                status="success",
                message="Requête exécutée avec succès",
            )

        except Exception as e:
            has_error = True

            # ❌ LOG REQUÊTE ERREUR
            ReportExecutionLog.objects.create(
                report=report,
                query=query,
                status="error",
                message=str(e),
            )

            attachments.append({
                "filename": f"{query.name}_ERREUR.txt",
                "content": str(e).encode("utf-8"),
                "mimetype": "text/plain",
            })

    # =================================================
    # 2️⃣ Récupération TO / CC (NOUVELLE LOGIQUE)
    # =================================================
    to_emails = list(
        ReportEmail.objects.filter(
            report=report,
            email_type="to"
        ).values_list("email", flat=True)
    )

    cc_emails = list(
        ReportEmail.objects.filter(
            report=report,
            email_type="cc"
        ).values_list("email", flat=True)
    )

    if not to_emails:
        has_error = True
        ReportExecutionLog.objects.create(
            report=report,
            query=None,
            status="error",
            message="Aucun destinataire TO défini pour le rapport",
        )
    else:
        try:
            send_report_email(
                subject=report.subject or f"Rapport : {report.name}",
                body=report.message or "Veuillez trouver les rapports en pièces jointes.",
                to_emails=to_emails,
                cc_emails=cc_emails,
                attachments=attachments,
            )

            # ✅ LOG GLOBAL EMAIL OK
            ReportExecutionLog.objects.create(
                report=report,
                query=None,
                status="success",
                message="Rapport envoyé par email avec succès",
            )

        except Exception as e:
            has_error = True
            ReportExecutionLog.objects.create(
                report=report,
                query=None,
                status="error",
                message=f"Erreur lors de l’envoi email : {str(e)}",
            )
            raise

    # =================================================
    # 3️⃣ FIN
    # =================================================
    report.last_executed_at = timezone.now()
    report.save(update_fields=["last_executed_at"])

    return (
        f"Rapport '{report.name}' exécuté avec erreurs"
        if has_error
        else f"Rapport '{report.name}' exécuté avec succès"
    )
