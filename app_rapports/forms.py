from django import forms
from django.utils import timezone

from .models import (
    DatabaseConnection,
    SqlQuery,
    EmailContact,
    Report
)

# ============================================================
# FORMULAIRE CONNEXION BASE DE DONNÉES
# ============================================================

class DatabaseForm(forms.ModelForm):
    class Meta:
        model = DatabaseConnection
        fields = "__all__"

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),

            "db_type": forms.Select(attrs={"class": "form-select"}),

            "host": forms.TextInput(attrs={"class": "form-control"}),

            "port": forms.NumberInput(attrs={"class": "form-control"}),

            "user": forms.TextInput(attrs={"class": "form-control"}),
 
            "password": forms.PasswordInput(
                attrs={"class": "form-control"},
                render_value=True
            ),

            "database_name": forms.TextInput(attrs={"class": "form-control"}),
        }

# modife base

class DatabaseConnectionForm(forms.ModelForm):
    class Meta:
        model = DatabaseConnection
        fields = [
            "name",
            "db_type",
            "host",
            "port",
            "user",
            "password",
            "database_name",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nom de la connexion"
            }),
            "db_type": forms.Select(attrs={
                "class": "form-select"
            }),
            "host": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "localhost"
            }),
            "port": forms.NumberInput(attrs={
                "class": "form-control"
            }),
            "user": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "password": forms.PasswordInput(attrs={
                  "class": "form-control",
                   "id": "id_password"
            }),

            "database_name": forms.TextInput(attrs={
                "class": "form-control"
            }),
        }


# ============================================================
# FORMULAIRE REQUÊTE SQL (SIMPLE)
# ===========================================================

class QueryForm(forms.ModelForm):
    class Meta:
        model = SqlQuery
        fields = ["name", "database", "sql_text"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "database": forms.Select(attrs={"class": "form-select"}),
            "sql_text": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }

# modifie requete
class SqlQueryForm(forms.ModelForm):
    class Meta:
        model = SqlQuery
        fields = ["name", "sql_text", "database"]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "sql_text": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6
            }),
            "database": forms.Select(attrs={
                "class": "form-select"
            }),
        }

# ============================================================
# FORMULAIRE RAPPORT
# (requêtes + emails + planification)
# ============================================================
class ReportForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["queries"].queryset = SqlQuery.objects.all().order_by("name")

    # Requêtes associées
    queries = forms.ModelMultipleChoiceField(
        queryset=SqlQuery.objects.all().order_by("name"),
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "6"}),
        required=True,
        label="Requêtes SQL"
    )


    # Emails TO
    to_emails = forms.ModelMultipleChoiceField(
        queryset=EmailContact.objects.all(),
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "6"}),
        required=True,
        label="Destinataires"
    )

    # Emails CC
    cc_emails = forms.ModelMultipleChoiceField(
        queryset=EmailContact.objects.all(),
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "6"}),
        required=False,
        label="Copie (CC)"
    )

    # Date unique
    execute_at = forms.DateTimeField(
        label="Date et heure d’exécution",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        input_formats=["%Y-%m-%dT%H:%M"],
        required=False,
    )

    # Planification périodique
    periodic_time = forms.TimeField(
        label="Heure d’exécution",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        required=False,
    )

    periodic_weekday = forms.ChoiceField(
        label="Jour de la semaine",
        choices=Report.WEEKDAY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
    )

    periodic_monthday = forms.IntegerField(
        label="Jour du mois",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 31}),
        required=False,
    )

    class Meta:
        model = Report
        fields = [
            "name", "subject", "message",
            "queries", "to_emails", "cc_emails",
            "is_periodic", "execute_at", "periodic_type",
            "periodic_time", "periodic_weekday", "periodic_monthday",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "is_periodic": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "periodic_type": forms.Select(attrs={"class": "form-select"}),
        }

    # ============================================================
    # VALIDATION
    # ============================================================
    def clean(self):
        cleaned_data = super().clean()

        is_periodic = cleaned_data.get("is_periodic")
        execute_at = cleaned_data.get("execute_at")
        periodic_type = cleaned_data.get("periodic_type")
        periodic_time = cleaned_data.get("periodic_time")
        periodic_weekday = cleaned_data.get("periodic_weekday")
        periodic_monthday = cleaned_data.get("periodic_monthday")

        queries = cleaned_data.get("queries")
        to_emails = cleaned_data.get("to_emails")

        now = timezone.now()

        # Requêtes obligatoires
        if not queries or queries.count() == 0:
            self.add_error("queries", "Veuillez sélectionner au moins une requête.")

        # Emails TO obligatoires
        if not to_emails or to_emails.count() == 0:
            self.add_error("to_emails", "Veuillez sélectionner au moins un destinataire.")

        # Planification
        if is_periodic:
            if execute_at:
                self.add_error("execute_at", "Un rapport périodique ne doit pas avoir de date unique.")
            if not periodic_type:
                self.add_error("periodic_type", "Veuillez choisir un type de périodicité.")
            if not periodic_time:
                self.add_error("periodic_time", "Veuillez définir une heure d’exécution.")
            if periodic_type == "weekly" and not periodic_weekday:
                self.add_error("periodic_weekday", "Veuillez sélectionner un jour de la semaine.")
            if periodic_type == "monthly":
                if periodic_monthday is None:
                    self.add_error("periodic_monthday", "Veuillez définir le jour du mois.")
                elif not 1 <= periodic_monthday <= 31:
                    self.add_error("periodic_monthday", "Le jour du mois doit être entre 1 et 31.")
        else:
            if not execute_at:
                self.add_error("execute_at", "La date et l’heure d’exécution sont obligatoires.")
            elif execute_at <= now:
                self.add_error("execute_at", "La date et l’heure doivent être dans le futur.")

        return cleaned_data
