# -*- coding: utf-8 -*-
"""DélaiZen — Scoring des impayés : savoir qui relancer, comment et avec quel message.

Point d'entrée Streamlit :

    streamlit run app.py

Toute la logique est dans le paquet ``delai_zen`` et l'affichage dans ``views``.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import streamlit as st  # noqa: E402

from delai_zen import config, db, navigation, state, ui  # noqa: E402

st.set_page_config(
    page_title=f"{config.APP_NAME} — scoring des impayés",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()
ui.inject_css()

page_courante = st.navigation(navigation.sections(), position="sidebar")

with st.sidebar:
    st.divider()
    st.markdown(f"### 🛡️ {config.APP_NAME}")
    st.caption(config.APP_TAGLINE)
    st.divider()
    st.caption(f"🧭 {state.libelle_date_simulation()}")
    st.caption(f"💾 Base locale : {config.DB_PATH.name}")
    st.caption("Prototype pédagogique — modèles juridiques à faire valider.")

page_courante.run()
