from django import forms
from django.utils import timezone

from .models import DatabaseConnection, SqlQuery, EmailContact


# ============================================================
# FORMULAIRE CONNEXION BASE DE DONNÉES
# ============================================================
class DatabaseForm(forms.ModelForm):

    class Meta:
        model = DatabaseConnection
        fields = "__all__"
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "host": forms.TextInput(attrs={"class": "form-control"}),
            "port": forms.NumberInput(attrs={"class": "form-control"}),
            "user": forms.TextInput(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control"}),
            "database_name": forms.TextInput(attrs={"class": "form-control"}),
        }
        error_messages = {
            "name": {"required": "Ce champ est obligatoire."},
            "host": {"required": "Ce champ est obligatoire."},
            "port": {"required": "Ce champ est obligatoire."},
            "user": {"required": "Ce champ est obligatoire."},
            "password": {"required": "Ce champ est obligatoire."},
            "database_name": {"required": "Ce champ est obligatoire."},
        }



# ============================================================
# FORMULAIRE REQUÊTE SQL + PLANIFICATION
# ============================================================
class QueryForm(forms.ModelForm):

    # --------------------------------------------------------
    # Emails (SelectMultiple obligatoire)
    # --------------------------------------------------------
    emails = forms.ModelMultipleChoiceField(
        queryset=EmailContact.objects.all(),
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-select",
                "size": "6"
            }
        ),
        required=True,
        label="Destinataires"
    )

    # --------------------------------------------------------
    # Date & heure unique (non périodique)
    # --------------------------------------------------------
    execute_at = forms.DateTimeField(
        label="Date et heure d’exécution",
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control",
            }
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        required=False,
    )

    # --------------------------------------------------------
    # Heure périodique
    # --------------------------------------------------------
    periodic_time = forms.TimeField(
        label="Heure d’exécution",
        widget=forms.TimeInput(
            attrs={
                "type": "time",
                "class": "form-control",
            }
        ),
        required=False,
    )

    # --------------------------------------------------------
    # Jour de semaine
    # --------------------------------------------------------
    periodic_weekday = forms.ChoiceField(
        label="Jour de la semaine",
        choices=SqlQuery.WEEKDAY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
    )

    # --------------------------------------------------------
    # Jour du mois
    # --------------------------------------------------------
    periodic_monthday = forms.IntegerField(
        label="Jour du mois",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 1,
                "max": 31,
            }
        ),
        required=False,
    )

    class Meta:
        model = SqlQuery
        fields = [
            "name",
            "database",
            "sql_text",
            "subject",
            "message",
            "is_periodic",
            "execute_at",
            "periodic_type",
            "periodic_time",
            "periodic_weekday",
            "periodic_monthday",
            "emails",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "database": forms.Select(attrs={"class": "form-select"}),
            "sql_text": forms.Textarea(
                attrs={"class": "form-control", "rows": 6}
            ),
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "message": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "is_periodic": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "periodic_type": forms.Select(
                attrs={"class": "form-select"}
            ),
        }

    # ========================================================
    # VALIDATION MÉTIER (PLANIFICATION + EMAILS)
    # ========================================================
    def clean(self):
        cleaned_data = super().clean()

        execute_at = cleaned_data.get("execute_at")
        is_periodic = cleaned_data.get("is_periodic")
        periodic_type = cleaned_data.get("periodic_type")
        periodic_time = cleaned_data.get("periodic_time")
        periodic_weekday = cleaned_data.get("periodic_weekday")
        periodic_monthday = cleaned_data.get("periodic_monthday")
        emails = cleaned_data.get("emails")

        now = timezone.now()

        # ====================================================
        # VALIDATION EMAILS
        # ====================================================
        if not emails or emails.count() == 0:
            self.add_error(
                "emails",
                " Veuillez sélectionner au moins un destinataire."
            )

        # ====================================================
        # MODE PÉRIODIQUE
        # ====================================================
        if is_periodic:

            # ❌ date unique interdite
            if execute_at:
                self.add_error(
                    "execute_at",
                    "Une requête périodique ne doit pas avoir de date unique."
                )

            # type obligatoire
            if not periodic_type:
                self.add_error(
                    "periodic_type",
                    "Veuillez choisir un type de périodicité."
                )

            # heure obligatoire
            if not periodic_time:
                self.add_error(
                    "periodic_time",
                    "Veuillez définir une heure d’exécution."
                )

            # hebdomadaire → jour obligatoire
            if periodic_type == "weekly" and not periodic_weekday:
                self.add_error(
                    "periodic_weekday",
                    "Veuillez sélectionner un jour de la semaine."
                )

            # mensuelle → jour du mois obligatoire
            if periodic_type == "monthly":
                if periodic_monthday is None:
                    self.add_error(
                        "periodic_monthday",
                        "Veuillez définir le jour du mois."
                    )
                elif not 1 <= periodic_monthday <= 31:
                    self.add_error(
                        "periodic_monthday",
                        "Le jour du mois doit être entre 1 et 31."
                    )

        # ====================================================
        # MODE NON PÉRIODIQUE
        # ====================================================
        else:
            if not execute_at:
                self.add_error(
                    "execute_at",
                    "La date et l’heure d’exécution sont obligatoires."
                )
            elif execute_at <= now:
                self.add_error(
                    "execute_at",
                    "La date et l’heure doivent être dans le futur."
                )

        return cleaned_data
