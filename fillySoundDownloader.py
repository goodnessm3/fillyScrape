#!/usr/bin/python3

import os
import re
from urllib.parse import unquote
import json
from urllib.parse import urlparse
import subprocess
import sqlite3
import shutil
import logging
from fillyCurlCommands import build_curl_command
import pickle
import time
import random

CONTENT_ROOT = '''https://i.4cdn.org/vt/{filename}{extension}'''  # this is where images are served for vt
cwd = os.getcwd()  # probably doesn't even need to be absolute paths if we cd into here to run the script lol
video_dest = os.path.join(cwd, "video")
audio_dest = os.path.join(cwd, "audio")
muxed_dest = os.path.join(cwd, "muxed")
thumbs_dest = os.path.join(cwd, "thumbs")
processed_folder = os.path.join(cwd, "processed")
USER_AGENT = '''"User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:58.0) Gecko/20100101 Firefox/58.0"'''

logging.basicConfig(
    format="%(asctime)s\t%(module)s\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def my_log(s):
    logging.info(s)


conn = sqlite3.connect("downloaded.sqlite3")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS files (hash TEXT PRIMARY KEY, fnumber INTEGER, soundurl TEXT, orifilename TEXT, success TEXT)")

sound_file_getter = re.compile(r'''sound=([^\]]*)''')
sound_name_getter = re.compile(r'''[^\[]*''')


def get_curl_command():

    if not os.path.exists("curl-cmd.pkl"):
        # retire an old command by deleting the pickle
        cm = build_curl_command()
        with open("curl-cmd.pkl", "wb") as f:
            pickle.dump(cm, f)
            # save and reuse the command for later, only retire it if we start getting bl0xxed
    else:
        with open("curl-cmd.pkl", "rb") as f:
            cm = pickle.load(f)

    # send the cookie if there is one. Ask for it and save it if not. We delete the cookie
    # after the end of each downloading session

    if not os.path.exists("cookie.txt"):
        cm.extend(["-c", "cookie.txt"])
    else:
        cm.extend(["-b", "cookie.txt"])

    return cm

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


def just_one_json():
    """for determining if there is only one .json here. If we are down to the last one,
    then we have caught up with the scraping process and we don't want to prematurely
    move it to the archived directory."""

    cnt = 0
    for q in os.listdir():
        if os.path.splitext(q)[1] == ".json":
            cnt += 1
        if cnt > 1:
            return False
    if cnt == 1:
        return True
    else:
        my_log("No JSON archives found in directory, something is wrong!")
        return False


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
    fnumber = post.get("tim", None)  # we'll use this when saving to the server rather than deal with user own filenames
    ex = post.get("ext", None)
    hash = post.get("md5", None)  # we need the hash to determine whether we've already downloaded this soundpost
    # if the file hash and catbox URL match something we already saw, we'll skip it.
    now = post.get("time", None)  # seconds since epoch

    if not all((fname, fnumber, ex)):
        return

    sound_file = sound_file_getter.findall(fname)
    if not sound_file:
        return

    stripped_fname = sound_name_getter.search(fname).group()
    sound_link = unquote(sound_file[0])
    if not sound_link[:8] == "https://":
        sound_link = "https://" + sound_link  # absolutely need this to avoid the redirect from catbox

    return sound_link, CONTENT_ROOT.format(filename=fnumber, extension=ex), stripped_fname, fnumber, ex, hash, now


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

    snd, video, fname, fnumber, ext, hash, now = tup
    fnumbers = str(fnumber)

    parsed_url = urlparse(snd)  # we are getting the file name to save to
    snd_name = os.path.basename(parsed_url.path)

    # TODO: user might upload an escaped URL which still works as a soundpost, like https%3A%2F%2F....

    if not snd_name:
        my_log(f"Problem with the sound file name for: {hash},{snd_name},{fnumber}")
        return False  # something wrong with extracting the sound URL, this happened with a Firefox-mangled name once

    if file_seen(hash, snd_name):
        return False

    vdest = os.path.join(video_dest, fnumbers + ext)
    adest = os.path.join(audio_dest, snd_name)
    mdest = os.path.join(muxed_dest, fnumbers + ext)
    thdest = os.path.join(thumbs_dest, fnumbers + ".webp")  # now that it's my bandwidth I understand why we use webp
    # thumbnail will always be webp because we decide what to save

    result_codes = ""

    my_log(f"starting to download soundpost: {hash},{snd_name},{fnumber}")

    with open("curl.log", "a") as log:

        try:
            with open(adest, "w") as af:
                runls = f'''curl -sS {snd}'''.split(" ")
                # vanilla curl command as we have had no issues with catbox yet
                try:
                    res = subprocess.run(runls, stdout=af, stderr=log, timeout=30)
                    # curl -sS: silent and show errors
                    result_codes += str(res.returncode)
                except subprocess.TimeoutExpired:
                    my_log(f"Failed to download {snd}.")
                    return False
            with open(vdest, "w") as vf:
                runls = get_curl_command() + [video]  # final argument is video link
                res = subprocess.run(runls, stdout=vf, stderr=log, timeout=30)
                result_codes += str(res.returncode)
                # this will usually succeed but we may download a cloudflare challenge, not the file we wanted
        except OSError:
            my_log("Error opening audio file for writing, maybe the file was named wrong. Aborting.")
            return False

    my_log("Downloads completed, muxing together and generating thumbnail.")

    with open("ffmpeg.log", "a") as log:
        vcmd, updated_dest = make_ffmpeg_command(vdest, adest, mdest)
        try:
            res = subprocess.run(vcmd.split(" "), stdout=log, stderr=log, timeout=240)
            # timeout needs to be LONG because for a still image + audio, the Pi needs to do the vp9 transcoding
            # without hardware acceleration. But we don't want to offer a mixture of .mp4 and .webm to users.
            result_codes += str(res.returncode)
            my_log(f"video muxed for {fnumber}")
        except subprocess.TimeoutExpired:
            my_log("ffmpeg was killed after taking too long to mux the files together.")
            result_codes += str(-1)

        thumb_cmd = f'''ffmpeg -v error -i {updated_dest} -vf select=eq(n\\,0),scale=iw/2:ih/2 -frames:v 1 -compression_level 6 -q:v 50 {thdest}'''
        try:
            res = subprocess.run(thumb_cmd.split(" "), stdout=log, stderr=log, timeout=240)
            result_codes += str(res.returncode)
            my_log(f"thumbnail generated for {fnumber}")
        except subprocess.TimeoutExpired:
            my_log("ffmpeg was killed after taking too long to generate a thumbnail.")
            result_codes += str(-1)

    save_file(hash, snd_name, snd, fnumber, fname, result_codes, ext, now)
    # TODO: write to the db regardless of success, otherwise we'll constantly retry broken files
    # not terrible because eventually the .json will be archived and we'll stop checking it
    my_log(f"archived a soundpost: {hash},{snd_name},{fnumber}")

    return True
    
    
def file_seen(file_hash, soundurl):

    """Have we seen this specific combo of image hash and catbox filename before?"""
    
    cursor.execute("SELECT 1 FROM files WHERE hash = ?", (file_hash + "|" + soundurl,))
    return cursor.fetchone() is not None


def sound_heard(catbox):

    """Did we ever encounter this catbox sound URL before? Used to disqualify
    downloads from warosu archive"""

    cursor.execute("SELECT 1 FROM files WHERE soundurl = ?", (catbox,))
    return cursor.fetchone() is not None
    

def save_file(file_hash, snd, soundurl, fnumber, orifilename, success, ext, now):

    """Make a new entry after processing a soundpost, regardless of whether it was successful (we can check failed ones
    later)"""
    
    cursor.execute("INSERT INTO files "
                   "(hash, soundurl, fnumber, orifilename, success, oriext, date) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (file_hash + "|" + snd, soundurl, fnumber, orifilename, success, ext, now))
    conn.commit()
    
    
def save_just_one(fi):

    """now a function to take a thread JSON file, archive the first new soundpost it finds, then return
    we'll run this with a cron job to gently scrape the thread every so often
    once the whole json file is exhausted we'll archive it in the "processed" folder

    Return True if we managed to download a soundpost, False if we went thru the whole
    list and didn't manage it. This is used to batch up downloads, every time we check,
    we download everything that is new."""

    with open(fi, "r") as f:
        js = json.load(f)
        for post in js["posts"]:
            if a := extract_soundpost(post):
                b = dl_soundpost(a)
                if b:
                    return True

    if just_one_json():  # prevent premature archival
        my_log("There is only a single .json file currently so we are not archiving it yet.")
        return False

    _, filename = os.path.split(fi)
    dest = os.path.join(processed_folder, filename)
    shutil.move(fi, dest)  # no sense revisiting the file if we've gone through it
    my_log(f"Looks like we got all soundposts from {fi}, archiving it.")

    
def update():

    success = True
    while success:
        lo = least_recent_op_number()
        success = save_just_one(f"{lo}.json")  # download everything new until nothing left

    if os.path.exists("cookie.txt"):
        os.remove("cookie.txt")  # don't let cloudflare's cookie get stale

    
    
if __name__ == "__main__":

    """We are being run by cron to just download a single sound post from the oldest thread .json we have"""

    time.sleep(random.randint(0, 86400))  # avoid running at a regular time
    # TODO: command line switch to disable random sleep
    update()