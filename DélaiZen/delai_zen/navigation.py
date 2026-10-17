# -*- coding: utf-8 -*-
"""Déclaration des pages et navigation (utilisable depuis n'importe quelle page)."""

from __future__ import annotations

import streamlit as st


def pages() -> dict[str, st.Page]:
    """Construit les pages de l'application (appelé à chaque exécution)."""
    from views import aide, dashboard, factures, parametres, relances, suivi

    return {
        "tableau-de-bord": st.Page(
            dashboard.render,
            title="Tableau de bord",
            icon="📊",
            url_path="tableau-de-bord",
            default=True,
        ),
        "relances": st.Page(relances.render, title="Relances du jour", icon="🔔", url_path="relances"),
        "factures": st.Page(factures.render, title="Factures", icon="📄", url_path="factures"),
        "suivi": st.Page(suivi.render, title="Suivi des actions", icon="🗂️", url_path="suivi"),
        "parametres": st.Page(parametres.render, title="Paramètres", icon="⚙️", url_path="parametres"),
        "aide": st.Page(aide.render, title="Aide & méthode", icon="❓", url_path="aide"),
    }


def sections() -> dict[str, list[st.Page]]:
    """Structure du menu latéral."""
    pages_ = pages()
    return {
        "Pilotage": [pages_["tableau-de-bord"], pages_["relances"]],
        "Gestion": [pages_["factures"], pages_["suivi"]],
        "Configuration": [pages_["parametres"], pages_["aide"]],
    }


def aller(cle: str) -> None:
    """Ouvre une page par sa clé (``tableau-de-bord``, ``factures``, …)."""
    cible = pages().get(cle)
    if cible is None:
        raise KeyError(f"Page inconnue : {cle}")
    st.switch_page(cible)
