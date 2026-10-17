# -*- coding: utf-8 -*-
"""Accès à la base SQLite : factures, actions de relance, paramètres."""

from __future__ import annotations

import contextlib
import datetime as dt
import sqlite3
from typing import Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS factures (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client              TEXT    NOT NULL,
    numero              TEXT    NOT NULL,
    montant             REAL    NOT NULL,
    date_facture        TEXT,
    echeance            TEXT    NOT NULL,
    contact             TEXT    NOT NULL DEFAULT '',
    telephone           TEXT    NOT NULL DEFAULT '',
    email               TEXT    NOT NULL DEFAULT '',
    retards_anterieurs  INTEGER NOT NULL DEFAULT 0,
    statut              TEXT    NOT NULL DEFAULT 'ouverte',
    date_paiement       TEXT,
    notes               TEXT    NOT NULL DEFAULT '',
    created_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    facture_id   INTEGER NOT NULL REFERENCES factures(id) ON DELETE CASCADE,
    date_action  TEXT    NOT NULL,
    niveau       TEXT    NOT NULL DEFAULT '',
    type_action  TEXT    NOT NULL DEFAULT 'autre',
    canal        TEXT    NOT NULL DEFAULT '',
    resultat     TEXT    NOT NULL DEFAULT 'fait',
    contenu      TEXT    NOT NULL DEFAULT '',
    commentaire  TEXT    NOT NULL DEFAULT '',
    utilisateur  TEXT    NOT NULL DEFAULT '',
    jours_retard INTEGER NOT NULL DEFAULT 0,
    montant      REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS parametres (
    cle     TEXT PRIMARY KEY,
    valeur  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actions_facture ON actions(facture_id);
CREATE INDEX IF NOT EXISTS idx_factures_echeance ON factures(echeance);
"""

CHAMPS_FACTURE = (
    "client",
    "numero",
    "montant",
    "date_facture",
    "echeance",
    "contact",
    "telephone",
    "email",
    "retards_anterieurs",
    "statut",
    "date_paiement",
    "notes",
)

CHAMPS_ACTION = (
    "facture_id",
    "date_action",
    "niveau",
    "type_action",
    "canal",
    "resultat",
    "contenu",
    "commentaire",
    "utilisateur",
    "jours_retard",
    "montant",
)


# --------------------------------------------------------------------------
# Connexion
# --------------------------------------------------------------------------
def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextlib.contextmanager
def session():
    """Contexte transactionnel : commit si tout se passe bien."""
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with session() as con:
        con.executescript(SCHEMA)


# --------------------------------------------------------------------------
# Paramètres
# --------------------------------------------------------------------------
def get_settings() -> dict:
    """Renvoie les paramètres complets, complétés par les valeurs par défaut."""
    settings = {
        "societe": dict(config.DEFAULT_SOCIETE),
        "seuils": dict(config.DEFAULT_SEUILS),
        "score": dict(config.DEFAULT_SCORE),
        "modeles": dict(config.DEFAULT_MODELES),
    }
    with session() as con:
        rows = con.execute("SELECT cle, valeur FROM parametres").fetchall()

    import json

    for row in rows:
        cle = row["cle"]
        if cle not in settings:
            continue
        try:
            valeur = json.loads(row["valeur"])
        except (TypeError, ValueError):
            continue
        if isinstance(valeur, dict) and isinstance(settings[cle], dict):
            settings[cle].update(valeur)
        else:
            settings[cle] = valeur
    return settings


def save_settings(settings: dict) -> None:
    import json

    with session() as con:
        for cle, valeur in settings.items():
            con.execute(
                "INSERT INTO parametres (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
                (cle, json.dumps(valeur, ensure_ascii=False)),
            )


def reset_settings() -> None:
    with session() as con:
        con.execute("DELETE FROM parametres")


# --------------------------------------------------------------------------
# Factures
# --------------------------------------------------------------------------
def list_factures() -> list[dict]:
    with session() as con:
        rows = con.execute("SELECT * FROM factures ORDER BY echeance").fetchall()
    return [dict(row) for row in rows]


def get_facture(facture_id: int) -> dict | None:
    with session() as con:
        row = con.execute("SELECT * FROM factures WHERE id = ?", (facture_id,)).fetchone()
    return dict(row) if row else None


def create_facture(data: dict) -> int:
    valeurs = {champ: data.get(champ) for champ in CHAMPS_FACTURE}
    valeurs["created_at"] = dt.datetime.now().isoformat(timespec="seconds")
    colonnes = ", ".join(valeurs)
    marqueurs = ", ".join("?" for _ in valeurs)
    with session() as con:
        cur = con.execute(
            f"INSERT INTO factures ({colonnes}) VALUES ({marqueurs})",
            tuple(valeurs.values()),
        )
        return int(cur.lastrowid)


def update_facture(facture_id: int, data: dict) -> None:
    valeurs = {champ: data[champ] for champ in CHAMPS_FACTURE if champ in data}
    if not valeurs:
        return
    affectations = ", ".join(f"{champ} = ?" for champ in valeurs)
    with session() as con:
        con.execute(
            f"UPDATE factures SET {affectations} WHERE id = ?",
            (*valeurs.values(), facture_id),
        )


def delete_facture(facture_id: int) -> None:
    with session() as con:
        con.execute("DELETE FROM factures WHERE id = ?", (facture_id,))


def marquer_payee(facture_id: int, date_paiement: str, utilisateur: str = "", commentaire: str = "") -> None:
    facture = get_facture(facture_id)
    with session() as con:
        con.execute(
            "UPDATE factures SET statut = 'payee', date_paiement = ? WHERE id = ?",
            (date_paiement, facture_id),
        )
        con.execute(
            "INSERT INTO actions (facture_id, date_action, niveau, type_action, canal, resultat, "
            "contenu, commentaire, utilisateur, jours_retard, montant) "
            "VALUES (?, ?, ?, 'paiement', ?, 'paye', ?, ?, ?, ?, ?)",
            (
                facture_id,
                dt.datetime.now().isoformat(timespec="seconds"),
                facture.get("statut", "") if facture else "",
                config.CANAL_ACTION["paiement"],
                f"Facture {facture.get('numero', '')} marquée payée." if facture else "Facture marquée payée.",
                commentaire,
                utilisateur,
                0,
                float(facture.get("montant", 0)) if facture else 0.0,
            ),
        )


def rouvrir_facture(facture_id: int) -> None:
    update_facture(facture_id, {"statut": "ouverte", "date_paiement": None})


# --------------------------------------------------------------------------
# Actions (historique des relances = preuves)
# --------------------------------------------------------------------------
def list_actions(facture_id: int | None = None) -> list[dict]:
    requete = (
        "SELECT a.*, f.client AS client, f.numero AS numero "
        "FROM actions a LEFT JOIN factures f ON f.id = a.facture_id "
    )
    parametres: tuple = ()
    if facture_id is not None:
        requete += "WHERE a.facture_id = ? "
        parametres = (facture_id,)
    requete += "ORDER BY a.date_action DESC, a.id DESC"
    with session() as con:
        rows = con.execute(requete, parametres).fetchall()
    return [dict(row) for row in rows]


def create_action(data: dict) -> int:
    valeurs = {champ: data.get(champ) for champ in CHAMPS_ACTION}
    colonnes = ", ".join(valeurs)
    marqueurs = ", ".join("?" for _ in valeurs)
    with session() as con:
        cur = con.execute(
            f"INSERT INTO actions ({colonnes}) VALUES ({marqueurs})",
            tuple(valeurs.values()),
        )
        return int(cur.lastrowid)


def delete_action(action_id: int) -> None:
    with session() as con:
        con.execute("DELETE FROM actions WHERE id = ?", (action_id,))


def count_factures() -> int:
    with session() as con:
        row = con.execute("SELECT COUNT(*) AS n FROM factures").fetchone()
    return int(row["n"])


# --------------------------------------------------------------------------
# Réinitialisation / jeu de démonstration
# --------------------------------------------------------------------------
def supprimer_tout() -> None:
    with session() as con:
        con.execute("DELETE FROM actions")
        con.execute("DELETE FROM factures")


DEMO_FACTURES: Iterable[dict] = (
    {"client": "Ocean Pro", "numero": "FAC-2026-052", "montant": 55000, "retard": 68,
     "contact": "Mme Alaoui", "telephone": "0661 00 00 05", "email": "finance@oceanpro.example",
     "retards_anterieurs": 4, "notes": "Dossier déjà évoqué avec le conseil juridique."},
    {"client": "Sous Distribution", "numero": "FAC-2026-098", "montant": 40000, "retard": 39,
     "contact": "M. Berrada", "telephone": "0661 00 00 06", "email": "compta@sousdist.example",
     "retards_anterieurs": 2, "notes": "Conteste une partie de la livraison."},
    {"client": "Maroc Bureautique", "numero": "FAC-2026-071", "montant": 18500, "retard": 42,
     "contact": "Service comptabilité", "telephone": "0661 00 00 07", "email": "finance@marocbureau.example",
     "retards_anterieurs": 1, "notes": ""},
    {"client": "Atlas Digital", "numero": "FAC-2026-101", "montant": 25000, "retard": 1,
     "contact": "M. Idrissi", "telephone": "0661 00 00 08", "email": "achats@atlasdigital.example",
     "retards_anterieurs": 0, "notes": ""},
    {"client": "Agadir Services", "numero": "FAC-2026-087", "montant": 12000, "retard": 16,
     "contact": "Mme Chafik", "telephone": "0661 00 00 09", "email": "gestion@agadirservices.example",
     "retards_anterieurs": 1, "notes": ""},
    {"client": "Argan Conseil", "numero": "FAC-2026-110", "montant": 9200, "retard": 0,
     "contact": "M. Naciri", "telephone": "0661 00 00 10", "email": "contact@arganconseil.example",
     "retards_anterieurs": 0, "notes": "Échéance du jour."},
    {"client": "Tiznit Equipement", "numero": "FAC-2026-044", "montant": 7600, "retard": 19,
     "contact": "Mme Sbai", "telephone": "0661 00 00 11", "email": "compta@tiznitequip.example",
     "retards_anterieurs": 0, "notes": "Réglée par virement.", "payee": True},
)


def charger_demo() -> int:
    """Insère un portefeuille de démonstration daté autour d'aujourd'hui."""
    aujourdhui = dt.date.today()
    created = dt.datetime.now().isoformat(timespec="seconds")
    with session() as con:
        for item in DEMO_FACTURES:
            retard = int(item["retard"])
            echeance = aujourdhui - dt.timedelta(days=retard)
            date_facture = echeance - dt.timedelta(days=30)
            payee = bool(item.get("payee"))
            cur = con.execute(
                "INSERT INTO factures (client, numero, montant, date_facture, echeance, contact, "
                "telephone, email, retards_anterieurs, statut, date_paiement, notes, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["client"], item["numero"], float(item["montant"]),
                    date_facture.isoformat(), echeance.isoformat(), item.get("contact", ""),
                    item.get("telephone", ""), item.get("email", ""),
                    int(item.get("retards_anterieurs", 0)),
                    "payee" if payee else "ouverte",
                    (aujourdhui - dt.timedelta(days=retard - 5)).isoformat() if payee else None,
                    item.get("notes", ""), created,
                ),
            )
            facture_id = int(cur.lastrowid)

            # Historique de relances pour les dossiers les plus avancés
            if retard >= 30:
                etapes = [("sms", 3), ("appel", 10), ("email", 20)]
                if retard >= 60:
                    etapes.append(("mise_en_demeure", 32))
                for niveau, depart in etapes:
                    if depart >= retard:
                        continue
                    quand = aujourdhui - dt.timedelta(days=depart)
                    con.execute(
                        "INSERT INTO actions (facture_id, date_action, niveau, type_action, canal, resultat, "
                        "contenu, commentaire, utilisateur, jours_retard, montant) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            facture_id,
                            dt.datetime.combine(quand, dt.time(9, 30)).isoformat(timespec="seconds"),
                            niveau,
                            niveau,
                            config.CANAL_ACTION.get(niveau, ""),
                            "sans_reponse",
                            f"Relance {config.TYPES_ACTION.get(niveau, niveau)} du {quand.strftime('%d/%m/%Y')}.",
                            "Aucun retour du client à ce jour.",
                            config.DEFAULT_SOCIETE["utilisateur"],
                            retard - depart,
                            float(item["montant"]),
                        ),
                    )
    return len(list(DEMO_FACTURES))


def exporter_tout() -> dict[str, list[dict]]:
    return {"factures": list_factures(), "actions": list_actions()}
