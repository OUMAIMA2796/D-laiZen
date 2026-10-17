# -*- coding: utf-8 -*-
"""Petits utilitaires de mise en forme (montants, dates, textes)."""

from __future__ import annotations

import datetime as dt

from .scoring import fmt_date, parse_date  # ré-exportés pour commodité

ESPACE_INSECABLE = "\u202f"


def fmt_montant(valeur, devise: str = "MAD", decimales: int = 2) -> str:
    """``55000`` -> ``55 000,00 MAD`` (format français, espace insécable)."""
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        nombre = 0.0
    texte = f"{nombre:,.{decimales}f}"
    texte = texte.replace(",", ESPACE_INSECABLE).replace(".", ",")
    return f"{texte} {devise}".strip()


def fmt_nombre(valeur, decimales: int = 0) -> str:
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        nombre = 0.0
    return f"{nombre:,.{decimales}f}".replace(",", ESPACE_INSECABLE).replace(".", ",")


def fmt_montant_court(valeur, devise: str = "MAD") -> str:
    """Montant abrégé pour les cartes : sans décimales au-delà de 10 000."""
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        nombre = 0.0
    return fmt_montant(nombre, devise, 0 if abs(nombre) >= 10000 else 2)


def fmt_datetime(valeur, fmt: str = "%d/%m/%Y %H:%M") -> str:
    if isinstance(valeur, str):
        try:
            valeur = dt.datetime.fromisoformat(valeur)
        except ValueError:
            date = parse_date(valeur)
            return date.strftime(fmt) if date else "—"
    if isinstance(valeur, dt.datetime):
        return valeur.strftime(fmt)
    date = parse_date(valeur)
    return date.strftime(fmt) if date else "—"


def fmt_jours(nombre: int) -> str:
    if nombre is None:
        return "—"
    return f"{nombre} j"


def pluraliser(nombre: int, singulier: str, pluriel: str | None = None) -> str:
    return singulier if abs(int(nombre)) <= 1 else (pluriel or f"{singulier}s")


def valeur_ou_tiret(valeur, defaut: str = "—") -> str:
    texte = ("" if valeur is None else str(valeur)).strip()
    return texte or defaut


def raccourcir(texte: str, taille: int = 60) -> str:
    texte = (texte or "").strip().replace("\n", " ")
    return texte if len(texte) <= taille else texte[: taille - 1] + "…"
