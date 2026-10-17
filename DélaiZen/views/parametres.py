# -*- coding: utf-8 -*-
"""Paramètres : société, seuils, scoring, modèles de messages, données, juridique."""

from __future__ import annotations

import datetime as dt
import json

import streamlit as st

from delai_zen import config, db, messages, scoring, state, ui


def _sauvegarder(reglages: dict, cle: str, valeurs: dict, message: str) -> None:
    nouveau = dict(reglages)
    nouveau[cle] = valeurs
    db.save_settings(nouveau)
    state.flash(message, "💾")
    st.rerun()


# --------------------------------------------------------------------------
# Société
# --------------------------------------------------------------------------
def _onglet_societe(reglages: dict) -> None:
    societe = reglages["societe"]
    st.caption("Ces informations apparaissent dans l'en-tête et dans les messages générés.")
    with st.form("dz_form_societe"):
        ligne1 = st.columns([2, 1, 1])
        nom = ligne1[0].text_input("Nom de la société", value=societe.get("nom", ""))
        devise = ligne1[1].selectbox(
            "Devise",
            config.DEVISES,
            index=config.DEVISES.index(societe.get("devise", "MAD")) if societe.get("devise") in config.DEVISES else 0,
        )
        ville = ligne1[2].text_input("Ville", value=societe.get("ville", ""))

        ligne2 = st.columns([1.4, 1.4, 1])
        utilisateur = ligne2[0].text_input("Utilisateur (signataire)", value=societe.get("utilisateur", ""))
        telephone = ligne2[1].text_input("Téléphone de la société", value=societe.get("telephone", ""))
        email = ligne2[2].text_input("Email de la société", value=societe.get("email", ""))

        ligne3 = st.columns(2)
        delai_email = ligne3[0].number_input(
            "Délai demandé par email (jours)",
            min_value=1,
            max_value=60,
            value=int(societe.get("delai_email_jours", 2)),
            help="Nombre de jours accordés au client dans les messages de type email ou appel.",
        )
        delai_med = ligne3[1].number_input(
            "Délai accordé en mise en demeure (jours)",
            min_value=1,
            max_value=90,
            value=int(societe.get("delai_mise_en_demeure_jours", 8)),
        )

        if st.form_submit_button("Enregistrer", type="primary", width="stretch"):
            if not nom.strip():
                st.error("Le nom de la société est obligatoire.")
            else:
                _sauvegarder(
                    reglages,
                    "societe",
                    {
                        "nom": nom.strip(),
                        "devise": devise,
                        "utilisateur": utilisateur.strip() or "Responsable financier",
                        "telephone": telephone.strip(),
                        "email": email.strip(),
                        "ville": ville.strip(),
                        "delai_email_jours": int(delai_email),
                        "delai_mise_en_demeure_jours": int(delai_med),
                    },
                    "Paramètres de la société enregistrés",
                )


# --------------------------------------------------------------------------
# Seuils
# --------------------------------------------------------------------------
def _onglet_seuils(reglages: dict) -> None:
    st.caption(
        "Le nombre de jours de retard détermine le niveau de traitement : c'est l'alerte. "
        "Modifiez les seuils si votre activité fonctionne autrement."
    )
    actuels = scoring.normaliser_seuils(reglages["seuils"])
    colonnes = st.columns(5)
    nouveaux = {}
    for index, cle in enumerate(config.SEUILS_ORDRE):
        with colonnes[index]:
            nouveaux[cle] = st.number_input(
                config.NIVEAU_COURT[cle],
                min_value=1,
                max_value=365,
                value=int(actuels[cle]),
                step=1,
                key=f"dz_seuil_{cle}",
                help=f"{config.NIVEAU_LABEL[cle]}",
            )

    propre = scoring.normaliser_seuils(nouveaux)
    modifie = propre != actuels
    if propre != {cle: int(valeur) for cle, valeur in nouveaux.items()}:
        st.warning(
            "Les seuils doivent être strictement croissants. DélaiZen a corrigé les valeurs "
            "incohérentes pour l'aperçu ci-dessous.",
            icon="⚠️",
        )

    st.markdown("**Grille appliquée**")
    grille = []
    for index, cle in enumerate(config.SEUILS_ORDRE):
        debut = propre[cle]
        suivant = config.SEUILS_ORDRE[index + 1] if index + 1 < len(config.SEUILS_ORDRE) else None
        fin = f"{propre[suivant] - 1}" if suivant else None
        grille.append(
            {
                "Retard (jours)": f"{debut} à {fin}" if fin else f"{debut} et plus",
                "Traitement": config.NIVEAU_LABEL[cle],
            }
        )

    st.dataframe(grille, hide_index=True, width="stretch")
    st.caption(
        f"Actuellement : {', '.join(f'{config.NIVEAU_COURT[cle]} dès {valeur} j' for cle, valeur in actuels.items())}"
    )

    if st.button("Enregistrer les seuils", type="primary", key="dz_save_seuils", disabled=not modifie):
        _sauvegarder(reglages, "seuils", propre, "Seuils de traitement enregistrés")
    if not modifie:
        st.caption("Modifiez une valeur pour activer l'enregistrement.")


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def _onglet_scoring(reglages: dict) -> None:
    st.caption(
        "Le score de 0 à 100 sert à classer les factures entre elles. Chaque critère est plafonné : "
        "un très gros montant ou un très long retard n'écrase pas le reste."
    )
    actuel = scoring.normaliser_score(reglages["score"])
    colonnes = st.columns(3)
    poids_retard = colonnes[0].slider(
        "Poids du retard (%)", 0, 100, int(round(actuel["poids_retard"] * 100)), 5, key="dz_poids_retard"
    )
    poids_montant = colonnes[1].slider(
        "Poids du montant (%)", 0, 100, int(round(actuel["poids_montant"] * 100)), 5, key="dz_poids_montant"
    )
    poids_histo = colonnes[2].slider(
        "Poids de l'historique (%)", 0, 100, int(round(actuel["poids_historique"] * 100)), 5, key="dz_poids_histo"
    )

    refs = st.columns(3)
    devise = reglages["societe"].get("devise", "MAD")
    ref_retard = refs[0].number_input(
        "Retard de référence (jours)", min_value=1, max_value=365, value=int(actuel["ref_retard"]), key="dz_ref_retard"
    )
    ref_montant = refs[1].number_input(
        f"Montant de référence ({devise})", min_value=1.0, value=float(actuel["ref_montant"]), step=1000.0, key="dz_ref_montant"
    )
    ref_retards = refs[2].number_input(
        "Retards passés de référence", min_value=1, max_value=50, value=int(actuel["ref_retards"]), key="dz_ref_retards"
    )

    essai_score = {
        "poids_retard": poids_retard,
        "poids_montant": poids_montant,
        "poids_historique": poids_histo,
        "ref_retard": ref_retard,
        "ref_montant": ref_montant,
        "ref_retards": ref_retards,
    }
    normalise = scoring.normaliser_score(essai_score)
    if abs(sum([poids_retard, poids_montant, poids_histo]) - 100) > 0:
        st.caption(
            f"Les poids sont ramenés à 100 % : retard {normalise['poids_retard'] * 100:.0f} % · "
            f"montant {normalise['poids_montant'] * 100:.0f} % · historique {normalise['poids_historique'] * 100:.0f} %."
        )

    factures = state.factures()
    if factures:
        essai_reglages = dict(reglages)
        essai_reglages["score"] = normalise
        avant = {int(f["id"]): f.get("score") for f in state.portefeuille(reglages)}
        apres = scoring.enrichir(factures, state.actions(), essai_reglages, state.aujourdhui())
        apercu = [
            {
                "Client": f["client"],
                "Montant": float(f["montant"] or 0),
                "Retard (j)": f["retard"],
                "Score actuel": avant.get(int(f["id"])) if avant.get(int(f["id"])) is not None else 0,
                "Score avec ces poids": f["score"] if f["score"] is not None else 0,
            }
            for f in apres[:8]
            if f.get("en_retard")
        ]
        st.markdown("**Effet sur les 8 factures les plus prioritaires**")
        st.dataframe(apercu, hide_index=True, width="stretch")

    modifie = normalise != actuel
    if st.button("Enregistrer le scoring", type="primary", key="dz_save_scoring", disabled=not modifie):
        _sauvegarder(reglages, "score", normalise, "Paramètres de scoring enregistrés")


# --------------------------------------------------------------------------
# Modèles de messages
# --------------------------------------------------------------------------
def _onglet_modeles(reglages: dict) -> None:
    st.caption(
        "Chaque niveau a son modèle. Les accolades sont remplacées automatiquement par les données du client "
        "au moment de l'envoi."
    )
    with st.expander("Placeholders disponibles", expanded=False):
        st.dataframe(
            [{"Code": code, "Contenu": libelle} for code, libelle in messages.PLACEHOLDERS.items()],
            hide_index=True,
            width="stretch",
        )

    modeles = dict(reglages.get("modeles", config.DEFAULT_MODELES))
    onglets = st.tabs([config.NIVEAU_COURT[cle] for cle in config.SEUILS_ORDRE])
    for onglet, cle in zip(onglets, config.SEUILS_ORDRE):
        with onglet:
            modeles[cle] = st.text_area(
                config.NIVEAU_LABEL[cle],
                value=modeles.get(cle, ""),
                height=260,
                key=f"dz_modele_{cle}",
            )
            if st.button(
                "↩️ Rétablir le modèle d'origine",
                key=f"dz_reset_modele_{cle}",
            ):
                modeles[cle] = config.DEFAULT_MODELES[cle]
                db.save_settings({**reglages, "modeles": modeles})
                state.flash("Modèle rétabli", "↩️")
                st.rerun()

    with st.expander("Aperçu sur une facture réelle", expanded=False):
        lignes = state.portefeuille(reglages)
        retard = [f for f in lignes if f.get("en_retard")]
        if not retard:
            st.info("Ajoutez une facture en retard pour voir un aperçu.")
        else:
            libelles = {int(f["id"]): f"{f['client']} — {f['numero']}" for f in retard}
            identifiant = st.selectbox(
                "Facture de test",
                list(libelles),
                format_func=lambda i: libelles[i],
                key="dz_apercu_modele",
            )
            exemple = next(f for f in retard if int(f["id"]) == int(identifiant))
            essai = {**reglages, "modeles": modeles}
            st.code(
                messages.rendre(messages.modele_pour(exemple["niveau"], essai), exemple, essai, state.aujourdhui()),
                language=None,
                wrap_lines=True,
            )

    if st.button("Enregistrer les modèles", type="primary", key="dz_save_modeles"):
        _sauvegarder(reglages, "modeles", modeles, "Modèles de messages enregistrés")


# --------------------------------------------------------------------------
# Données
# --------------------------------------------------------------------------
def _onglet_donnees(reglages: dict) -> None:
    ui.titre_section("Date de travail", "Testez l'effet du temps : ce que vous verrez dans 10 jours.")
    aujourdhui = dt.date.today()
    actif = bool(st.session_state.get(state.CLE_DATE))
    colonnes = st.columns([1, 1, 2])
    with colonnes[0]:
        simuler = st.toggle("Simuler une autre date", value=actif, key="dz_toggle_simulation")
    with colonnes[1]:
        date_choisie = st.date_input(
            "Date de simulation",
            value=st.session_state.get(state.CLE_DATE) or aujourdhui,
            key="dz_date_simulation_input",
            disabled=not simuler,
        )
    with colonnes[2]:
        if simuler and date_choisie != aujourdhui:
            st.info(f"Les calculs utilisent la date du {date_choisie.strftime('%d/%m/%Y')}.", icon="🧪")
        else:
            st.caption("Les calculs utilisent la date du jour.")

    nouvelle_date = date_choisie if simuler else None
    if nouvelle_date != st.session_state.get(state.CLE_DATE):
        st.session_state[state.CLE_DATE] = nouvelle_date
        st.rerun()

    st.divider()
    ui.titre_section("Données", f"Base de données locale : {config.DB_PATH}")
    factures = state.factures()
    actions = state.actions()
    st.caption(f"{len(factures)} facture(s) · {len(actions)} relance(s) enregistrée(s)")

    sauvegarde = json.dumps(
        {"factures": factures, "actions": actions, "parametres": reglages},
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    colonnes = st.columns(3)
    with colonnes[0]:
        st.download_button(
            "⬇️ Sauvegarde complète (JSON)",
            data=sauvegarde.encode("utf-8"),
            file_name=f"delaizen_sauvegarde_{aujourdhui.strftime('%Y%m%d')}.json",
            mime="application/json",
            width="stretch",
            key="dz_sauvegarde_json",
        )
    with colonnes[1]:
        if st.button("📥 Charger la démonstration", width="stretch", key="dz_charger_demo"):
            db.charger_demo()
            state.flash("Portefeuille de démonstration chargé", "📥")
            st.rerun()
    with colonnes[2]:
        if st.button("↩️ Rétablir les paramètres", width="stretch", key="dz_reset_parametres"):
            db.reset_settings()
            state.flash("Paramètres rétablis par défaut", "↩️")
            st.rerun()

    st.divider()
    st.error(
        "Zone sensible : la suppression efface toutes les factures et tout l'historique de relances. "
        "Exportez d'abord une sauvegarde si nécessaire.",
        icon="⚠️",
    )
    confirmation = st.text_input(
        "Tapez SUPPRIMER pour confirmer",
        key="dz_confirmation_suppression",
        placeholder="SUPPRIMER",
    )
    if st.button("🗑️ Effacer toutes les données", disabled=confirmation.strip().upper() != "SUPPRIMER", key="dz_purge"):
        db.supprimer_tout()
        state.definir_selection(None)
        state.flash("Toutes les données ont été effacées", "🗑️")
        st.rerun()


# --------------------------------------------------------------------------
# Juridique
# --------------------------------------------------------------------------
def _onglet_juridique(reglages: dict) -> None:
    st.markdown(config.MENTIONS_JURIDIQUES)
    st.divider()
    seuils = scoring.normaliser_seuils(reglages["seuils"])
    st.markdown(
        f"**Seuils actuellement en vigueur** : "
        f"{config.NIVEAU_COURT['mise_en_demeure']} à {seuils['mise_en_demeure']} jours, "
        f"{config.NIVEAU_COURT['avocat']} à {seuils['avocat']} jours. "
        "Ces deux paliers doivent être validés par un juriste avant utilisation réelle."
    )
    st.info(
        "**Ce que DélaiZen ne fait pas** : il ne calcule pas les intérêts de retard, ne vérifie pas la "
        "prescription et n'envoie rien à votre place. Il prépare, classe et garde trace.",
        icon="ℹ️",
    )


def render() -> None:
    reglages = state.settings()
    lignes = state.portefeuille(reglages)
    state.afficher_flash()
    ui.entete(reglages, lignes, state.aujourdhui())

    onglets = st.tabs(
        [
            "🏢 Société",
            "🎚️ Seuils des niveaux",
            "🧮 Scoring",
            "✉️ Modèles de messages",
            "💾 Données",
            "⚖️ Juridique & données personnelles",
        ]
    )
    with onglets[0]:
        _onglet_societe(reglages)
    with onglets[1]:
        _onglet_seuils(reglages)
    with onglets[2]:
        _onglet_scoring(reglages)
    with onglets[3]:
        _onglet_modeles(reglages)
    with onglets[4]:
        _onglet_donnees(reglages)
    with onglets[5]:
        _onglet_juridique(reglages)
