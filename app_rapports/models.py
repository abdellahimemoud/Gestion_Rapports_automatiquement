from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.timezone import now

# =======================
# CONNEXION BASE DE DONNÉES
# =======================
class DatabaseConnection(models.Model):

    DB_TYPES = [
        ('oracle', 'Oracle'),
        ('mysql', 'MySQL'),
        ('postgres', 'PostgreSQL'),
    ]

    name = models.CharField(max_length=200)

    db_type = models.CharField(
        max_length=20,
        choices=DB_TYPES,
        default='oracle'
    )

    host = models.CharField(max_length=200)

    port = models.PositiveIntegerField(default=1521)

    user = models.CharField(max_length=200)

    password = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    database_name = models.CharField(
        max_length=200,
        help_text="MySQL/Postgres: DB name | Oracle: SERVICE_NAME (ex: ORCLPDB1)"
    )

    def __str__(self):
        return f"{self.name} ({self.db_type})"


# =======================
# EMAILS
# =======================
class EmailContact(models.Model):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email


# =======================
# REQUÊTE SQL
# =======================
class SqlQuery(models.Model):
    name = models.CharField(max_length=200)
    database = models.ForeignKey(
        DatabaseConnection,
        on_delete=models.CASCADE,
        related_name="queries"
    )
    sql_text = models.TextField(verbose_name="Requête SQL")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =======================
# RAPPORT
# =======================
class Report(models.Model):

    PERIODIC_TYPE_CHOICES = [
        ("daily", "Chaque jour"),
        ("weekly", "Chaque semaine"),
        ("monthly", "Chaque mois"),
    ]

    WEEKDAY_CHOICES = [
        ("mon", "Lundi"),
        ("tue", "Mardi"),
        ("wed", "Mercredi"),
        ("thu", "Jeudi"),
        ("fri", "Vendredi"),
        ("sat", "Samedi"),
        ("sun", "Dimanche"),
    ]

    # 🔑 CODE UNIQUE DU RAPPORT
    code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True  
    )

    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=255)
    message = models.TextField(blank=True, null=True)

    # 🔥 Plusieurs requêtes par rapport
    queries = models.ManyToManyField(
        SqlQuery,
        related_name="reports"
    )

    to_emails = models.ManyToManyField(
        EmailContact,
        related_name="reports_to"
    )

    cc_emails = models.ManyToManyField(
        EmailContact,
        related_name="reports_cc",
        blank=True
    )

    execute_at = models.DateTimeField(blank=True, null=True)

    is_periodic = models.BooleanField(default=False)
    periodic_type = models.CharField(
        max_length=10,
        choices=PERIODIC_TYPE_CHOICES,
        blank=True,
        null=True
    )
    periodic_time = models.TimeField(blank=True, null=True)
    periodic_weekday = models.CharField(
        max_length=3,
        choices=WEEKDAY_CHOICES,
        blank=True,
        null=True
    )
    periodic_monthday = models.PositiveIntegerField(blank=True, null=True)

    last_executed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # =======================
    # GÉNÉRATION DU CODE
    # =======================
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)

    def generate_code(self):
        year = now().year
        last = Report.objects.filter(
            created_at__year=year
        ).count() + 1
        return f"R-{last:02d}"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """
        Validation métier :
        - Rapport périodique → type + heure obligatoires
        - Rapport ponctuel → date future obligatoire
        """
        if self.is_periodic:
            if not self.periodic_type or not self.periodic_time:
                raise ValidationError("Planification périodique incomplète.")
        else:
            if self.execute_at and self.execute_at <= timezone.now():
                raise ValidationError("La date d'exécution doit être dans le futur.")

    def __str__(self):
        return self.name


# =======================
# 🔥 FICHIERS GÉNÉRÉS PAR REQUÊTE
# =======================
class ReportFile(models.Model):
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="files"
    )

    query = models.ForeignKey(
        SqlQuery,
        on_delete=models.CASCADE,
        related_name="generated_files"
    )

    file = models.FileField(upload_to="reports/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.report.name} - {self.query.name}"


# =======================
# ✅ LOGS D’EXÉCUTION (GLOBAL + REQUÊTES)
# =======================
class ReportExecutionLog(models.Model):
    STATUS_CHOICES = (
        ("success", "Succès"),
        ("error", "Erreur"),
    )

    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    # 🔥 NULL = log global (exécution ou email)
    # NON NULL = log lié à une requête précise
    query = models.ForeignKey(
        SqlQuery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_logs"
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES
    )

    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        scope = self.query.name if self.query else "GLOBAL"
        return f"{self.report.name} [{scope}] - {self.status}"
