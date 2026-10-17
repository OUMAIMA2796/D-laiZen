# -*- coding: utf-8 -*-
"""Accès aux données et à l'état de session, partagés par les pages."""

from __future__ import annotations

import datetime as dt

import streamlit as st

from . import db, scoring

CLE_FLASH = "_dz_flash"
CLE_DATE = "_dz_date_simulation"


# --------------------------------------------------------------------------
# Données
# --------------------------------------------------------------------------
def settings() -> dict:
    return db.get_settings()


def factures() -> list[dict]:
    return db.list_factures()


def actions(facture_id: int | None = None) -> list[dict]:
    return db.list_actions(facture_id)


def aujourdhui() -> dt.date:
    """Date de travail : la date du jour, ou la date de simulation choisie."""
    simulee = st.session_state.get(CLE_DATE)
    return simulee if isinstance(simulee, dt.date) else dt.date.today()


def portefeuille(reglages: dict | None = None) -> list[dict]:
    reglages = reglages or settings()
    return scoring.enrichir(db.list_factures(), db.list_actions(), reglages, aujourdhui())


def libelle_date_simulation() -> str:
    if st.session_state.get(CLE_DATE):
        return f"Date de simulation : {aujourdhui().strftime('%d/%m/%Y')}"
    return f"Date du jour : {aujourdhui().strftime('%d/%m/%Y')}"


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
def flash(message: str, icon: str = "✅") -> None:
    st.session_state.setdefault(CLE_FLASH, []).append((message, icon))


def afficher_flash() -> None:
    messages = st.session_state.pop(CLE_FLASH, [])
    for message, icon in messages:
        st.toast(message, icon=icon)


def rafraichir() -> None:
    st.rerun()


# --------------------------------------------------------------------------
# Sélection courante (tableaux, fiches, formulaires)
# --------------------------------------------------------------------------
def selection() -> int | None:
    valeur = st.session_state.get("_dz_selection")
    return int(valeur) if valeur else None


def definir_selection(facture_id: int | None) -> None:
    st.session_state["_dz_selection"] = int(facture_id) if facture_id else None


def facture_selectionnee(portefeuille: list[dict] | None = None) -> dict | None:
    identifiant = selection()
    if not identifiant:
        return None
    lignes = portefeuille if portefeuille is not None else portefeuille_global()
    for ligne in lignes:
        if int(ligne["id"]) == identifiant:
            return ligne
    return None


def portefeuille_global() -> list[dict]:
    return portefeuille()
