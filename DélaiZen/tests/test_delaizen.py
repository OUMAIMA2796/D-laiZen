# -*- coding: utf-8 -*-
"""Tests des règles métier de DélaiZen (sans interface).

Exécution :  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

# Base de données jetable, isolée des vraies données
_TEMP = tempfile.mkdtemp(prefix="delaizen_tests_")
os.environ["DELAIZEN_DB"] = str(Path(_TEMP) / "test.db")

from delai_zen import config, db, import_export, messages, scoring  # noqa: E402

AUJOURDHUI = dt.date(2026, 10, 17)


def facture(**remplacements) -> dict:
    base = {
        "id": 1,
        "client": "Client Test",
        "numero": "FAC-001",
        "montant": 20000.0,
        "date_facture": "2026-09-01",
        "echeance": "2026-09-30",
        "contact": "Mme Test",
        "telephone": "0661000000",
        "email": "test@client.example",
        "retards_anterieurs": 1,
        "statut": "ouverte",
        "date_paiement": None,
        "notes": "",
    }
    base.update(remplacements)
    return base


def reglages_par_defaut() -> dict:
    return {
        "societe": dict(config.DEFAULT_SOCIETE),
        "seuils": dict(config.DEFAULT_SEUILS),
        "score": dict(config.DEFAULT_SCORE),
        "modeles": dict(config.DEFAULT_MODELES),
    }


class TestNiveaux(unittest.TestCase):
    def setUp(self) -> None:
        self.seuils = scoring.normaliser_seuils(config.DEFAULT_SEUILS)

    def _niveau(self, jours_de_retard: int) -> str:
        echeance = AUJOURDHUI - dt.timedelta(days=jours_de_retard)
        return scoring.niveau_de(facture(echeance=echeance.isoformat()), self.seuils, AUJOURDHUI)

    def test_grille_des_seuils(self) -> None:
        attendus = {
            1: "sms", 7: "sms",
            8: "appel", 14: "appel",
            15: "email", 29: "email",
            30: "mise_en_demeure", 59: "mise_en_demeure",
            60: "avocat", 120: "avocat",
        }
        for retard, niveau in attendus.items():
            with self.subTest(retard=retard):
                self.assertEqual(self._niveau(retard), niveau)

    def test_avant_echeance(self) -> None:
        self.assertEqual(self._niveau(0), "a_echeance")
        self.assertEqual(self._niveau(-5), "a_venir")

    def test_facture_payee(self) -> None:
        self.assertEqual(
            scoring.niveau_de(facture(statut="payee"), self.seuils, AUJOURDHUI), "payee"
        )

    def test_palier_suivant(self) -> None:
        self.assertEqual(scoring.niveau_suivant("sms", self.seuils), ("appel", 8))
        self.assertEqual(scoring.niveau_suivant("avocat", self.seuils), (None, 0))
        self.assertEqual(scoring.niveau_suivant("a_echeance", self.seuils), ("sms", 1))

    def test_seuils_incorrects_sont_corriges(self) -> None:
        propres = scoring.normaliser_seuils({"sms": 10, "appel": 3, "email": 0, "mise_en_demeure": 30, "avocat": 20})
        valeurs = list(propres.values())
        self.assertEqual(valeurs, sorted(valeurs))
        self.assertTrue(all(valeur >= 1 for valeur in valeurs))


class TestScoring(unittest.TestCase):
    def setUp(self) -> None:
        self.score = scoring.normaliser_score(config.DEFAULT_SCORE)

    def _score(self, **remplacements) -> int | None:
        return scoring.score_de(facture(**remplacements), self.score, AUJOURDHUI)[0]

    def test_facture_non_echue_sans_score(self) -> None:
        echeance = (AUJOURDHUI + dt.timedelta(days=10)).isoformat()
        self.assertIsNone(self._score(echeance=echeance))
        self.assertEqual(self._score(statut="payee"), 0)

    def test_score_borne(self) -> None:
        score = self._score(
            echeance="2020-01-01", montant=10_000_000, retards_anterieurs=50
        )
        self.assertEqual(score, 100)

    def test_score_minimum_un_jour_de_retard(self) -> None:
        score = self._score(echeance=AUJOURDHUI.isoformat(), montant=1, retards_anterieurs=0)
        self.assertIsNone(score)  # le jour de l'échéance, pas encore en retard
        score = self._score(
            echeance=(AUJOURDHUI - dt.timedelta(days=1)).isoformat(), montant=1, retards_anterieurs=0
        )
        self.assertGreaterEqual(score, 1)

    def test_le_retard_pese_plus_que_le_montant(self) -> None:
        # 70 jours pour 3 000 doit passer avant 2 jours pour 40 000
        ancien_petit = self._score(
            echeance=(AUJOURDHUI - dt.timedelta(days=70)).isoformat(), montant=3000, retards_anterieurs=0
        )
        recent_gros = self._score(
            echeance=(AUJOURDHUI - dt.timedelta(days=2)).isoformat(), montant=40000, retards_anterieurs=0
        )
        self.assertGreater(ancien_petit, recent_gros)

    def test_poids_pris_en_compte(self) -> None:
        base = self._score(echeance="2026-09-30", montant=10000, retards_anterieurs=0)
        tout_historique = scoring.normaliser_score(
            {"poids_retard": 0, "poids_montant": 0, "poids_historique": 1,
             "ref_retard": 90, "ref_montant": 50000, "ref_retards": 5}
        )
        historique = scoring.score_de(
            facture(echeance="2026-09-30", montant=10000, retards_anterieurs=5),
            tout_historique,
            AUJOURDHUI,
        )[0]
        self.assertEqual(historique, 100)
        self.assertLess(base, 50)


class TestPortefeuille(unittest.TestCase):
    def setUp(self) -> None:
        self.reglages = reglages_par_defaut()
        self.factures = [
            facture(id=1, numero="A", client="Ancien petit", montant=3000,
                    echeance=(AUJOURDHUI - dt.timedelta(days=70)).isoformat(), retards_anterieurs=0),
            facture(id=2, numero="B", client="Récent gros", montant=40000,
                    echeance=(AUJOURDHUI - dt.timedelta(days=2)).isoformat(), retards_anterieurs=0),
            facture(id=3, numero="C", client="Payée", montant=5000, statut="payee",
                    date_paiement="2026-10-01", echeance="2026-09-15"),
            facture(id=4, numero="D", client="Pas due", montant=9000,
                    echeance=(AUJOURDHUI + dt.timedelta(days=12)).isoformat()),
        ]

    def test_classement_par_score(self) -> None:
        portefeuille = scoring.enrichir(self.factures, [], self.reglages, AUJOURDHUI)
        self.assertEqual(portefeuille[0]["client"], "Ancien petit")
        scores = [f["score"] for f in portefeuille if f["score"] is not None]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_kpis(self) -> None:
        portefeuille = scoring.enrichir(self.factures, [], self.reglages, AUJOURDHUI)
        indicateurs = scoring.kpis(portefeuille)
        self.assertEqual(indicateurs["nb_factures"], 4)
        self.assertEqual(indicateurs["nb_retard"], 2)
        self.assertEqual(indicateurs["nb_payees"], 1)
        self.assertEqual(indicateurs["montant_retard"], 43000.0)
        self.assertEqual(indicateurs["montant_ouvert"], 52000.0)
        self.assertEqual(indicateurs["retard_moyen"], 36)
        self.assertEqual(indicateurs["nb_a_traiter"], 2)

    def test_action_a_jour(self) -> None:
        action = {
            "id": 1, "facture_id": 1, "date_action": "2026-10-16T09:00:00", "niveau": "avocat",
            "type_action": "avocat", "resultat": "sans_reponse", "jours_retard": 69,
        }
        portefeuille = scoring.enrichir(self.factures, [action], self.reglages, AUJOURDHUI)
        ancien = next(f for f in portefeuille if f["id"] == 1)
        self.assertTrue(ancien["action_a_jour"])
        recent = next(f for f in portefeuille if f["id"] == 2)
        self.assertFalse(recent["action_a_jour"])

    def test_repartition(self) -> None:
        portefeuille = scoring.enrichir(self.factures, [], self.reglages, AUJOURDHUI)
        stats = scoring.repartition(portefeuille)
        self.assertEqual(stats["avocat"]["nb"], 1)
        self.assertEqual(stats["sms"]["nb"], 1)
        self.assertEqual(stats["payee"]["nb"], 1)
        self.assertEqual(stats["a_venir"]["nb"], 1)

    def test_evolution_encours(self) -> None:
        portefeuille = scoring.enrichir(self.factures, [], self.reglages, AUJOURDHUI)
        courbe = scoring.evolution_encours(portefeuille, jours=90, aujourdhui=AUJOURDHUI)
        self.assertEqual(len(courbe), 90)
        self.assertEqual(courbe[-1]["date"], AUJOURDHUI)
        # Aujourd'hui : A (3000) + B (40000) + D (9000) en encours, C est payée
        self.assertEqual(courbe[-1]["encours"], 52000.0)
        self.assertEqual(courbe[-1]["retard"], 43000.0)
        # À la première date de la courbe, seules les factures déjà émises comptent
        self.assertLessEqual(courbe[0]["encours"], courbe[-1]["encours"])


class TestMessages(unittest.TestCase):
    def setUp(self) -> None:
        self.reglages = reglages_par_defaut()
        self.facture = scoring.enrichir(
            [facture(echeance=(AUJOURDHUI - dt.timedelta(days=35)).isoformat(), montant=18500)],
            [],
            self.reglages,
            AUJOURDHUI,
        )[0]

    def test_niveau_et_remplacement(self) -> None:
        self.assertEqual(self.facture["niveau"], "mise_en_demeure")
        message = messages.message_pour(self.facture, self.reglages, AUJOURDHUI).replace("\u202f", " ")
        self.assertIn("Client Test", message)
        self.assertIn("18 500,00 MAD", message)
        self.assertIn("35", message)
        self.assertNotIn("{client}", message)
        self.assertNotIn("{montant}", message)

    def test_aucun_placeholder_inconnu(self) -> None:
        for niveau in config.SEUILS_ORDRE:
            with self.subTest(niveau=niveau):
                facture_niveau = dict(self.facture)
                facture_niveau["niveau"] = niveau
                message = messages.message_pour(facture_niveau, self.reglages, AUJOURDHUI)
                for code in messages.PLACEHOLDERS:
                    if code in ("{chronologie}",):
                        continue
                    self.assertNotIn(code, message)

    def test_modele_personnalise(self) -> None:
        perso = reglages_par_defaut()
        perso["modeles"]["sms"] = "Rappel : {client} doit {montant} ({retard} {retard_mot})."
        facture_sms = dict(self.facture, niveau="sms", retard=3)
        message = messages.message_pour(facture_sms, perso)
        self.assertEqual(message, "Rappel : Client Test doit 18\u202f500,00 (3 jours).")

    def test_accolade_isolee_ne_casse_pas(self) -> None:
        perso = reglages_par_defaut()
        perso["modeles"]["sms"] = "Bonjour {client} - dossier {ouvert"
        facture_sms = dict(self.facture, niveau="sms")
        self.assertEqual(
            messages.message_pour(facture_sms, perso), "Bonjour {client} - dossier {ouvert"
        )

    def test_liens(self) -> None:
        sms = dict(self.facture, niveau="sms", retard=3)
        self.assertTrue(messages.lien_email(self.facture, self.reglages, AUJOURDHUI).startswith("mailto:test@client.example"))
        self.assertTrue(messages.lien_sms(sms, self.reglages, AUJOURDHUI).startswith("sms:0661000000"))
        self.assertEqual(messages.lien_telephone(self.facture), "tel:0661000000")
        self.assertIsNone(messages.lien_email(facture(email=""), self.reglages, AUJOURDHUI))

    def test_chronologie(self) -> None:
        actions = [
            {"id": 1, "date_action": "2026-09-20T09:00:00", "type_action": "sms", "resultat": "sans_reponse",
             "jours_retard": 3, "commentaire": ""},
            {"id": 2, "date_action": "2026-10-01T10:00:00", "type_action": "appel", "resultat": "promesse_paiement",
             "jours_retard": 14, "commentaire": "Règlement annoncé le 15/10."},
        ]
        texte = messages.chronologie(actions)
        self.assertIn("20/09/2026", texte)
        self.assertIn("SMS de rappel", texte)
        self.assertIn("Promesse de paiement", texte)
        self.assertIn("Règlement annoncé le 15/10.", texte)
        self.assertLess(texte.index("SMS de rappel"), texte.index("Appel téléphonique"))


class TestImportExport(unittest.TestCase):
    def test_modele_et_import(self) -> None:
        modele = import_export.modele_csv()
        self.assertIn("client;numero;montant", modele)
        crees, erreurs = import_export.importer(modele.encode("utf-8"), AUJOURDHUI)
        self.assertEqual(crees, 1)
        self.assertEqual(erreurs, [])

        # Une deuxième fois : le numéro existe déjà
        crees, erreurs = import_export.importer(modele.encode("utf-8"), AUJOURDHUI)
        self.assertEqual(crees, 0)
        self.assertTrue(any("existe déjà" in erreur for erreur in erreurs))

    def test_lignes_invalides(self) -> None:
        csv = (
            "client;numero;montant;echeance\n"
            ";FAC-900;1000;01/10/2026\n"
            "Client X;;1000;01/10/2026\n"
            "Client Y;FAC-901;0;01/10/2026\n"
            "Client Z;FAC-902;5000;pas-une-date\n"
        )
        crees, erreurs = import_export.importer(csv.encode("utf-8"), AUJOURDHUI)
        self.assertEqual(crees, 0)
        self.assertEqual(len(erreurs), 4)

    def test_dossier_de_recouvrement(self) -> None:
        perso = reglages_par_defaut()
        ligne = scoring.enrichir(
            [facture(echeance=(AUJOURDHUI - dt.timedelta(days=65)).isoformat())], [], perso, AUJOURDHUI
        )[0]
        dossier = import_export.dossier_recouvrement(ligne, perso, AUJOURDHUI)
        self.assertIn("DOSSIER DE RECOUVREMENT", dossier)
        self.assertIn("FAC-001", dossier)
        self.assertIn("Client Test", dossier)
        self.assertIn("65", dossier)


class TestBaseDeDonnees(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        db.supprimer_tout()

    def test_cycle_de_vie(self) -> None:
        identifiant = db.create_facture(
            {
                "client": "Cycle", "numero": "FAC-CYCLE", "montant": 1500.0,
                "date_facture": "2026-09-01", "echeance": "2026-10-01", "contact": "",
                "telephone": "", "email": "", "retards_anterieurs": 0,
                "statut": "ouverte", "date_paiement": None, "notes": "",
            }
        )
        self.assertIsNotNone(db.get_facture(identifiant))

        db.update_facture(identifiant, {"montant": 2000.0})
        self.assertEqual(db.get_facture(identifiant)["montant"], 2000.0)

        db.create_action({"facture_id": identifiant, "date_action": "2026-10-17T09:00:00",
                          "niveau": "sms", "type_action": "sms", "canal": "SMS", "resultat": "fait",
                          "contenu": "msg", "commentaire": "", "utilisateur": "Test",
                          "jours_retard": 16, "montant": 2000.0})
        self.assertEqual(len(db.list_actions(identifiant)), 1)

        db.marquer_payee(identifiant, "2026-10-17", "Test")
        self.assertEqual(db.get_facture(identifiant)["statut"], "payee")
        # L'encaissement est tracé dans l'historique
        self.assertEqual(len(db.list_actions(identifiant)), 2)

        db.delete_facture(identifiant)
        self.assertIsNone(db.get_facture(identifiant))
        # Suppression en cascade de l'historique
        self.assertEqual(len(db.list_actions(identifiant)), 0)

    def test_demo_et_parametres(self) -> None:
        nombre = db.charger_demo()
        self.assertGreaterEqual(nombre, 5)
        self.assertEqual(len(db.list_factures()), nombre)

        db.save_settings({"societe": {"nom": "Test SARL", "devise": "MAD"}})
        reglages = db.get_settings()
        self.assertEqual(reglages["societe"]["nom"], "Test SARL")
        # Les autres clés restent les valeurs par défaut
        self.assertEqual(reglages["societe"]["devise"], "MAD")
        self.assertEqual(reglages["seuils"]["avocat"], 60)

        db.reset_settings()
        self.assertEqual(db.get_settings()["societe"]["nom"], config.DEFAULT_SOCIETE["nom"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
