from openpyxl.styles import Font
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_POST

import json
from io import BytesIO

import pandas as pd
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
    Report,
    ReportExecutionLog,
    ReportQueryParameter,
    ReportEmail,
)

from .forms import (
    DatabaseForm,
    QueryForm,
    ReportForm,
    DatabaseConnectionForm,
    SqlQueryForm,
)

from .utils import (
    execute_sql_on_remote,
    extract_sql_parameters,
)
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from .models import Report, ReportExecutionLog
  
# =====================================================
# HOME
# =====================================================

@login_required(login_url="login")
def home(request):
    return render(request, "app_rapports/home.html")



# =====================================================
# DATABASES
# =====================================================
@login_required(login_url="login")
def db_list(request):
    return render(
        request,
        "app_rapports/db_list.html",
        {"dbs": DatabaseConnection.objects.all()},
    )

@login_required(login_url="login")
def db_create(request):
    form = DatabaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Base créée avec succès")
        return redirect("db_list")
    return render(request, "app_rapports/db_create.html", {"form": form})

@login_required(login_url="login")
def db_update(request, pk):
    db = get_object_or_404(DatabaseConnection, pk=pk)
    form = DatabaseConnectionForm(request.POST or None, instance=db)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request,f"Base {db.name}  modifiée avec succès")
        return redirect("db_list")
    return render(
        request,
        "app_rapports/db_create.html",
        {"form": form, "edit": True},
    )
@login_required(login_url="login")
def db_delete(request, pk):
    db = get_object_or_404(DatabaseConnection, pk=pk)
    if SqlQuery.objects.filter(database=db).exists():
        messages.error(
            request,
            "Suppression impossible : base utilisée par une ou plusieurs requête ",
        )
        return redirect("db_list")
    db.delete()
    messages.success(request, f"Base  {db.name}  supprimée avec succès")
    return redirect("db_list")

@login_required(login_url="login")
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

# =====================================================
# QUERIES
# =====================================================
@login_required(login_url="login")
def query_list(request):
    return render(
        request,
        "app_rapports/query_list.html",
        {"queries": SqlQuery.objects.all().order_by("-created_at")},
    )
@login_required(login_url="login")
def query_create(request):
    form = QueryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Requête créée avec succès")
        return redirect("query_list")
    return render(request, "app_rapports/query_create.html", {"form": form})

@login_required(login_url="login")
def query_update(request, pk):
    query = get_object_or_404(SqlQuery, pk=pk)
    form = SqlQueryForm(request.POST or None, instance=query)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Requête {query.name}  modifiée avec succès")
        return redirect("query_list")
    return render(
        request,
        "app_rapports/query_create.html",
        {"form": form, "edit": True},
    )

@login_required(login_url="login")
def query_delete(request, pk):
    query = get_object_or_404(SqlQuery, pk=pk)
    if Report.objects.filter(queries=query).exists():
        messages.error(
            request,
            "Suppression impossible : requête utilisée dans un ou plusieurs rapport",
        )
        return redirect("query_list")
    query.delete()
    messages.success(request, f"Requête {query.name} supprimée avec succès")
    return redirect("query_list")


# =====================================================
# REPORTS
# =====================================================
@login_required(login_url="login")
def report_list(request):
    q = request.GET.get("q", "").strip()

    last_global_log = ReportExecutionLog.objects.filter(
        report=OuterRef("pk"),
        query__isnull=True
    ).order_by("-created_at")

    reports = Report.objects.annotate(
        last_log_date=Subquery(last_global_log.values("created_at")[:1]),
        last_log_status=Subquery(last_global_log.values("status")[:1]),
    ).order_by("-created_at")

    if q:
        reports = reports.filter(name__icontains=q)

    return render(
        request,
        "app_rapports/report_list.html",
        {
            "reports": reports,
            "q": q,
        },
    )

@login_required(login_url="login")
def report_logs(request, rid):
    report = get_object_or_404(Report, id=rid)
    logs = report.logs.all().order_by("-created_at")
    return render(
        request,
        "app_rapports/report_logs.html",
        {"report": report, "logs": logs},
    )


# =====================================================
# CREATE REPORT
# =====================================================
@login_required(login_url="login")
def report_create(request):
    form = ReportForm(
    request.POST or None,
    initial={"request": request}
)


    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.save()

        report.queries.set(form.cleaned_data["queries"])

        # ===============================
        # EMAILS (CORRECTION ICI)
        # ===============================
        ReportEmail.objects.filter(report=report).delete()

        to_emails = request.POST.getlist("to_emails[]")
        cc_emails = request.POST.getlist("cc_emails[]")

        for email in to_emails:
            ReportEmail.objects.create(
                report=report,
                email=email,
                email_type="to",
            )

        for email in cc_emails:
            ReportEmail.objects.create(
                report=report,
                email=email,
                email_type="cc",
            )

        # ===============================
        # PARAMÈTRES SQL
        # ===============================
        ReportQueryParameter.objects.filter(report=report).delete()

        for k, v in request.POST.items():
            if k.startswith("param_") and v:
                _, qid, name = k.split("_", 2)
                ReportQueryParameter.objects.create(
                    report=report,
                    query_id=int(qid),
                    name=name,
                    value=v,
                )

        _create_or_update_schedule(report, form.cleaned_data)

        messages.success(request, "Rapport créé avec succès")
        return redirect("report_list")

    return render(
        request,
        "app_rapports/report_create.html",
        {
            "form": form,
            "is_edit": False,
            "to_emails": [],
            "cc_emails": [],
        },
    )


# =====================================================
# UPDATE REPORT
# =====================================================
@login_required(login_url="login")
def report_update(request, pk):
    report = get_object_or_404(Report, pk=pk)
    form = ReportForm(request.POST or None, instance=report)

    # Emails existants (affichage)
    to_emails = ReportEmail.objects.filter(report=report, email_type="to")
    cc_emails = ReportEmail.objects.filter(report=report, email_type="cc")

    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.save()

        # Requêtes associées
        report.queries.set(form.cleaned_data["queries"])

        # ===============================
        # EMAILS TO / CC (CORRIGÉ)
        # ===============================
        ReportEmail.objects.filter(report=report).delete()

        to_emails_post = request.POST.getlist("to_emails[]")
        cc_emails_post = request.POST.getlist("cc_emails[]")

        for email in to_emails_post:
            ReportEmail.objects.create(
                report=report,
                email=email,
                email_type="to",
            )

        for email in cc_emails_post:
            ReportEmail.objects.create(
                report=report,
                email=email,
                email_type="cc",
            )

        # ===============================
        # PARAMÈTRES SQL
        # ===============================
        ReportQueryParameter.objects.filter(report=report).delete()

        for k, v in request.POST.items():
            if k.startswith("param_") and v:
                _, qid, name = k.split("_", 2)
                ReportQueryParameter.objects.create(
                    report=report,
                    query_id=int(qid),
                    name=name,
                    value=v,
                )

        # ===============================
        # PLANIFICATION
        # ===============================
        PeriodicTask.objects.filter(name=f"Report-{report.id}").delete()
        _create_or_update_schedule(report, form.cleaned_data)

        messages.success(request, f"Rapport {report.name} modifié avec succès")
        return redirect("report_list")

    return render(
        request,
        "app_rapports/report_create.html",
        {
            "form": form,
            "report": report,
            "is_edit": True,
            "to_emails": to_emails,
            "cc_emails": cc_emails,
        },
    )



# =====================================================
# DELETE / EXEC / DOWNLOAD
# =====================================================
@login_required(login_url="login")
def report_delete(request, pk):
    report = get_object_or_404(Report, pk=pk)
    report.delete()
    messages.success(request, f"Rapport {report.name} supprimé avec succès")
    return redirect("report_list")

@login_required(login_url="login")
def report_execute(request, rid):
    report = get_object_or_404(Report, id=rid)
    from .tasks import execute_report_task

    execute_report_task.delay(report.id)
    messages.success(request, f"Rapport {report.name}  exécuté avec succès")
    return redirect("report_list")

# ==========================================================
# TÉLÉCHARGEMENT RAPPORT
# ==========================================================
@login_required(login_url="login")
def report_download(request, rid):
    report = get_object_or_404(Report, id=rid)
    queries = report.queries.all()

    if not queries.exists():
        return HttpResponseBadRequest("Aucune requête associée à ce rapport")

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        for q in queries:
            # ==========================
            # PARAMÈTRES SQL
            # ==========================
            params = {
                p.name: p.value
                for p in ReportQueryParameter.objects.filter(
                    report=report,
                    query=q
                )
            }

            df = execute_sql_on_remote(
                q.database,
                q.sql_text,
                params
            )

            if df.empty:
                df = pd.DataFrame({
                    "INFO": [f"Aucune donnée retournée pour la requête : {q.name}"]
                })

            # ==========================
            # 🔢 TOTAUX (ULTRA SAFE)
            # ==========================
            enable_totals = getattr(q, "enable_totals", False)
            total_columns = getattr(q, "total_columns", [])

            if enable_totals and isinstance(total_columns, list) and not df.empty:
                total_row = {col: "" for col in df.columns}

                label_col = df.columns[0]
                total_row[label_col] = getattr(q, "total_label", "TOTAL")

                for col in total_columns:
                    if col in df.columns:
                        try:
                            total_row[col] = (
                                pd.to_numeric(df[col], errors="coerce")
                                .fillna(0)
                                .sum()
                            )
                        except Exception:
                            total_row[col] = ""

                df = pd.concat(
                    [df, pd.DataFrame([total_row])],
                    ignore_index=True
                )

            sheet_name = q.name[:31]

            df.to_excel(
                writer,
                index=False,
                sheet_name=sheet_name
            )

            # ==========================
            # STYLE EXCEL (TOTAL EN GRAS)
            # ==========================
            if enable_totals and not df.empty:
                ws = writer.book[sheet_name]
                last_row = ws.max_row
                for cell in ws[last_row]:
                    cell.font = Font(bold=True)

    output.seek(0)

    filename = f"{report.name}_{timezone.now():%Y%m%d%H%M%S}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response



# =====================================================
# CRONTAB HELPERS
# =====================================================
def _create_or_update_schedule(report, data):
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

    if report.is_periodic:
        schedule = _create_crontab_schedule(data)
        PeriodicTask.objects.create(
            crontab=schedule,
            name=f"Report-{report.id}",
            task="app_rapports.tasks.execute_report_task",
            args=json.dumps([report.id]),
            enabled=True,
        )

def _create_crontab_schedule(data):
    tz = timezone.get_current_timezone_name()
    hour = data["periodic_time"].hour
    minute = data["periodic_time"].minute

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


# =====================================================
# API PARAMÈTRES SQL
# =====================================================
@require_POST
def query_parameters(request):
    data = json.loads(request.body)
    response = []

    for qid in data.get("query_ids", []):
        query = SqlQuery.objects.get(id=qid)
        for p in extract_sql_parameters(query.sql_text):
            response.append(
                {
                    "query_id": query.id,
                    "query_name": query.name,
                    "param": p,
                }
            )

    return JsonResponse(response, safe=False)


# =========================
# 🔐 LOGIN
# =========================
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")  
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("home")  
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect")

    return render(request, "auth/login.html")


# admin
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Case, When, IntegerField

def admin_required(view_func):
    return user_passes_test(
        lambda u: u.is_authenticated and u.is_staff,
        login_url="home"
    )(view_func)

# =========================
# 📝 REGISTER
# =========================
@admin_required
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        role = request.POST.get("role")

        if password1 != password2:
            messages.error(request, "Les mots de passe ne correspondent pas")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Nom d'utilisateur déjà utilisé")
            return redirect("register")

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Email invalide")
            return redirect("register")

        # 🔒 BLOQUER SUPER ADMIN SI PAS AUTORISÉ
        if role == "superadmin" and not request.user.is_superuser:
            messages.error(
                request,
                "Vous n'avez pas l'autorisation de créer un Super Administrateur"
            )
            return redirect("register")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1
        )

        # 🔐 ATTRIBUTION DES DROITS
        if role == "superadmin":
            user.is_staff = True
            user.is_superuser = True
        elif role == "admin":
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False

        user.save()
        login(request, user)
        return redirect("home")

    return render(request, "auth/register.html")


# =========================
# 🚪 LOGOUT
# =========================
@login_required(login_url="login")
def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("login")



# Liste complète des utilisateurs
@admin_required
def users_list(request):
    users = User.objects.annotate(
        role_order=Case(
            When(is_superuser=True, then=0),  
            When(is_staff=True, then=1),        
            default=2,                          
            output_field=IntegerField()
        )
    ).order_by("role_order", "username")

    return render(request, "auth/users_list.html", {
        "users": users
    })

#Modifier utilisateur
@admin_required
def user_edit(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # 🔒 PROTECTION SUPER ADMIN
    if user.is_superuser and not request.user.is_superuser:
        messages.error(
            request,
            "Vous n'avez pas l'autorisation de modifier un Super Administrateur"
        )
        return redirect("users_list")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        role = request.POST.get("role")  

        # 🔁 Username unique
        if User.objects.exclude(id=user.id).filter(username=username).exists():
            messages.error(request, "Nom d'utilisateur déjà utilisé")
            return redirect("user_edit", user_id=user.id)

        user.username = username
        user.email = email

        # 🔐 GESTION DES PERMISSIONS
        if role == "superadmin":
            if not request.user.is_superuser:
                messages.error(
                    request,
                    "Action non autorisée : Super Administrateur"
                )
                return redirect("users_list")

            user.is_staff = True
            user.is_superuser = True

        elif role == "admin":
            user.is_staff = True
            user.is_superuser = False

        else:  # user
            user.is_staff = False
            user.is_superuser = False

        user.save()

        messages.success(request, "Utilisateur modifié avec succès")
        return redirect("users_list")

    return render(request, "auth/user_edit.html", {
        "user": user
    })

# Supprimer  utilisateur
@admin_required
def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # ❌ Empêcher l'auto-suppression
    if user == request.user:
        messages.error(
            request,
            "Vous ne pouvez pas supprimer votre propre compte"
        )
        return redirect("users_list")

    # 🔒 Protection Super Admin
    if user.is_superuser and not request.user.is_superuser:
        messages.error(
            request,
            "Vous n'avez pas l'autorisation de supprimer un Super Administrateur"
        )
        return redirect("users_list")

    if request.method == "POST":
        user.delete()
        messages.success(request, "Utilisateur supprimé avec succès")
        return redirect("users_list")

    return redirect("users_list")



