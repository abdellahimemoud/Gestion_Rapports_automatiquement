import re
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import mysql.connector
import pymysql
import oracledb
import psycopg2

from django.core.mail import EmailMessage
from decouple import config

# =====================================================
# 🔄 Remplacer {sysdate}, {sysdate-7}, {sysdate+30}
# =====================================================
def replace_sysdate(sql_text):
    """
    Remplace :
    {sysdate}
    {sysdate-7}
    {sysdate+30}
    par des dates réelles (YYYY-MM-DD)
    """

    def _replace(match):
        expr = match.group(1).lower().strip()
        today = datetime.today()

        if expr == "sysdate":
            return f"'{today.strftime('%Y-%m-%d')}'"

        m = re.match(r"sysdate([+-]\d+)", expr)
        if m:
            days = int(m.group(1))
            new_date = today + timedelta(days=days)
            return f"'{new_date.strftime('%Y-%m-%d')}'"

        return match.group(0)

    return re.sub(r"\{([^}]+)\}", _replace, sql_text)


# =====================================================
# 🔎 Extraire les paramètres SQL :param
# =====================================================
def extract_sql_parameters(sql_text):
    """
    Exemple :
    SELECT * FROM t WHERE code = :code AND date = :date
    → ["code", "date"]
    """
    return list(set(re.findall(r":(\w+)", sql_text)))


# =====================================================
# 🔁 Adapter SQL selon la base
# =====================================================
def adapt_sql_for_db(sql_text, db_type):
    """
    Convertit :
    :param  → %s (MySQL/Postgres)
    :param  → :param (Oracle)
    """

    if db_type == "oracle":
        return sql_text

    # MySQL / PostgreSQL utilisent %s
    return re.sub(r":\w+", "%s", sql_text)


# =====================================================
# 🔁 Adapter paramètres selon la base
# =====================================================
def adapt_params_for_db(sql_text, params, db_type):
    """
    Oracle → dictionnaire {param: value}
    MySQL/Postgres → liste [value1, value2]
    """

    if not params:
        return {} if db_type == "oracle" else []

    param_names = extract_sql_parameters(sql_text)

    if db_type == "oracle":
        return {name: params.get(name) for name in param_names}

    return [params.get(name) for name in param_names]


# =====================================================
# 🔥 Exécuter SQL distant
# =====================================================
def execute_sql_on_remote(db, sql_text, params=None):
    """
    Exécute une requête SQL distante
    Compatible Oracle / MySQL / PostgreSQL
    """

    params = params or {}

    try:
        sql_text = replace_sysdate(sql_text)

        adapted_sql = adapt_sql_for_db(sql_text, db.db_type)
        adapted_params = adapt_params_for_db(sql_text, params, db.db_type)

        # ======================
        # MySQL
        # ======================
        if db.db_type == "mysql":
            conn = mysql.connector.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                database=db.database_name,
                port=int(db.port),
                autocommit=True
            )

        # ======================
        # Oracle
        # ======================
        elif db.db_type == "oracle":
            conn = oracledb.connect(
                user=db.user,
                password=db.password or "",
                host=db.host,
                port=int(db.port),
                service_name=db.database_name
            )

        # ======================
        # PostgreSQL
        # ======================
        elif db.db_type == "postgres":
            conn = psycopg2.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                dbname=db.database_name,
                port=int(db.port)
            )

        else:
            raise ValueError("Type de base non supporté")

        cursor = conn.cursor()
        cursor.execute(adapted_sql, adapted_params)

        if cursor.description:
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(rows, columns=columns)
        else:
            df = pd.DataFrame()

        cursor.close()
        conn.close()
        return df

    except Exception as e:
        # ⚠️ IMPORTANT : ne pas masquer l’erreur (Celery retry)
        print(f"❌ Erreur SQL ({db.db_type}) :", e)
        raise


# =====================================================
# 📄 DataFrame → Excel (bytes)
# =====================================================
def df_to_excel_bytes(df):
    """
    Convertit un DataFrame en fichier Excel (bytes)
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Résultats")

    output.seek(0)
    return output.getvalue()


# =====================================================
# 📧 Envoyer email avec pièces jointes
# =====================================================
def send_report_email(
    subject,
    body,
    to_emails,
    attachments,
    cc_emails=None
):
    """
    Envoie un email avec plusieurs fichiers
    """

    if not to_emails:
        raise ValueError("Aucun destinataire TO défini")

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=config('from_email'),
        to=to_emails,
        cc=cc_emails or []
    )

    for file in attachments:
        email.attach(
            file["filename"],
            file["content"],
            file["mimetype"]
        )

    email.send(fail_silently=False)


# =====================================================
# 🔎 Tester la connexion base
# =====================================================
def test_database_connection(db):
    """
    Teste la connexion à la base
    """

    try:
        if db.db_type == "mysql":
            conn = pymysql.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                database=db.database_name,
                port=int(db.port),
                connect_timeout=3
            )

        elif db.db_type == "oracle":
            conn = oracledb.connect(
                user=db.user,
                password=db.password or "",
                host=db.host,
                port=int(db.port),
                service_name=db.database_name
            )

        elif db.db_type == "postgres":
            conn = psycopg2.connect(
                host=db.host,
                user=db.user,
                password=db.password or "",
                dbname=db.database_name,
                port=int(db.port),
                connect_timeout=3
            )

        else:
            return False

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur connexion ({db.db_type}) :", e)
        return False


# message erreur
def humanize_email_error(error: Exception) -> str:
    error_str = str(error).lower()

    if "getaddrinfo failed" in error_str:
        return (
            "Impossible de se connecter au serveur email. "
            "Vérifiez votre connexion Internet."
        )

    if "connection refused" in error_str:
        return (
            "La connexion au serveur email a été refusée. "
            "Le serveur SMTP est peut-être indisponible."
        )

    if "authentication" in error_str or "login" in error_str:
        return (
            "Échec de l’authentification email. "
            "Vérifiez l’adresse email et le mot de passe SMTP."
        )

    if "recipient" in error_str:
        return (
            "Une ou plusieurs adresses email sont invalides."
        )

    if "timeout" in error_str:
        return (
            "Le serveur email ne répond pas (délai dépassé). "
            "Veuillez réessayer plus tard."
        )

    return f"Erreur inconnue lors de l’envoi de l’email : {str(error)}"
