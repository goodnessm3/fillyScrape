import psycopg2
import subprocess
import json
import requests
import sys
import tempfile
import os
import sqlite3
import whisper


def hash_to_transcript(hsh):

    """Split off the sound file name from the internal hash which isn't really a hash. Fetch the sound file
    from the local network, save it in a temp file, send it to the whisper model for transcription
    and return the transcribed text"""

    _, file = hsh.split("|")
    _, ext = os.path.splitext(file)
    data = requests.get(SETTINGS["local_audio"].format(file=file))
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)  # can't use "with" wrapper on Windows, permission issues?
    tmp.write(data.content)
    tmp.close()
    transcript = None

    try:
        transcript = model.transcribe(tmp.name, fp16=True)
    except Exception as e:
        print("Transcription failed!")
        print(e)

    os.remove(tmp.name)  # clean up regardless of success

    if transcript:
        result = transcript["text"].strip()  # sometimes there is leading whitespace
        print(fnumber, ":", result)
        return result


def upload_transcript(hsh, fnumber):

    """Given a hash and fnumber, transcribe the audio of the corresponding file and upload the
    text transcript into the special Postgres table with the searchable transcript index"""

    transcript = hash_to_transcript(hsh)
    cur.execute('''INSERT INTO transcripts (id, hash, transcript) VALUES (%s, %s, %s)''', (fnumber, hsh, transcript))
    conn.commit()


print("Loading settings")
with open("transcribe_settings.json", "r") as f:
    SETTINGS = json.load(f)

print("Downloading sqlite3 db from local Pi host")
sq = requests.get(SETTINGS["sqlite_path"])  # download the whole database of scraping records
# assumes the db is available on the local network as a file that can be downloaded
sqfile = tempfile.NamedTemporaryFile(delete=False)
sqfile.write(sq.content)  # write the downloaded sqlite3 db to a temp file so we can open and read it
sqfile.close()  # avoid permissions errors on Windows when something else tries to open it

print("Getting set of all known image fnumbers")
sqconn = sqlite3.connect(sqfile.name)
sqcur = sqconn.cursor()
sqcur.execute('''SELECT fnumber FROM files WHERE success = '0000';''')
# anything with a bad success code might have caused ffmpeg problems, we'll skip them
every_fnumber = set([x[0] for x in sqcur.fetchall()])
# this is a set of everything we ever saw, to find out what is new compared between the dbs

print("Establishing ssh tunnel")
# first set up an SSH tunnel to communicate with the remote Postgres db
tunnel = subprocess.Popen(SETTINGS["ssh_string"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# the ssh string sets up a tunnel that listens on a local port and forwards it to the remote postgres port
# login is handled via an ssh key described in the ssh string
# make a connection to the db
print("Connecting to remote db")
conn = psycopg2.connect(SETTINGS["conn_string"])  # careful, conn string contains the db password
cur = conn.cursor()

print("Getting set of all transcribed soundpost fnumbers")
cur.execute('''SELECT id FROM transcripts''')
seen = set([x[0] for x in cur.fetchall()])

toget = every_fnumber - seen  # set difference, find out what's new in sqlite and not yet present in postgres
print(f"{len(toget)} new soundposts to transcribe.")

if len(toget) < 1:
    print("Nothing to do, exiting!")
    sys.exit()

print("starting whisper model")
try:
    model = whisper.load_model("turbo", device="cuda")
except Exception as e:
    print("Something went wrong loading whisper")
    print(e)
    toget = []  # just skip the loop below so we can get to the cleanup functions

for fnumber in toget:
    sqcur.execute('''SELECT hash, fnumber FROM files WHERE fnumber = ?''', (fnumber,))
    h, fn = sqcur.fetchone()
    try:
        upload_transcript(h, fn)
    except Exception as e:
        print(f"Error for fnumber: {fnumber}")
        print(e)

# cleanup: close SSH tunnel and delete sqlite3 tempfile
sqconn.close()
conn.close()
os.remove(sqfile.name)
tunnel.terminate()