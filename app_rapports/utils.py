import mysql.connector
import pandas as pd
from django.core.mail import EmailMessage
from io import BytesIO
import pymysql


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
# 🔥 Exécuter SQL sur base distante
# =====================================================
def execute_sql_on_remote(db, sql_text):
    """
    Exécute une requête SQL distante et retourne un DataFrame
    """
    try:
        conn = mysql.connector.connect(
            host=db.host,
            user=db.user,
            password=db.password or "",
            database=db.database_name,
            port=db.port
        )

        cursor = conn.cursor()
        cursor.execute(sql_text)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        df = pd.DataFrame(rows, columns=columns)

        cursor.close()
        conn.close()

        return df

    except Exception as e:
        print("❌ Erreur exécution SQL :", e)
        return pd.DataFrame()


# =====================================================
# 📄 Convertir DataFrame → Excel (bytes)
# =====================================================
def df_to_excel_bytes(df):
    """
    Convertit un DataFrame en fichier Excel (bytes)
    """
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)
    return output.read()


# =====================================================
# 📧 Envoyer email avec pièce jointe Excel
# =====================================================
def send_report_email(subject, body, to_emails, excel_bytes, filename):
    """
    Envoie un email avec fichier Excel en pièce jointe
    """
    if not to_emails:
        print("⚠️ Aucun destinataire email.")
        return

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email="abdellahisidimedmemoud@gmail.com",
        to=to_emails
    )

    email.attach(
        filename,
        excel_bytes,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    email.send(fail_silently=False)


# =====================================================
# 🔎 Tester la connexion MySQL
# =====================================================
def test_mysql_connection(db):
    """
    Teste la connexion MySQL
    db = instance DatabaseConnection
    """
    try:
        conn = pymysql.connect(
            host=db.host,
            user=db.user,
            password=db.password,
            database=db.database_name,
            port=int(db.port),
            connect_timeout=3
        )
        conn.close()
        return True

    except Exception as e:
        print("❌ Erreur connexion MySQL :", e)
        return False
