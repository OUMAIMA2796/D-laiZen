# -*- coding: utf-8 -*-
"""Aide et méthode : les 7 étapes, les deux mécanismes, le cadre juridique."""

from __future__ import annotations

import streamlit as st

from delai_zen import config, scoring, state, ui


def render() -> None:
    reglages = state.settings()
    lignes = state.portefeuille(reglages)
    state.afficher_flash()
    ui.entete(reglages, lignes, state.aujourdhui())

    st.markdown(
        """
**DélaiZen** note chaque facture en retard sur 100 et indique l'action à mener selon le nombre
de jours de retard. Deux mécanismes, deux usages :

| Mécanisme | Ce qu'il fait | À quoi il sert |
|---|---|---|
| **Le scoring** | donne à chaque facture une note de 0 à 100 qui mesure l'urgence de la traiter | à **classer** les factures |
| **L'alerte** | se déclenche quand l'échéance est dépassée : le nombre de jours de retard fixe le niveau de traitement | à **agir** |
"""
    )

    st.divider()
    ui.titre_section("Les sept étapes", "De l'enregistrement de la facture à son paiement.")

    with st.expander("1. Régler l'application", expanded=False):
        st.markdown(
            "Dans **Paramètres**, indiquez le nom de votre société, la devise et, si besoin, modifiez les "
            "seuils ainsi que les poids du score. Vos modèles de messages se règlent au même endroit."
        )
    with st.expander("2. Enregistrer les factures", expanded=False):
        st.markdown(
            "Dans **Factures**, saisissez le client, le numéro de facture, le montant, l'échéance, le téléphone, "
            "l'email et le nombre de retards passés du client. Un import CSV est disponible pour les portefeuilles "
            "existants."
        )
    with st.expander("3. Laisser l'application calculer", expanded=False):
        st.markdown(
            "À chaque affichage, DélaiZen compare les échéances à la date du jour, compte les jours de retard, "
            "attribue le niveau de traitement et calcule le score de 0 à 100. Aucune action de votre part."
        )
    with st.expander("4. Lire la synthèse", expanded=False):
        seuils = scoring.normaliser_seuils(reglages["seuils"])
        st.markdown(
            "Le **Tableau de bord** affiche le montant impayé, le nombre de factures en retard, le retard moyen "
            "et la répartition par niveau. Un clic sur une part du donut filtre la liste."
        )
        st.code(
            "\n".join(
                f"{f'{seuils[cle]} j et plus':>12} → {config.NIVEAU_LABEL[cle]}"
                for cle in config.SEUILS_ORDRE
            ),
            language=None,
        )
    with st.expander("5. Ouvrir la facture à traiter en premier", expanded=False):
        st.markdown(
            "La liste est classée par score. La fiche indique le niveau atteint, le score détaillé critère par "
            "critère, les étapes passées et le temps restant avant le niveau suivant."
        )
    with st.expander("6. Envoyer le message", expanded=False):
        st.markdown(
            "Dans **Relances du jour**, ouvrez la facture : le SMS, le script d'appel, l'email, la mise en demeure "
            "ou la note pour l'avocat est déjà rédigé avec le nom du client, le montant et les dates. Copiez-le, "
            "envoyez-le par vos propres moyens, puis journalisez l'action comme faite."
        )
    with st.expander("7. Clôturer", expanded=False):
        st.markdown(
            "Quand le client règle, marquez la facture **payée** (elle sort de la file). Sinon, l'alerte monte d'un "
            "niveau automatiquement dès que le seuil suivant est atteint."
        )

    st.divider()
    gauche, droite = st.columns(2)
    with gauche:
        ui.titre_section("Comment le score est calculé")
        score = scoring.normaliser_score(reglages["score"])
        devise = reglages["societe"].get("devise", "MAD")
        st.markdown(
            f"""
Chaque facture en retard reçoit 3 notes, plafonnées, puis pondérées :

| Critère | Poids | Référence (plafond) |
|---|---|---|
| Ancienneté du retard | {score['poids_retard'] * 100:.0f} % | {score['ref_retard']:.0f} jours |
| Montant de la créance | {score['poids_montant'] * 100:.0f} % | {score['ref_montant']:.0f} {devise} |
| Historique du client | {score['poids_historique'] * 100:.0f} % | {score['ref_retards']:.0f} retards passés |

`score = 100 × (poids × retard/ref + poids × montant/ref + poids × historique/ref)`

Le score sert uniquement à **classer** : une facture de 3 000 {devise} en retard de 70 jours peut passer
avant une facture de 40 000 {devise} en retard de 2 jours, parce que l'urgence prime.
"""
        )
    with droite:
        ui.titre_section("Niveaux de traitement")
        seuils = scoring.normaliser_seuils(reglages["seuils"])
        for index, cle in enumerate(config.SEUILS_ORDRE):
            debut = seuils[cle]
            suivant = config.SEUILS_ORDRE[index + 1] if index + 1 < len(config.SEUILS_ORDRE) else None
            fin = f"{seuils[suivant] - 1} jours" if suivant else "et plus"
            st.markdown(
                f"{ui.badge_niveau(cle)} <span class='dz-meta'>retard de "
                f"{debut} à {fin} · {ui.esc(config.NIVEAU_LABEL[cle])}</span>",
                unsafe_allow_html=True,
            )
        st.caption(
            "Les niveaux se calculent depuis l'échéance : dès que le seuil est franchi, le traitement change "
            "et le message préparé avec lui."
        )

    st.divider()
    ui.titre_section("Ce que DélaiZen fait — et ne fait pas")
    colonnes = st.columns(2)
    with colonnes[0]:
        st.success(
            "**Il fait** : repérer les retards dès le premier jour, classer les factures par urgence, "
            "préparer le message adapté à chaque niveau, garder l'historique daté des relances, "
            "produire un dossier de recouvrement.",
            icon="✅",
        )
    with colonnes[1]:
        st.warning(
            "**Il ne fait pas** : envoyer les messages à votre place (vous copiez et envoyez), calculer les "
            "intérêts de retard, vérifier la prescription, remplacer un juriste ou un service de recouvrement.",
            icon="⚠️",
        )

    st.divider()
    st.markdown(config.MENTIONS_JURIDIQUES)

    st.divider()
    with st.expander("Questions fréquentes", expanded=False):
        st.markdown(
            f"""
**Où sont stockées mes données ?**
Dans un fichier SQLite local : `{config.DB_PATH}`. Rien n'est envoyé sur Internet. Le dossier `data/` contient
l'intégralité de votre portefeuille : sauvegardez-le.

**Puis-je tester une autre date ?**
Oui : dans **Paramètres → Données**, activez « Simuler une autre date » pour voir ce que deviendront les
relances dans 10 ou 30 jours.

**Que se passe-t-il si je change un seuil ?**
Toutes les factures sont reclassées immédiatement et les messages préparés utilisent le nouveau modèle du niveau.

**Comment savoir si une facture a déjà été relancée ?**
La colonne « Relance » du tableau indique « à jour » dès qu'une action a été enregistrée depuis l'entrée dans le
palier courant. L'onglet **Suivi des actions** conserve le détail, avec le message envoyé.

**Est-ce que le score dépend de mon activité ?**
Oui : les poids et les références sont réglables. Deux références comptent particulièrement, le montant et le
nombre de retards passés, à ajuster selon la taille de votre portefeuille.

**Que faire d'un client qui conteste ?**
Journalisez l'action avec le résultat « Contesté par le client » : la trace est conservée et le dossier pourra
être transmis avec l'historique complet.
"""
        )
