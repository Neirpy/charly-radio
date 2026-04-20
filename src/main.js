// On simule ton JSON généré par l'IA
const playlist = [
    { id: "s1At5s0YLSs", duree: 148 }, // Musique 1
    { id: "fJ9rUzIMcZQ", duree: 191 }  // Musique 2
];

let player;
const DATE_ZERO = new Date('2024-01-01T00:00:00Z').getTime(); // Date de référence

// Initialisation de l'API YouTube (appelé automatiquement par le script YouTube)
window.onYouTubeIframeAPIReady = function() {
    player = new YT.Player('lecteur-youtube', {
        height: '360',
        width: '640',
        playerVars: {
            'autoplay': 1,
            'controls': 0, // Cache les contrôles pour faire "Radio"
            'disablekb': 1
        },
        events: {
            'onStateChange': onPlayerStateChange
        }
    });
};

document.getElementById('btn-rejoindre').addEventListener('click', () => {
    document.getElementById('ecran-accueil').style.display = 'none';
    document.getElementById('lecteur-container').style.display = 'block';
    lancerRadioSynchro();
});

function lancerRadioSynchro() {
    // 1. Calculer le temps total de la boucle
    const dureeTotaleBoucle = playlist.reduce((total, track) => total + track.duree, 0);
    
    // 2. Calculer le temps écoulé depuis la DATE_ZERO en secondes
    const maintenant = Date.now();
    const secondesEcoulees = Math.floor((maintenant - DATE_ZERO) / 1000);
    
    // 3. Trouver où on en est dans la boucle actuelle
    let positionDansBoucle = secondesEcoulees % dureeTotaleBoucle;
    
    // 4. Trouver la bonne vidéo et le moment exact
    let tempsCumule = 0;
    for (let track of playlist) {
        if (positionDansBoucle < tempsCumule + track.duree) {
            let startSeconds = positionDansBoucle - tempsCumule;
            
            // Lancer la vidéo au bon moment
            player.loadVideoById({
                videoId: track.id,
                startSeconds: startSeconds
            });
            break;
        }
        tempsCumule += track.duree;
    }
}

// Quand une musique se termine, on recalcule pour lancer la suivante
function onPlayerStateChange(event) {
    if (event.data === YT.PlayerState.ENDED) {
        lancerRadioSynchro();
    }
}