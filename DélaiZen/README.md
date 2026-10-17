# DélaiZen — Scoring des impayés

Application **Streamlit** qui note chaque facture en retard sur 100 et indique l'action à mener
selon le nombre de jours de retard. But : savoir chaque jour **quelle facture relancer, comment,
et avec quel message**.

- **Le scoring** (0 à 100) classe les factures par urgence : on commence toujours par le haut de la liste.
- **L'alerte** se déclenche à l'échéance : le nombre de jours de retard fixe le niveau de traitement,
  qui lui-même décide du message préparé.

Tout est local : les données vivent dans un fichier SQLite sur votre machine, rien n'est envoyé sur Internet.

---

## 1. Installation

```powershell
cd "C:\Users\hp\OneDrive\Bureau\DélaiZen"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur <http://localhost:8501>.

> Sur cette machine, si `python` n'est pas reconnu, utilisez le chemin complet :
> `& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m streamlit run app.py`
>
> Version vérifiée : Python 3.11, Streamlit 1.66, pandas 3.0, plotly 7.1.

Premier lancement : l'application propose de **charger un portefeuille de démonstration**
(7 clients, retards de 1 à 68 jours) pour voir immédiatement le scoring et les messages.

---

## 2. Les sept étapes

| Étape | Écran | Ce que vous faites |
|---|---|---|
| 1. Régler l'application | **Paramètres** | nom de la société, devise, seuils des niveaux, poids du score, modèles de messages |
| 2. Enregistrer les factures | **Factures** | client, n° de facture, montant, échéance, téléphone, email, retards passés (ou import CSV) |
| 3. Laisser calculer | tout l'écran | retard, niveau de traitement et score sont recalculés à chaque affichage |
| 4. Lire la synthèse | **Tableau de bord** | montant impayé, nombre de retards, retard moyen, répartition par niveau, courbe d'encours — un clic sur une part du donut filtre la liste |
| 5. Ouvrir la facture prioritaire | **Tableau de bord / Factures** | fiche : niveau atteint, score détaillé, étapes passées, jours restants avant le palier suivant |
| 6. Envoyer le message | **Relances du jour** | message déjà rédigé (SMS, script d'appel, email, mise en demeure, note avocat) : copier, envoyer, journaliser |
| 7. Clôturer | **Factures** | « marquer payée » ; sinon l'alerte monte d'un niveau dès le seuil suivant |

La routine quotidienne tient en trois gestes : ouvrir **Relances du jour**, traiter la file du haut
vers le bas (copier → envoyer → « Action faite »), marquer payées les factures réglées.

---

## 3. Niveaux de traitement (réglables)

| Retard | Traitement | Message préparé |
|---|---|---|
| 1 à 7 jours | SMS de rappel | texte court, prêt à copier |
| 8 à 14 jours | Appel téléphonique | script d'appel en 8 points |
| 15 à 29 jours | Email personnalisé | objet + corps, échéance de règlement |
| 30 à 59 jours | Mise en demeure | courrier formel, délai « sous huitaine » |
| 60 jours et plus | Transmission à l'avocat | note de transmission + chronologie des relances |

Les seuils sont modifiables (Paramètres → *Seuils des niveaux*) ; ils sont automatiquement
maintenus croissants.

## 4. Scoring (réglable)

```
score = 100 × ( poids_retard   × min(retard / ref_retard, 1)
              + poids_montant  × min(montant / ref_montant, 1)
              + poids_histo    × min(retards_passés / ref_retards, 1) )
```

Par défaut : retard 55 %, montant 30 %, historique 15 % ; références 90 jours, 50 000 MAD,
5 retards passés. Chaque critère sature à 1, donc un très long retard ou un très gros montant
n'écrase pas les autres. Le score sert à **classer** ; le niveau (calculé depuis l'échéance) sert à **agir**.

Une facture non échue n'a pas de score : elle apparaît dans la file le lendemain de son échéance.

---

## 5. Ce que l'application produit

- **Messages prêts à envoyer** : SMS, script d'appel, email, mise en demeure, note pour l'avocat,
  remplis avec le nom du client, le montant et les dates (bloc de code : un clic copie le texte).
- **Liens directs** : ouvrir le message dans la messagerie (`mailto:`), appeler le client (`tel:`),
  envoyer un SMS pré-rempli (`sms:`).
- **Historique des relances** : chaque action journalisée conserve la date, le canal, le résultat,
  le message envoyé et le commentaire. C'est la **preuve de relance** en cas de dossier contentieux.
- **Dossier de recouvrement** : synthèse texte (créance, chronologie, pièces à joindre), exportable
  depuis *Factures → Exporter* ou *Suivi des actions → Preuves*.
- **Exports CSV** : portefeuille, historique des relances, paramètres (JSON), sauvegarde complète.

---

## 6. Structure du projet

| Chemin | Rôle |
|---|---|
| `app.py` | point d'entrée Streamlit, navigation entre les pages |
| `delai_zen/config.py` | constantes, niveaux, seuils et modèles par défaut |
| `delai_zen/db.py` | base SQLite (factures, actions, paramètres), jeu de démonstration |
| `delai_zen/scoring.py` | retard, niveau de traitement, score, indicateurs, courbe d'encours |
| `delai_zen/messages.py` | modèles de messages, placeholders, liens email/SMS/téléphone |
| `delai_zen/import_export.py` | import CSV, exports, dossier de recouvrement |
| `delai_zen/navigation.py` | déclaration des pages |
| `delai_zen/state.py` | accès aux données et à l'état de session |
| `delai_zen/texte.py` | formats d'affichage (montants, dates) |
| `delai_zen/ui.py` | habillage (CSS, en-tête, cartes, badges, états vides) |
| `views/*.py` | les six pages : tableau de bord, relances, factures, suivi, paramètres, aide |
| `tests/test_delaizen.py` | tests des règles métier (26 tests) |
| `data/delai_zen.db` | **vos données** (créé au premier lancement) |

### Où sont mes données ?

- Base : `data/delai_zen.db` (SQLite). Copiez ce dossier pour une sauvegarde complète.
- Variables d'environnement optionnelles : `DELAIZEN_DB` (chemin du fichier), `DELAIZEN_DATA_DIR`.
- Paramètres → *Données* : date de simulation (voir l'effet du temps), chargement de la démo,
  export JSON, purge complète (confirmation par saisie de `SUPPRIMER`).

### Import CSV

Colonnes reconnues (séparateur `;` ou `,`) : `client`, `numero`, `montant`, `date_facture`,
`echeance`, `contact`, `telephone`, `email`, `retards_anterieurs`, `notes`.
Dates au format `JJ/MM/AAAA` ou `AAAA-MM-JJ`. Les lignes invalides sont ignorées et listées.
Un modèle est téléchargeable dans *Factures → Importer*.

---

## 7. Tests

```powershell
python -m unittest discover -s tests -v
```

Couvre la grille des seuils, le calcul du score, le classement, les indicateurs, la courbe
d'encours, le remplissage des modèles, l'import CSV, le dossier de recouvrement et le cycle de vie
en base (création, paiement, suppression en cascade).

---

## 8. Limites, juridique et données personnelles

- Les modèles de **mise en demeure** et de **note à l'avocat** sont des **brouillons** : un juriste
  doit les valider avant tout envoi, ainsi que les seuils de **30** et **60** jours.
- L'application **n'envoie rien** à votre place, ne calcule pas les intérêts de retard et ne vérifie
  pas la prescription. Elle prépare, classe et garde trace.
- Les noms, téléphones et emails des clients sont des **données personnelles**. Au Maroc, vérifiez vos
  obligations au titre de la **loi 09-08** et auprès de la **CNDP** : finalité du traitement,
  information des personnes, durée de conservation, sécurité des accès.
- Les données restent locales, mais le fichier SQLite n'est pas chiffré : protégez l'accès à la
  machine et aux sauvegardes.
