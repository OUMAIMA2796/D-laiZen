# -*- coding: utf-8 -*-
"""Constantes, valeurs par défaut et emplacements de fichiers."""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Emplacements
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DELAIZEN_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("DELAIZEN_DB", DATA_DIR / "delai_zen.db"))

APP_NAME = "DélaiZen"
APP_VERSION = "1.0.0"
APP_TAGLINE = "Scoring des impayés — savoir qui relancer, comment et avec quel message"

# --------------------------------------------------------------------------
# Niveaux de traitement
# --------------------------------------------------------------------------
# L'ordre des seuils est important : du plus faible au plus élevé.
SEUILS_ORDRE = ["sms", "appel", "email", "mise_en_demeure", "avocat"]

NIVEAU_LABEL = {
    "a_venir": "À venir",
    "a_echeance": "À échéance",
    "sms": "SMS de rappel",
    "appel": "Appel téléphonique",
    "email": "Email personnalisé",
    "mise_en_demeure": "Mise en demeure",
    "avocat": "Transmission à l'avocat",
    "payee": "Payée",
}

NIVEAU_COURT = {
    "a_venir": "À venir",
    "a_echeance": "À échéance",
    "sms": "SMS",
    "appel": "Appel",
    "email": "Email",
    "mise_en_demeure": "Mise en demeure",
    "avocat": "Avocat",
    "payee": "Payée",
}

NIVEAU_ICON = {
    "a_venir": "🗓️",
    "a_echeance": "📅",
    "sms": "💬",
    "appel": "📞",
    "email": "✉️",
    "mise_en_demeure": "📄",
    "avocat": "⚖️",
    "payee": "✅",
}

NIVEAU_COLOR = {
    "a_venir": "#94a3b8",
    "a_echeance": "#64748b",
    "sms": "#10b981",
    "appel": "#8b5cf6",
    "email": "#3b82f6",
    "mise_en_demeure": "#f59e0b",
    "avocat": "#ef4444",
    "payee": "#059669",
}

# Types d'action tracés dans l'historique
TYPES_ACTION = {
    "sms": "SMS de rappel",
    "appel": "Appel téléphonique",
    "email": "Email de relance",
    "mise_en_demeure": "Mise en demeure",
    "avocat": "Transmission avocat",
    "paiement": "Encaissement",
    "note_interne": "Note interne",
    "autre": "Autre",
}

CANAL_ACTION = {
    "sms": "SMS",
    "appel": "Téléphone",
    "email": "Email",
    "mise_en_demeure": "Courrier",
    "avocat": "Juridique",
    "paiement": "Banque",
    "note_interne": "Interne",
    "autre": "Autre",
}

RESULTATS_ACTION = {
    "fait": "Envoyé / fait",
    "sans_reponse": "Sans réponse",
    "promesse_paiement": "Promesse de paiement",
    "conteste": "Contesté par le client",
    "paye": "Réglé",
    "autre": "Autre",
}

# Le type d'action attendu pour chaque niveau de traitement
ACTION_DU_NIVEAU = {
    "sms": "sms",
    "appel": "appel",
    "email": "email",
    "mise_en_demeure": "mise_en_demeure",
    "avocat": "avocat",
}

# --------------------------------------------------------------------------
# Réglages par défaut (modifiables dans l'écran Paramètres)
# --------------------------------------------------------------------------
DEFAULT_SEUILS = {
    "sms": 1,
    "appel": 8,
    "email": 15,
    "mise_en_demeure": 30,
    "avocat": 60,
}

DEFAULT_SCORE = {
    # Poids relatifs (la somme est normalisée à 1)
    "poids_retard": 0.55,
    "poids_montant": 0.30,
    "poids_historique": 0.15,
    # Valeurs de référence servant de plafond à chaque critère
    "ref_retard": 90,        # à 90 jours de retard, le critère sature
    "ref_montant": 50000.0,  # en devise de l'entreprise
    "ref_retards": 5,        # nombre de retards passés faisant saturer le critère
}

DEFAULT_SOCIETE = {
    "nom": "Mon entreprise",
    "devise": "MAD",
    "utilisateur": "Responsable financier",
    "telephone": "0522 00 00 00",
    "email": "contact@mon-entreprise.ma",
    "ville": "Casablanca",
    "delai_email_jours": 2,
    "delai_mise_en_demeure_jours": 8,
}

DEFAULT_MODELES = {
    "sms": (
        "Bonjour {client}, {societe} : la facture {facture} de {montant} {devise}, "
        "echeance du {echeance}, reste a regler ({retard} {retard_mot} de retard). "
        "Merci de nous indiquer une date de paiement ou de nous appeler au {telephone_societe}. "
        "Si vous avez deja paye, merci d'ignorer ce message."
    ),
    "appel": (
        "SCRIPT D'APPEL — relance téléphonique ({retard} {retard_mot} de retard)\n"
        "\n"
        "1. Ouverture : « Bonjour, {societe} à l'appareil, je souhaite échanger avec le service comptabilité. »\n"
        "2. Identification : confirmer que l'on parle bien à {client} ({contact}).\n"
        "3. Objet : « Nous n'avons pas reçu le règlement de la facture {facture} d'un montant de {montant} {devise}, "
        "échue le {echeance}. »\n"
        "4. Constat : « À ce jour, le retard est de {retard} {retard_mot}. »\n"
        "5. Question ouverte : « Avez-vous rencontré une difficulté particulière ? »\n"
        "6. Demande : obtenir une date de règlement ferme ou un échéancier écrit avant le {date_limite}. Noter la réponse.\n"
        "7. Clôture : « Je note donc votre engagement. Je vous envoie un rappel écrit pour confirmation. Merci de votre collaboration. »\n"
        "8. Après l'appel : enregistrer l'action dans DélaiZen (résultat + date promise) puis envoyer l'email de confirmation.\n"
        "\n"
        "Si le client ne répond pas : réessayer à une heure différente, laisser un message court, puis consigner « sans réponse »."
    ),
    "email": (
        "Objet : Relance — facture {facture} de {montant} {devise} ({retard} {retard_mot} de retard)\n"
        "\n"
        "Bonjour {contact},\n"
        "\n"
        "Sauf erreur de notre part, la facture {facture} d'un montant de {montant} {devise}, échue le {echeance}, "
        "reste impayée à ce jour, soit un retard de {retard} {retard_mot}.\n"
        "\n"
        "Nous vous remercions de bien vouloir procéder au règlement avant le {date_limite}, ou de nous contacter "
        "au {telephone_societe} si un échelonnement vous paraît nécessaire.\n"
        "\n"
        "Si le paiement a été effectué entre-temps, merci d'ignorer ce message et de nous transmettre la référence du virement.\n"
        "\n"
        "Cordialement,\n"
        "{utilisateur}\n"
        "{societe} — {telephone_societe}"
    ),
    "mise_en_demeure": (
        "{societe}\n"
        "[Adresse] — ICE : [ICE] — RC : [RC]\n"
        "\n"
        "MISE EN DEMEURE DE PAYER\n"
        "Lettre recommandée avec accusé de réception\n"
        "\n"
        "À l'attention de {client}\n"
        "[Adresse du client]\n"
        "\n"
        "Objet : mise en demeure de payer la facture {facture}\n"
        "\n"
        "Madame, Monsieur,\n"
        "\n"
        "Nous constatons que la facture {facture} d'un montant de {montant} {devise}, émise le {date_facture} "
        "et échue le {echeance}, demeure impayée à ce jour, soit {retard} {retard_mot} de retard "
        "({nombre_relances} relance(s) effectuée(s), dernière en date du {derniere_relance}).\n"
        "\n"
        "Malgré nos relances, aucune régularisation n'est intervenue. Par la présente, nous vous mettons en demeure "
        "de payer la somme de {montant} {devise} sous huitaine à compter de la réception de ce courrier.\n"
        "\n"
        "À défaut de règlement dans ce délai, nous serons contraints d'engager les mesures de recouvrement nécessaires, "
        "y compris judiciaires, les frais et intérêts restant à votre charge.\n"
        "\n"
        "Vous pouvez nous joindre au {telephone_societe} pour toute question ou pour convenir d'un échéancier.\n"
        "\n"
        "Fait à {ville}, le {date_du_jour}\n"
        "\n"
        "{utilisateur}\n"
        "{societe}\n"
        "\n"
        "— Modèle à faire valider par un juriste avant tout envoi."
    ),
    "avocat": (
        "NOTE DE TRANSMISSION AU CONSEIL JURIDIQUE\n"
        "\n"
        "Dossier : {client} — facture {facture}\n"
        "Montant réclamé : {montant} {devise}\n"
        "Date de facture : {date_facture} — échéance : {echeance}\n"
        "Retard constaté : {retard} {retard_mot}\n"
        "Score de priorité : {score}/100\n"
        "Coordonnées : {telephone} / {email}\n"
        "\n"
        "SITUATION\n"
        "Le client n'a pas réglé la facture {facture} malgré {nombre_relances} relance(s), "
        "dont la dernière en date du {derniere_relance}. Le passage au niveau {prochain_niveau} "
        "est prévu dans {jours_avant_prochain} jour(s).\n"
        "\n"
        "CHRONOLOGIE DES RELANCES\n"
        "{chronologie}\n"
        "\n"
        "PIÈCES À JOINDRE\n"
        "- facture et bon de commande / de livraison signés ;\n"
        "- preuves de relance (copies SMS, emails, courriers et accusés de réception) ;\n"
        "- relevé de compte client et échéanciers éventuels.\n"
        "\n"
        "PROCHAINES ÉTAPES\n"
        "1. Valider la prescription applicable et le calcul des intérêts de retard.\n"
        "2. Apprécier l'opportunité d'une mise en demeure complémentaire ou d'une injonction de payer.\n"
        "3. Chiffrer les frais de recouvrement à refacturer.\n"
        "\n"
        "— Note préparée automatiquement par DélaiZen : à valider par un juriste avant tout usage."
    ),
}

DEFAULT_SETTINGS = {
    "societe": DEFAULT_SOCIETE,
    "seuils": DEFAULT_SEUILS,
    "score": DEFAULT_SCORE,
    "modeles": DEFAULT_MODELES,
}

DEVISES = ["MAD", "EUR", "USD", "XOF", "TND", "DZD"]

MENTIONS_JURIDIQUES = """**Points juridiques et données personnelles**

- Les modèles de **mise en demeure** et de **note à l'avocat** sont des brouillons. Un juriste doit les valider
  avant tout envoi, ainsi que les seuils de **30** et **60** jours.
- Les noms, téléphones et emails des clients sont des **données personnelles**. Au Maroc, vérifiez vos obligations
  au titre de la **loi 09-08** et auprès de la **CNDP** : finalité du traitement, information des personnes,
  durée de conservation, sécurité des accès.
- Conservez les **preuves de relance** (dates, canaux, contenus) : c'est ce que l'historique de DélaiZen produit,
  utile si le dossier est transmis à un avocat.
"""
