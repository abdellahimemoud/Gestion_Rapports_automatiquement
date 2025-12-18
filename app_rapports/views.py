from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages

import json
import pymysql

from .models import DatabaseConnection, SqlQuery, EmailContact
from .forms import DatabaseForm, QueryForm
from .tasks import execute_sql_query_task
from .utils import execute_sql_on_remote, df_to_excel_bytes, send_report_email

from django_celery_beat.models import PeriodicTask, CrontabSchedule
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


# =====================================================================
# PAGE D’ACCUEIL
# =====================================================================
def home(request):
    return render(request, "app_rapports/home.html")


# =====================================================================
# BASES DE DONNÉES
# =====================================================================
def db_list(request):
    return render(
        request,
        "app_rapports/db_list.html",
        {"dbs": DatabaseConnection.objects.all()}
    )


def db_create(request):
    if request.method == "POST":
        form = DatabaseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Base de données créée avec succès ")
            return redirect("db_list")
        else:
            messages.error(request, "Formulaire invalide. Veuillez corriger les erreurs ")
    else:
        form = DatabaseForm()

    return render(request, "app_rapports/db_create.html", {"form": form})


# =====================================================================
# TEST CONNEXION MYSQL
# =====================================================================
def test_db_connection(request, db_id):
    db = get_object_or_404(DatabaseConnection, id=db_id)
    try:
        conn = pymysql.connect(
            host=db.host,
            user=db.user,
            password=db.password,
            database=db.database_name,
            port=int(db.port),
            connect_timeout=3,
        )
        conn.close()
        return JsonResponse({"success": True})
    except Exception:
        return JsonResponse({"success": False})


# =====================================================================
# LISTE DES REQUÊTES
# =====================================================================
def query_list(request):
    return render(
        request,
        "app_rapports/query_list.html",
        {"queries": SqlQuery.objects.all().order_by("-created_at")}
    )


# =====================================================================
# CRÉATION + PLANIFICATION
# =====================================================================
def query_create(request):
    if request.method == "POST":
        form = QueryForm(request.POST)

        # 🔴 FORMULAIRE INVALIDE
        if not form.is_valid():
            messages.error(
                request,
                "Formulaire invalide. Corrigez les champs en rouge "
            )
            return render(
                request,
                "app_rapports/query_create.html",
                {"form": form}
            )

        query = form.save(commit=False)

        # ==================================================
        # MODE NON PÉRIODIQUE
        # ==================================================
        if not query.is_periodic:
            execute_at = form.cleaned_data["execute_at"]
            query.execute_at = execute_at
            query.save()

            execute_sql_query_task.apply_async(
                args=[query.id],
                eta=execute_at
            )

        # ==================================================
        # MODE PÉRIODIQUE (CELERY BEAT)
        # ==================================================
        else:
            periodic_type = form.cleaned_data["periodic_type"]
            periodic_time = form.cleaned_data["periodic_time"]
            periodic_weekday = form.cleaned_data["periodic_weekday"]
            periodic_monthday = form.cleaned_data["periodic_monthday"]

            hour = periodic_time.hour
            minute = periodic_time.minute

            if periodic_type == "daily":
                schedule, _ = CrontabSchedule.objects.get_or_create(
                    hour=hour,
                    minute=minute
                )

            elif periodic_type == "weekly":
                schedule, _ = CrontabSchedule.objects.get_or_create(
                    day_of_week=periodic_weekday,
                    hour=hour,
                    minute=minute
                )

            elif periodic_type == "monthly":
                schedule, _ = CrontabSchedule.objects.get_or_create(
                    day_of_month=periodic_monthday,
                    hour=hour,
                    minute=minute
                )

            else:
                messages.error(
                    request,
                    "Type de périodicité invalide "
                )
                return redirect("query_create")

            query.execute_at = timezone.now()
            query.save()

            PeriodicTask.objects.create(
                crontab=schedule,
                name=f"SQL Query {query.id} - {query.name}",
                task="app_rapports.tasks.execute_sql_query_task",
                args=json.dumps([query.id]),
                enabled=True,
            )

        # ==================================================
        # EMAILS
        # ==================================================
        query.emails.set(form.cleaned_data["emails"])

        messages.success(
            request,
            "Requête créée et planifiée avec succès "
        )
        return redirect("query_list")

    return render(
        request,
        "app_rapports/query_create.html",
        {"form": QueryForm()}
    )


# =====================================================================
# TÉLÉCHARGEMENT EXCEL
# =====================================================================
def query_download(request, qid):
    q = get_object_or_404(SqlQuery, id=qid)

    df = execute_sql_on_remote(q.database, q.sql_text)
    excel_bytes = df_to_excel_bytes(df)

    filename = f"{q.name}_{timezone.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    response = HttpResponse(
        excel_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# =====================================================================
# EXÉCUTION MANUELLE
# =====================================================================
def query_run(request, qid):
    q = get_object_or_404(SqlQuery, id=qid)

    df = execute_sql_on_remote(q.database, q.sql_text)
    excel_bytes = df_to_excel_bytes(df)

    emails = [e.email for e in q.emails.all()]
    filename = f"{q.name}_{timezone.now().strftime('%Y%m%d%H%M%S')}.xlsx"

    send_report_email(
        subject=q.subject,
        body=q.message or "Bonjour, veuillez trouver le rapport ci-joint.",
        to_emails=emails,
        excel_bytes=excel_bytes,
        filename=filename
    )

    messages.success(request, "Rapport envoyé par email avec succès ")

    return render(
        request,
        "app_rapports/query_run.html",
        {"name": q.name, "emails": emails}
    )


# =====================================================================
# API AJAX – AJOUT EMAIL
# =====================================================================
def save_email(request):
    if request.method != "POST":
        return JsonResponse({
            "status": "error",
            "message": "Méthode non autorisée "
        })

    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()

        if not email:
            return JsonResponse({
                "status": "error",
                "message": "Veuillez saisir une adresse email "
            })

        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                "status": "error",
                "message": "Adresse email invalide "
            })

        if EmailContact.objects.filter(email__iexact=email).exists():
            return JsonResponse({
                "status": "error",
                "message": "Cet email existe déjà "
            })

        new_email = EmailContact.objects.create(email=email)

        return JsonResponse({
            "status": "success",
            "id": new_email.id,
            "email": new_email.email
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Erreur serveur : {str(e)} "
        })
