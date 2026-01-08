import re
from datetime import datetime, timedelta
import mysql.connector
import pandas as pd
from django.core.mail import EmailMessage
from io import BytesIO
import pymysql
import oracledb
import psycopg2


# =====================================================
# ✔ Remplacer {{date}} dans la requête SQL (optionnel)
# =====================================================
def apply_user_date(sql_text, user_date):
    """
    Remplace la variable {{date}} dans la requête SQL

    Exemple :
    SELECT * FROM ventes WHERE date = '{{date}}'
    """
    if user_date:
        return sql_text.replace("{{date}}", str(user_date))
    return sql_text


# =====================================================
# 🔄 Remplacer {sysdate}, {sysdate-7}, {sysdate+30}
# =====================================================
def replace_sysdate(sql_text):
    """
    Remplace les expressions dynamiques :
    {sysdate}
    {sysdate-7}
    {sysdate+30}

    par des dates réelles au format YYYY-MM-DD
    """

    def _replace(match):
        expression = match.group(1).lower().strip()
        today = datetime.today()

        # {sysdate}
        if expression == "sysdate":
            return f"'{today.strftime('%Y-%m-%d')}'"

        # {sysdate-7} ou {sysdate+30}
        m = re.match(r"sysdate([+-]\d+)", expression)
        if m:
            days = int(m.group(1))
            new_date = today + timedelta(days=days)
            return f"'{new_date.strftime('%Y-%m-%d')}'"

        # inconnu → on laisse tel quel
        return match.group(0)

    return re.sub(r"\{([^}]+)\}", _replace, sql_text)


# =====================================================
# 🔥 Exécuter SQL sur base distante (MySQL / Oracle / PostgreSQL)
# =====================================================
def execute_sql_on_remote(db, sql_text):
    """
    Exécute une requête SQL distante selon le type de base
    Retourne un DataFrame pandas
    """

    try:
        # 🔄 Remplacement des dates dynamiques
        sql_text = replace_sysdate(sql_text)

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
        cursor.execute(sql_text)

        # SELECT
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
        print(f"❌ Erreur SQL ({db.db_type}) :", e)
        return pd.DataFrame()

# =====================================================
# 📄 Convertir DataFrame → Excel (bytes)
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
# 📧 Envoyer email avec PLUSIEURS pièces jointes
# =====================================================
def send_report_email(
    subject,
    body,
    to_emails,
    attachments,
    cc_emails=None
):
    """
    Envoie un email avec plusieurs fichiers en pièce jointe
    """

    if not to_emails:
        raise ValueError("Aucun destinataire TO défini.")

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email="abdellahisidimedmemoud@gmail.com",
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
# 🔎 Tester la connexion (toutes bases)
# =====================================================
def test_database_connection(db):
    """
    Teste la connexion selon le type de base
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

