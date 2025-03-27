#!/usr/bin/python3

from jinja2 import Environment, FileSystemLoader
import os
import sqlite3
from urllib.parse import quote
import datetime
import logging
from fillyStats import get_stats

# Define paths
thumbnail_folder = "thumbs"
muxed_folder = "muxed"
video_folder = "video"
output_folder = "output"


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
        video_name = fnum + oriext  # TODO: might be something else
        video_path = muxed_folder + "/" + video_name
        thumbnail_path = thumbnail_folder + "/" + filename
        dl_link = "/named/" + video_folder + "/" + fnum + oriext + f"?filename={oriname} " + oriext

        if os.path.exists(video_path):
            videos.append({"thumbnail": thumbnail_path,
                           "video": video_path,
                           "download_link": dl_link,
                           "oriname": get_original_name_only(fnum)})

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("fillysoundposts.html")

# Render the template
updated_time = "Last updated: " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
output_html = template.render(videos=videos, makedate=updated_time, stats_string=get_stats())

# Save to output folder
os.makedirs(output_folder, exist_ok=True)
with open(os.path.join(output_folder, "fillysoundposts.html"), "w", encoding="utf-8") as f:
    f.write(output_html)

my_log("Static site generated in 'output/fillysoundposts.html'")
