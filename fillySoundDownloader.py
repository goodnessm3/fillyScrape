#!/usr/bin/python3

CONTENT_ROOT = '''https://i.4cdn.org/vt/{filename}{extension}'''  # this is where images are served for vt

import os
cwd = os.getcwd()

# probably doesn't even need to be absolute paths if we cd into here to run the script lol

video_dest = os.path.join(cwd, "video")
audio_dest = os.path.join(cwd, "audio")
muxed_dest = os.path.join(cwd, "muxed")
thumbs_dest = os.path.join(cwd, "thumbs")
processed_folder = os.path.join(cwd, "processed")

import re
from urllib.parse import unquote
import json
from fillyLog import my_log
from urllib.parse import urlparse
import subprocess
import sqlite3
import shutil

conn = sqlite3.connect("downloaded.sqlite3")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS files (hash TEXT PRIMARY KEY, fnumber INTEGER, soundurl TEXT, orifilename TEXT, success TEXT)")

sound_file_getter = re.compile(r'''sound=([^\]]*)''')
sound_name_getter = re.compile(r'''[^\[]*''')


def least_recent_op_number():

    """Look through all the .json files in the cwd and return the lowest post number, which will correspond
    to the most recent thread OP post number"""

    lowest = 999999999999
    
    for x in os.listdir():
        a, b = os.path.splitext(x)
        if b == ".json":
            postno = int(a)
            if postno < lowest:
                lowest = postno

    return lowest


def is_soundpost(post):

    fname = post.get("filename", None)
    if not fname:
        return False
    if "[sound=" in fname:
        return True
    return False


def extract_soundpost(post):

    """Given a post from a thread JSON, return the file URL and sound URL if it was a soundpost, else return None."""

    fname = post.get("filename", None)  # store the original name to provide when people re-download
    fnumber = post.get("tim", None)  # we'll use this when saving to the server rather than deal with users' own filenames
    ex = post.get("ext", None)
    hash = post.get("md5", None)  # we need the hash to determine whether we've already downloaded this soundpost
    # if the file hash and catbox URL match something we already saw, we'll skip it.

    if not all((fname, fnumber, ex)):
        return

    sound_file = sound_file_getter.findall(fname)
    if not sound_file:
        return

    stripped_fname = sound_name_getter.search(fname).group()
    sound_link = unquote(sound_file[0])
    if not sound_link[:8] == "https://":
        sound_link = "https://" + sound_link  # absolutely need this to avoid the redirect from catbox

    return sound_link, CONTENT_ROOT.format(filename=fnumber, extension=ex), stripped_fname, fnumber, ex, hash


def make_ffmpeg_command(vdest, adest, mdest):

    """We need a slightly different command depending on whether the sound is accompanied by a video or a still image"""

    _, video_ext = os.path.splitext(vdest)
    video_ext = video_ext.lower()  # .webm, .mp4, or a still image

    if video_ext == ".webm" or video_ext == ".mp4":  # the most common situation
        vcmd = f'''ffmpeg -v error -i {vdest} -i {adest} -c:v copy -c:a libopus -b:a 128k {mdest}'''
    else:  # we got a still image
        mroot, _ = os.path.splitext(mdest)  # we've been passed an image file but we want to write a .webm
        mdest = mroot + ".webm"
        vcmd = f'''ffmpeg -v error -loop 1 -i {vdest} -i {adest} -c:v libvpx-vp9 -b:v 1M -c:a libopus -b:a 128k -shortest -vf format=yuv420p {mdest}'''

    return vcmd, mdest  # in case mdest was changed due to a picture not a video


def dl_soundpost(tup):
    """Expects a tuple from the extract_soundpost function"""

    snd, video, fname, fnumber, ext, hash = tup
    fnumbers = str(fnumber)

    parsed_url = urlparse(snd)  # we are getting the file name to save to
    snd_name = os.path.basename(parsed_url.path)

    if file_seen(hash, snd_name):
        return False

    vdest = os.path.join(video_dest, fnumbers + ext)
    adest = os.path.join(audio_dest, snd_name)
    mdest = os.path.join(muxed_dest, fnumbers + ext)
    thdest = os.path.join(thumbs_dest, fnumbers + ".jpg")

    result_codes = ""

    my_log(f"starting to download soundpost: {hash},{snd_name},{fnumber}")

    with open("curl.log", "a") as log:
        # cm1 = f'''curl {snd} > {adest}'''
        # cm2 = f'''curl {video} > {vdest}'''

        with open(adest, "w") as af:
            res = subprocess.run(f'''curl -sS {snd}'''.split(" "), stdout=af, stderr=log, timeout=30)
            # curl -sS: silent and show errors
            result_codes += str(res.returncode)
        with open(vdest, "w") as vf:
            res = subprocess.run(f'''curl -sS {video}'''.split(" "), stdout=vf, stderr=log, timeout=30)
            result_codes += str(res.returncode)

    with open("ffmpeg.log", "a") as log:
        vcmd, updated_dest = make_ffmpeg_command(vdest, adest, mdest)
        try:
            res = subprocess.run(vcmd.split(" "), stdout=log, stderr=log, timeout=30)
            result_codes += str(res.returncode)
        except subprocess.TimeoutExpired:
            my_log("ffmpeg was killed after taking too long to mux the files together.")
            result_codes += str(-1)

        thumb_cmd = f'''ffmpeg -v error -i {updated_dest} -vf select=eq(n\,0) -frames:v 1 -q:v 2 {thdest}'''
        res = subprocess.run(thumb_cmd.split(" "), stdout=log, stderr=log)
        result_codes += str(res.returncode)

    save_file(hash, snd_name, snd, fnumber, fname, result_codes)
    my_log(f"archived a soundpost: {hash},{snd_name},{fnumber}")

    return True
    
    
def file_seen(file_hash, soundurl):

    """Have we seen this specific combo of image hash and catbox filename before?"""
    
    cursor.execute("SELECT 1 FROM files WHERE hash = ?", (file_hash + "|" + soundurl,))
    return cursor.fetchone() is not None
    

def save_file(file_hash, snd, soundurl, fnumber, orifilename, success):

    """Make a new entry after processing a soundpost, regardless of whether it was successful (we can check failed ones
    later)"""
    
    cursor.execute("INSERT INTO files (hash, soundurl, fnumber, orifilename, success) VALUES (?, ?, ?, ?, ?)", (file_hash + "|" +  snd, soundurl, fnumber, orifilename, success))
    conn.commit()
    
    
def save_just_one(fi):

    """now a function to take a thread JSON file, archive the first new soundpost it finds, then return
    we'll run this with a cron job to gently scrape the thread every so often
    once the whole json file is exhausted we'll archive it in the "processed" folder"""

    with open(fi, "r") as f:
        js = json.load(f)
        for post in js["posts"]:
            if a := extract_soundpost(post):
                b = dl_soundpost(a)
                if b:
                    return

    _, filename = os.path.split(fi)
    dest = os.path.join(processed_folder, filename)
    shutil.move(fi, dest)  # no sense revisiting the file if we've gone through it
    my_log(f"Looks like we got all soundposts from {fi}, archiving it.")
    
    
def update():

    lo = least_recent_op_number()
    save_just_one(f"{lo}.json")
    
    
if __name__ == "__main__":

    """We are being run by cron to just download a single sound post from the oldest thread .json we have"""

    update()