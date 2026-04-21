import yt_dlp
import json
import os

# --- 1. TA CONFIGURATION ---
URL_PLAYLIST = "https://www.youtube.com/playlist?list=PL_TON_ID_DE_PLAYLIST"
ID_JINGLE = "ID_DE_TA_VIDEO_JINGLE" # La vidéo non répertoriée de ton jingle
DUREE_JINGLE = 15 # Durée exacte de ton jingle en secondes
INSERER_JINGLE_TOUTES_LES = 3 # Un jingle toutes les X musiques

CHEMIN_JSON = "./ma-radio/playlist.json" # Le chemin vers ton projet Vite

print("📻 Récupération de la playlist en cours (ça peut prendre quelques secondes)...")

# --- 2. EXTRACTION YOUTUBE ---
ydl_opts = {
    'extract_flat': False, # Obligatoire pour avoir la durée précise de chaque vidéo
    'quiet': True,
    'ignoreerrors': True   # Ignore les vidéos supprimées ou privées
}

radio_playlist = []

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    result = ydl.extract_info(URL_PLAYLIST, download=False)
    
    if 'entries' in result:
        compteur = 0
        for video in result['entries']:
            if video and 'duration' in video:
                # Ajouter la musique
                radio_playlist.append({
                    "id": video['id'],
                    "duree": video['duration'],
                    "titre": video['title']
                })
                compteur += 1
                
                # Ajouter le jingle toutes les X musiques
                if compteur % INSERER_JINGLE_TOUTES_LES == 0:
                    radio_playlist.append({
                        "id": ID_JINGLE,
                        "duree": DUREE_JINGLE,
                        "titre": "🎙️ JINGLE OFFICIEL"
                    })

# --- 3. SAUVEGARDE DU FICHIER ---
# On écrase l'ancien playlist.json par le nouveau
os.makedirs(os.path.dirname(CHEMIN_JSON), exist_ok=True)
with open(CHEMIN_JSON, 'w', encoding='utf-8') as f:
    json.dump(radio_playlist, f, ensure_ascii=False, indent=4)

print(f"✅ Succès ! La playlist de {len(radio_playlist)} pistes a été générée dans {CHEMIN_JSON}")