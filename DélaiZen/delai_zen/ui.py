# -*- coding: utf-8 -*-
"""Habillage de l'interface Streamlit (CSS, cartes, badges, en-tête)."""

from __future__ import annotations

import datetime as dt
import html

import streamlit as st

from . import config, scoring
from .texte import fmt_montant

CSS = """
<style>
:root {
    --dz-navy: #0b1626;
    --dz-teal: #10b981;
    --dz-slate: #64748b;
    --dz-line: #e2e8f0;
    --dz-ink: #0f172a;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1626 0%, #0f1f33 100%) !important;
}
[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small {
    color: #93a4bb !important;
}
[data-testid="stSidebar"] hr {
    border-color: #1e293b !important;
}
.block-container {
    padding-top: 1.4rem;
    padding-bottom: 2.5rem;
    max-width: 1500px;
}
.dz-entete {
    border: 1px solid var(--dz-line);
    border-left: 5px solid var(--dz-teal);
    border-radius: 12px;
    padding: 14px 18px;
    background: #ffffff;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    justify-content: space-between;
    align-items: center;
}
.dz-entete-titre { font-size: 1.15rem; font-weight: 800; color: var(--dz-ink); }
.dz-entete-sous { font-size: 0.85rem; color: var(--dz-slate); margin-top: 2px; }
.dz-entete-user {
    text-align: right;
    font-size: 0.82rem;
    color: var(--dz-slate);
    line-height: 1.35;
}
.dz-avatar {
    display: inline-block;
    width: 30px; height: 30px;
    background: var(--dz-navy);
    color: #fff;
    border-radius: 50%;
    text-align: center;
    line-height: 30px;
    font-weight: 800;
    font-size: 0.85rem;
    margin-right: 6px;
}
.kpi-card {
    border: 1px solid var(--dz-line);
    border-radius: 12px;
    padding: 14px 16px;
    background: #ffffff;
    min-width: 0;
    overflow-wrap: normal;
    word-break: normal;
}
.kpi-grille {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin-bottom: 6px;
}
.kpi-title {
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--dz-slate);
    display: flex; align-items: center; gap: 7px;
    line-height: 1.2;
}
.kpi-value {
    font-size: clamp(1.05rem, 1.6vw, 1.6rem);
    font-weight: 800;
    color: var(--dz-ink);
    line-height: 1.25;
    margin-top: 6px;
    white-space: nowrap;
}
.kpi-sub { font-size: 0.76rem; color: var(--dz-slate); margin-top: 3px; }
.dz-section { font-size: 1.05rem; font-weight: 800; color: var(--dz-ink); margin: 6px 0 2px 0; }
.dz-section-sous { font-size: 0.83rem; color: var(--dz-slate); margin-bottom: 8px; }
.badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
}
.dz-fiche {
    border: 1px solid var(--dz-line);
    border-radius: 12px;
    padding: 16px 18px;
    background: #ffffff;
}
.dz-meta { font-size: 0.8rem; color: var(--dz-slate); }
.dz-crit { font-size: 0.82rem; color: var(--dz-ink); margin-bottom: 2px; }
.dz-chip {
    display: inline-block;
    border: 1px solid var(--dz-line);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 0.8rem;
    margin: 0 6px 6px 0;
    background: #f8fafc;
}
.dz-chrono { border-left: 2px solid var(--dz-line); padding-left: 12px; margin-left: 4px; }
.dz-chrono-item { font-size: 0.84rem; color: var(--dz-ink); margin-bottom: 8px; }
.dz-chrono-date { font-weight: 700; }
.dz-chrono-meta { color: var(--dz-slate); font-size: 0.78rem; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(valeur) -> str:
    return html.escape("" if valeur is None else str(valeur))


# --------------------------------------------------------------------------
# En-tête
# --------------------------------------------------------------------------
def entete(settings: dict, portefeuille: list[dict], aujourdhui: dt.date | None = None) -> None:
    aujourdhui = aujourdhui or dt.date.today()
    societe = settings.get("societe", {})
    utilisateur = societe.get("utilisateur") or "Utilisateur"
    initiales = "".join(mot[0] for mot in str(utilisateur).split()[:2]).upper() or "U"
    en_retard = [f for f in portefeuille if f.get("en_retard")]
    a_traiter = [f for f in en_retard if not f.get("action_a_jour")]
    montant = sum(float(f["montant"] or 0) for f in en_retard)

    st.markdown(
        '<div class="dz-entete">'
        "<div>"
        f'<div class="dz-entete-titre">🏢 {esc(societe.get("nom", "Mon entreprise"))}</div>'
        '<div class="dz-entete-sous">'
        f"Situation au {aujourdhui.strftime('%d/%m/%Y')} · Devise : {esc(societe.get('devise', 'MAD'))} · "
        f"{len(en_retard)} facture(s) en retard pour {fmt_montant(montant, societe.get('devise', 'MAD'))} · "
        f"{len(a_traiter)} action(s) à mener"
        "</div>"
        "</div>"
        '<div class="dz-entete-user">'
        f'<span class="dz-avatar">{esc(initiales)}</span><b>{esc(utilisateur)}</b><br>'
        f'<span class="dz-meta">Session locale · {esc(config.APP_NAME)} {esc(config.APP_VERSION)}</span>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def titre_section(titre: str, sous_titre: str = "") -> None:
    st.markdown(f'<div class="dz-section">{esc(titre)}</div>', unsafe_allow_html=True)
    if sous_titre:
        st.markdown(f'<div class="dz-section-sous">{esc(sous_titre)}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Cartes et badges
# --------------------------------------------------------------------------
def kpi_card(titre: str, valeur: str, sous_titre: str = "", couleur: str = "#10b981", icone: str = "") -> None:
    kpi_grille([(titre, valeur, sous_titre, couleur, icone)])


def kpi_grille(cartes: list[tuple[str, str, str, str, str]]) -> None:
    """Bandeau de cartes réactif : ``(titre, valeur, sous-titre, couleur, icône)``.

    Le HTML est produit sans indentation : Markdown interpréterait les lignes
    indentées comme un bloc de code.
    """
    blocs = []
    for titre, valeur, sous_titre, couleur, icone in cartes:
        blocs.append(
            '<div class="kpi-card">'
            f'<div class="kpi-title"><span style="color:{couleur}">{icone or "●"}</span>{esc(titre)}</div>'
            f'<div class="kpi-value">{esc(valeur)}</div>'
            f'<div class="kpi-sub">{esc(sous_titre)}</div>'
            "</div>"
        )
    st.markdown('<div class="kpi-grille">' + "".join(blocs) + "</div>", unsafe_allow_html=True)


def badge(texte: str, couleur: str, icone: str = "") -> str:
    contenu = f"{icone} {esc(texte)}".strip()
    return f'<span class="badge" style="background:{couleur}">{contenu}</span>'


def badge_niveau(niveau: str) -> str:
    return badge(
        config.NIVEAU_COURT.get(niveau, niveau),
        config.NIVEAU_COLOR.get(niveau, "#64748b"),
        config.NIVEAU_ICON.get(niveau, ""),
    )


def badge_score(score: int | None) -> str:
    if score is None:
        return '<span class="badge" style="background:#94a3b8">—</span>'
    couleur = scoring.libelle_priorite(score)[1]
    return f'<span class="badge" style="background:{couleur}">{score}/100</span>'


def fiche_facture_html(facture: dict, devise: str = "MAD") -> str:
    return (
        f'<div class="dz-fiche">'
        f'<div style="font-size:1.05rem;font-weight:800;color:#0f172a">{esc(facture.get("client"))}</div>'
        f'<div class="dz-meta">Facture {esc(facture.get("numero"))} · {esc(facture.get("contact") or "—")}</div>'
        f'<div style="margin-top:8px;font-size:1.3rem;font-weight:800">{esc(fmt_montant(facture.get("montant"), devise))}</div>'
        f'<div class="dz-meta">Échéance {esc(facture.get("echeance"))} · retard {facture.get("retard", 0)} jour(s)</div>'
        f'<div style="margin-top:8px">{badge_niveau(facture.get("niveau", ""))} {badge_score(facture.get("score"))}</div>'
        f"</div>"
    )


def chronologie_html(actions: list[dict]) -> str:
    if not actions:
        return '<div class="dz-meta">Aucune action enregistrée pour cette facture.</div>'
    fortes = sorted(actions, key=lambda a: (a.get("date_action") or "", a.get("id") or 0), reverse=True)
    blocs = []
    for action in fortes:
        type_action = config.TYPES_ACTION.get(action.get("type_action", ""), action.get("type_action", ""))
        resultat = config.RESULTATS_ACTION.get(action.get("resultat", ""), action.get("resultat", ""))
        couleur = config.NIVEAU_COLOR.get(action.get("niveau", ""), "#64748b")
        commentaire = (action.get("commentaire") or "").strip()
        blocs.append(
            '<div class="dz-chrono-item">'
            f'<span class="dz-chrono-date">{esc(action.get("date_action", "")[:16].replace("T", " "))}</span> '
            f'<span style="color:{couleur};font-weight:700">{esc(type_action)}</span><br>'
            f'<span class="dz-chrono-meta">{esc(resultat)} · {action.get("jours_retard", 0)} j de retard'
            f'{" · " + esc(commentaire) if commentaire else ""}</span>'
            "</div>"
        )
    return '<div class="dz-chrono">' + "".join(blocs) + "</div>"


# --------------------------------------------------------------------------
# États vides
# --------------------------------------------------------------------------
def etat_vide() -> None:
    st.info(
        "**Aucune facture enregistrée pour le moment.**\n\n"
        "1. Renseignez le nom de votre société dans **Paramètres**.\n"
        "2. Ajoutez vos factures dans **Factures** (ou importez un CSV).\n"
        "3. DélaiZen calcule alors le retard, le niveau de traitement et le score, "
        "puis prépare les messages dans **Relances du jour**."
    )
    c1, c2, _ = st.columns([1.3, 1.3, 2])
    if c1.button("📥 Charger la démonstration", type="primary", width="stretch", help="Ajoute 7 factures d'exemple datées autour d'aujourd'hui."):
        from . import db

        db.charger_demo()
        st.toast("Portefeuille de démonstration chargé", icon="✅")
        st.rerun()
    if c2.button("➕ Ajouter une facture", width="stretch"):
        from . import navigation

        navigation.aller("factures")
