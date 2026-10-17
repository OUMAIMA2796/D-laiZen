# -*- coding: utf-8 -*-
"""Gestion des factures : consultation, saisie, import et export."""

from __future__ import annotations

import json

import streamlit as st

from delai_zen import db, import_export, state, texte, ui
from views import composants


def _onglet_portefeuille(reglages: dict, lignes: list[dict]) -> None:
    devise = reglages["societe"].get("devise", "MAD")
    commandes = st.columns([2.4, 1.6, 1.2])
    with commandes[0]:
        choix = composants.filtre_niveau("filtre_niveau_factures")
    with commandes[1]:
        recherche = st.text_input(
            "Rechercher",
            placeholder="Client, n° de facture, email, téléphone…",
            key="dz_recherche_facture",
        )
    with commandes[2]:
        tri = st.selectbox(
            "Trier par",
            ["Score de priorité", "Montant décroissant", "Retard décroissant", "Échéance", "Client"],
            key="dz_tri_factures",
        )

    filtrees = composants.appliquer_filtre(lignes, choix)
    if recherche.strip():
        terme = recherche.strip().lower()
        filtrees = [
            f
            for f in filtrees
            if terme
            in " ".join(
                str(f.get(champ) or "")
                for champ in ("client", "numero", "email", "telephone", "contact", "notes")
            ).lower()
        ]

    cles_tri = {
        "Score de priorité": lambda f: (-(f.get("score") if f.get("score") is not None else -1), -f["retard"]),
        "Montant décroissant": lambda f: -float(f.get("montant") or 0),
        "Retard décroissant": lambda f: -f["retard"],
        "Échéance": lambda f: (f.get("echeance") or ""),
        "Client": lambda f: (f.get("client") or "").lower(),
    }
    filtrees = sorted(filtrees, key=cles_tri[tri])

    st.caption(
        f"{len(filtrees)} facture(s) affichée(s) sur {len(lignes)} · "
        f"encours filtré : {texte.fmt_montant(sum(float(f.get('montant') or 0) for f in filtrees), devise)}"
    )

    selection = composants.tableau_portefeuille(filtrees, reglages, cle="dz_tableau_factures", hauteur=420)
    if selection:
        state.definir_selection(selection)

    facture = state.facture_selectionnee(lignes)
    if facture:
        st.write("")
        with st.container(border=True):
            composants.render_detail(facture, reglages, cle="dz_factures_detail")
    else:
        st.caption("💡 Cliquez sur une ligne pour ouvrir la fiche de la facture.")


def _onglet_ajouter(reglages: dict) -> None:
    st.caption(
        "Renseignez le client, le numéro de facture, le montant, l'échéance et les coordonnées. "
        "Le score, le niveau de traitement et le message de relance sont calculés automatiquement."
    )
    valeurs = composants.formulaire_facture(None, cle="dz_ajout")
    if not valeurs:
        return

    existants = {(f.get("numero") or "").strip().lower() for f in state.factures()}
    if valeurs["numero"].lower() in existants:
        st.error(f"Le numéro de facture « {valeurs['numero']} » existe déjà.")
        return

    db.create_facture(valeurs)
    state.definir_selection(None)
    state.flash(f"Facture {valeurs['numero']} ajoutée", "✅")
    st.rerun()


def _onglet_importer(reglages: dict) -> None:
    st.caption(
        "Importez un fichier CSV (séparateur « ; » ou « , »). Colonnes reconnues : "
        + ", ".join(import_export.COLONNES_MODELE)
        + "."
    )
    st.download_button(
        "⬇️ Télécharger le modèle CSV",
        data=import_export.modele_csv().encode("utf-8-sig"),
        file_name="modele_factures_delaizen.csv",
        mime="text/csv",
        key="dz_modele_csv",
    )
    fichier = st.file_uploader("Fichier CSV des factures", type=["csv", "txt"], key="dz_upload_factures")
    if fichier is None:
        return
    if st.button("Importer les factures", type="primary", key="dz_lancer_import"):
        crees, erreurs = import_export.importer(fichier.getvalue(), state.aujourdhui())
        if crees:
            state.flash(f"{crees} facture(s) importée(s)", "📥")
        if erreurs:
            st.warning(f"{len(erreurs)} ligne(s) ignorée(s).")
            with st.expander("Voir le détail", expanded=True):
                for erreur in erreurs[:50]:
                    st.write(f"- {erreur}")
        if not crees and not erreurs:
            st.info("Aucune ligne exploitable dans ce fichier.")
        if crees:
            st.rerun()


def _onglet_exporter(reglages: dict, lignes: list[dict]) -> None:
    aujourdhui = state.aujourdhui()
    st.caption("Toutes les données restent sur votre machine : les exports sont de simples fichiers CSV.")
    colonnes = st.columns(3)
    with colonnes[0]:
        st.download_button(
            "⬇️ Factures (CSV)",
            data=import_export.exporter_factures(lignes, reglages),
            file_name=import_export.nom_fichier("delaizen_factures", "csv", aujourdhui),
            mime="text/csv",
            width="stretch",
            key="dz_export_factures",
        )
    with colonnes[1]:
        st.download_button(
            "⬇️ Historique des relances (CSV)",
            data=import_export.exporter_actions(state.actions(), reglages),
            file_name=import_export.nom_fichier("delaizen_relances", "csv", aujourdhui),
            mime="text/csv",
            width="stretch",
            key="dz_export_actions",
        )
    with colonnes[2]:
        st.download_button(
            "⬇️ Paramètres (JSON)",
            data=json.dumps(reglages, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=import_export.nom_fichier("delaizen_parametres", "json", aujourdhui),
            mime="application/json",
            width="stretch",
            key="dz_export_parametres",
        )

    st.divider()
    ui.titre_section(
        "Dossier de recouvrement",
        "Synthèse prête à transmettre à un juriste : créance, relances effectuées et message en cours.",
    )
    if not lignes:
        st.info("Aucune facture disponible.")
        return
    options = [int(f["id"]) for f in lignes]
    libelles = {int(f["id"]): f"{f['client']} — {f['numero']} ({f['niveau_court']})" for f in lignes}
    identifiant = st.selectbox(
        "Facture concernée",
        options,
        format_func=lambda i: libelles.get(i, str(i)),
        key="dz_dossier_facture",
    )
    facture = next(f for f in lignes if int(f["id"]) == int(identifiant))
    dossier = import_export.dossier_recouvrement(facture, reglages, aujourdhui)
    st.code(dossier, language=None, wrap_lines=True, height=320)
    st.download_button(
        "⬇️ Télécharger le dossier (texte)",
        data=dossier.encode("utf-8-sig"),
        file_name=f"dossier_{facture['client'].replace(' ', '_')}_{facture['numero']}.txt",
        mime="text/plain",
        type="primary",
        key="dz_export_dossier",
    )


def render() -> None:
    reglages = state.settings()
    lignes = state.portefeuille(reglages)
    state.afficher_flash()
    ui.entete(reglages, lignes, state.aujourdhui())

    onglets = st.tabs(["📋 Portefeuille", "➕ Ajouter une facture", "⬆️ Importer (CSV)", "⬇️ Exporter"])
    with onglets[0]:
        if not lignes:
            ui.etat_vide()
        else:
            _onglet_portefeuille(reglages, lignes)
    with onglets[1]:
        _onglet_ajouter(reglages)
    with onglets[2]:
        _onglet_importer(reglages)
    with onglets[3]:
        _onglet_exporter(reglages, lignes)
