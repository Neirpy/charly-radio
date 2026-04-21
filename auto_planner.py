import json
import os
import requests
import datetime

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4:26b"
OUTPUT_FILE = "playlist_radio.json"
LIB_FILE = "bibliotheque.json"
CONFIG_FILE = "ai_config.json"
HISTORY_FILE = "historique_diffusion.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_day_name():
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    return days[datetime.datetime.now().weekday()]

def automate_radio():
    print(f"--- Automation Radio Intel : {datetime.datetime.now()} ---")
    
    # 1. Chargement des données
    lib = load_json(LIB_FILE, {})
    config = load_json(CONFIG_FILE, {})
    history = load_json(HISTORY_FILE, [])
    day_name = get_day_name()
    
    if not lib:
        print("Erreur: Bibliothèque vide.")
        return

    # 2. Préparation du prompt
    simplified_lib = []
    for playlist_name, data in lib.items():
        for track in data.get("tracks", []):
            simplified_lib.append({
                "id": track["id"],
                "titre": track["titre"],
                "duree": track["duree"],
                "playlist": playlist_name
            })

    recent_ids = []
    for entry in history[-5:]:
        recent_ids.extend(entry.get("track_ids", []))

    standard_rules = config.get("standard_day_rules", "")
    day_mood = config.get("weekly_moods", {}).get(day_name, "")

    prompt = f"""Tu es un programmateur radio expert. Automatisme quotidien.
Aujourd'hui c'est {day_name}. Ambiance : {day_mood}
Règles : {standard_rules}
INTERDICTION de rejouer ces IDs : {recent_ids[:100]}

Bibliothèque (Échantillon) :
{json.dumps(simplified_lib[:300], ensure_ascii=False)}

Génère un planning JSON complet (24h) au format :
[ {{"id": "XX", "start_minute": 600, "titre": "XX"}}, ... ]
Réponds UNIQUEMENT le JSON."""

    print(f"Envoi de la requête à Ollama ({MODEL_NAME})...")
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }, timeout=180)
        
        result = response.json()
        response_text = result.get("response", "[]")
        playlist_suggested = json.loads(response_text)
        
        if not playlist_suggested:
            print("L'IA n'a retourné aucun résultat.")
            return

        # Ajouter l'heure lisible
        for track in playlist_suggested:
            sm = track.get('start_minute', 0)
            track['heure_cible'] = f"{int(sm//60):02d}:{int(sm%60):02d}"

        # 3. Sauvegarder
        save_json(OUTPUT_FILE, playlist_suggested)
        
        # Mettre à jour l'historique
        history.append({
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "track_ids": [t['id'] for t in playlist_suggested]
        })
        save_json(HISTORY_FILE, history[-30:])
        
        print(f"Succès ! {len(playlist_suggested)} titres programmés pour {day_name}.")
        
    except Exception as e:
        print(f"Erreur d'automatisation : {e}")

if __name__ == "__main__":
    automate_radio()
