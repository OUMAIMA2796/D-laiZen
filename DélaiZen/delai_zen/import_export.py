# -*- coding: utf-8 -*-
"""Import / export CSV et génération du dossier de recouvrement."""

from __future__ import annotations

import datetime as dt
import io
import unicodedata

import pandas as pd

from . import config, db, messages, scoring
from .texte import fmt_date, fmt_datetime, fmt_montant, valeur_ou_tiret

SEPARATEUR = ";"

COLONNES_MODELE = [
    "client",
    "numero",
    "montant",
    "date_facture",
    "echeance",
    "contact",
    "telephone",
    "email",
    "retards_anterieurs",
    "notes",
]

ALIAS = {
    "client": {"client", "nom client", "nom du client", "societe", "raison sociale"},
    "numero": {"numero", "numero facture", "n facture", "no facture", "facture", "reference", "piece"},
    "montant": {"montant", "montant ttc", "montant ht", "total", "montant du", "valeur"},
    "date_facture": {"date facture", "date d emission", "date emission", "date de facture", "emission"},
    "echeance": {"echeance", "date echeance", "date d echeance", "date limite", "echeance de paiement"},
    "contact": {"contact", "interlocuteur", "personne a contacter"},
    "telephone": {"telephone", "tel", "tel client", "telephone client", "gsm", "mobile", "portable"},
    "email": {"email", "e mail", "mail", "courriel", "email client"},
    "retards_anterieurs": {"retards anterieurs", "retards passes", "nombre de retards", "historique", "incidents"},
    "notes": {"notes", "note", "commentaire", "commentaires", "observation", "observations"},
}


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------
def _normaliser(texte) -> str:
    brut = unicodedata.normalize("NFKD", str(texte or ""))
    sans_accents = "".join(c for c in brut if not unicodedata.combining(c))
    return " ".join(sans_accents.lower().replace("_", " ").replace("-", " ").replace(".", " ").split())


def _entete_vers_champ(entete) -> str | None:
    normalise = _normaliser(entete)
    for champ, alias in ALIAS.items():
        if normalise in alias:
            return champ
    return None


def _texte(valeur) -> str:
    """Chaîne nettoyée : ``None``, ``NaN`` et « nan » deviennent une chaîne vide."""
    if valeur is None or valeur is pd.NA:
        return ""
    if isinstance(valeur, float) and valeur != valeur:
        return ""
    texte = str(valeur).strip()
    return "" if texte.lower() in {"nan", "nat", "none", "null"} else texte


def _nombre(valeur) -> float:
    if valeur is None:
        return 0.0
    texte = str(valeur).strip().replace("\u202f", "").replace(" ", "")
    if not texte or texte.lower() in {"nan", "none"}:
        return 0.0
    texte = texte.replace(",", ".")
    texte = "".join(c for c in texte if c.isdigit() or c in ".-")
    try:
        return float(texte)
    except ValueError:
        return 0.0


def modele_csv() -> str:
    aujourdhui = dt.date.today()
    echeance = aujourdhui + dt.timedelta(days=30)
    lignes = [
        COLONNES_MODELE,
        [
            "Client exemple",
            "FAC-2026-001",
            "12500,00",
            aujourdhui.strftime("%d/%m/%Y"),
            echeance.strftime("%d/%m/%Y"),
            "Mme Exemple",
            "0661000000",
            "compta@client.example",
            "0",
            "Facture de test",
        ],
    ]
    return "\n".join(SEPARATEUR.join(ligne) for ligne in lignes) + "\n"


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------
def importer(contenu: bytes, aujourdhui: dt.date | None = None) -> tuple[int, list[str]]:
    """Importe un CSV et renvoie (nombre de factures créées, messages d'erreur)."""
    aujourdhui = aujourdhui or dt.date.today()
    try:
        cadre = pd.read_csv(io.BytesIO(contenu), sep=None, engine="python", dtype=str)
    except Exception as erreur:  # pragma: no cover - dépend du fichier fourni
        return 0, [f"Lecture du fichier impossible : {erreur}"]

    correspondance = {}
    for colonne in cadre.columns:
        champ = _entete_vers_champ(colonne)
        if champ:
            correspondance[champ] = colonne

    manquants = [champ for champ in ("client", "numero", "montant", "echeance") if champ not in correspondance]
    if manquants:
        return 0, [
            "Colonnes obligatoires absentes : " + ", ".join(manquants) + ". "
            "Le fichier doit contenir au minimum : client, numero, montant, echeance."
        ]

    existants = {(f.get("numero") or "").strip().lower() for f in db.list_factures()}
    crees = 0
    erreurs: list[str] = []

    for position, (_, ligne) in enumerate(cadre.iterrows(), start=2):
        def valeur(champ):
            colonne = correspondance.get(champ)
            return ligne[colonne] if colonne else None

        client = _texte(valeur("client"))
        numero = _texte(valeur("numero"))
        montant = _nombre(valeur("montant"))
        echeance = scoring.parse_date(valeur("echeance"))
        date_facture = scoring.parse_date(valeur("date_facture")) or (
            echeance - dt.timedelta(days=30) if echeance else None
        )

        if not client or not numero:
            erreurs.append(f"Ligne {position} ignorée : client ou numéro de facture manquant.")
            continue
        if montant <= 0:
            erreurs.append(f"Ligne {position} ({numero}) ignorée : montant invalide.")
            continue
        if echeance is None:
            erreurs.append(f"Ligne {position} ({numero}) ignorée : échéance illisible.")
            continue
        if numero.lower() in existants:
            erreurs.append(f"Ligne {position} ({numero}) ignorée : ce numéro de facture existe déjà.")
            continue

        db.create_facture(
            {
                "client": client,
                "numero": numero,
                "montant": montant,
                "date_facture": date_facture.isoformat() if date_facture else None,
                "echeance": echeance.isoformat(),
                "contact": _texte(valeur("contact")),
                "telephone": _texte(valeur("telephone")),
                "email": _texte(valeur("email")),
                "retards_anterieurs": int(_nombre(valeur("retards_anterieurs"))),
                "statut": "ouverte",
                "date_paiement": None,
                "notes": _texte(valeur("notes")),
            }
        )
        existants.add(numero.lower())
        crees += 1

    return crees, erreurs


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------
def _encoder(texte: str) -> bytes:
    return texte.encode("utf-8-sig")


def exporter_factures(portefeuille: list[dict], reglages: dict) -> bytes:
    devise = reglages["societe"].get("devise", "MAD")
    lignes = []
    for facture in portefeuille:
        lignes.append(
            {
                "client": facture.get("client"),
                "numero": facture.get("numero"),
                f"montant_{devise}": f"{float(facture.get('montant') or 0):.2f}".replace(".", ","),
                "date_facture": fmt_date(facture.get("date_facture")),
                "echeance": fmt_date(facture.get("echeance")),
                "jours_retard": facture.get("retard"),
                "niveau_traitement": facture.get("niveau_label"),
                "score_priorite": facture.get("score") if facture.get("score") is not None else "",
                "priorite": facture.get("priorite"),
                "statut": "Payée" if facture.get("statut") == "payee" else "Ouverte",
                "date_paiement": fmt_date(facture.get("date_paiement")),
                "contact": facture.get("contact"),
                "telephone": facture.get("telephone"),
                "email": facture.get("email"),
                "retards_anterieurs": facture.get("retards_anterieurs"),
                "nb_relances": facture.get("nb_actions"),
                "derniere_action": fmt_datetime(facture["derniere_action"]["date_action"]) if facture.get("derniere_action") else "",
                "notes": facture.get("notes"),
            }
        )
    cadre = pd.DataFrame(lignes)
    return _encoder(cadre.to_csv(index=False, sep=SEPARATEUR))


def exporter_actions(actions: list[dict], reglages: dict) -> bytes:
    lignes = []
    for action in actions:
        lignes.append(
            {
                "date_action": fmt_datetime(action.get("date_action")),
                "client": action.get("client"),
                "numero_facture": action.get("numero"),
                "niveau_atteint": config.NIVEAU_LABEL.get(action.get("niveau", ""), action.get("niveau")),
                "action": config.TYPES_ACTION.get(action.get("type_action", ""), action.get("type_action")),
                "canal": action.get("canal"),
                "resultat": config.RESULTATS_ACTION.get(action.get("resultat", ""), action.get("resultat")),
                "jours_retard": action.get("jours_retard"),
                "montant": f"{float(action.get('montant') or 0):.2f}".replace(".", ","),
                "utilisateur": action.get("utilisateur"),
                "commentaire": action.get("commentaire"),
                "message_envoye": (action.get("contenu") or "").replace("\n", " | "),
            }
        )
    cadre = pd.DataFrame(lignes)
    return _encoder(cadre.to_csv(index=False, sep=SEPARATEUR))


# --------------------------------------------------------------------------
# Dossier de recouvrement (preuve à transmettre)
# --------------------------------------------------------------------------
def dossier_recouvrement(facture: dict, reglages: dict, aujourdhui: dt.date | None = None) -> str:
    aujourdhui = aujourdhui or dt.date.today()
    societe = reglages.get("societe", {})
    devise = societe.get("devise", "MAD")
    actions = facture.get("actions") or []

    return f"""DOSSIER DE RECOUVREMENT
Généré le {aujourdhui.strftime('%d/%m/%Y')} par {config.APP_NAME}

CRÉANCIER
{societe.get('nom', 'Mon entreprise')}
{societe.get('telephone', '')} — {societe.get('email', '')}
{societe.get('ville', '')}

DÉBITEUR
{facture.get('client', '')}
Contact : {valeur_ou_tiret(facture.get('contact'))}
Téléphone : {valeur_ou_tiret(facture.get('telephone'))}
Email : {valeur_ou_tiret(facture.get('email'))}

CRÉANCE
Facture n° {facture.get('numero', '')}
Date d'émission : {fmt_date(facture.get('date_facture'))}
Échéance : {fmt_date(facture.get('echeance'))}
Montant : {fmt_montant(facture.get('montant'), devise)}
Retard constaté : {facture.get('retard', 0)} jour(s)
Niveau de traitement atteint : {config.NIVEAU_LABEL.get(facture.get('niveau', ''), facture.get('niveau', ''))}
Score de priorité : {facture.get('score') if facture.get('score') is not None else '—'}/100
Retards antérieurs du client : {facture.get('retards_anterieurs', 0)}

RELANCES EFFECTUÉES ({len(actions)})
{messages.chronologie(actions)}

MESSAGE PRÉPARÉ POUR LE NIVEAU EN COURS
{messages.message_pour(facture, reglages, aujourdhui)}

PIÈCES À JOINDRE
- facture et bon de commande / de livraison ;
- copies des relances (SMS, emails, courriers) et accusés de réception ;
- relevé de compte client.

MENTIONS
Document interne destiné à préparer une action de recouvrement. Les modèles juridiques
doivent être validés par un juriste. Les données personnelles sont traitées dans le cadre
de la loi 09-08 et des règles de la CNDP (finalité, durée de conservation, sécurité).
"""


def nom_fichier(prefixe: str, extension: str = "csv", aujourdhui: dt.date | None = None) -> str:
    aujourdhui = aujourdhui or dt.date.today()
    return f"{prefixe}_{aujourdhui.strftime('%Y%m%d')}.{extension}"
