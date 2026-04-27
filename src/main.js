import playlist from '../playlist_radio.json';

let player;
let syncInterval;
let currentActiveId = null;

// Initialisation de l'API YouTube
window.onYouTubeIframeAPIReady = function() {
    player = new YT.Player('lecteur-youtube', {
        height: '360',
        width: '640',
        playerVars: {
            'autoplay': 1,
            'controls': 0, 
            'disablekb': 1,
            'rel': 0,
            'modestbranding': 1
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange,
            'onError': onPlayerError
        }
    });
};

function onPlayerReady(event) {
    console.log("Lecteur YouTube prêt.");
    renderPlanning();
}

function onPlayerError(event) {
    console.error("Erreur YouTube:", event.data);
    setTimeout(lancerRadioSynchro, 5000);
}

document.getElementById('btn-rejoindre').addEventListener('click', () => {
    document.getElementById('ecran-accueil').style.display = 'none';
    document.getElementById('lecteur-container').style.display = 'block';
    
    lancerRadioSynchro();
    
    if (syncInterval) clearInterval(syncInterval);
    syncInterval = setInterval(lancerRadioSynchro, 10000);
});

function renderPlanning() {
    const listContainer = document.getElementById('planning-list');
    if (!listContainer) return;
    
    listContainer.innerHTML = '';
    
    playlist.forEach((track, index) => {
        const item = document.createElement('div');
        item.className = 'planning-item';
        item.id = `track-${index}`;
        
        // Formater l'heure (HH:MM)
        const h = Math.floor(track.start_minute / 60);
        const m = Math.floor(track.start_minute % 60);
        const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
        
        item.innerHTML = `
            <div class="item-time">${timeStr}</div>
            <div class="item-title">${track.titre}</div>
        `;
        
        listContainer.appendChild(item);
    });
}

function updatePlanningActive(activeId) {
    if (activeId === currentActiveId) return;
    currentActiveId = activeId;

    // Retirer la classe active de tous les items
    document.querySelectorAll('.planning-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Trouver l'index du morceau actif dans la playlist
    const index = playlist.findIndex(t => t.id === activeId);
    if (index !== -1) {
        const activeItem = document.getElementById(`track-${index}`);
        if (activeItem) {
            activeItem.classList.add('active');
            // Auto-scroll vers l'élément actif
            activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
}

function lancerRadioSynchro() {
    if (!player || typeof player.loadVideoById !== 'function') return;

    const now = new Date();
    const secondsSinceMidnight = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
    
    const currentTrack = playlist.find(track => {
        const start = track.start_minute * 60;
        const end = start + track.duree;
        return secondsSinceMidnight >= start && secondsSinceMidnight < end;
    });

    if (currentTrack) {
        updatePlanningActive(currentTrack.id);
        const startOffset = Math.floor(secondsSinceMidnight - (currentTrack.start_minute * 60));
        
        const videoData = player.getVideoData();
        const currentId = videoData ? videoData.video_id : null;
        const currentTime = player.getCurrentTime();

        if (currentId !== currentTrack.id || Math.abs(currentTime - startOffset) > 5) {
            player.loadVideoById({
                videoId: currentTrack.id,
                startSeconds: startOffset
            });
        }
    } else {
        updatePlanningActive(null);
        if (player.getPlayerState() !== YT.PlayerState.ENDED && player.getPlayerState() !== YT.PlayerState.CUED) {
            player.stopVideo();
        }
    }
}

function onPlayerStateChange(event) {
    if (event.data === YT.PlayerState.ENDED) {
        lancerRadioSynchro();
    }
}