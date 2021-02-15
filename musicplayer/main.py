import uuid
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from flask import Flask, jsonify, render_template, request, g
from flask.helpers import send_file
from pytube import Playlist, YouTube
from werkzeug.utils import secure_filename

UPLOAD_DIR = Path(__file__).with_name("uploads")
DB_PATH = Path(__file__).with_name("musicplayer.db")

app = Flask(__name__)

def get_conn():
	""" returns sqlite3 connection """
	try:
		return g.db
	except AttributeError:
		conn = sqlite3.connect(DB_PATH)
		g.db = conn
		return conn

@app.teardown_appcontext
def close_conn(exception):  #pylint: disable=unused-argument
	if hasattr(g, "db"):
		g.db.close()

@app.errorhandler(500)
def resource_not_found(e):
	return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
	return render_template("index.html")

@app.route("/api/playlists/upload", methods=["POST"])
def upload():
	"""returns {error:bool} """
	conn = get_conn()
	cursor = conn.cursor()
	playlist_url = request.json["playlist"]
	
	if not playlist_url:
		return jsonify({"error": "No url provided"}), 400
	parse_result = urlparse(playlist_url)
	if "youtube.com" not in parse_result.netloc:
		return jsonify({"error": f"Invalid url provided: {playlist_url!r}"}), 400
	
	playlist = Playlist(playlist_url)
	if next(
		cursor.execute("SELECT COUNT(title) FROM playlists WHERE title = ?", (playlist.title, ))
	)[0] > 0:
		return jsonify({"error": "Playlist already exists"}), 400
	
	folder = secure_filename(playlist.title)
	if not folder or UPLOAD_DIR.joinpath(folder).exists():
		folder = uuid.uuid4().hex
	
	with conn:
		#create playlist
		cursor.execute(
			"INSERT INTO playlists(title, folder, url) VALUES(?, ?, ?)",
			(playlist.title, folder, playlist_url)
		)
		playlist_id = cursor.lastrowid
		playlist_folder = UPLOAD_DIR.joinpath(folder)
		
		#download videos
		download_videos(cursor, playlist.videos, playlist_folder, playlist_id)
	#success
	return jsonify({"error": ""})

def download_videos(cursor, videos, playlist_folder, playlist_id):
	for video in videos:
		filename = secure_filename(video.title)
		print(f"Downloading {video.title!r} to {filename}")
		if not filename or Path(filename).exists():
			filename = uuid.uuid4().hex
		real_filename = Path(
			video.streams.get_audio_only().download(playlist_folder, filename)
		).name  #includes extension
		cursor.execute(
			"INSERT INTO songs(playlist_id, title, filename, url) VALUES(?, ?, ?, ?)",
			(playlist_id, video.title, real_filename, video.watch_url)
		)

@app.route("/api/playlists/list")
def list_playlists():
	"""returns lists of {id:int, title:str, folder:str, url:str} objects"""
	conn = get_conn()
	cursor = conn.cursor()
	with conn:
		res = cursor.execute("SELECT id, title, folder, url FROM playlists")
		playlists = []
		
		for row in res:
			playlists.append({"id": row[0], "title": row[1], "folder": row[2], "url": row[3]})
		return jsonify(playlists)

@app.route("/api/songs/list/<int:playlist_id>")
def list_songs(playlist_id):
	"""returns list of {title:str,filename:str,url:str} objects"""
	conn = get_conn()
	cursor = conn.cursor()
	with conn:
		res = cursor.execute(
			"SELECT title, filename, url FROM songs WHERE playlist_id = ?", (playlist_id, )
		)
		
		songs = []
		for row in res:
			songs.append({"title": row[0], "filename": row[1], "url": row[2]})
		return jsonify(songs)

@app.route("/api/playlists/update/<int:playlist_id>", methods=["POST"])
def update(playlist_id):
	conn = get_conn()
	cursor = conn.cursor()
	with conn:
		try:
			folder, playlist_url = next(
				cursor.execute("SELECT folder, url FROM playlists WHERE id = ?", (playlist_id, ))
			)
		except StopIteration:
			return jsonify({"error": f"Invalid playlist_id: {playlist_id}"}), 404
		playlist_folder = UPLOAD_DIR.joinpath(folder)
		db_videos = list(
			cursor.execute(
			"SELECT id, filename, url FROM songs WHERE playlist_id = ?", (playlist_id, )
			)
		)  # videos already in the database
		db_video_urls = {url for _, _, url in db_videos}
		
		playlist = Playlist(playlist_url)
		#curr_videos = playlist.videos
		curr_video_urls = []  # videos fetched from the playlist
		for url in playlist.video_urls:
			#TODO kind hacky
			parse_res = list(urlparse(url))
			parse_res[1] = parse_res[1].replace("www.", "")
			curr_video_urls.append(urlunparse(parse_res))
		to_delete = [
			(id, filename) for id, filename, url in db_videos if url not in curr_video_urls
		]
		to_add = (YouTube(url) for url in curr_video_urls if url not in db_video_urls)
		
		download_videos(cursor, to_add, playlist_folder, playlist_id)
		
		cursor.executemany("DELETE FROM songs WHERE id = ?", ((id, ) for id, _ in to_delete))
		for _, filename in to_delete:
			print(f"Deleted {filename!r}")
			UPLOAD_DIR.joinpath(playlist_folder, filename).unlink()
	return jsonify({"error": ""})

@app.route("/api/playlists/delete/<int:playlist_id>", methods=["POST"])
def delete(playlist_id):
	conn = get_conn()
	cursor = conn.cursor()
	with conn:
		cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id, ))
		cursor.execute("DELETE FROM songs where playlist_id = ?", (playlist_id, ))
	return jsonify({"error": ""})

@app.route("/api/songs/play/<folder>/<filename>")
def play(folder, filename):
	return send_file(UPLOAD_DIR.joinpath(secure_filename(folder), secure_filename(filename)))

def main():
	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()
	with conn:
		cursor.execute(
			"""CREATE TABLE IF NOT EXISTS playlists(
				id INTEGER PRIMARY KEY,
				title TEXT,
				folder TEXT,
				url TEXT
			)"""
		)
		cursor.execute(
			"""CREATE TABLE IF NOT EXISTS songs(
				id INTEGER PRIMARY KEY,
				playlist_id INTEGER,
				title TEXT,
				filename TEXT,
				url TEXT
			)"""
		)
	conn.close()
	app.run()

if __name__ == "__main__":
	main()
