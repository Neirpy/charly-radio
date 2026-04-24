# 📻 Radio Charly Lab

*Read this in [English](README_EN.md).*

Radio du Charly Lab qui se synchronise en fonction du temps. 
Ce projet est un système complet de webradio intelligente. Il comprend un lecteur web synchronisé, une interface de programmation visuelle, et un moteur IA hybride capable de générer 24 heures de programmation musicale sans répétition en fonction de l'humeur de la journée.

## 🛠️ Architecture du Projet

Le projet est divisé en trois parties principales :

1. **Lecteur Web (Frontend)** : Un site web développé avec Vite/JS qui lit le fichier `playlist_radio.json` et synchronise parfaitement la lecture en fonction de l'heure réelle de l'auditeur.
2. **Interface de Programmation (Desktop)** : Le script `planner_radio.py` offre une interface graphique (PyQt6) pour visualiser la grille des programmes, glisser-déposer des sons, et générer des créneaux via une IA locale (Ollama).
3. **Moteur Auto-Pilote (Cloud)** : Le script `gemini_planner.py` permet de générer 24h de programmation instantanément via l'API Google Gemini. Il est conçu pour être lancé automatiquement chaque nuit par GitHub Actions.

---

## 🚀 1. Installation du Lecteur Web (Frontend)

C'est la partie visible par les auditeurs.

**Prérequis** : Avoir [Node.js](https://nodejs.org/) installé.

1. Installez les dépendances :
   ```bash
   npm install
   ```
2. Lancez le serveur de développement :
   ```bash
   npm run dev
   ```
3. Ouvrez votre navigateur sur `http://localhost:5173`. La musique se lance au bon moment de la playlist générée !

---

## 🖥️ 2. Interface de Programmation Locale (GUI)

C'est votre outil de studio. Il permet de voir et de modifier la grille.

**Prérequis** : Avoir Python 3.10+ et [Ollama](https://ollama.com/) (si vous utilisez la génération locale).

1. Créez un environnement virtuel et activez-le :
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Installez les librairies PyQt6 :
   ```bash
   pip install PyQt6
   ```
3. Lancez l'application :
   ```bash
   python planner_radio.py
   ```
*Note : Si vous utilisez le bouton "Générer avec l'IA" dans cette interface, assurez-vous que l'application Ollama est lancée en arrière-plan avec le modèle demandé.*

---

## 🧠 3. Le Pilote Automatique IA (Gemini Planner)

Ce script (`gemini_planner.py`) génère le fichier `playlist_radio.json` pour 24 heures en utilisant le modèle Gemma 4 hébergé sur l'API Google Gemini.

### Installation & Sécurisation

1. Assurez-vous d'avoir les dépendances :
   ```bash
   pip install python-dotenv google-genai
   ```
2. Créez un fichier `.env` à la racine du projet (ce fichier ne sera jamais partagé sur GitHub grâce au `.gitignore`) :
   ```env
   GEMINI_API_KEY=Votre_Clef_Secrete_Ici
   ```
3. Testez le script :
   ```bash
   python gemini_planner.py
   ```
   *Le script va lire les consignes dans `ai_config.json`, générer 12 "ancres" via Gemini, et remplir tous les vides intelligemment sans répéter les morceaux. Il mettra ensuite à jour `playlist_radio.json` et `historique_diffusion.json`.*

---

## 🤖 4. Automatisation avec GitHub Actions

Le projet est configuré pour **se mettre à jour tout seul toutes les nuits à minuit**.

1. Allez sur votre dépôt GitHub.
2. Allez dans **Settings > Secrets and variables > Actions**.
3. Cliquez sur **New repository secret**.
4. Nommez le secret `GEMINI_API_KEY` et collez votre vraie clé secrète dans la valeur.
5. C'est tout ! Chaque nuit, GitHub lancera `gemini_planner.py`, créera la grille de la journée, et poussera les modifications en ligne. Le lecteur web sera automatiquement à jour pour les auditeurs.

### Configurer l'humeur de la Radio
Vous pouvez modifier les consignes données à l'IA en éditant simplement le fichier `ai_config.json`.
