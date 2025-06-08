#!/usr/bin/python3

from jinja2 import Environment, FileSystemLoader
import os
import sqlite3
from urllib.parse import quote
import datetime
import logging
from fillyStats import get_stats
import subprocess

def get_git_branch():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except subprocess.CalledProcessError:
        return "unknown"

is_dev = get_git_branch() == "dev"

# Define paths
thumbnail_folder = "thumbs"
muxed_folder = "muxed"
video_folder = "video"
output_folder = "output"

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif"]


logging.basicConfig(
    format="%(asctime)s\t%(module)s\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def my_log(s):
    logging.info(s)


conn = sqlite3.connect("downloaded.sqlite3")
cursor = conn.cursor()


def doublequote(astr):

    first = quote(astr, safe="")
    second = first.replace("%", "%25")

    return second


def get_soundpost_data(fnum):

    """Given the number under which the image was saved, retrieve the corresponding original name from the db"""

    cursor.execute('''SELECT orifilename, soundurl, oriext, date FROM files WHERE fnumber = ?''', (fnum,))
    res = cursor.fetchone()
    if res:
        name, sndurl, oriext, date = res
        return f'''{name}[sound={doublequote(sndurl)}]''', oriext, date


def get_original_name_only(fnum):

    cursor.execute('''SELECT orifilename FROM files WHERE fnumber = ?''', (fnum,))
    res = cursor.fetchone()
    return res[0].lower()


# Collect video and thumbnail filenames
videos = []
thumblist = sorted(os.listdir(thumbnail_folder))
thumblist.reverse()  # newest at top

for filename in thumblist:
    if filename.endswith(".webp"):
        fnum = os.path.splitext(filename)[0]
        oriname, oriext, date = get_soundpost_data(fnum)
        if oriext.lower() in IMAGE_EXTENSIONS:
            newext = ".webm"  # image extension is irrelevant, we made it into a webm
        else:
            newext = oriext  # no change needed
        video_name = fnum + newext  # 05/26 10:57!!
        video_path = muxed_folder + "/" + video_name
        thumbnail_path = thumbnail_folder + "/" + filename
        dl_link = "/named/" + video_folder + "/" + fnum + oriext + f"?filename={oriname} " + oriext

        if os.path.exists(video_path):
            videos.append({"thumbnail": thumbnail_path,
                           "video": video_path,
                           "download_link": dl_link,
                           "oriname": get_original_name_only(fnum),
                           "fnum": fnum})

    #if "1745768408068768" in filename:
        #breakpoint()

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("fillysoundposts.html")

# Render the template
updated_time = "Last updated: " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
output_html = template.render(videos=videos, makedate=updated_time, stats_string=get_stats(), is_dev=is_dev)

# Save to output folder
os.makedirs(output_folder, exist_ok=True)
with open(os.path.join(output_folder, "fillysoundposts.html"), "w", encoding="utf-8") as f:
    f.write(output_html)

my_log("Static site generated in 'output/fillysoundposts.html'")
