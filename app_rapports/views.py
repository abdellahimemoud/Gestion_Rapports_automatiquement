from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

import json
import zipfile
from io import BytesIO

import pymysql
import psycopg2
import cx_Oracle

from django_celery_beat.models import (
    PeriodicTask,
    CrontabSchedule,
    ClockedSchedule,
)

from .models import (
    DatabaseConnection,
    SqlQuery,
    EmailContact,
    Report,
    ReportExecutionLog,
    ReportQueryParameter,
)
from .forms import DatabaseForm, QueryForm, ReportForm
from .utils import (
    execute_sql_on_remote,
    df_to_excel_bytes,
    send_report_email,
    extract_sql_parameters,
)
from .forms import DatabaseConnectionForm 
from .forms import SqlQueryForm
from .forms import ReportForm
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
        if db.db_type == "mysql":
            conn = pymysql.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                database=db.database_name,
                port=int(db.port),
                connect_timeout=3,
            )

        elif db.db_type == "postgres":
            conn = psycopg2.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                dbname=db.database_name,
                port=int(db.port),
                connect_timeout=3,
            )

        elif db.db_type == "oracle":
            dsn = cx_Oracle.makedsn(
                db.host,
                int(db.port),
                service_name=db.database_name,
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
        return JsonResponse({"success": False, "error": str(e)})


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

    send_report_email(
        subject=f"Résultat : {query.name}",
        body="Veuillez trouver le rapport en pièce jointe.",
        to_emails=[e.email for e in query.emails.all()],
        attachments=[{
            "filename": f"{query.name}.xlsx",
            "content": excel_bytes,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }],
    )

    messages.success(request, f"Requête '{query.name}' exécutée")
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


# =====================================================================
# EMAIL AJAX
# =====================================================================
def save_email(request):
    if request.method != "POST":    
        return JsonResponse({"status": "error", "message": "Méthode non autorisée"})
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        if not email:
            return JsonResponse({"status": "error", "message": "Email requis"})
        validate_email(email)
        if EmailContact.objects.filter(email__iexact=email).exists():
            return JsonResponse({"status": "error", "message": "Email déjà existant"})
        contact = EmailContact.objects.create(email=email)
        return JsonResponse({"status": "success", "id": contact.id, "email": contact.email})
    except ValidationError:
        return JsonResponse({"status": "error", "message": "Email invalide"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


# ==========================================================
# RAPPORTS
# ==========================================================
def report_list(request):
    q = request.GET.get("q", "").strip()
    reports = Report.objects.all().order_by("-created_at")

    if q:
        reports = reports.filter(code__icontains=q)

    return render(
        request,
        "app_rapports/report_list.html",
        {"reports": reports, "q": q},
    )


def report_logs(request, rid):
    report = get_object_or_404(Report, id=rid)
    logs = report.logs.all().order_by("-created_at")
    return render(
        request,
        "app_rapports/report_logs.html",
        {"report": report, "logs": logs},
    )


# ==========================================================
# CRÉATION RAPPORT + PARAMÈTRES + PLANIFICATION
# ==========================================================
def report_create(request):
    form = ReportForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.save()

        report.queries.set(form.cleaned_data["queries"])
        report.to_emails.set(form.cleaned_data["to_emails"])
        report.cc_emails.set(form.cleaned_data["cc_emails"])

        # 🔥 Nettoyage des anciens paramètres
        ReportQueryParameter.objects.filter(report=report).delete()

        # ✅ Enregistrement CORRECT des paramètres
        for key, value in request.POST.items():
            if key.startswith("param_") and value:
                try:
                    _, qid, name = key.split("_", 2)
                    ReportQueryParameter.objects.create(
                        report=report,
                        query_id=int(qid),
                        name=name,
                        value=value,
                    )
                except ValueError:
                    continue

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

        messages.success(request, f"Rapport {report.name} créé avec succès")
        return redirect("report_list")

    return render(request, "app_rapports/report_create.html", {"form": form})


# ==========================================================
# EXÉCUTION IMMÉDIATE
# ==========================================================
def report_execute(request, rid):
    report = get_object_or_404(Report, id=rid)
    from .tasks import execute_report_task

    execute_report_task.delay(report.id)
    messages.success(request, f"Rapport {report.name} exécuté")
    return redirect("report_list")


# ==========================================================
# TÉLÉCHARGEMENT RAPPORT
# ==========================================================
def report_download(request, rid):
    report = get_object_or_404(Report, id=rid)
    queries = report.queries.all()

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

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for q in queries:
            df = execute_sql_on_remote(q.database, q.sql_text)
            excel_bytes = df_to_excel_bytes(df)
            zip_file.writestr(f"{q.name}.xlsx", excel_bytes)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = (
        f'attachment; filename="{report.name}_{timezone.now():%Y%m%d%H%M%S}.zip"'
    )
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
            minute=minute, hour=hour, timezone=tz
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


# ==========================================================
# API PARAMÈTRES SQL
# ==========================================================
@require_POST
def query_parameters(request):
    data = json.loads(request.body)
    response = []

    for qid in data.get("query_ids", []):
        query = SqlQuery.objects.get(id=qid)
        params = extract_sql_parameters(query.sql_text)

        for p in params:
            response.append({
                "query_id": query.id,
                "query_name": query.name,
                "param": p,
            })

    return JsonResponse(response, safe=False)


# modifie une base

def db_update(request, pk):
    db = get_object_or_404(DatabaseConnection, pk=pk)

    if request.method == "POST":
        form = DatabaseConnectionForm(request.POST, instance=db)
        if form.is_valid():
            form.save()
            return redirect("db_list")
    else:
        form = DatabaseConnectionForm(instance=db)

    return render(request, "app_rapports/db_create.html", {
        "form": form,
        "edit": True
    })


#  Suppression

def db_delete(request, pk):
    db = get_object_or_404(DatabaseConnection, pk=pk)

    # 🔒 Vérifier si utilisée
    is_used = SqlQuery.objects.filter(database=db).exists()

    if is_used:
        messages.error(
            request,
            " Suppression impossible : cette base est utilisée dans une ou plusieurs requêtes."
        )
        return redirect("db_list")  

    db.delete()
    messages.success(request, " Base supprimée avec succès.")
    return redirect("db_list")


# Modifier une requête
from .forms import SqlQueryForm


def query_update(request, pk):
    query = get_object_or_404(SqlQuery, pk=pk)

    if request.method == "POST":
        form = SqlQueryForm(request.POST, instance=query)
        if form.is_valid():
            form.save()
            return redirect("query_list")
    else:
        form = SqlQueryForm(instance=query)

    return render(request, "app_rapports/query_create.html", {
        "form": form,
        "edit": True
    })


# Supprimer une requête

def query_delete(request, pk):
    query = get_object_or_404(SqlQuery, pk=pk)

    # 🔒 Empêcher suppression si utilisée dans un rapport
    if Report.objects.filter(queries=query).exists():
        messages.error(
            request,
            " Suppression impossible : cette requête est utilisée dans un rapport."
        )
        return redirect("query_list")

    query.delete()
    messages.success(request, " Requête supprimée avec succès.")
    return redirect("query_list")


# Modifier un rapport
def report_update(request, pk):
    report = get_object_or_404(Report, pk=pk)

    if request.method == "POST":
        form = ReportForm(request.POST, instance=report)
        if form.is_valid():
            form.save()
            return redirect("report_list")
    else:
        form = ReportForm(instance=report)

    return render(request, "app_rapports/report_create.html", {
    "form": form,
    "report": report,
    "is_edit": True
})


# Supprimer un rapport
def report_delete(request, pk):
    report = get_object_or_404(Report, pk=pk)

    if request.method == "POST":
        report.delete()
        messages.success(
        request,
        " Le rapport a été supprimé avec succès."
    )
        return redirect("report_list")

    return redirect("report_list")
