from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


# =======================
# CONNEXION BASE DE DONNÉES
# =======================
class DatabaseConnection(models.Model):
    name = models.CharField(max_length=200)
    host = models.CharField(max_length=200)
    port = models.PositiveIntegerField(default=3306)
    user = models.CharField(max_length=200)
    password = models.CharField(max_length=200, blank=True, null=True)
    database_name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


# =======================
# EMAILS DESTINATAIRES
# =======================
class EmailContact(models.Model):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email


# =======================
# REQUÊTE SQL PLANIFIÉE
# =======================
class SqlQuery(models.Model):

    # 🔁 Types de périodicité
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

    # =======================
    # INFOS GÉNÉRALES
    # =======================
    name = models.CharField(max_length=200)

    database = models.ForeignKey(
        DatabaseConnection,
        on_delete=models.CASCADE,
        related_name="queries"
    )

    sql_text = models.TextField()

    subject = models.CharField(
        max_length=255,
        verbose_name="Objet de l’email"
    )

    message = models.TextField(
        blank=True,
        null=True,
        verbose_name="Message"
    )

    emails = models.ManyToManyField(
        EmailContact,
        blank=True,
        related_name="queries"
    )

    # =======================
    # MODE NON RÉPÉTITIF
    # =======================
    execute_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date et heure d'exécution"
    )

    # =======================
    # MODE RÉPÉTITIF
    # =======================
    is_periodic = models.BooleanField(
        default=False,
        verbose_name="Requête répétitive"
    )

    periodic_type = models.CharField(
        max_length=10,
        choices=PERIODIC_TYPE_CHOICES,
        blank=True,
        null=True,
        verbose_name="Type de périodicité"
    )

    periodic_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name="Heure d'exécution"
    )

    periodic_weekday = models.CharField(
        max_length=3,
        choices=WEEKDAY_CHOICES,
        blank=True,
        null=True,
        verbose_name="Jour de la semaine"
    )

    periodic_monthday = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Jour du mois (1–31)"
    )

    # =======================
    # STATUT / MÉTADONNÉES
    # =======================
    is_executed = models.BooleanField(
        default=False,
        verbose_name="Déjà exécutée"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =======================
    # VALIDATION MÉTIER
    # =======================
    # def clean(self):

    #     # 🔴 MODE PÉRIODIQUE
    #     if self.is_periodic:
    #         if self.execute_at:
    #             raise ValidationError({
    #                 "execute_at": "Impossible d’utiliser une date unique pour une requête répétitive."
    #             })

    #         if not self.periodic_type:
    #             raise ValidationError({
    #                 "periodic_type": ""
    #             })

    #         if not self.periodic_time:
    #             raise ValidationError({
    #                 "periodic_time": "Heure d’exécution obligatoire."
    #             })

    #         if self.periodic_type == "weekly" and not self.periodic_weekday:
    #             raise ValidationError({
    #                 "periodic_weekday": "Jour de la semaine obligatoire."
    #             })

    #         if self.periodic_type == "monthly":
    #             if self.periodic_monthday is None:
    #                 raise ValidationError({
    #                     "periodic_monthday": "Jour du mois obligatoire."
    #                 })
    #             if not (1 <= self.periodic_monthday <= 31):
    #                 raise ValidationError({
    #                     "periodic_monthday": "Le jour du mois doit être entre 1 et 31."
    #                 })

    #     # 🔵 MODE UNIQUE
    #     else:
    #         if not self.execute_at:
    #             raise ValidationError({
    #                 "execute_at": ""
    #             })

    #         if self.execute_at <= timezone.now():
    #             raise ValidationError({
    #                 "execute_at": "La date et l’heure doivent être dans le futur."
    #             })

    #     super().clean()

    # =======================
    # UTILS
    # =======================
    def email_list(self):
        return ", ".join(e.email for e in self.emails.all())

    def __str__(self):
        return self.name
