import sys
import os
import json
import hashlib
import yt_dlp
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QListWidget, QLabel, QPushButton, 
                             QMessageBox, QLineEdit, QComboBox, QScrollArea, 
                             QFrame, QListWidgetItem, QGroupBox, QDialog, 
                             QTextEdit, QFormLayout, QSpinBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag, QPainter, QColor, QPen, QFont

# --- CONSTANTES ---
PIXELS_PER_MINUTE = 8  # On augmente l'échelle pour que tout soit plus lisible (1h = 480px)
CANVAS_HEIGHT = 24 * 60 * PIXELS_PER_MINUTE
TIMELINE_WIDTH = 60
SNAP_MARGIN_PIXELS = 15  # Marge d'aimantation (~5 minutes)

# --- HELPER ---
def is_valid_json(s):
    try:
        json.loads(s)
        return True
    except:
        return False

# --- GÉNÉRATEUR DE COULEUR ---
def get_playlist_color(playlist_name):
    if "JINGLE" in playlist_name.upper():
        return "#ffd6a5", "#fd8c04"
    colors = [
        ("#ffadad", "#e07a7a"), ("#fdffb6", "#d4d678"), 
        ("#caffbf", "#8fc985"), ("#9bf6ff", "#63c5ce"), 
        ("#a0c4ff", "#6892d6"), ("#bdb2ff", "#8b80d6"), 
        ("#ffc6ff", "#c98ec9"), ("#e4c1f9", "#b38cc9")
    ]
    hash_val = int(hashlib.md5(playlist_name.encode('utf-8')).hexdigest(), 16)
    return colors[hash_val % len(colors)]

# --- BACKGROUND WORKER YOUTUBE ---
class YoutubeWorker(QThread):
    finished = pyqtSignal(list, str, str)  
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        ydl_opts = {'extract_flat': False, 'quiet': True, 'ignoreerrors': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(self.url, download=False)
                if 'entries' not in result:
                    self.error.emit("Aucune vidéo trouvée.")
                    return
                
                titre_playlist = result.get('title', 'Playlist Sans Nom')
                tracks = []
                for video in result['entries']:
                    if video and 'duration' in video:
                        tracks.append({
                            "id": video['id'],
                            "titre": video['title'],
                            "duree": video['duration'],
                            "playlist": titre_playlist
                        })
                self.finished.emit(tracks, self.url, titre_playlist)
        except Exception as e:
            self.error.emit(str(e))

# --- WORKER IA LOCALE (OLLAMA) ---
class AIWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, model_name, user_context, library_data, mode="full", start_hour=0, duration_hours=24):
        super().__init__()
        self.model_name = model_name
        self.user_context = user_context
        self.library_data = library_data
        self.mode = mode
        self.start_hour = start_hour
        self.duration_hours = duration_hours

    def load_ai_config(self):
        try:
            if os.path.exists("ai_config.json"):
                with open("ai_config.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except: pass
        return {}

    def load_history(self):
        try:
            if os.path.exists("historique_diffusion.json"):
                with open("historique_diffusion.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except: pass
        return []

    def get_day_name(self):
        import datetime
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        return days[datetime.datetime.now().weekday()]

    def run(self):
        import subprocess
        import re
        
        config = self.load_ai_config()
        history = self.load_history()
        day_name = self.get_day_name()
        
        # 15 pistes max, titres courts
        all_tracks = []
        for playlist_name, data in self.library_data.items():
            for track in data.get("tracks", []):
                all_tracks.append({
                    "id": track["id"],
                    "titre": track["titre"][:40]
                })
            tracks_subset = all_tracks[:30] # On peut passer plus de titres (30)
        lib_lines = "\n".join([f"{t['id']}|{t['titre']}" for t in tracks_subset])

        recent_ids = ",".join([
            tid for day in history[-3:] for tid in day.get("track_ids", [])
        ][:10])
        
        start_min_offset = self.start_hour * 60
        end_min = start_min_offset + self.duration_hours * 60
        
        # On demande à l'IA environ 1 morceau directeur par heure ou toutes les 30 min
        n_anchors = max(4, self.duration_hours)
        n_anchors = min(n_anchors, 12)  # Max 12 ancres pour Ollama
        
        day_mood = config.get("weekly_moods", {}).get(day_name, "good vibes")
        ctx = self.user_context[:100]
        
        # Liste des genres (playlists) disponibles
        genres = list(self.library_data.keys())
        genres_str = ", ".join(genres)
        
        prompt = (
            f"You are the Program Director. Mode: Hybrid (AI Anchors + Auto-fill).\n"
            f"Day:{day_name} Mood:{day_mood} UserContext:{ctx}\n"
            f"Available Playlists (Genres): {genres_str}\n"
            f"Music list (id|title):\n{lib_lines}\n"
            f"Avoid IDs: {recent_ids}\n\n"
            f"TASK: Select {n_anchors} 'Anchor Tracks' from the list. Each track marks a vibe shift.\n"
            f"For each anchor, give: id, start_minute (between {start_min_offset} and {end_min}), and 'fill_genre' (the playlist name to use for filling the gap AFTER this track).\n"
            f"JSON FORMAT:\n"
            f'[{{"id":"ID", "start_minute":480, "titre":"Title", "fill_genre":"{genres[0]}"}},...]\n'
            f"JSON output:"
        )
        
        print(f"DEBUG prompt ({len(prompt)} chars)")
        
        response_text = ""
        try:
            result = subprocess.run(
                ["ollama", "run", self.model_name],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            response_text = result.stdout.strip()
            err_text = result.stderr.strip()
            
            print(f"DEBUG stderr: {err_text[:200]}")
            print(f"DEBUG stdout: {repr(response_text[:600])}")
            
            if not response_text:
                self.error.emit(f"Ollama n'a rien retourné.\nStderr: {err_text[:300]}")
                return

            # Extraction du tableau JSON dans la réponse
            match = re.search(r'\[.+\]', response_text, re.DOTALL)
            if match:
                raw_json = match.group(0)
                try:
                    playlist_suggested = json.loads(raw_json)
                except json.JSONDecodeError:
                    # JSON tronqué : on récupère les objets complets
                    objects = re.findall(r'\{[^{}]+\}', raw_json)
                    playlist_suggested = [json.loads(o) for o in objects if is_valid_json(o)]
                    print(f"DEBUG: JSON partiel, récupéré {len(playlist_suggested)} objets")
            else:
                playlist_suggested = json.loads(response_text)
            
            self.finished.emit(playlist_suggested)
            
        except subprocess.TimeoutExpired:
            self.error.emit("Timeout : le modèle a mis trop de temps. Essayez un modèle plus léger.")
        except Exception as e:
            self.error.emit(f"Erreur IA : {str(e)}\n\nRéponse:\n{response_text[:300]}")


# --- FENÊTRE MODALE GÉNÉRATION IA ---
class AIGenerationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration de la Programmation IA")
        self.setMinimumSize(520, 450)
        self.setStyleSheet("""
            QDialog { background-color: #f4f1ea; border: 4px solid #1a1a1a; }
            QLabel { font-weight: bold; color: #1a1a1a; }
            QLineEdit, QTextEdit, QComboBox, QSpinBox { 
                background: white; border: 2px solid #1a1a1a; 
                padding: 8px; border-radius: 5px; 
            }
            QPushButton#GenBtn {
                background-color: #ff48b0; color: white;
                font-weight: bold; font-size: 16px; padding: 12px;
                border: 3px solid #1a1a1a;
            }
        """)

        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.model_input = QLineEdit("gemma4:26b")
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Journée complète (24h)", "Tranche horaire"])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        
        # Heure de début (visible seulement en mode Tranche)
        self.start_hour_spin = QSpinBox()
        self.start_hour_spin.setRange(0, 23)
        self.start_hour_spin.setSuffix("h00")
        import datetime
        self.start_hour_spin.setValue(datetime.datetime.now().hour)
        self.start_hour_spin.setVisible(False)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 8)
        self.duration_spin.setSuffix(" heure(s)")
        self.duration_spin.setValue(2)
        self.duration_spin.setVisible(False)
        
        form.addRow("Modèle Ollama :", self.model_input)
        form.addRow("Mode de rendu :", self.mode_combo)
        form.addRow("Heure de début :", self.start_hour_spin)
        form.addRow("Durée :", self.duration_spin)
        layout.addLayout(form)

        layout.addWidget(QLabel("Décrivez l'ambiance et le contexte :"))
        self.context_input = QTextEdit()
        self.context_input.setPlaceholderText("Ex: Matinée calme, après-midi énergique avec du Groove...")
        layout.addWidget(self.context_input)

        self.btn_generate = QPushButton("Lancer le calcul")
        self.btn_generate.setObjectName("GenBtn")
        self.btn_generate.clicked.connect(self.accept)
        layout.addWidget(self.btn_generate)

    def on_mode_changed(self, index):
        is_slot = (index == 1)
        self.start_hour_spin.setVisible(is_slot)
        self.duration_spin.setVisible(is_slot)

    def get_data(self):
        is_full = self.mode_combo.currentIndex() == 0
        return {
            "model": self.model_input.text(),
            "context": self.context_input.toPlainText(),
            "mode": "full" if is_full else "slot",
            "start_hour": 0 if is_full else self.start_hour_spin.value(),
            "duration_hours": 24 if is_full else self.duration_spin.value()
        }

# --- BLOC CALENDRIER (La Musique) ---
class TimelineBlock(QFrame):
    def __init__(self, track_info, parent=None):
        super().__init__(parent)
        self.track_info = track_info
        
        self.duration_mins = track_info.get('duree', 60) / 60.0
        self.height_px = int(self.duration_mins * PIXELS_PER_MINUTE)
        # On garde un minimum de 22px pour que le bouton de suppression reste cliquable, 
        # mais sans déformer le temps (on gère ça par l'échelle globale)
        if self.height_px < 22: self.height_px = 22
        self.setFixedHeight(self.height_px)
        
        bg_color, border_color = get_playlist_color(track_info.get('playlist', ''))
        
        self.setStyleSheet(f"""
            TimelineBlock {{
                background-color: rgba({int(bg_color[1:3], 16)}, {int(bg_color[3:5], 16)}, {int(bg_color[5:7], 16)}, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.5);
                border-left: 5px solid {border_color};
                border-radius: 6px;
            }}
            TimelineBlock:hover {{
                background-color: {bg_color};
                border: 1px solid {border_color};
            }}
        """)
        
        # Mode d'affichage intelligent selon la place
        if self.height_px < 40:
            # Mode compact : Titre et Heure sur la même ligne
            layout = QHBoxLayout(self)
            layout.setContentsMargins(6, 2, 6, 2)
            self.lbl_time = QLabel()
            self.lbl_time.setStyleSheet("font-size: 10px; font-weight: bold; color: #1c1c1e;")
            
            # Titre tronqué si besoin
            titre_court = track_info['titre']
            if len(titre_court) > 40: titre_court = titre_court[:37] + "..."
            self.lbl_titre = QLabel(titre_court)
            self.lbl_titre.setStyleSheet("font-size: 10px; color: #3a3a3c;")
            
            layout.addWidget(self.lbl_time)
            layout.addWidget(self.lbl_titre, stretch=1)
        else:
            # Mode classique : l'un au dessus de l'autre
            layout = QVBoxLayout(self)
            layout.setContentsMargins(6, 2, 6, 2)
            layout.setSpacing(0)
            self.lbl_time = QLabel()
            self.lbl_time.setStyleSheet("font-size: 10px; font-weight: bold; color: #1c1c1e;")
            self.lbl_titre = QLabel(f"{track_info['titre']}")
            self.lbl_titre.setStyleSheet("font-size: 11px; color: #3a3a3c;")
            self.lbl_titre.setWordWrap(True)
            layout.addWidget(self.lbl_time)
            layout.addWidget(self.lbl_titre)
            layout.addStretch()

        self.btn_del = QPushButton("×", self)
        self.btn_del.setFixedSize(16, 16)
        self.btn_del.setStyleSheet("background: rgba(0,0,0,0.1); color: #333; border-radius: 8px; border: none;")
        self.btn_del.clicked.connect(self.deleteLater)
        
        self.update_time_display()

    def update_time_display(self):
        start_min = self.track_info.get('start_minute', 0)
        end_min = start_min + self.duration_mins
        
        sh, sm = int(start_min // 60), int(start_min % 60)
        eh, em = int(end_min // 60), int(end_min % 60)
        
        self.lbl_time.setText(f"🕒 {sh:02d}:{sm:02d} - {eh:02d}:{em:02d}")

    def resizeEvent(self, event):
        self.btn_del.move(self.width() - 20, 2)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-trackdata", json.dumps(self.track_info).encode('utf-8'))
            drag.setMimeData(mime)
            self.setHidden(True)
            if drag.exec(Qt.DropAction.MoveAction) == Qt.DropAction.IgnoreAction:
                self.setHidden(False)
            else:
                self.deleteLater()

# --- LE CANVAS DE 24H ---
class ScheduleCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setFixedHeight(CANVAS_HEIGHT)
        self.setMinimumWidth(400)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen_line = QPen(QColor(200, 200, 200, 150))
        pen_text = QPen(QColor(100, 100, 100))
        painter.setFont(QFont("-apple-system", 10, QFont.Weight.Bold))
        
        for hour in range(25):
            y = hour * 60 * PIXELS_PER_MINUTE
            painter.setPen(pen_line)
            painter.drawLine(TIMELINE_WIDTH, y, self.width(), y)
            painter.setPen(pen_text)
            painter.drawText(5, y + 4, 50, 20, Qt.AlignmentFlag.AlignRight, f"{hour:02d}:00")

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-trackdata"):
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        data = event.mimeData().data("application/x-trackdata")
        track_info = json.loads(str(data.data(), encoding='utf-8'))
        
        drop_y = event.position().y()
        track_height = max(int((track_info.get('duree', 60) / 60.0) * PIXELS_PER_MINUTE), 30)
        
        # 1. --- LOGIQUE D'AIMANTATION (SNAPPING) AVANCÉE ---
        # On cherche tous les points d'accroche possibles (bords des autres blocs et heures)
        snap_points = []
        for child in self.children():
            if isinstance(child, TimelineBlock) and not child.isHidden():
                snap_points.append(child.y()) # Top
                snap_points.append(child.y() + child.height()) # Bottom
        
        # Ajout des heures piles
        for h in range(25):
            snap_points.append(h * 60 * PIXELS_PER_MINUTE)

        # On trouve le point d'aimantation le plus proche pour le HAUT ou le BAS
        best_y = drop_y
        min_dist = SNAP_MARGIN_PIXELS * 1.5
        
        for p in snap_points:
            # Aimante le haut du bloc au point p
            if abs(drop_y - p) < min_dist:
                best_y = p
                min_dist = abs(drop_y - p)
            # Aimante le bas du bloc au point p (donc le haut est à p - hauteur)
            if abs((drop_y + track_height) - p) < min_dist:
                best_y = p - track_height
                min_dist = abs((drop_y + track_height) - p)

        corrected_y = max(0, best_y)

        # 2. --- PRÉVENTION DES CHEVAUCHEMENTS ---
        def is_colliding(y, height):
            for child in self.children():
                if isinstance(child, TimelineBlock) and not child.isHidden():
                    if not (y + height <= child.y() or y >= child.y() + child.height()):
                        return child
            return None

        # Si ça chevauche, on cherche la place libre la plus proche vers le haut ou le bas
        collision = is_colliding(corrected_y, track_height)
        if collision:
            # On tente de coller juste après la collision
            alt_y_down = collision.y() + collision.height()
            alt_y_up = collision.y() - track_height
            
            # On prend la direction la plus proche du drop initial
            if abs(alt_y_down - drop_y) < abs(alt_y_up - drop_y):
                corrected_y = alt_y_down
            else:
                corrected_y = alt_y_up
            
            # Deuxième vérification (au cas où il y a une autre musique juste après)
            # Pour rester simple, si la deuxième place est prise, on ne fait rien ou on décale encore.
            # Mais "se coller bien" est la priorité.
        
        corrected_y = max(0, corrected_y)

        # 3. --- APPLICATION ---
        track_info['start_minute'] = corrected_y / PIXELS_PER_MINUTE
        block = TimelineBlock(track_info, self)
        block.setGeometry(TIMELINE_WIDTH + 10, int(corrected_y), self.width() - TIMELINE_WIDTH - 20, block.height())
        block.show()
        event.accept()

    def resizeEvent(self, event):
        for child in self.children():
            if isinstance(child, TimelineBlock):
                child.setGeometry(TIMELINE_WIDTH + 10, child.y(), self.width() - TIMELINE_WIDTH - 20, child.height())

# --- APPLICATION PRINCIPALE ---
class RadioPlannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📻 Radio Central - Design Apple")
        self.resize(1300, 900)
        
        self.fichier_bibliotheque = "bibliotheque.json"
        self.playlists_data = self.charger_bibliotheque()
        
        # Styleshoot global mis à jour (Correction Bug Combobox)
        self.setStyleSheet("""
            QMainWindow { background-color: #f2f2f7; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; }
            QFrame#Panel { background-color: rgba(255, 255, 255, 0.7); border-radius: 12px; border: 1px solid #ffffff; }
            QPushButton#ActionBtn { 
                background-color: #007aff; color: white; font-weight: bold; padding: 8px 12px; border-radius: 8px; border: none;
            }
            QPushButton#ActionBtn:hover { background-color: #0056b3; }
            QPushButton#IconBtn { background-color: #e5e5ea; border-radius: 6px; padding: 5px; }
            QPushButton#IconBtn:hover { background-color: #d1d1d6; }
            
            QListWidget { background-color: transparent; border: none; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid rgba(0,0,0,0.05); }
            QListWidget::item:selected { background-color: rgba(0, 122, 255, 0.1); color: #007aff; border-radius: 6px; }
            
            QLineEdit, QComboBox { 
                padding: 8px; 
                border-radius: 6px; 
                border: 1px solid #d1d1d6; 
                background: white; 
                color: #1c1c1e; 
            }
            
            /* Correction du bug de lisibilité de la liste déroulante */
            QComboBox QAbstractItemView {
                background-color: white;
                color: #1c1c1e;
                selection-background-color: #007aff;
                selection-color: white;
                outline: none;
            }

            QComboBox QAbstractItemView::item {
                padding: 8px;
                background-color: white;
                color: #1c1c1e;
            }

            QComboBox QAbstractItemView::item:selected {
                background-color: #007aff;
                color: white;
            }
        """)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ==========================================
        # GAUCHE : BIBLIOTHÈQUE
        # ==========================================
        left_panel = QFrame()
        left_panel.setObjectName("Panel")
        left_panel.setFixedWidth(350)
        lib_layout = QVBoxLayout(left_panel)
        
        lbl_lib = QLabel("Bibliothèque")
        lbl_lib.setStyleSheet("font-size: 22px; font-weight: bold; color: #1c1c1e;")
        lib_layout.addWidget(lbl_lib)

        yt_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Lien playlist YouTube...")
        btn_add = QPushButton("Importer")
        btn_add.setObjectName("ActionBtn")
        btn_add.clicked.connect(self.fetch_playlist)
        yt_layout.addWidget(self.url_input)
        yt_layout.addWidget(btn_add)
        lib_layout.addLayout(yt_layout)
        
        btn_load = QPushButton("📂 Charger la Playlist Actuelle")
        btn_load.clicked.connect(self.charger_playlist_existante)
        btn_load.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 10px; border-radius: 8px; margin-bottom: 10px;")
        lib_layout.addWidget(btn_load)

        # Ligne Combobox + Boutons Actions
        combo_layout = QHBoxLayout()
        self.combo_playlists = QComboBox()
        self.combo_playlists.currentIndexChanged.connect(self.switch_playlist)
        
        btn_refresh = QPushButton("🔄")
        btn_refresh.setObjectName("IconBtn")
        btn_refresh.setFixedSize(32, 32)
        btn_refresh.setToolTip("Actualiser cette playlist")
        btn_refresh.clicked.connect(self.actualiser_playlist_courante)
        
        btn_delete = QPushButton("🗑️")
        btn_delete.setObjectName("IconBtn")
        btn_delete.setFixedSize(32, 32)
        btn_delete.setToolTip("Supprimer cette playlist")
        btn_delete.clicked.connect(self.supprimer_playlist_courante)

        combo_layout.addWidget(self.combo_playlists, stretch=1)
        combo_layout.addWidget(btn_refresh)
        combo_layout.addWidget(btn_delete)
        lib_layout.addLayout(combo_layout)
        
        self.lib_list = QListWidget()
        self.lib_list.setDragEnabled(True)
        self.lib_list.startDrag = self.custom_start_drag
        lib_layout.addWidget(self.lib_list)

        # ==========================================
        # SECTION IA (OLLAMA)
        # ==========================================
        btn_open_ai = QPushButton("🤖 Générer avec l'IA")
        btn_open_ai.setObjectName("ActionBtn")
        btn_open_ai.setStyleSheet("""
            background-color: #ff48b0; color: white; height: 50px; font-size: 18px;
        """)
        btn_open_ai.clicked.connect(self.open_ai_dialog)
        lib_layout.addWidget(btn_open_ai)

        # ==========================================
        # DROITE : CALENDRIER CONTINU
        # ==========================================
        right_panel = QFrame()
        right_panel.setObjectName("Panel")
        prog_layout = QVBoxLayout(right_panel)
        
        header_row = QHBoxLayout()
        lbl_prog = QLabel("Emploi du temps")
        lbl_prog.setStyleSheet("font-size: 22px; font-weight: bold; color: #1c1c1e;")
        header_row.addWidget(lbl_prog)
        header_row.addStretch()
        
        btn_export = QPushButton("💾 Sauvegarder la Grille")
        btn_export.setObjectName("ActionBtn")
        btn_export.clicked.connect(self.generer_json)
        
        btn_clear_grid = QPushButton("🗑️ Effacer la Grille")
        btn_clear_grid.setObjectName("ActionBtn")
        btn_clear_grid.setStyleSheet("background-color: #ff3b30; color: white;")
        btn_clear_grid.clicked.connect(self.clear_canvas)
        
        header_row.addWidget(btn_export)
        header_row.addWidget(btn_clear_grid)
        prog_layout.addLayout(header_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background-color: transparent;")
        
        self.canvas = ScheduleCanvas()
        self.scroll_area.setWidget(self.canvas)
        prog_layout.addWidget(self.scroll_area)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, stretch=1)

        for nom in self.playlists_data.keys():
            self.combo_playlists.addItem(nom)
        if self.playlists_data:
            self.switch_playlist()

    # --- LOGIQUE IA ---
    def open_ai_dialog(self):
        dialog = AIGenerationDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['context'].strip():
                QMessageBox.warning(self, "Erreur", "Veuillez entrer un contexte.")
                return
            
            self.statusBar().showMessage("L'IA réfléchit... (cela peut prendre du temps)")
            
            self.ai_worker = AIWorker(data['model'], data['context'], self.playlists_data, data['mode'],
                                      start_hour=data.get('start_hour', 0),
                                      duration_hours=data.get('duration_hours', 24))
            self.ai_worker.finished.connect(self.on_ai_finished)
            self.ai_worker.error.connect(lambda err: QMessageBox.critical(self, "Erreur IA", err))
            self.ai_worker.start()

    def on_ai_finished(self, suggested_playlist):
        self.statusBar().showMessage("IA Terminée !")
        
        if not suggested_playlist:
            QMessageBox.warning(self, "IA", "L'IA n'a retourné aucun titre.")
            return

        # On demande confirmation avant d'effacer
        repl = QMessageBox.question(self, "Confirmer", "L'IA a généré une structure. Voulez-vous remplacer le planning actuel ?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if repl == QMessageBox.StandardButton.Yes:
            # Calcul de la zone temporelle visée
            start_total = self.ai_worker.start_hour * 60
            duration_total = self.ai_worker.duration_hours * 60
            end_total = start_total + duration_total

            # On ne supprime QUE ce qui est dans la zone temporelle visée
            for child in self.canvas.children():
                if isinstance(child, TimelineBlock):
                    block_start = child.track_info.get('start_minute', 0)
                    if block_start >= start_total and block_start < end_total:
                        child.deleteLater()
            
            # --- Résolution et Tri des ancres ---
            anchors = []
            used_ids = set()
            # On ajoute l'historique récent aux IDs utilisés
            try:
                with open("historique_diffusion.json", "r") as f:
                    hist = json.load(f)
                    for entry in hist[-3:]:
                        used_ids.update(entry.get("track_ids", []))
            except: pass

            for item in suggested_playlist:
                tid = item.get('id')
                time = float(item.get('start_minute', 0))
                genre = item.get('fill_genre')
                found = self.find_track_in_lib(tid, item.get('titre'))
                if found:
                    anchors.append({
                        "track": found,
                        "start_min": time,
                        "fill_genre": genre
                    })
                    used_ids.add(found['id'])
            
            anchors.sort(key=lambda x: x['start_min'])
            
            if not anchors:
                QMessageBox.warning(self, "IA", "Aucun morceau directeur valide n'a été trouvé.")
                return

            # --- Remplissage Hybride ---
            start_total = self.ai_worker.start_hour * 60
            duration_total = self.ai_worker.duration_hours * 60
            end_total = start_total + duration_total
            
            count = 0
            current_time = start_total
            
            def add_block(track, time):
                nonlocal count
                track_data = track.copy()
                track_data['start_minute'] = time
                block = TimelineBlock(track_data, self.canvas)
                y_pos = int(time * PIXELS_PER_MINUTE)
                block.setGeometry(TIMELINE_WIDTH + 10, y_pos, self.canvas.width() - TIMELINE_WIDTH - 20, block.height())
                block.show()
                count += 1
                return track['duree'] / 60.0

            # Remplissage par segments
            for i, anchor in enumerate(anchors):
                # 1. Remplissage AVANT l'ancre si possible (avec le genre de l'ancre précédente ou défaut)
                # On simplifie : on saute jusqu'à l'heure de l'ancre si current_time < anchor_start
                # Mais si on veut remplir, on le fait. Ici, on va d'abord placer l'ancre si on est à son heure
                
                if current_time < anchor['start_min']:
                    # On remplit le vide avant l'ancre
                    # Quel genre ? On prend celui de l'ancre si pas de précédente
                    genre_to_use = anchors[i-1]['fill_genre'] if i > 0 else anchor['fill_genre']
                    
                    while current_time < anchor['start_min'] - 2: # Marge de 2 min
                        next_track = self.pick_random_track(genre_to_use, used_ids)
                        if not next_track: break
                        
                        # Si le morceau dépasse l'ancre, on s'arrête ou on cherche plus court ?
                        # On simplifie : on le met
                        dur = add_block(next_track, current_time)
                        used_ids.add(next_track['id'])
                        current_time += dur
                
                # 2. Placer l'ancre (en s'assurant de ne pas chevaucher si on a trop rempli)
                current_time = max(current_time, anchor['start_min'])
                dur_anchor = add_block(anchor['track'], current_time)
                current_time += dur_anchor

            # 3. Remplissage Final jusqu'à la fin de la durée demandée
            last_genre = anchors[-1]['fill_genre']
            while current_time < end_total - 2:
                next_track = self.pick_random_track(last_genre, used_ids)
                if not next_track: break
                dur = add_block(next_track, current_time)
                used_ids.add(next_track['id'])
                current_time += dur

            QMessageBox.information(self, "IA", f"L'IA a généré une structure complète avec {count} titres.")

    def pick_random_track(self, genre, used_ids):
        import random
        # 1. Chercher dans le genre demandé
        candidates = []
        if genre in self.playlists_data:
            candidates = [t for t in self.playlists_data[genre].get("tracks", []) if t['id'] not in used_ids]
        
        # 2. Fallback sur n'importe quel genre si vide
        if not candidates:
            for g in self.playlists_data.keys():
                candidates.extend([t for t in self.playlists_data[g].get("tracks", []) if t['id'] not in used_ids])
        
        if candidates:
            return random.choice(candidates)
        return None

    def clear_canvas(self):
        repl = QMessageBox.question(self, "Confirmer", "Voulez-vous vraiment effacer TOUT le planning ?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if repl == QMessageBox.StandardButton.Yes:
            for child in self.canvas.children():
                if isinstance(child, TimelineBlock):
                    child.deleteLater()
            self.statusBar().showMessage("Grille effacée.")

    def find_track_in_lib(self, track_id, track_title=None):
        for playlist_name, data in self.playlists_data.items():
            for track in data.get("tracks", []):
                # Match exact par ID
                if track["id"] == track_id:
                    track['playlist'] = playlist_name
                    return track
                # Match par titre si l'IA s'est trompée d'ID mais a donné le bon nom
                if track_title and track_title.lower() in track["titre"].lower():
                    track['playlist'] = playlist_name
                    return track
        return None

    def charger_playlist_existante(self):
        path = "playlist_radio.json"
        if not os.path.exists(path):
            QMessageBox.warning(self, "Erreur", "Le fichier playlist_radio.json n'existe pas.")
            return
        
        # On vide tout proprement
        for child in self.canvas.children():
            if isinstance(child, TimelineBlock):
                child.deleteLater()
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                count = 0
                for track in data:
                    start_min = track.get('start_minute')
                    if start_min is not None:
                        block = TimelineBlock(track, self.canvas)
                        y_pos = int(start_min * PIXELS_PER_MINUTE)
                        block.setGeometry(TIMELINE_WIDTH + 10, y_pos, self.canvas.width() - TIMELINE_WIDTH - 20, block.height())
                        block.show()
                        count += 1
            QMessageBox.information(self, "Succès", f"{count} titres chargés avec succès !")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec du chargement : {str(e)}")

    # --- NOUVELLE FONCTION : SUPPRIMER PLAYLIST ---
    def supprimer_playlist_courante(self):
        name = self.combo_playlists.currentText()
        if not name or name not in self.playlists_data: return
        
        reponse = QMessageBox.question(self, "Confirmer", f"Supprimer la playlist '{name}' de la bibliothèque ?", 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reponse == QMessageBox.StandardButton.Yes:
            del self.playlists_data[name]
            self.sauvegarder_bibliotheque()
            
            # Nettoyer l'interface
            index = self.combo_playlists.findText(name)
            self.combo_playlists.removeItem(index)
            if self.combo_playlists.count() == 0:
                self.lib_list.clear()

    # --- AUTRES FONCTIONS ---
    def actualiser_playlist_courante(self):
        name = self.combo_playlists.currentText()
        if name not in self.playlists_data: return
        url = self.playlists_data[name].get("url")
        if url:
            self.url_input.setText(url)
            self.fetch_playlist()

    def custom_start_drag(self, supported_actions):
        item = self.lib_list.currentItem()
        if not item: return
        track_info = item.data(Qt.ItemDataRole.UserRole)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-trackdata", json.dumps(track_info).encode('utf-8'))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def fetch_playlist(self):
        url = self.url_input.text().strip()
        if not url: return
        self.url_input.setEnabled(False)
        self.worker = YoutubeWorker(url)
        self.worker.finished.connect(self.on_playlist_fetched)
        self.worker.error.connect(lambda err: QMessageBox.critical(self, "Erreur", err))
        self.worker.start()

    def on_playlist_fetched(self, tracks, url, title):
        self.url_input.setEnabled(True)
        self.url_input.clear()
        
        # Retirer l'ancienne version s'il y a une actualisation
        nom_existant = self.combo_playlists.currentText()
        if nom_existant in self.playlists_data and self.playlists_data[nom_existant].get('url') == url:
            del self.playlists_data[nom_existant]
            self.combo_playlists.removeItem(self.combo_playlists.findText(nom_existant))
            
        name = f"{title}"
        self.playlists_data[name] = { "url": url, "tracks": tracks }
        self.sauvegarder_bibliotheque()
        
        self.combo_playlists.addItem(name)
        self.combo_playlists.setCurrentText(name)
        self.switch_playlist()

    def switch_playlist(self):
        name = self.combo_playlists.currentText()
        if name not in self.playlists_data: return
        self.lib_list.clear()
        for track in self.playlists_data[name].get("tracks", []):
            item = QListWidgetItem(f"{track['titre']} [{int(track['duree']//60):02d}:{int(track['duree']%60):02d}]")
            track['playlist'] = name 
            item.setData(Qt.ItemDataRole.UserRole, track)
            self.lib_list.addItem(item)

    def charger_bibliotheque(self):
        if os.path.exists(self.fichier_bibliotheque):
            try:
                with open(self.fichier_bibliotheque, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    def sauvegarder_bibliotheque(self):
        with open(self.fichier_bibliotheque, "w", encoding="utf-8") as f:
            json.dump(self.playlists_data, f, ensure_ascii=False, indent=4)

    def generer_json(self):
        playlist_finale = []
        for child in self.canvas.children():
            if isinstance(child, TimelineBlock):
                track_data = child.track_info.copy()
                start_min = int(track_data.get('start_minute', 0))
                track_data['heure_cible'] = f"{start_min//60:02d}:{start_min%60:02d}"
                playlist_finale.append(track_data)
        
        playlist_finale.sort(key=lambda x: x.get('start_minute', 0))
        
        with open("playlist_radio.json", "w", encoding="utf-8") as f:
            json.dump(playlist_finale, f, indent=4, ensure_ascii=False)
            
        # --- MISE À JOUR DE L'HISTORIQUE ---
        self.update_history(playlist_finale)
        
        QMessageBox.information(self, "Succès", "Planning sauvegardé et historique mis à jour !")

    def update_history(self, playlist):
        import datetime
        path = "historique_diffusion.json"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        ids = [t['id'] for t in playlist]
        
        history = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except: pass
        
        # On ajoute le jour actuel
        history.append({"date": today, "track_ids": ids})
        
        # On ne garde que les 30 derniers jours pour pas que le fichier soit trop lourd
        history = history[-30:]
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = RadioPlannerApp()
    fenetre.show()
    sys.exit(app.exec())