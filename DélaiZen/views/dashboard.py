# -*- coding: utf-8 -*-
"""Tableau de bord : synthèse, répartition par niveau et file prioritaire."""

from __future__ import annotations

import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from delai_zen import config, scoring, state, texte, ui
from views import composants


def _graphique_repartition(lignes: list[dict]) -> str | None:
    stats = scoring.repartition(lignes)
    # « À venir » regroupe les factures non échues et celles échues du jour.
    groupes = [
        ("a_venir", config.NIVEAU_COURT["a_venir"], ["a_venir", "a_echeance"]),
        ("sms", config.NIVEAU_COURT["sms"], ["sms"]),
        ("appel", config.NIVEAU_COURT["appel"], ["appel"]),
        ("email", config.NIVEAU_COURT["email"], ["email"]),
        ("mise_en_demeure", config.NIVEAU_COURT["mise_en_demeure"], ["mise_en_demeure"]),
        ("avocat", config.NIVEAU_COURT["avocat"], ["avocat"]),
        ("payee", config.NIVEAU_COURT["payee"], ["payee"]),
    ]

    labels, valeurs, couleurs = [], [], []
    for cle, libelle, cles in groupes:
        nombre = sum(stats.get(c, {}).get("nb", 0) for c in cles)
        if nombre:
            labels.append(libelle)
            valeurs.append(nombre)
            couleurs.append(config.NIVEAU_COLOR[cle])

    total = sum(valeurs)
    if not total:
        st.info("Aucune facture à répartir.")
        return None

    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=valeurs,
            hole=0.62,
            marker=dict(colors=couleurs, line=dict(color="#ffffff", width=2)),
            textinfo="none",
            hovertemplate="%{label} : %{value} facture(s)<extra></extra>",
            sort=False,
        )
    )
    figure.update_layout(
        showlegend=True,
        legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=11, color="#475569")),
        margin=dict(t=10, b=10, l=10, r=10),
        height=330,
        annotations=[
            dict(
                text=f"<b>{total}</b><br><span style='font-size:11px'>factures</span>",
                x=0.5,
                y=0.5,
                font=dict(size=17, color="#0f172a"),
                showarrow=False,
            )
        ],
    )
    evenement = st.plotly_chart(
        figure,
        key="dz_donut_niveaux",
        on_select="rerun",
        selection_mode="points",
        theme=None,
        width="stretch",
    )
    return composants.niveau_clique(evenement)


def _graphique_evolution(lignes: list[dict], reglages: dict, aujourdhui: dt.date) -> None:
    devise = reglages["societe"].get("devise", "MAD")
    courbe = scoring.evolution_encours(lignes, jours=90, aujourdhui=aujourdhui)
    if not courbe:
        return
    dates = [point["date"] for point in courbe]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=[point["encours"] for point in courbe],
            mode="lines",
            name="Encours impayé",
            line=dict(color="#0f172a", width=2),
            fill="tozeroy",
            fillcolor="rgba(148,163,184,0.18)",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=[point["retard"] for point in courbe],
            mode="lines",
            name="Dont en retard",
            line=dict(color="#ef4444", width=3),
            fill="tozeroy",
            fillcolor="rgba(239,68,68,0.16)",
        )
    )
    dernier = courbe[-1]
    figure.add_annotation(
        x=dernier["date"],
        y=dernier["retard"],
        text=texte.fmt_montant(dernier["retard"], devise, 0),
        showarrow=True,
        arrowhead=2,
        ax=-60,
        ay=-35,
        bgcolor="#ef4444",
        font=dict(color="#ffffff", size=11),
    )
    figure.update_layout(
        height=330,
        margin=dict(t=10, b=10, l=10, r=10),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11, color="#475569")),
        hovermode="x unified",
        xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#64748b")),
        yaxis=dict(
            tickformat=",.0f",
            ticksuffix=f" {devise}",
            tickfont=dict(size=10, color="#64748b"),
            gridcolor="#eef2f7",
        ),
    )
    st.plotly_chart(figure, key="dz_courbe_encours", theme=None, width="stretch")


def _paliers_a_venir(lignes: list[dict], jours: int = 7) -> list[dict]:
    return sorted(
        [
            ligne
            for ligne in lignes
            if ligne.get("en_retard")
            and ligne.get("niveau_suivant")
            and ligne.get("jours_avant_prochain") is not None
            and ligne["jours_avant_prochain"] <= jours
        ],
        key=lambda ligne: ligne["jours_avant_prochain"],
    )


def render() -> None:
    reglages = state.settings()
    lignes = state.portefeuille(reglages)
    aujourdhui = state.aujourdhui()
    state.afficher_flash()
    ui.entete(reglages, lignes, aujourdhui)

    if not lignes:
        ui.etat_vide()
        return

    indicateurs = scoring.kpis(lignes)
    composants.indicateurs_kpi(indicateurs, reglages)
    st.write("")

    gauche, droite = st.columns([1, 1.5], gap="large")
    with gauche:
        ui.titre_section("Répartition des niveaux", "Un clic sur une part filtre la liste ci-dessous.")
        choix_donut = _graphique_repartition(lignes)
    with droite:
        ui.titre_section("Évolution de l'encours impayé", "Reconstitution sur les 90 derniers jours.")
        _graphique_evolution(lignes, reglages, aujourdhui)

    if choix_donut:
        st.session_state["filtre_niveau"] = choix_donut

    st.divider()
    ui.titre_section(
        "File de traitement",
        "Les factures sont classées par score de priorité : commencez par le haut de la liste.",
    )

    commandes = st.columns([3, 1])
    with commandes[0]:
        choix = composants.filtre_niveau("filtre_niveau")
    with commandes[1]:
        seulement_a_faire = st.toggle("Masquer les dossiers relancés", value=False)

    filtrees = composants.appliquer_filtre(lignes, choix)
    if seulement_a_faire:
        filtrees = [f for f in filtrees if f.get("en_retard") and not f.get("action_a_jour")]

    selection = composants.tableau_portefeuille(filtrees, reglages, cle="dz_tableau_dashboard", hauteur=340)
    if selection:
        state.definir_selection(selection)

    facture = state.facture_selectionnee(lignes)
    if facture:
        st.write("")
        with st.container(border=True):
            composants.render_detail(facture, reglages, cle="dz_dashboard_detail", compact=True)
    else:
        st.caption(
            "💡 Cliquez sur une ligne du tableau pour afficher la fiche complète : niveau atteint, "
            "score détaillé, message déjà rédigé et journal des relances."
        )

    paliers = _paliers_a_venir(lignes)
    if paliers:
        with st.expander(f"⏭️ Alertes à venir sous 7 jours ({len(paliers)})", expanded=False):
            st.caption(
                "Ces factures vont changer de niveau de traitement prochainement : elles montent d'un cran "
                "automatiquement quand le seuil suivant est atteint."
            )
            donnees = [
                {
                    "Client": ligne["client"],
                    "N° facture": ligne["numero"],
                    "Niveau actuel": ligne["niveau_court"],
                    "Passe à": config.NIVEAU_COURT.get(ligne["niveau_suivant"], ligne["niveau_suivant"]),
                    "Dans (jours)": ligne["jours_avant_prochain"],
                    "Montant": float(ligne["montant"] or 0),
                }
                for ligne in paliers
            ]
            st.dataframe(donnees, hide_index=True, width="stretch")

    st.divider()
    st.caption(
        f"Encours total suivi : {texte.fmt_montant(scoring.montant_total(lignes), reglages['societe'].get('devise', 'MAD'))} · "
        f"âge moyen pondéré des créances ouvertes : {scoring.dso_estime(lignes)} jours · "
        f"score de priorité moyen : {indicateurs['score_moyen']}/100"
    )
