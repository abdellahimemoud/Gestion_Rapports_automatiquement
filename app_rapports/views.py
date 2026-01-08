from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import json
import pymysql
import zipfile
from io import BytesIO 


from .models import (
    DatabaseConnection,
    SqlQuery,
    EmailContact,
    Report,
    ReportExecutionLog
)
from .forms import DatabaseForm, QueryForm, ReportForm
from .utils import (
    execute_sql_on_remote,
    df_to_excel_bytes,
    send_report_email
)

from django_celery_beat.models import (
    PeriodicTask,
    CrontabSchedule,
    ClockedSchedule,
)

import pymysql
import psycopg2
import cx_Oracle

# ==========================================================
# ACCUEIL
# ==========================================================
def home(request):
    return render(request, "app_rapports/home.html")


# ==========================================================
# BASES DE DONNÉES
# ==========================================================
def db_list(request):
    return render(
        request,
        "app_rapports/db_list.html",
        {"dbs": DatabaseConnection.objects.all()},
    )


def db_create(request):
    form = DatabaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Base de données créée avec succès")
        return redirect("db_list")
    return render(request, "app_rapports/db_create.html", {"form": form})


def test_db_connection(request, db_id):
    db = get_object_or_404(DatabaseConnection, id=db_id)

    try:
        # ======================
        # MYSQL
        # ======================
        if db.db_type == "mysql":
            conn = pymysql.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                database=db.database_name,
                port=int(db.port),
                connect_timeout=3,
            )

        # ======================
        # POSTGRESQL
        # ======================
        elif db.db_type == "postgres":
            conn = psycopg2.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                dbname=db.database_name,
                port=int(db.port),
                connect_timeout=3,
            )

        # ======================
        # ORACLE (SERVICE_NAME)
        # ======================
        elif db.db_type == "oracle":
            dsn = cx_Oracle.makedsn(
                db.host,
                int(db.port),
                service_name=db.database_name,  # 🔥 SERVICE_NAME
            )

            conn = cx_Oracle.connect(
                user=db.user,
                password=db.password or "",
                dsn=dsn,
                encoding="UTF-8",
            )

        else:
            return JsonResponse({"success": False})

        conn.close()
        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)  # utile en debug
        })



# ==========================================================
# REQUÊTES SQL
# ==========================================================
def query_list(request):
    return render(
        request,
        "app_rapports/query_list.html",
        {"queries": SqlQuery.objects.all().order_by("-created_at")},
    )


def query_create(request):
    form = QueryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Requête SQL créée avec succès")
        return redirect("query_list")
    return render(request, "app_rapports/query_create.html", {"form": form})


def query_run(request, qid):
    query = get_object_or_404(SqlQuery, id=qid)

    df = execute_sql_on_remote(query.database, query.sql_text)
    excel_bytes = df_to_excel_bytes(df)

    attachments = [{
        "filename": f"{query.name}.xlsx",
        "content": excel_bytes,
        "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }]

    send_report_email(
        subject=f"Résultat : {query.name}",
        body="Veuillez trouver le rapport en pièce jointe.",
        to_emails=[e.email for e in query.emails.all()],
        attachments=attachments,
    )

    messages.success(request, f"Requête '{query.name}' exécutée et envoyée")
    return redirect("query_list")


def query_download(request, qid):
    query = get_object_or_404(SqlQuery, id=qid)

    df = execute_sql_on_remote(query.database, query.sql_text)
    excel_bytes = df_to_excel_bytes(df)

    filename = f"{query.name}_{timezone.now():%Y%m%d%H%M%S}.xlsx"

    response = HttpResponse(
        excel_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ==========================================================
# RAPPORTS
# ==========================================================
def report_list(request):
    q = request.GET.get("q", "").strip()

    reports = Report.objects.all().order_by("-created_at")

    if q:
        reports = reports.filter(code__icontains=q)

    context = {
        "reports": reports,
        "q": q,
    }
    return render(request, "app_rapports/report_list.html", context)

def report_detail(request, rid):
    report = get_object_or_404(Report, id=rid)
    return render(
        request,
        "app_rapports/report_detail.html",
        {"report": report},
    )


# ==========================================================
# LOGS D’EXÉCUTION
# ==========================================================
def report_logs(request, rid):
    report = get_object_or_404(Report, id=rid)
    logs = report.logs.all().order_by("-created_at")
    return render(
        request,
        "app_rapports/report_logs.html",
        {"report": report, "logs": logs},
    )


# ==========================================================
# CRÉATION RAPPORT + PLANIFICATION
# ==========================================================
def report_create(request):
    form = ReportForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        report = form.save()
        report.queries.set(form.cleaned_data["queries"])
        report.to_emails.set(form.cleaned_data["to_emails"])
        report.cc_emails.set(form.cleaned_data["cc_emails"])

        # ⏰ Exécution unique
        if not report.is_periodic and report.execute_at:
            clocked, _ = ClockedSchedule.objects.get_or_create(
                clocked_time=report.execute_at
            )
            PeriodicTask.objects.create(
                clocked=clocked,
                one_off=True,
                name=f"Report-{report.id}",
                task="app_rapports.tasks.execute_report_task",
                args=json.dumps([report.id]),
            )

        # 🔁 Exécution périodique
        if report.is_periodic:
            schedule = _create_crontab_schedule(form.cleaned_data)
            PeriodicTask.objects.create(
                crontab=schedule,
                name=f"Report-{report.id}",
                task="app_rapports.tasks.execute_report_task",
                args=json.dumps([report.id]),
                enabled=True,
            )

        messages.success(request, "Rapport créé et planifié avec succès")
        return redirect("report_list")

    return render(request, "app_rapports/report_create.html", {"form": form})


# ==========================================================
# EXÉCUTION IMMÉDIATE (Celery)
# ==========================================================
def report_execute(request, rid):
    report = get_object_or_404(Report, id=rid)
    from .tasks import execute_report_task

    execute_report_task.delay(report.id)
    messages.success(request, f"Rapport '{report.name}' exécuté")
    return redirect("report_list")


# ==========================================================
# TÉLÉCHARGEMENT RAPPORT (1 Excel ou ZIP)
# ==========================================================
def report_download(request, rid):
    report = get_object_or_404(Report, id=rid)
    queries = report.queries.all()

    # 🔹 CAS 1 : une seule requête → Excel direct
    if queries.count() == 1:
        q = queries.first()
        df = execute_sql_on_remote(q.database, q.sql_text)
        excel_bytes = df_to_excel_bytes(df)

        filename = f"{report.name}_{timezone.now():%Y%m%d%H%M%S}.xlsx"

        response = HttpResponse(
            excel_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    # 🔹 CAS 2 : plusieurs requêtes → ZIP
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for q in queries:
            df = execute_sql_on_remote(q.database, q.sql_text)
            excel_bytes = df_to_excel_bytes(df)

            excel_name = f"{q.name}.xlsx"
            zip_file.writestr(excel_name, excel_bytes)

    zip_buffer.seek(0)

    zip_filename = f"{report.name}_{timezone.now():%Y%m%d%H%M%S}.zip"

    response = HttpResponse(
        zip_buffer.getvalue(),
        content_type="application/zip",
    )
    response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
    return response


# ==========================================================
# CRONTAB HELPER
# ==========================================================
def _create_crontab_schedule(data):
    hour = data["periodic_time"].hour
    minute = data["periodic_time"].minute
    tz = timezone.get_current_timezone_name()

    if data["periodic_type"] == "daily":
        return CrontabSchedule.objects.create(
            minute=minute,
            hour=hour,
            timezone=tz,
        )

    if data["periodic_type"] == "weekly":
        return CrontabSchedule.objects.create(
            minute=minute,
            hour=hour,
            day_of_week=data["periodic_weekday"],
            timezone=tz,
        )

    if data["periodic_type"] == "monthly":
        return CrontabSchedule.objects.create(
            minute=minute,
            hour=hour,
            day_of_month=data["periodic_monthday"],
            timezone=tz,
        )
