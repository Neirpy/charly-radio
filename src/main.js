import playlist from '../playlist_radio.json';

let player;
let syncInterval;

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
}

function onPlayerError(event) {
    console.error("Erreur YouTube:", event.data);
    // En cas d'erreur de chargement (vidéo bloquée, etc.), on tente de passer à la suite après 5s
    setTimeout(lancerRadioSynchro, 5000);
}

document.getElementById('btn-rejoindre').addEventListener('click', () => {
    document.getElementById('ecran-accueil').style.display = 'none';
    document.getElementById('lecteur-container').style.display = 'block';
    
    lancerRadioSynchro();
    
    // On vérifie toutes les 10 secondes si l'on doit changer de piste (utile après un silence)
    if (syncInterval) clearInterval(syncInterval);
    syncInterval = setInterval(lancerRadioSynchro, 10000);
});

function lancerRadioSynchro() {
    if (!player || typeof player.loadVideoById !== 'function') return;

    const now = new Date();
    // Secondes écoulées depuis minuit
    const secondsSinceMidnight = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
    
    // Trouver le morceau qui correspond au temps actuel
    const currentTrack = playlist.find(track => {
        const start = track.start_minute * 60;
        const end = start + track.duree;
        return secondsSinceMidnight >= start && secondsSinceMidnight < end;
    });

    if (currentTrack) {
        const startOffset = Math.floor(secondsSinceMidnight - (currentTrack.start_minute * 60));
        
        // On ne recharge la vidéo QUE si elle n'est pas déjà en cours de lecture
        // ou si le décalage de temps est trop important (> 5 secondes de désynchro)
        const videoData = player.getVideoData();
        const currentId = videoData ? videoData.video_id : null;
        const currentTime = player.getCurrentTime();

        if (currentId !== currentTrack.id || Math.abs(currentTime - startOffset) > 5) {
            console.log(`Synchronisation : Lecture de ${currentTrack.titre} à ${startOffset}s`);
            player.loadVideoById({
                videoId: currentTrack.id,
                startSeconds: startOffset
            });
        }
    } else {
        // Aucun morceau programmé à cette heure
        if (player.getPlayerState() !== YT.PlayerState.ENDED && player.getPlayerState() !== YT.PlayerState.CUED) {
            console.log("Rien n'est programmé actuellement. Mise en pause.");
            player.stopVideo();
        }
    }
}

// Gestion des transitions
function onPlayerStateChange(event) {
    // Si la vidéo se termine, on relance immédiatement la synchro pour le morceau suivant
    if (event.data === YT.PlayerState.ENDED) {
        lancerRadioSynchro();
    }
}