# -*- coding: utf-8 -*-
"""Scoring des impayés, niveau de traitement et indicateurs.

Deux mécanismes, deux usages :

* le **scoring** (0 à 100) mesure l'urgence de traiter une facture : il sert à **classer** ;
* le **niveau de traitement** est calculé depuis l'échéance : il sert à **agir**.

Formule du score (pédagogique, transparente et réglable) :

    score = 100 x ( w_retard   x min(retard / ref_retard, 1)
                  + w_montant  x min(montant / ref_montant, 1)
                  + w_histo    x min(retards_passés / ref_retards, 1) )

Chaque composante est plafonnée à 1 : un retard très long ou un montant énorme
n'écrase pas complètement les autres critères.
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

from . import config

FORMATS_DATE = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")

PRIORITES = (
    (80, "Critique", "#ef4444"),
    (60, "Élevée", "#f59e0b"),
    (40, "Modérée", "#3b82f6"),
    (0, "Faible", "#64748b"),
)


# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------
def parse_date(valeur) -> dt.date | None:
    """Convertit une date (str ISO ou française, date, datetime, NaT) en ``date``."""
    if valeur is None:
        return None
    if isinstance(valeur, dt.datetime):
        return valeur.date()
    if isinstance(valeur, dt.date):
        return valeur
    texte = str(valeur).strip()
    if not texte or texte.lower() in {"nan", "nat", "none", "null"}:
        return None
    for fmt in FORMATS_DATE:
        try:
            return dt.datetime.strptime(texte[:10], fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(valeur, fmt: str = "%d/%m/%Y") -> str:
    date = parse_date(valeur)
    return date.strftime(fmt) if date else "—"


def clamp(valeur: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(valeur)))


def normaliser_seuils(seuils: dict) -> dict:
    """Garantit des seuils entiers, positifs et strictement croissants."""
    propre: dict[str, int] = {}
    precedent = 0
    for cle in config.SEUILS_ORDRE:
        try:
            valeur = int(seuils.get(cle, config.DEFAULT_SEUILS[cle]))
        except (TypeError, ValueError):
            valeur = config.DEFAULT_SEUILS[cle]
        valeur = max(1, valeur)
        if valeur <= precedent:
            valeur = precedent + 1
        propre[cle] = valeur
        precedent = valeur
    return propre


def normaliser_score(score: dict) -> dict:
    """Garantit des poids positifs dont la somme vaut 1."""
    propre = dict(config.DEFAULT_SCORE)
    propre.update({cle: valeur for cle, valeur in (score or {}).items() if cle in propre})
    poids = ["poids_retard", "poids_montant", "poids_historique"]
    valeurs = [max(0.0, float(propre.get(cle) or 0)) for cle in poids]
    total = sum(valeurs)
    if total <= 0:
        valeurs = [config.DEFAULT_SCORE[cle] for cle in poids]
        total = sum(valeurs)
    for cle, valeur in zip(poids, valeurs):
        propre[cle] = round(valeur / total, 4)
    for cle in ("ref_retard", "ref_montant", "ref_retards"):
        try:
            propre[cle] = max(1.0, float(propre[cle]))
        except (TypeError, ValueError):
            propre[cle] = float(config.DEFAULT_SCORE[cle])
    return propre


# --------------------------------------------------------------------------
# Niveau de traitement (déclenché par l'échéance)
# --------------------------------------------------------------------------
def jours_de_retard(echeance, aujourdhui: dt.date) -> int:
    date = parse_date(echeance)
    if date is None:
        return 0
    return (aujourdhui - date).days


def niveau_de(facture: dict, seuils: dict, aujourdhui: dt.date) -> str:
    if facture.get("statut") == "payee":
        return "payee"
    retard = jours_de_retard(facture.get("echeance"), aujourdhui)
    if retard < 0:
        return "a_venir"
    if retard == 0:
        return "a_echeance"
    niveau = config.SEUILS_ORDRE[0]
    for cle in config.SEUILS_ORDRE:
        if retard >= int(seuils[cle]):
            niveau = cle
    return niveau


def niveau_suivant(niveau: str, seuils: dict) -> tuple[str | None, int]:
    """Renvoie (niveau suivant, seuil du niveau suivant) ou (None, 0)."""
    if niveau in config.SEUILS_ORDRE:
        index = config.SEUILS_ORDRE.index(niveau) + 1
        if index < len(config.SEUILS_ORDRE):
            suivant = config.SEUILS_ORDRE[index]
            return suivant, int(seuils[suivant])
        return None, 0
    if niveau in ("a_venir", "a_echeance"):
        premier = config.SEUILS_ORDRE[0]
        return premier, int(seuils[premier])
    return None, 0


# --------------------------------------------------------------------------
# Scoring (classement)
# --------------------------------------------------------------------------
def score_de(facture: dict, score_settings: dict, aujourdhui: dt.date) -> tuple[int | None, dict]:
    """Score 0-100 d'une facture en retard (``None`` si elle n'est pas en retard)."""
    if facture.get("statut") == "payee":
        return 0, {"raison": "Facture payée", "composantes": {}, "normalise": {}}

    retard = jours_de_retard(facture.get("echeance"), aujourdhui)
    if retard <= 0:
        return None, {"raison": "Pas encore en retard", "composantes": {}, "normalise": {}}

    montant = float(facture.get("montant") or 0)
    anterieurs = max(0, int(facture.get("retards_anterieurs") or 0))

    normalise = {
        "retard": clamp(retard / score_settings["ref_retard"]),
        "montant": clamp(montant / score_settings["ref_montant"]),
        "historique": clamp(anterieurs / score_settings["ref_retards"]),
    }
    composantes = {
        "retard": 100 * score_settings["poids_retard"] * normalise["retard"],
        "montant": 100 * score_settings["poids_montant"] * normalise["montant"],
        "historique": 100 * score_settings["poids_historique"] * normalise["historique"],
    }
    total = round(sum(composantes.values()))
    return max(1, min(100, total)), {"composantes": composantes, "normalise": normalise}


def libelle_priorite(score: int | None) -> tuple[str, str]:
    if score is None:
        return "Surveillance", "#94a3b8"
    for seuil, libelle, couleur in PRIORITES:
        if score >= seuil:
            return libelle, couleur
    return "Faible", "#64748b"


# --------------------------------------------------------------------------
# Enrichissement du portefeuille
# --------------------------------------------------------------------------
def enrichir(
    factures: Iterable[dict],
    actions: Iterable[dict],
    settings: dict,
    aujourdhui: dt.date | None = None,
) -> list[dict]:
    """Ajoute retard, niveau, score, échéance du prochain seuil et état de relance."""
    aujourdhui = aujourdhui or dt.date.today()
    seuils = normaliser_seuils(settings.get("seuils", {}))
    score_settings = normaliser_score(settings.get("score", {}))

    actions_par_facture: dict[int, list[dict]] = {}
    for action in actions:
        actions_par_facture.setdefault(int(action["facture_id"]), []).append(action)

    resultat: list[dict] = []
    for facture in factures:
        ligne = dict(facture)
        retard = jours_de_retard(ligne.get("echeance"), aujourdhui)
        niveau = niveau_de(ligne, seuils, aujourdhui)
        score, detail = score_de(ligne, score_settings, aujourdhui)
        suivant, seuil_suivant = niveau_suivant(niveau, seuils)

        jalons = actions_par_facture.get(int(ligne["id"]), [])
        jalons = sorted(jalons, key=lambda a: (a.get("date_action") or "", a.get("id") or 0), reverse=True)

        # Une action est "à jour" si elle a été enregistrée depuis l'entrée dans le niveau courant.
        action_a_jour = False
        entree_niveau: dt.date | None = None
        if niveau in config.SEUILS_ORDRE:
            entree_niveau = aujourdhui - dt.timedelta(days=max(0, retard - int(seuils[niveau])))
            type_attendu = config.ACTION_DU_NIVEAU.get(niveau)
            for action in jalons:
                if action.get("type_action") != type_attendu:
                    continue
                date_action = parse_date(action.get("date_action"))
                if date_action and date_action >= entree_niveau:
                    action_a_jour = True
                    break

        ligne.update(
            {
                "retard": retard,
                "niveau": niveau,
                "niveau_court": config.NIVEAU_COURT.get(niveau, niveau),
                "niveau_label": config.NIVEAU_LABEL.get(niveau, niveau),
                "score": score,
                "score_detail": detail,
                "priorite": libelle_priorite(score)[0],
                "priorite_couleur": libelle_priorite(score)[1],
                "niveau_suivant": suivant,
                "seuil_suivant": seuil_suivant,
                "jours_avant_prochain": (seuil_suivant - retard) if suivant else None,
                "echeance_parse": parse_date(ligne.get("echeance")),
                "date_facture_parse": parse_date(ligne.get("date_facture")),
                "date_paiement_parse": parse_date(ligne.get("date_paiement")),
                "actions": jalons,
                "nb_actions": len(jalons),
                "derniere_action": jalons[0] if jalons else None,
                "action_a_jour": action_a_jour,
                "en_retard": niveau in config.SEUILS_ORDRE,
            }
        )
        resultat.append(ligne)

    resultat.sort(
        key=lambda f: (
            -(f["score"] if f["score"] is not None else -1),
            -f["retard"],
            -float(f["montant"] or 0),
        )
    )
    return resultat


# --------------------------------------------------------------------------
# Indicateurs (synthèse)
# --------------------------------------------------------------------------
def kpis(portefeuille: Iterable[dict]) -> dict:
    lignes = list(portefeuille)
    ouvertes = [f for f in lignes if f.get("statut") != "payee"]
    en_retard = [f for f in ouvertes if f["en_retard"]]
    payees = [f for f in lignes if f.get("statut") == "payee"]
    avocat = [f for f in en_retard if f["niveau"] == "avocat"]
    a_transmettre = [f for f in en_retard if f["niveau"] in ("mise_en_demeure", "avocat")]

    montant_ouvert = sum(float(f["montant"] or 0) for f in ouvertes)
    montant_retard = sum(float(f["montant"] or 0) for f in en_retard)
    montant_paye = sum(float(f["montant"] or 0) for f in payees)
    retards = [f["retard"] for f in en_retard]

    return {
        "montant_ouvert": montant_ouvert,
        "montant_retard": montant_retard,
        "montant_paye": montant_paye,
        "nb_factures": len(lignes),
        "nb_ouvertes": len(ouvertes),
        "nb_retard": len(en_retard),
        "nb_payees": len(payees),
        "nb_avocat": len(avocat),
        "nb_juridique": len(a_transmettre),
        "retard_moyen": round(sum(retards) / len(retards)) if retards else 0,
        "retard_max": max(retards) if retards else 0,
        "nb_a_traiter": len([f for f in en_retard if not f["action_a_jour"]]),
        "part_retard": (montant_retard / montant_ouvert) if montant_ouvert else 0.0,
        "score_moyen": round(sum(f["score"] for f in en_retard) / len(en_retard)) if en_retard else 0,
    }


def repartition(portefeuille: Iterable[dict]) -> dict[str, dict]:
    """Nombre de factures et montant par niveau de traitement."""
    stats: dict[str, dict] = {}
    for cle in list(config.SEUILS_ORDRE) + ["a_echeance", "a_venir", "payee"]:
        stats[cle] = {"nb": 0, "montant": 0.0}
    for facture in portefeuille:
        entree = stats.setdefault(facture["niveau"], {"nb": 0, "montant": 0.0})
        entree["nb"] += 1
        entree["montant"] += float(facture["montant"] or 0)
    return stats


def evolution_encours(
    portefeuille: Iterable[dict],
    jours: int = 90,
    aujourdhui: dt.date | None = None,
) -> list[dict]:
    """Reconstitue jour par jour l'encours impayé et sa partie en retard.

    Une facture compte dans l'encours à partir de sa date de facture (ou de son
    échéance si la date de facture n'est pas renseignée) jusqu'à son paiement.
    """
    aujourdhui = aujourdhui or dt.date.today()
    lignes = []
    for facture in portefeuille:
        debut = facture.get("date_facture_parse") or facture.get("echeance_parse")
        fin = facture.get("date_paiement_parse")
        lignes.append(
            {
                "debut": debut,
                "fin": fin,
                "echeance": facture.get("echeance_parse"),
                "montant": float(facture.get("montant") or 0),
            }
        )

    courbe = []
    for delta in range(jours - 1, -1, -1):
        jour = aujourdhui - dt.timedelta(days=delta)
        encours = 0.0
        en_retard = 0.0
        for ligne in lignes:
            if ligne["debut"] and ligne["debut"] > jour:
                continue
            if ligne["fin"] and ligne["fin"] <= jour:
                continue
            encours += ligne["montant"]
            if ligne["echeance"] and ligne["echeance"] < jour:
                en_retard += ligne["montant"]
        courbe.append({"date": jour, "encours": encours, "retard": en_retard})
    return courbe


def montant_total(portefeuille: Iterable[dict]) -> float:
    return sum(float(f["montant"] or 0) for f in portefeuille)


def dso_estime(portefeuille: Iterable[dict]) -> int:
    """Âge moyen pondéré par le montant des factures ouvertes (en jours)."""
    ouvertes = [f for f in portefeuille if f.get("statut") != "payee"]
    total = sum(float(f["montant"] or 0) for f in ouvertes)
    if not total:
        return 0
    age = sum(max(0, f["retard"]) * float(f["montant"] or 0) for f in ouvertes)
    return round(age / total)
