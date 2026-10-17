# -*- coding: utf-8 -*-
"""Modèles de messages remplis automatiquement pour chaque niveau de traitement."""

from __future__ import annotations

import datetime as dt
import urllib.parse

from . import config
from .texte import fmt_date, fmt_datetime, fmt_montant, fmt_nombre, pluraliser, valeur_ou_tiret

CONTENU_VIDE = """Aucun message à préparer à ce stade.

Cette facture n'est pas encore en retard : elle apparaîtra automatiquement dans la
file de relance le jour suivant son échéance."""

PLACEHOLDERS = {
    "{client}": "Nom du client",
    "{contact}": "Personne à contacter chez le client",
    "{facture}": "Numéro de facture",
    "{montant}": "Montant formaté sans devise (ex. 55 000,00)",
    "{montant_devise}": "Montant suivi de la devise (ex. 55 000,00 MAD)",
    "{devise}": "Devise",
    "{date_facture}": "Date d'émission de la facture",
    "{echeance}": "Date d'échéance de la facture",
    "{retard}": "Nombre de jours de retard",
    "{retard_mot}": "« jour » ou « jours »",
    "{niveau}": "Niveau de traitement atteint",
    "{prochain_niveau}": "Niveau de traitement suivant",
    "{prochain_seuil}": "Seuil (en jours) du niveau suivant",
    "{jours_avant_prochain}": "Jours restants avant le niveau suivant",
    "{date_limite}": "Date limite proposée au client",
    "{date_du_jour}": "Date du jour",
    "{societe}": "Nom de votre société",
    "{utilisateur}": "Nom de l'utilisateur connecté",
    "{ville}": "Ville de votre société",
    "{telephone}": "Téléphone du client",
    "{email}": "Email du client",
    "{telephone_societe}": "Téléphone de votre société",
    "{score}": "Score de priorité",
    "{nombre_relances}": "Nombre de relances déjà enregistrées",
    "{derniere_relance}": "Date de la dernière relance",
    "{chronologie}": "Historique des relances (généré automatiquement)",
}


class _Modele(dict):
    """Remplace les placeholders connus, laisse les autres visibles."""

    def __missing__(self, cle):
        return "{" + cle + "}"


def chronologie(actions: list[dict], limite: int | None = None) -> str:
    """Historique des relances sous forme de liste, du plus ancien au plus récent."""
    lignes = sorted(actions, key=lambda a: (a.get("date_action") or "", a.get("id") or 0))
    if not lignes:
        return "- aucune relance enregistrée à ce jour."
    if limite:
        lignes = lignes[-limite:]
    resultat = []
    for action in lignes:
        type_action = config.TYPES_ACTION.get(action.get("type_action", ""), action.get("type_action", ""))
        resultat_action = config.RESULTATS_ACTION.get(action.get("resultat", ""), action.get("resultat", ""))
        morceaux = [
            fmt_datetime(action.get("date_action")),
            f"{type_action}",
            f"({action.get('jours_retard', 0)} j de retard)",
            f"→ {resultat_action}",
        ]
        commentaire = (action.get("commentaire") or "").strip()
        if commentaire:
            morceaux.append(f"— {commentaire}")
        resultat.append("- " + " ".join(morceaux))
    return "\n".join(resultat)


def contexte(facture: dict, settings: dict, aujourdhui: dt.date | None = None) -> dict:
    """Toutes les valeurs injectables dans un modèle."""
    aujourdhui = aujourdhui or dt.date.today()
    societe = settings.get("societe", {})
    devise = societe.get("devise", "MAD")
    retard = int(facture.get("retard") or 0)
    montant = float(facture.get("montant") or 0)
    niveau = facture.get("niveau", "")
    niveau_suivant = facture.get("niveau_suivant")
    actions = facture.get("actions") or []
    texte_montant = fmt_nombre(montant, 2)

    # Date limite proposée au client, selon le niveau atteint
    if niveau == "mise_en_demeure":
        delai = int(societe.get("delai_mise_en_demeure_jours", 8) or 8)
    else:
        delai = int(societe.get("delai_email_jours", 2) or 2)
    date_limite = aujourdhui + dt.timedelta(days=delai)

    derniere = None
    if actions:
        plus_recente = max(actions, key=lambda a: (a.get("date_action") or "", a.get("id") or 0))
        derniere = fmt_date(plus_recente.get("date_action"))

    return _Modele(
        {
            "client": valeur_ou_tiret(facture.get("client"), "Client"),
            "contact": valeur_ou_tiret(facture.get("contact"), valeur_ou_tiret(facture.get("client"), "Madame, Monsieur")),
            "facture": valeur_ou_tiret(facture.get("numero"), "—"),
            "montant": f"{texte_montant}",
            "montant_devise": fmt_montant(montant, devise),
            "montant_brut": f"{montant:.2f}",
            "devise": devise,
            "date_facture": fmt_date(facture.get("date_facture")),
            "echeance": fmt_date(facture.get("echeance")),
            "retard": retard,
            "retard_mot": pluraliser(retard, "jour"),
            "niveau": config.NIVEAU_LABEL.get(niveau, niveau),
            "prochain_niveau": config.NIVEAU_LABEL.get(niveau_suivant, "fin de procédure") if niveau_suivant else "transmission définitive",
            "prochain_seuil": facture.get("seuil_suivant") or "—",
            "jours_avant_prochain": facture.get("jours_avant_prochain") or 0,
            "date_limite": date_limite.strftime("%d/%m/%Y"),
            "date_du_jour": aujourdhui.strftime("%d/%m/%Y"),
            "societe": valeur_ou_tiret(societe.get("nom"), "Mon entreprise"),
            "utilisateur": valeur_ou_tiret(societe.get("utilisateur"), "—"),
            "ville": valeur_ou_tiret(societe.get("ville"), "—"),
            "telephone": valeur_ou_tiret(facture.get("telephone")),
            "email": valeur_ou_tiret(facture.get("email")),
            "telephone_societe": valeur_ou_tiret(societe.get("telephone"), "—"),
            "score": facture.get("score") if facture.get("score") is not None else "—",
            "nombre_relances": len(actions),
            "derniere_relance": derniere or "—",
            "chronologie": chronologie(actions),
        }
    )


def modele_pour(niveau: str, settings: dict) -> str | None:
    """Modèle enregistré pour ce niveau (``None`` si aucune relance n'est due)."""
    if niveau not in config.SEUILS_ORDRE:
        return None
    modeles = settings.get("modeles", {})
    if niveau in modeles:
        return modeles[niveau]
    return config.DEFAULT_MODELES.get(niveau)


def rendre(modele: str | None, facture: dict, settings: dict, aujourdhui: dt.date | None = None) -> str:
    """Remplit un modèle avec les données de la facture."""
    if not modele:
        return CONTENU_VIDE
    valeurs = contexte(facture, settings, aujourdhui)
    try:
        return modele.format_map(valeurs)
    except (IndexError, KeyError, ValueError):
        # Modèle contenant une accolade isolée : on renvoie le texte brut.
        return modele


def message_pour(facture: dict, settings: dict, aujourdhui: dt.date | None = None) -> str:
    return rendre(modele_pour(facture.get("niveau", ""), settings), facture, settings, aujourdhui)


def sujet_email(facture: dict, settings: dict, aujourdhui: dt.date | None = None) -> str:
    """Extrait la ligne « Objet : … » du message, sinon en construit un."""
    message = message_pour(facture, settings, aujourdhui)
    for ligne in message.splitlines():
        if ligne.lower().startswith("objet"):
            return ligne.split(":", 1)[1].strip() or ligne.strip()
    devise = settings.get("societe", {}).get("devise", "MAD")
    return (
        f"Relance — facture {facture.get('numero', '')} de "
        f"{fmt_montant(facture.get('montant'), devise)}"
    )


def corps_email(facture: dict, settings: dict, aujourdhui: dt.date | None = None) -> str:
    """Corps du message, sans la ligne d'objet."""
    lignes = [
        ligne
        for ligne in message_pour(facture, settings, aujourdhui).splitlines()
        if not ligne.lower().startswith("objet")
    ]
    return "\n".join(lignes).strip()


# --------------------------------------------------------------------------
# Liens d'action (mailto, SMS, téléphone)
# --------------------------------------------------------------------------
def _destination_email(facture: dict) -> str:
    return (facture.get("email") or "").strip()


def lien_email(facture: dict, settings: dict, aujourdhui: dt.date | None = None) -> str | None:
    adresse = _destination_email(facture)
    if not adresse:
        return None
    parametres = urllib.parse.urlencode(
        {"subject": sujet_email(facture, settings, aujourdhui), "body": corps_email(facture, settings, aujourdhui)}
    )
    return f"mailto:{adresse}?{parametres}"


def lien_sms(facture: dict, settings: dict, aujourdhui: dt.date | None = None) -> str | None:
    numero = "".join(ch for ch in (facture.get("telephone") or "") if ch.isdigit() or ch == "+")
    if not numero:
        return None
    corps = message_pour(facture, settings, aujourdhui) if facture.get("niveau") == "sms" else corps_email(facture, settings, aujourdhui)
    return f"sms:{numero}?&body={urllib.parse.quote(corps)}"


def lien_telephone(facture: dict) -> str | None:
    numero = "".join(ch for ch in (facture.get("telephone") or "") if ch.isdigit() or ch == "+")
    return f"tel:{numero}" if numero else None
