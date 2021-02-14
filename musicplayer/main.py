import uuid
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request, g
from flask.helpers import send_file
from pytube import Playlist
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

@app.route("/")
def index():
	return render_template("index.html")

@app.route("/api/playlists/download", methods=["POST"])
def download():
	"""returns {error:bool} """
	conn = get_conn()
	cursor = conn.cursor()
	playlist_url = request.json["playlist"]
	if not playlist_url:
		return jsonify({"error": "No url provided"}), 400
	playlist = Playlist(playlist_url)
	if next(
		cursor.execute("SELECT COUNT(title) FROM playlists WHERE title = ?", (playlist.title, ))
	):
		return jsonify({"error": "Playlist already exists"}), 400
	folder = secure_filename(playlist.title)
	if not folder or Path(folder).exists():
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
		for video in playlist.videos:
			filename = secure_filename(video.title)
			print(f"Downloading {video.title!r} to {filename}")
			if not filename or Path(filename).exists():
				filename = uuid.uuid4().hex
			video.streams.get_audio_only().download(playlist_folder, filename)
			cursor.execute(
				"INSERT INTO songs(playlist_id, title, filename, url) VALUES(?, ?, ?, ?)",
				(playlist_id, video.title, filename, video.watch_url)
			)
	#success
	return jsonify({"error": ""})

@app.route("/api/playlists/list")
def list_playlists():
	"""returns lists of {id:int, title:str, filename:str, url:str} objects"""
	conn = get_conn()
	cursor = conn.cursor()
	with conn:
		res = cursor.execute("""
		SELECT id, title, folder, url FROM playlists""")
		playlists = []
		for row in res:
			playlists.append({"id": row[0], "title": row[1], "filename": row[2], "url": row[3]})
		return jsonify(playlists)

@app.route("/api/songs/list/<int:playlist_id>")
def list_songs(playlist_id):
	"""returns list of {title:str,filename:str,url:str} objects"""
	conn = get_conn()
	cursor = conn.cursor()
	with conn:
		res = cursor.execute(
			"""
			SELECT title, filename, url FROM songs WHERE playlist_id = ?
		""", (playlist_id, )
		)
		songs = []
		for row in res:
			songs.append({"title": row[0], "filename": row[1], "url": row[2]})
		return jsonify(songs)

@app.route("/api/playlists/delete/<int:playlist_id>")
def delete(playlist_id):
	conn = get_conn()
	cursor = conn.cursor()
	with conn:
		cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id, ))
		cursor.execute("DELETE FROM songs where playlist_id = ?", (playlist_id, ))

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
