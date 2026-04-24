import json
import os
import random
import re
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Charge les variables du fichier .env
load_dotenv()

# --- 1. CONFIGURATION API ---
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key or api_key == "Ta_Cle_Secrete_Ici":
    print("❌ Erreur : Veuillez configurer votre GEMINI_API_KEY dans le fichier .env")
    exit(1)

client = genai.Client(api_key=api_key)

# --- 2. CHARGEMENT DES CONFIGURATIONS ---
def load_json(filepath, default_val):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default_val

ai_config = load_json('ai_config.json', {})
bibliotheque = load_json('bibliotheque.json', {})
history = load_json('historique_diffusion.json', [])

# Déterminer le jour actuel en français
jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
day_name = jours_fr[datetime.now().weekday()]

# Récupérer le contexte depuis ai_config.json
day_mood = ai_config.get("weekly_moods", {}).get(day_name, "Bonnes ondes")
standard_rules = ai_config.get("standard_day_rules", "")

# --- 3. PRÉPARATION DE LA BIBLIOTHÈQUE ---
playlists_data = {}
all_tracks = []

# Supporte les formats dict ou list
if isinstance(bibliotheque, dict):
    playlists_data = bibliotheque
    for g, data in bibliotheque.items():
        all_tracks.extend(data.get("tracks", []))
elif isinstance(bibliotheque, list):
    playlists_data = {"TOUT": {"tracks": bibliotheque}}
    all_tracks.extend(bibliotheque)

# Extraire une liste de titres pour le prompt (limité pour ne pas exploser le token count)
tracks_subset = all_tracks[:50]
lib_lines = "\n".join([f"{t['id']}|{t['titre'][:40]}" for t in tracks_subset])

genres = list(playlists_data.keys())
genres_str = ", ".join(genres)

# Historique pour éviter les répétitions immédiates
used_ids = []
for entry in history[-3:]:
    for tid in entry.get("track_ids", []):
        if tid not in used_ids: used_ids.append(tid)

recent_ids = ",".join(used_ids[-15:])

# --- 4. LE PROMPT HYBRIDE (24H) ---
start_min_offset = 0
end_min = 1440 # 24 heures
n_anchors = 12

prompt = (
    f"You are the Program Director. Mode: Hybrid (AI Anchors + Auto-fill) for a 24-hour schedule.\n"
    f"Day:{day_name} Mood:{day_mood}\n"
    f"Rules:{standard_rules}\n"
    f"Available Playlists (Genres): {genres_str}\n"
    f"Music list sample (id|title):\n{lib_lines}\n"
    f"Avoid IDs: {recent_ids}\n\n"
    f"TASK: Select {n_anchors} 'Anchor Tracks' from the list. Each track marks a vibe shift.\n"
    f"For each anchor, give: id, start_minute (between {start_min_offset} and {end_min}), and 'fill_genre' (the playlist name to use for filling the gap AFTER this track).\n"
    f"JSON FORMAT ONLY:\n"
    f'[\n  {{"id":"ID", "start_minute":0, "titre":"Title", "fill_genre":"{genres[0] if genres else "Pop"}"}},\n  ...\n]\n'
)

# --- 5. GÉNÉRATION ---
print(f"🧠 Demande à Gemini en cours pour le {day_name} (Modèle: gemma-4-26b-a4b-it)...")
try:
    response = client.models.generate_content(
        model='gemma-4-26b-a4b-it',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    
    # Extraction propre du JSON
    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    suggested_playlist = json.loads(raw_text.strip())
except Exception as e:
    print(f"❌ Erreur lors de la génération avec l'API : {e}")
    exit(1)

# --- 6. RÉSOLUTION ET REMPLISSAGE HYBRIDE ---
def find_track_in_lib(tid, ttitle):
    for g, data in playlists_data.items():
        for t in data.get("tracks", []):
            if t['id'] == tid: return t
    return None

def pick_random_track(genre, used_ids_list):
    candidates = []
    if genre in playlists_data:
        candidates = [t for t in playlists_data[genre].get("tracks", []) if t['id'] not in used_ids_list]
    
    if not candidates:
        for g in playlists_data.keys():
            candidates.extend([t for t in playlists_data[g].get("tracks", []) if t['id'] not in used_ids_list])
    
    if not candidates and len(used_ids_list) > 0:
        print("DEBUG: Bibliothèque épuisée, on autorise des répétitions (sauf pour les sons > 20 min)...")
        long_tracks = set()
        for g in playlists_data.values():
            for t in g.get("tracks", []):
                if t.get('duree', 0) > 1200:
                    long_tracks.add(t['id'])
        
        recent_to_keep = used_ids_list[-30:]
        used_ids_list.clear()
        for t_id in long_tracks: used_ids_list.append(t_id)
        for t_id in recent_to_keep:
            if t_id not in used_ids_list: used_ids_list.append(t_id)
            
        return pick_random_track(genre, used_ids_list)
        
    if candidates:
        return random.choice(candidates)
    return None

print("🔄 Construction de la grille 24h avec remplissage automatique...")

anchors = []
for item in suggested_playlist:
    found = find_track_in_lib(item.get('id'), item.get('titre'))
    if found:
        anchors.append({
            "track": found,
            "start_min": float(item.get('start_minute', 0)),
            "fill_genre": item.get('fill_genre')
        })
        if found['id'] not in used_ids: used_ids.append(found['id'])

anchors.sort(key=lambda x: x['start_min'])

if not anchors:
    print("❌ L'IA n'a renvoyé aucune ancre valide.")
    exit(1)

playlist_finale = []
current_time = 0

def add_track(track, time_min):
    t_copy = track.copy()
    t_copy['start_minute'] = time_min
    playlist_finale.append(t_copy)
    return track.get('duree', 0) / 60.0

for i, anchor in enumerate(anchors):
    if current_time < anchor['start_min']:
        genre_to_use = anchors[i-1]['fill_genre'] if i > 0 else anchor['fill_genre']
        while current_time < anchor['start_min'] - 2:
            next_track = pick_random_track(genre_to_use, used_ids)
            if not next_track: break
            dur = add_track(next_track, current_time)
            if next_track['id'] not in used_ids: used_ids.append(next_track['id'])
            current_time += dur
            
    current_time = max(current_time, anchor['start_min'])
    dur_anchor = add_track(anchor['track'], current_time)
    current_time += dur_anchor

# Remplissage jusqu'à 24h
last_genre = anchors[-1]['fill_genre']
while current_time < end_min - 2:
    next_track = pick_random_track(last_genre, used_ids)
    if not next_track: break
    dur = add_track(next_track, current_time)
    if next_track['id'] not in used_ids: used_ids.append(next_track['id'])
    current_time += dur

# --- 7. SAUVEGARDE FINALE ---
with open('playlist_radio.json', 'w', encoding='utf-8') as f:
    json.dump(playlist_finale, f, indent=4, ensure_ascii=False)

# Mettre à jour l'historique
history.append({
    "date": datetime.now().isoformat(),
    "track_ids": [t['id'] for t in playlist_finale]
})
with open('historique_diffusion.json', 'w', encoding='utf-8') as f:
    json.dump(history[-10:], f, indent=4, ensure_ascii=False) # On garde les 10 derniers jours

print(f"✅ Succès ! Grille 24h de {len(playlist_finale)} titres générée.")
