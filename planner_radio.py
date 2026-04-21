import sys
import os
import json
import hashlib
import yt_dlp
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QListWidget, QLabel, QPushButton, 
                             QMessageBox, QLineEdit, QComboBox, QScrollArea, 
                             QFrame, QListWidgetItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag, QPainter, QColor, QPen, QFont

# --- CONSTANTES ---
PIXELS_PER_MINUTE = 8  # On augmente l'échelle pour que tout soit plus lisible (1h = 480px)
CANVAS_HEIGHT = 24 * 60 * PIXELS_PER_MINUTE
TIMELINE_WIDTH = 60
SNAP_MARGIN_PIXELS = 15  # Marge d'aimantation (~5 minutes)

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
        header_row.addWidget(btn_export)
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
        QMessageBox.information(self, "Succès", "Planning sauvegardé dans playlist_radio.json !")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = RadioPlannerApp()
    fenetre.show()
    sys.exit(app.exec())