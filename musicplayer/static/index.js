(async function () {
	let songsList = document.getElementById("songs-list");
	let playButton = document.getElementById("play");
	let pauseButton = document.getElementById("pause");
	let skipButton = document.getElementById("skip");
	let audio = document.createElement("audio");
	let resp = await fetch("/api/playlists/list");
	let playlists = await resp.json();
	let songs = [];
	playButton.addEventListener("click", play);
	pauseButton.addEventListener("click", pause);
	skipButton.addEventListener("click", nextSong);
	for (let playlist of playlists) {
		let listItem = document.createElement("li");
		listItem.setAttribute("data-id", playlist.id);
		listItem.textContent = playlist.title;
		listItem.addEventListener("click", selectPlaylist);
		songsList.appendChild(listItem);
	}
	function selectPlaylist(event) {
		let currPlaylist = parseInt(event.target.getAttribute("data-id"), 10);
		fetchSongs(currPlaylist).then(() => {
			nextSong();
			play();
		});
	}
	async function fetchSongs(currPlaylist) {
		songs = await fetch("/api/songs/list/" + currPlaylist);
	}
	function play() {
		audio.play();
	}
	function pause() {
		audio.pause();
	}
	function nextSong() {}
})();
