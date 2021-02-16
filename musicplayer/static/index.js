(async function () {
	// element variables
	let songsList = document.getElementById("playlists");
	let playPauseButton = document.getElementById("play-pause");
	let skipButton = document.getElementById("skip");
	let songLink = document.getElementById("song-link");
	let uploadForm = document.getElementById("upload-form");
	let uploadInput = document.getElementById("upload-input");
	let progressAlert = document.getElementById("progress");
	let errorAlert = document.getElementById("error");
	let currSongIndicator = document.getElementById("current-song");
	let songProgress = document.getElementById("song-progress");
	let bodyTag = document.getElementsByTagName("body")[0];
	let audio = document.createElement("audio");

	// misc variables
	let songs = [];
	let currPlaylist = undefined;
	let currSong = undefined;

	// set event handlers
	playPauseButton.addEventListener("click", playPause);
	skipButton.addEventListener("click", nextSong);
	uploadForm.addEventListener("submit", uploadPlaylist);
	audio.addEventListener("timeupdate", updateProgress);
	audio.addEventListener("ended", nextSong);
	window.onkeydown = (event) => {
		if (event.target == bodyTag) {
			if (event.key === " ") {
				playPause();
			} else if (event.key === "ArrowRight") {
				nextSong();
			}
		}
	};

	// fetch playlists
	let resp = await fetch("/api/playlists/list");
	let playlists = (await resp.json()).sort((a, b) => {
		// sort by title
		let title1 = a.title;
		let title2 = b.title;
		if (title1 < title2) {
			return -1;
		} else if (title1 > title2) {
			return 1;
		} else {
			return 0;
		}
	});
	console.log(playlists);

	// create playlist DOM elements
	if (playlists.length == 0) {
		let listItem = document.createElement("li");
		listItem.className = "list-group-item";
		listItem.textContent = "No playlists found";
		songsList.appendChild(listItem);
	} else {
		for (let playlist of playlists) {
			let listItem = document.createElement("li");
			listItem.className = "playlist-item list-group-item list-group-item-action";
			listItem.setAttribute("data-id", playlist.id);
			listItem.textContent = playlist.title;
			listItem.addEventListener("click", selectPlaylist);

			let buttons = document.createElement("div");
			buttons.className = "playlist-buttons btn-group";

			let updateButton = document.createElement("button");
			updateButton.className = "btn";
			updateButton.textContent = "Update";
			updateButton.addEventListener("click", updatePlaylist);

			let linkButton = document.createElement("a");
			linkButton.className = "playlist-link btn";
			linkButton.target = "_blank";
			linkButton.rel = "noopener";
			linkButton.href = playlist.url;
			linkButton.textContent = "Link";
			linkButton.addEventListener("click", (event) => {
				event.stopPropagation();
				event.target.blur();
			});
			/*let linkButton = document.createElement("button");
			linkButton.className = "playlist-link-btn";
			linkButton.textContent = "Link";
			link.appendChild(linkButton);*/

			let deleteButton = document.createElement("button");
			deleteButton.className = "btn";
			deleteButton.textContent = "Delete";
			deleteButton.addEventListener("click", deletePlaylist);

			buttons.append(updateButton, linkButton, deleteButton);
			listItem.appendChild(buttons);
			songsList.appendChild(listItem);
		}
	}

	function selectPlaylist(event) {
		errorAlert.hidden = true;
		event.target.classList.add("list-group-item-dark");
		let playlistId = parseInt(event.target.getAttribute("data-id"), 10);
		currPlaylist = playlists.find((playlist) => playlist.id === playlistId);
		fetchSongs(playlistId).then(nextSong);
	}

	async function fetchSongs(playlistId) {
		songs = await fetch("/api/songs/list/" + playlistId).then((resp) => resp.json());
	}

	function updatePlaylist(event) {
		event.stopPropagation();
		console.log(event.target.parentElement.parentElement);
		let playlistID = parseInt(
			event.target.parentElement.parentElement.getAttribute("data-id"),
			10
		);
		console.log(playlistID);
		progressAlert.textContent = "Updating...";
		progressAlert.hidden = false;
		fetch("/api/playlists/update/" + playlistID, { method: "POST" }).then((resp) => {
			progressAlert.hidden = true;
			if (!resp.ok) {
				resp.json().then((resp) => {
					errorAlert.textContent = resp.error;
					errorAlert.hidden = false;
				});
			}
		});
	}

	function deletePlaylist(event) {
		event.stopPropagation();
		swal({
			title: "Are you sure?",
			icon: "warning",
			buttons: true,
			dangerMode: true,
		}).then((resp) => {
			if (resp) {
				let playlistID = parseInt(
					event.target.parentElement.parentElement.getAttribute("data-id"),
					10
				);

				progressAlert.textContent = "Deleting...";
				progressAlert.hidden = false;
				fetch("/api/playlists/delete/" + playlistID, { method: "POST" }).then((resp) => {
					progressAlert.hidden = true;
					if (!resp.ok) {
						resp.json().then((resp) => {
							errorAlert.textContent = resp.error;
							errorAlert.hidden = false;
						});
					}
				});
			}
		});
	}

	function play() {
		playPauseButton.textContent = "Pause";
		audio.play();
	}

	function pause() {
		playPauseButton.textContent = "Play";
		audio.pause();
	}

	function playPause() {
		errorAlert.hidden = true;
		if (currSong) {
			if (audio.paused) {
				play();
			} else {
				pause();
			}
		} else {
			errorAlert.textContent = "No playlist selected";
			errorAlert.hidden = false;
		}
	}

	function nextSong(event) {
		if (event && event.target) {
			event.target.blur();
		}
		console.log(songs);
		if (songs.length > 0) {
			let song = randomItem(songs);
			while (currSong === song) {
				//avoid playing same song twice in a row
				song = randomItem(songs);
			}
			currSong = song;
			audio.src = `/api/songs/play/${currPlaylist.folder}/${currSong.filename}`;
			songLink.href = currSong.url;
			currSongIndicator.textContent = currSong.title;

			audio.load();
			play();
		} else {
			errorAlert.textContent = "Playlist is empty";
			errorAlert.hidden = false;
		}
	}

	function updateProgress() {
		songProgress.textContent = `${toMMSS(audio.currentTime)} / ${toMMSS(audio.duration)}`;
	}

	function uploadPlaylist(event) {
		event.preventDefault();
		let playlist = uploadInput.value;
		progressAlert.textContent = "Uploading...";
		progressAlert.hidden = false;
		errorAlert.hidden = true;
		fetch("/api/playlists/upload", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify({ playlist }),
		}).then((resp) => {
			progressAlert.hidden = true;
			if (!resp.ok) {
				resp.json().then((resp) => {
					errorAlert.textContent = resp.error;
					errorAlert.hidden = false;
				});
			}
		});
	}

	function randomItem(arr) {
		return arr[Math.floor(Math.random() * arr.length)];
	}
	function toMMSS(seconds) {
		// converts integer seconds to str "MM:SS"
		seconds = Math.floor(seconds);
		let minutes = Math.floor(seconds / 60);
		seconds %= 60;
		return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
	}
})();
