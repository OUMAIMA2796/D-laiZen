# -*- coding: utf-8 -*-
"""Suivi des actions : historique des relances, preuves et corrections."""

from __future__ import annotations

import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from delai_zen import config, db, import_export, scoring, state, texte, ui


def _filtres(actions: list[dict], aujourdhui: dt.date) -> list[dict]:
    lignes = list(actions)
    colonnes = st.columns([2, 1.2, 1.2, 1.6])
    with colonnes[0]:
        recherche = st.text_input(
            "Rechercher", placeholder="Client, n° de facture, commentaire…", key="dz_recherche_action"
        )
    with colonnes[1]:
        type_action = st.selectbox(
            "Type d'action",
            ["Tous"] + list(config.TYPES_ACTION),
            format_func=lambda v: v if v == "Tous" else config.TYPES_ACTION[v],
            key="dz_filtre_type_action",
        )
    with colonnes[2]:
        resultat = st.selectbox(
            "Résultat",
            ["Tous"] + list(config.RESULTATS_ACTION),
            format_func=lambda v: v if v == "Tous" else config.RESULTATS_ACTION[v],
            key="dz_filtre_resultat",
        )
    with colonnes[3]:
        periode = st.date_input(
            "Période",
            value=(aujourdhui - dt.timedelta(days=90), aujourdhui),
            key="dz_filtre_periode",
        )

    if recherche.strip():
        terme = recherche.strip().lower()
        lignes = [
            action
            for action in lignes
            if terme
            in " ".join(
                str(action.get(champ) or "")
                for champ in ("client", "numero", "commentaire", "contenu", "utilisateur")
            ).lower()
        ]
    if type_action != "Tous":
        lignes = [a for a in lignes if a.get("type_action") == type_action]
    if resultat != "Tous":
        lignes = [a for a in lignes if a.get("resultat") == resultat]
    if isinstance(periode, (tuple, list)) and len(periode) == 2:
        debut, fin = periode
        lignes = [
            a
            for a in lignes
            if (date := scoring.parse_date(a.get("date_action"))) and debut <= date <= fin
        ]
    return lignes


def _tableau(actions: list[dict], reglages: dict) -> None:
    if not actions:
        st.info("Aucune action ne correspond à ces critères.")
        return
    donnees = [
        {
            "Date": texte.fmt_datetime(action.get("date_action")),
            "Client": action.get("client") or "—",
            "N° facture": action.get("numero") or "—",
            "Niveau atteint": config.NIVEAU_LABEL.get(action.get("niveau", ""), action.get("niveau")),
            "Action": config.TYPES_ACTION.get(action.get("type_action", ""), action.get("type_action")),
            "Canal": action.get("canal"),
            "Résultat": config.RESULTATS_ACTION.get(action.get("resultat", ""), action.get("resultat")),
            "Retard (j)": int(action.get("jours_retard") or 0),
            "Montant": float(action.get("montant") or 0),
            "Par": action.get("utilisateur"),
            "Commentaire": action.get("commentaire"),
        }
        for action in actions
    ]
    st.dataframe(donnees, hide_index=True, width="stretch", height=380)


def _graphique_actions(actions: list[dict]) -> None:
    if not actions:
        return
    compteurs: dict[str, int] = {}
    for action in actions:
        cle = action.get("type_action", "autre")
        compteurs[cle] = compteurs.get(cle, 0) + 1
    ordre = [cle for cle in config.TYPES_ACTION if cle in compteurs]
    figure = go.Figure(
        go.Bar(
            x=[compteurs[cle] for cle in ordre],
            y=[config.TYPES_ACTION[cle] for cle in ordre],
            orientation="h",
            marker=dict(color=[config.NIVEAU_COLOR.get(config.ACTION_DU_NIVEAU.get(cle, ""), "#94a3b8") for cle in ordre]),
            hovertemplate="%{y} : %{x}<extra></extra>",
        )
    )
    figure.update_layout(
        height=260,
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis=dict(title=None, gridcolor="#eef2f7"),
        yaxis=dict(autorange="reversed", title=None),
        showlegend=False,
    )
    st.plotly_chart(figure, key="dz_bar_actions", theme=None, width="stretch")


def _preuve_par_facture(lignes: list[dict], reglages: dict, aujourdhui: dt.date) -> None:
    ui.titre_section(
        "Preuve de relance par facture",
        "Ce que DélaiZen peut produire si le dossier part chez un avocat : les relances datées, une par une.",
    )
    if not lignes:
        st.info("Aucune facture enregistrée.")
        return
    identifiants = [int(f["id"]) for f in lignes]
    libelles = {int(f["id"]): f"{f['client']} — {f['numero']}" for f in lignes}
    identifiant = st.selectbox(
        "Facture",
        identifiants,
        format_func=lambda i: libelles.get(i, str(i)),
        key="dz_preuve_facture",
    )
    facture = next(f for f in lignes if int(f["id"]) == int(identifiant))
    gauche, droite = st.columns([1.1, 1])
    with gauche:
        st.markdown(ui.chronologie_html(facture.get("actions") or []), unsafe_allow_html=True)
    with droite:
        st.markdown(
            f"**{facture['client']}** — facture {facture['numero']}  \n"
            f"{texte.fmt_montant(facture['montant'], reglages['societe'].get('devise', 'MAD'))} · "
            f"retard {facture['retard']} j · niveau {facture['niveau_court']}  \n"
            f"{facture.get('nb_actions', 0)} relance(s) enregistrée(s)"
        )
        dossier = import_export.dossier_recouvrement(facture, reglages, aujourdhui)
        st.download_button(
            "⬇️ Dossier de recouvrement (texte)",
            data=dossier.encode("utf-8-sig"),
            file_name=f"dossier_{facture['numero']}.txt",
            mime="text/plain",
            key="dz_preuve_dossier",
        )
        with st.expander("Aperçu du dossier", expanded=False):
            st.code(dossier, language=None, wrap_lines=True, height=260)


def render() -> None:
    reglages = state.settings()
    lignes = state.portefeuille(reglages)
    aujourdhui = state.aujourdhui()
    actions = state.actions()
    state.afficher_flash()
    ui.entete(reglages, lignes, aujourdhui)

    ui.titre_section(
        "Suivi des actions",
        "L'historique des relances : c'est la preuve de ce qui a été fait et quand.",
    )
    if not actions:
        st.info(
            "Aucune relance enregistrée pour l'instant. Ouvrez une facture dans **Relances du jour** "
            "et journalisez l'action effectuée."
        )
        return

    debut_mois = aujourdhui.replace(day=1)
    ce_mois = [a for a in actions if (d := scoring.parse_date(a.get("date_action"))) and d >= debut_mois]
    sans_reponse = [a for a in actions if a.get("resultat") == "sans_reponse"]
    clients = {a.get("client") for a in actions if a.get("client")}

    colonnes = st.columns(4)
    with colonnes[0]:
        ui.kpi_card("Actions enregistrées", str(len(actions)), f"dont {len(ce_mois)} ce mois-ci", "#0f172a", "🗂️")
    with colonnes[1]:
        ui.kpi_card("Clients relancés", str(len(clients)), "clients distincts concernés", "#3b82f6", "👥")
    with colonnes[2]:
        ui.kpi_card("Sans réponse", str(len(sans_reponse)), "à relancer ou à escalader", "#f59e0b", "⏳")
    with colonnes[3]:
        encaissements = [a for a in actions if a.get("type_action") == "paiement"]
        ui.kpi_card(
            "Factures encaissées",
            str(len(encaissements)),
            texte.fmt_montant_court(sum(float(a.get("montant") or 0) for a in encaissements), reglages["societe"].get("devise", "MAD")),
            "#10b981",
            "✅",
        )

    st.divider()
    onglets = st.tabs(["📜 Historique", "📊 Répartition", "🧾 Preuves", "🧹 Corriger"])
    with onglets[0]:
        filtrees = _filtres(actions, aujourdhui)
        st.caption(f"{len(filtrees)} action(s) affichée(s).")
        _tableau(filtrees, reglages)
        st.download_button(
            "⬇️ Exporter cet historique (CSV)",
            data=import_export.exporter_actions(filtrees, reglages),
            file_name=import_export.nom_fichier("delaizen_relances", "csv", aujourdhui),
            mime="text/csv",
            key="dz_export_actions_suivi",
        )
    with onglets[1]:
        _graphique_actions(actions)
    with onglets[2]:
        _preuve_par_facture(lignes, reglages, aujourdhui)
    with onglets[3]:
        st.caption("Corriger une saisie : la suppression est définitive.")
        options = [int(a["id"]) for a in actions]
        libelles = {
            int(a["id"]): f"{texte.fmt_datetime(a.get('date_action'))} — {a.get('client')} — "
            f"{config.TYPES_ACTION.get(a.get('type_action', ''), '')}"
            for a in actions
        }
        identifiant = st.selectbox(
            "Action à supprimer",
            options,
            format_func=lambda i: libelles.get(i, str(i)),
            key="dz_action_a_supprimer",
        )
        if st.button("🗑️ Supprimer cette action", key="dz_supprimer_action"):
            db.delete_action(int(identifiant))
            state.flash("Action supprimée", "🗑️")
            st.rerun()

    st.caption(
        "💡 Ces données restent locales (fichier SQLite). Pensez à exporter régulièrement "
        "l'historique : c'est votre preuve de relance."
    )
