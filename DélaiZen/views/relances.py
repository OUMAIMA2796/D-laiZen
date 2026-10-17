# -*- coding: utf-8 -*-
"""Relances du jour : la file de travail, message par message."""

from __future__ import annotations

import datetime as dt

import streamlit as st

from delai_zen import config, navigation, scoring, state, texte, ui
from views import composants


def _carte_relance(facture: dict, reglages: dict, cle: str) -> None:
    devise = reglages["societe"].get("devise", "MAD")
    niveau = facture.get("niveau", "")
    etiquette = (
        f"{config.NIVEAU_ICON.get(niveau, '•')} {facture.get('client')} · "
        f"{texte.fmt_montant(facture.get('montant'), devise)} · "
        f"{config.NIVEAU_COURT.get(niveau, niveau)} · retard {facture.get('retard')} j"
        + ("   ✅ relance à jour" if facture.get("action_a_jour") else "")
    )
    with st.expander(etiquette, expanded=False):
        bandeau = st.columns([3, 1])
        with bandeau[0]:
            st.markdown(
                f"{ui.badge_niveau(niveau)} {ui.badge_score(facture.get('score'))} "
                f"<span class='dz-meta'>priorité {facture.get('priorite', '—')} · "
                f"facture {ui.esc(facture.get('numero'))} · échéance {scoring.fmt_date(facture.get('echeance'))}</span>",
                unsafe_allow_html=True,
            )
        with bandeau[1]:
            if facture.get("niveau_suivant"):
                st.caption(
                    f"⏭️ {config.NIVEAU_COURT.get(facture['niveau_suivant'])} "
                    f"dans {facture['jours_avant_prochain']} j"
                )
            elif niveau == "avocat":
                st.caption("⚖️ dernier palier")

        if facture.get("action_a_jour"):
            st.success(
                "Relance déjà enregistrée depuis l'entrée dans ce palier : "
                "inutile de relancer une deuxième fois aujourd'hui.",
                icon="✅",
            )
        else:
            st.warning("Aucune relance enregistrée depuis l'entrée dans ce palier.", icon="⏳")

        composants.bloc_message(facture, reglages, cle)

        boutons = st.columns([1, 1, 1])
        if boutons[0].button(
            "🗂️ Action faite",
            key=f"{cle}_action",
            width="stretch",
            type="primary",
            help="Journalise la relance : type, résultat, date et message envoyé.",
        ):
            composants.dialogue_action(facture, reglages, cle)
        if boutons[1].button("✅ Marquer payée", key=f"{cle}_payer", width="stretch"):
            composants.dialogue_paiement(facture, reglages, cle)
        if boutons[2].button(
            "📄 Ouvrir la fiche", key=f"{cle}_fiche", width="stretch", help="Ouvre la facture dans la page Factures."
        ):
            state.definir_selection(int(facture["id"]))
            navigation.aller("factures")

        if facture.get("actions"):
            st.caption("Dernières relances :")
            st.markdown(ui.chronologie_html(facture["actions"][:4]), unsafe_allow_html=True)


def _relances_faites_aujourdhui(lignes: list[dict], reglages: dict, aujourdhui: dt.date) -> None:
    actions = []
    for facture in lignes:
        for action in facture.get("actions") or []:
            date_action = scoring.parse_date(action.get("date_action"))
            if date_action == aujourdhui:
                actions.append((facture, action))
    if not actions:
        return
    with st.expander(f"✅ Relances enregistrées aujourd'hui ({len(actions)})", expanded=False):
        st.dataframe(
            [
                {
                    "Client": facture["client"],
                    "N° facture": facture["numero"],
                    "Action": config.TYPES_ACTION.get(action.get("type_action"), action.get("type_action")),
                    "Résultat": config.RESULTATS_ACTION.get(action.get("resultat"), action.get("resultat")),
                    "Heure": texte.fmt_datetime(action.get("date_action"), "%H:%M"),
                    "Commentaire": action.get("commentaire"),
                }
                for facture, action in actions
            ],
            hide_index=True,
            width="stretch",
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

    en_retard = [f for f in lignes if f.get("en_retard")]
    devise = reglages["societe"].get("devise", "MAD")
    a_faire = [f for f in en_retard if not f.get("action_a_jour")]

    if not en_retard:
        st.success(
            "Aucune facture en retard aujourd'hui. DélaiZen surveille les échéances : "
            "les factures apparaîtront ici dès le premier jour de retard.",
            icon="🎉",
        )
        _relances_faites_aujourdhui(lignes, reglages, aujourdhui)
        return

    urgentes = [f for f in en_retard if f.get("niveau") in ("mise_en_demeure", "avocat")]
    ui.kpi_grille(
        [
            (
                "À relancer",
                str(len(a_faire)),
                f"sur {len(en_retard)} facture(s) en retard",
                "#ef4444",
                "🔔",
            ),
            (
                "Montant concerné",
                texte.fmt_montant_court(sum(float(f["montant"] or 0) for f in a_faire), devise),
                "créances sans relance à ce palier",
                "#0f172a",
                "💰",
            ),
            (
                "Score moyen",
                f"{scoring.kpis(lignes)['score_moyen']}/100",
                "priorité moyenne du portefeuille en retard",
                "#f59e0b",
                "📊",
            ),
            (
                "Dossiers sensibles",
                str(len(urgentes)),
                "mise en demeure ou avocat",
                "#dc2626",
                "⚖️",
            ),
        ]
    )

    st.divider()
    ui.titre_section(
        "File de relance du jour",
        "Du score le plus élevé au plus faible. Ouvrez une ligne, copiez le message préparé, envoyez-le, puis journalisez l'action.",
    )

    commandes = st.columns([2.2, 1.4, 1.2])
    with commandes[0]:
        choix_niveau = composants.filtre_niveau("filtre_niveau_relances")
    with commandes[1]:
        vue = st.segmented_control(
            "Présentation",
            ["Par priorité", "Par niveau"],
            default="Par priorité",
            key="dz_vue_relances",
        )
    with commandes[2]:
        limite = st.selectbox("Afficher", [10, 25, 50, 100, "Tout"], index=1, key="dz_limite_relances")

    filtrees = [f for f in composants.appliquer_filtre(en_retard, choix_niveau)]
    if vue == "Par priorité":
        filtrees = filtrees  # déjà trié par score
    else:
        ordre = {cle: index for index, cle in enumerate(config.SEUILS_ORDRE)}
        filtrees = sorted(filtrees, key=lambda f: (ordre.get(f["niveau"], 99), -(f["score"] or 0)))

    if not filtrees:
        st.info("Aucune facture à relancer dans ce filtre.")
    else:
        montant = sum(float(f["montant"] or 0) for f in filtrees)
        st.caption(
            f"{len(filtrees)} facture(s) à traiter · {texte.fmt_montant(montant, devise)} · "
            f"{len([f for f in filtrees if not f.get('action_a_jour')])} sans relance à ce palier"
        )

    visibles = filtrees if limite == "Tout" else filtrees[: int(limite)]
    if len(filtrees) > len(visibles):
        st.caption(f"Les {len(visibles)} premières factures sont affichées (changez « Afficher » pour en voir plus).")

    for index, facture in enumerate(visibles):
        _carte_relance(facture, reglages, cle=f"dz_rel_{facture['id']}_{index}")

    st.divider()
    _relances_faites_aujourdhui(lignes, reglages, aujourdhui)

    st.caption(
        "Rappel : le niveau change automatiquement quand le seuil suivant est atteint "
        f"({', '.join(f'{config.NIVEAU_COURT[cle]} ≥ {valeur} j' for cle, valeur in scoring.normaliser_seuils(reglages['seuils']).items())})."
    )
