# -*- coding: utf-8 -*-
"""Composants réutilisables : tableaux, fiche facture, formulaires, dialogues."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from delai_zen import config, db, messages, scoring, state, texte, ui


# --------------------------------------------------------------------------
# Tableaux
# --------------------------------------------------------------------------
def _lignes_selectionnees(evenement) -> list[int]:
    try:
        return list(evenement.selection.rows)
    except AttributeError:
        return list((evenement or {}).get("selection", {}).get("rows", []))


def tableau_portefeuille(
    lignes: list[dict],
    reglages: dict,
    cle: str,
    hauteur: int | None = None,
    message_vide: str = "Aucune facture ne correspond à ce filtre.",
) -> int | None:
    """Tableau cliquable : renvoie l'identifiant de la facture sélectionnée."""
    if not lignes:
        st.info(message_vide)
        return None

    devise = reglages["societe"].get("devise", "MAD")
    donnees = []
    for ligne in lignes:
        derniere = ligne.get("derniere_action")
        donnees.append(
            {
                "id": int(ligne["id"]),
                "Client": ligne.get("client") or "—",
                "N° facture": ligne.get("numero") or "—",
                f"Montant ({devise})": float(ligne.get("montant") or 0),
                "Échéance": scoring.fmt_date(ligne.get("echeance")),
                "Retard (j)": int(ligne.get("retard") or 0),
                "Niveau": config.NIVEAU_COURT.get(ligne["niveau"], ligne["niveau"]),
                "Score": ligne.get("score") if ligne.get("score") is not None else 0,
                "Priorité": ligne.get("priorite", "—"),
                "Relance": (
                    "✅ à jour"
                    if ligne.get("action_a_jour")
                    else ("⏳ à faire" if ligne.get("en_retard") else "—")
                ),
                "Dernière action": texte.fmt_datetime(derniere.get("date_action")) if derniere else "—",
            }
        )

    cadre = pd.DataFrame(donnees)
    evenement = st.dataframe(
        cadre,
        hide_index=True,
        width="stretch",
        height=hauteur,
        on_select="rerun",
        selection_mode="single-row",
        key=cle,
        column_config={
            "id": None,
            f"Montant ({devise})": st.column_config.NumberColumn(format="%.2f"),
            "Retard (j)": st.column_config.NumberColumn(format="%.0f j"),
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f/100"),
        },
    )

    indices = _lignes_selectionnees(evenement)
    if indices:
        return int(cadre.iloc[indices[0]]["id"])
    return None


FILTRE_TOUTES = "Toutes"
FILTRE_PAYEES = "Payée"
FILTRE_SANS_RETARD = "À venir"


def options_filtre_niveau() -> list[str]:
    return (
        [FILTRE_TOUTES]
        + [config.NIVEAU_COURT[cle] for cle in config.SEUILS_ORDRE]
        + [FILTRE_PAYEES, FILTRE_SANS_RETARD]
    )


def filtre_niveau(cle: str = "filtre_niveau", label: str = "Filtrer par niveau de traitement") -> str:
    """Sélecteur de niveau, utilisé aussi bien par les pastilles que par le donut."""
    options = options_filtre_niveau()
    arguments = {} if cle in st.session_state else {"default": FILTRE_TOUTES}
    choix = st.pills(label, options, selection_mode="single", key=cle, **arguments)
    return choix or FILTRE_TOUTES


def appliquer_filtre(lignes: list[dict], choix: str) -> list[dict]:
    if choix == FILTRE_TOUTES:
        return lignes
    if choix == FILTRE_PAYEES:
        return [f for f in lignes if f.get("niveau") == "payee"]
    if choix == FILTRE_SANS_RETARD:
        return [f for f in lignes if f.get("niveau") in ("a_venir", "a_echeance")]
    return [f for f in lignes if f.get("niveau_court") == choix]


def niveau_clique(evenement) -> str | None:
    """Libellé du segment cliqué sur un graphique (donut)."""
    try:
        points = evenement.selection.points
    except AttributeError:
        points = (evenement or {}).get("selection", {}).get("points", [])
    if points:
        return points[0].get("label")
    return None


def indicateurs_kpi(indicateurs: dict, reglages: dict) -> None:
    devise = reglages["societe"].get("devise", "MAD")
    ui.kpi_grille(
        [
            (
                "Encours impayé",
                texte.fmt_montant_court(indicateurs["montant_ouvert"], devise),
                f"{indicateurs['nb_ouvertes']} facture(s) non réglée(s)",
                "#0f172a",
                "💰",
            ),
            (
                "Dont en retard",
                texte.fmt_montant_court(indicateurs["montant_retard"], devise),
                f"{indicateurs['part_retard'] * 100:.0f} % de l'encours",
                "#ef4444",
                "⏰",
            ),
            (
                "Factures en retard",
                f"{indicateurs['nb_retard']} / {indicateurs['nb_factures']}",
                f"{indicateurs['nb_a_traiter']} action(s) à mener",
                "#f59e0b",
                "📄",
            ),
            (
                "Retard moyen",
                f"{indicateurs['retard_moyen']} jours",
                f"le plus ancien : {indicateurs['retard_max']} jours",
                "#3b82f6",
                "📈",
            ),
            (
                "Dossiers juridiques",
                str(indicateurs["nb_juridique"]),
                f"dont {indicateurs['nb_avocat']} à transmettre à l'avocat",
                "#dc2626",
                "⚖️",
            ),
        ]
    )


# --------------------------------------------------------------------------
# Messages et preuves
# --------------------------------------------------------------------------
def bloc_message(facture: dict, reglages: dict, cle: str, avec_liens: bool = True) -> None:
    niveau = facture.get("niveau", "")
    if niveau not in config.SEUILS_ORDRE:
        st.info(
            f"Cette facture est au niveau **{config.NIVEAU_LABEL.get(niveau, niveau)}** : "
            "aucune relance n'est due pour l'instant. Elle basculera automatiquement dans la file "
            "le jour suivant son échéance."
        )
        return

    contenu = messages.message_pour(facture, reglages, state.aujourdhui())
    st.caption(
        "Message déjà rédigé avec le nom du client, le montant et les dates. "
        "Utilisez l'icône de copie en haut à droite du bloc, puis envoyez-le par vos propres moyens."
    )
    st.code(contenu, language=None, wrap_lines=True)

    if niveau in ("mise_en_demeure", "avocat"):
        st.warning(
            "Brouillon juridique : à faire valider par un juriste avant envoi "
            "(mentions légales à compléter et seuil à confirmer).",
            icon="⚠️",
        )

    if not avec_liens:
        return

    liens = st.columns(3)
    lien_mail = messages.lien_email(facture, reglages, state.aujourdhui())
    lien_tel = messages.lien_telephone(facture)
    lien_sms = messages.lien_sms(facture, reglages, state.aujourdhui())

    with liens[0]:
        if lien_mail:
            st.link_button("✉️ Email", lien_mail, width="stretch", help="Ouvre la messagerie avec l'objet et le message déjà remplis.")
        else:
            st.button("✉️ Email manquant", disabled=True, width="stretch", key=f"{cle}_mail_vide")
    with liens[1]:
        if lien_tel:
            st.link_button("📞 Appeler", lien_tel, width="stretch", help="Compose le numéro du client.")
        else:
            st.button("📞 Tél. manquant", disabled=True, width="stretch", key=f"{cle}_tel_vide")
    with liens[2]:
        if lien_sms:
            st.link_button("💬 SMS", lien_sms, width="stretch", help="Ouvre l'application SMS avec le message déjà rempli.")
        else:
            st.button("💬 SMS indisponible", disabled=True, width="stretch", key=f"{cle}_sms_vide")


# --------------------------------------------------------------------------
# Dialogues
# --------------------------------------------------------------------------
@st.dialog("Enregistrer une action de relance")
def dialogue_action(facture: dict, reglages: dict, cle: str) -> None:
    niveau = facture.get("niveau", "")
    types = [type_action for type_action in config.TYPES_ACTION if type_action != "paiement"]
    defaut = config.ACTION_DU_NIVEAU.get(niveau, "note_interne")
    contenu = messages.message_pour(facture, reglages, state.aujourdhui())

    st.markdown(
        f"**{facture.get('client')}** — facture {facture.get('numero')} · "
        f"{config.NIVEAU_LABEL.get(niveau, niveau)} · retard {facture.get('retard')} j"
    )
    with st.form(key=f"{cle}_form_action"):
        type_action = st.selectbox(
            "Action réalisée",
            types,
            index=types.index(defaut) if defaut in types else len(types) - 1,
            format_func=lambda v: config.TYPES_ACTION[v],
        )
        colonnes = st.columns(2)
        with colonnes[0]:
            resultat = st.selectbox(
                "Résultat",
                list(config.RESULTATS_ACTION),
                index=0,
                format_func=lambda v: config.RESULTATS_ACTION[v],
            )
        with colonnes[1]:
            quand = st.date_input("Date de l'action", value=state.aujourdhui())
        commentaire = st.text_input(
            "Commentaire (facultatif)",
            placeholder="Ex. promesse de règlement au 30/10, contestation d'une ligne…",
        )
        joindre = st.checkbox("Joindre le message envoyé à l'historique (preuve)", value=True)
        valider = st.form_submit_button("Enregistrer l'action", type="primary", width="stretch")

    if valider:
        db.create_action(
            {
                "facture_id": int(facture["id"]),
                "date_action": dt.datetime.combine(quand, dt.datetime.now().time()).isoformat(timespec="seconds"),
                "niveau": niveau,
                "type_action": type_action,
                "canal": config.CANAL_ACTION.get(type_action, ""),
                "resultat": resultat,
                "contenu": contenu if joindre else "",
                "commentaire": commentaire,
                "utilisateur": reglages["societe"].get("utilisateur", ""),
                "jours_retard": int(facture.get("retard") or 0),
                "montant": float(facture.get("montant") or 0),
            }
        )
        state.flash(f"Action enregistrée pour {facture.get('client')}", "🗂️")
        st.rerun()


@st.dialog("Marquer la facture comme payée")
def dialogue_paiement(facture: dict, reglages: dict, cle: str) -> None:
    st.markdown(
        f"Facture **{facture.get('numero')}** — {facture.get('client')} · "
        f"{texte.fmt_montant(facture.get('montant'), reglages['societe'].get('devise', 'MAD'))}"
    )
    with st.form(key=f"{cle}_form_paiement"):
        quand = st.date_input("Date du paiement", value=state.aujourdhui())
        commentaire = st.text_input("Commentaire (facultatif)", placeholder="Virement, chèque n°…")
        valider = st.form_submit_button("Confirmer l'encaissement", type="primary", width="stretch")
    if valider:
        db.marquer_payee(
            int(facture["id"]),
            quand.isoformat(),
            reglages["societe"].get("utilisateur", ""),
            commentaire,
        )
        state.flash(f"Facture {facture.get('numero')} marquée payée", "✅")
        st.rerun()


@st.dialog("Modifier la facture")
def dialogue_modifier(facture: dict, reglages: dict, cle: str) -> None:
    valeurs = formulaire_facture(facture, cle=f"{cle}_edit")
    if valeurs is not None:
        db.update_facture(int(facture["id"]), valeurs)
        state.flash("Facture mise à jour", "✏️")
        st.rerun()


@st.dialog("Supprimer la facture")
def dialogue_supprimer(facture: dict, cle: str) -> None:
    st.warning(
        f"La facture **{facture.get('numero')}** de {facture.get('client')} et tout son historique "
        "de relances seront définitivement supprimés.",
        icon="🗑️",
    )
    colonnes = st.columns(2)
    if colonnes[0].button("Supprimer définitivement", type="primary", width="stretch", key=f"{cle}_confirme"):
        db.delete_facture(int(facture["id"]))
        state.definir_selection(None)
        state.flash("Facture supprimée", "🗑️")
        st.rerun()
    if colonnes[1].button("Annuler", width="stretch", key=f"{cle}_annule"):
        st.rerun()


# --------------------------------------------------------------------------
# Formulaire facture (ajout et modification)
# --------------------------------------------------------------------------
def formulaire_facture(facture: dict | None = None, cle: str = "form") -> dict | None:
    """Renvoie les valeurs saisies si le formulaire est validé, sinon ``None``."""
    facture = facture or {}
    aujourdhui = state.aujourdhui()
    echeance = scoring.parse_date(facture.get("echeance")) or (aujourdhui + dt.timedelta(days=30))
    date_facture = scoring.parse_date(facture.get("date_facture")) or (echeance - dt.timedelta(days=30))

    with st.form(key=f"{cle}_facture", clear_on_submit=facture.get("id") is None):
        ligne1 = st.columns([2, 1, 1])
        client = ligne1[0].text_input("Client *", value=facture.get("client", ""), placeholder="Nom du client")
        numero = ligne1[1].text_input("N° de facture *", value=facture.get("numero", ""), placeholder="FAC-2026-001")
        montant = ligne1[2].number_input(
            "Montant *", min_value=0.0, value=float(facture.get("montant") or 0.0), step=100.0, format="%.2f"
        )

        ligne2 = st.columns(3)
        date_emission = ligne2[0].date_input("Date d'émission", value=date_facture)
        date_echeance = ligne2[1].date_input("Échéance *", value=echeance)
        retards_anterieurs = ligne2[2].number_input(
            "Retards passés du client",
            min_value=0,
            max_value=99,
            value=int(facture.get("retards_anterieurs") or 0),
            help="Nombre de fois où ce client a déjà payé en retard. Ce critère entre dans le score.",
        )

        ligne3 = st.columns(3)
        contact = ligne3[0].text_input("Contact", value=facture.get("contact", ""), placeholder="Mme Alaoui")
        telephone = ligne3[1].text_input("Téléphone", value=facture.get("telephone", ""), placeholder="0661 00 00 00")
        email = ligne3[2].text_input("Email", value=facture.get("email", ""), placeholder="compta@client.ma")

        notes = st.text_area("Notes internes", value=facture.get("notes", ""), height=70)

        statut = facture.get("statut", "ouverte")
        if facture.get("id"):
            statut = st.radio(
                "Statut",
                ["ouverte", "payee"],
                index=0 if statut != "payee" else 1,
                horizontal=True,
                format_func=lambda v: "Ouverte" if v == "ouverte" else "Payée",
            )

        valider = st.form_submit_button(
            "Enregistrer la facture" if not facture.get("id") else "Mettre à jour",
            type="primary",
            width="stretch",
        )

    if not valider:
        return None

    erreurs = []
    if not client.strip():
        erreurs.append("Le nom du client est obligatoire.")
    if not numero.strip():
        erreurs.append("Le numéro de facture est obligatoire.")
    if montant <= 0:
        erreurs.append("Le montant doit être supérieur à zéro.")
    if date_echeance < date_emission:
        erreurs.append("L'échéance ne peut pas précéder la date d'émission.")
    if email and "@" not in email:
        erreurs.append("L'adresse email semble invalide.")

    if erreurs:
        for erreur in erreurs:
            st.error(erreur)
        return None

    return {
        "client": client.strip(),
        "numero": numero.strip(),
        "montant": float(montant),
        "date_facture": date_emission.isoformat(),
        "echeance": date_echeance.isoformat(),
        "contact": contact.strip(),
        "telephone": telephone.strip(),
        "email": email.strip(),
        "retards_anterieurs": int(retards_anterieurs),
        "statut": statut,
        "date_paiement": facture.get("date_paiement"),
        "notes": notes.strip(),
    }


# --------------------------------------------------------------------------
# Fiche détaillée
# --------------------------------------------------------------------------
def render_detail(facture: dict, reglages: dict, cle: str, compact: bool = False) -> None:
    """Fiche complète : score détaillé, paliers, historique, message et actions."""
    devise = reglages["societe"].get("devise", "MAD")
    niveau = facture.get("niveau", "")

    gauche, droite = st.columns([1, 1.05], gap="large")

    with gauche:
        st.markdown(
            f"### {ui.esc(facture.get('client'))} "
            f"<span class='dz-meta'>· facture {ui.esc(facture.get('numero'))}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"{ui.badge_niveau(niveau)} {ui.badge_score(facture.get('score'))}",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:1.35rem;font-weight:800;margin-top:6px'>"
            f"{texte.fmt_montant(facture.get('montant'), devise)}</div>"
            f"<div class='dz-meta'>Échéance {scoring.fmt_date(facture.get('echeance'))} · "
            f"retard <b>{facture.get('retard', 0)} jour(s)</b> · "
            f"score de priorité <b>{facture.get('score') if facture.get('score') is not None else '—'}/100</b></div>",
            unsafe_allow_html=True,
        )

        # Prochain palier
        if facture.get("niveau_suivant"):
            st.info(
                f"Palier suivant : **{config.NIVEAU_LABEL.get(facture['niveau_suivant'])}** "
                f"dans **{facture['jours_avant_prochain']} jour(s)** "
                f"(seuil {facture['seuil_suivant']} jours de retard).",
                icon="⏭️",
            )
        elif niveau == "avocat":
            st.error("Dernier palier atteint : dossier à transmettre au conseil juridique.", icon="⚖️")

        # Détail du score
        with st.expander("Comment ce score est-il calculé ?", expanded=not compact):
            detail = facture.get("score_detail", {})
            composantes = detail.get("composantes") or {}
            normalise = detail.get("normalise") or {}
            reglages_score = scoring.normaliser_score(reglages.get("score", {}))
            if not composantes:
                st.caption(detail.get("raison", "Score non applicable."))
            else:
                lignes = [
                    ("Ancienneté du retard", composantes.get("retard", 0), normalise.get("retard", 0),
                     reglages_score["poids_retard"], f"{facture.get('retard')} / {reglages_score['ref_retard']:.0f} jours"),
                    ("Montant de la créance", composantes.get("montant", 0), normalise.get("montant", 0),
                     reglages_score["poids_montant"],
                     f"{texte.fmt_montant(facture.get('montant'), devise)} / {texte.fmt_montant(reglages_score['ref_montant'], devise)}"),
                    ("Historique du client", composantes.get("historique", 0), normalise.get("historique", 0),
                     reglages_score["poids_historique"],
                     f"{facture.get('retards_anterieurs', 0)} / {reglages_score['ref_retards']:.0f} retards passés"),
                ]
                for libelle, points, part, poids, reference in lignes:
                    st.markdown(
                        f"<div class='dz-crit'><b>{libelle}</b> — poids {poids * 100:.0f} % · "
                        f"{points:.1f} point(s) · {reference}</div>",
                        unsafe_allow_html=True,
                    )
                    st.progress(min(1.0, max(0.0, part)))
                st.caption(
                    "Score = somme des trois critères plafonnés, sur 100. Poids et valeurs de référence "
                    "sont réglables dans Paramètres."
                )

        # Historique
        st.markdown("#### Étapes passées")
        st.markdown(ui.chronologie_html(facture.get("actions") or []), unsafe_allow_html=True)

        # Coordonnées
        st.markdown("#### Coordonnées")
        st.markdown(
            f"<div class='dz-chip'>👤 {ui.esc(facture.get('contact') or '—')}</div>"
            f"<div class='dz-chip'>📞 {ui.esc(facture.get('telephone') or '—')}</div>"
            f"<div class='dz-chip'>✉️ {ui.esc(facture.get('email') or '—')}</div>",
            unsafe_allow_html=True,
        )
        if facture.get("notes"):
            st.caption(f"📝 {facture['notes']}")

        # Actions de dossier
        st.markdown("#### Gérer le dossier")
        boutons = st.columns(3)
        if facture.get("statut") == "payee":
            if boutons[0].button("↩️ Rouvrir", width="stretch", key=f"{cle}_rouvrir", help="Replace la facture dans la file des relances."):
                db.rouvrir_facture(int(facture["id"]))
                state.flash("Facture rouverte", "↩️")
                st.rerun()
        else:
            if boutons[0].button("✅ Marquer payée", width="stretch", type="primary", key=f"{cle}_payer"):
                dialogue_paiement(facture, reglages, cle)
        if boutons[1].button("✏️ Modifier", width="stretch", key=f"{cle}_modifier"):
            dialogue_modifier(facture, reglages, cle)
        if boutons[2].button("🗑️ Supprimer", width="stretch", key=f"{cle}_supprimer"):
            dialogue_supprimer(facture, cle)

    with droite:
        st.markdown(f"#### 📨 Message préparé — {config.NIVEAU_LABEL.get(niveau, niveau)}")
        bloc_message(facture, reglages, cle)

        if niveau in config.SEUILS_ORDRE:
            st.markdown("#### 🗂️ Journaliser la relance")
            st.caption(
                "Enregistrer l'action garde une trace datée : c'est la preuve de relance en cas de "
                "transmission à un avocat."
            )
            if st.button(
                "🗂️ Action faite",
                type="primary",
                width="stretch",
                key=f"{cle}_action",
                help="Journalise la relance : type, résultat, date et message envoyé.",
            ):
                dialogue_action(facture, reglages, cle)
            if facture.get("action_a_jour"):
                st.success("Une relance a déjà été enregistrée depuis l'entrée dans ce palier.", icon="✅")
            else:
                st.warning("Aucune relance enregistrée depuis l'entrée dans ce palier.", icon="⏳")
