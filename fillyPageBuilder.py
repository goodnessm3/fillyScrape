#!/usr/bin/python3

from jinja2 import Environment, FileSystemLoader
import os
import sqlite3

# Define paths
thumbnail_folder = "thumbs"
muxed_folder = "muxed"
video_folder = "video"
output_folder = "output"

from urllib.parse import quote
import datetime

conn = sqlite3.connect("downloaded.sqlite3")
cursor = conn.cursor()


def doublequote(astr):

    first = quote(astr, safe="")
    second = first.replace("%", "%25")

    return second


def get_original_file_name(file_name):

    """Given the number under which the image was saved, retrieve the corresponding original name from the db"""

    fnumber, ext = os.path.splitext(file_name)
    cursor.execute('''SELECT orifilename, soundurl FROM files WHERE fnumber = ?''', (fnumber,))
    res = cursor.fetchone()
    if res:
        name, sndurl = res
        return f'''{name}[sound={doublequote(sndurl)}]'''  # WE GOTTA NAME THE FILE RIGHT SPLITEXT


def make_download_link(file_name):

    fnumber, ext = os.path.splitext(file_name)
    oriname = get_original_file_name(file_name)
    return "/named/" + video_folder + "/" + fnumber + ".webm" + f"?filename={oriname}"


# Collect video and thumbnail filenames
videos = []
for filename in sorted(os.listdir(thumbnail_folder)):
    if filename.endswith(".jpg"):
        fnum = os.path.splitext(filename)[0]
        video_name = fnum + ".webm"  # TODO: might be something else
        video_path = muxed_folder + "/" + video_name
        thumbnail_path = thumbnail_folder + "/" + filename

        if os.path.exists(video_path):
            videos.append({"thumbnail": thumbnail_path, "video": video_path, "download_link": make_download_link(filename) + ".webm"})

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("fillysoundposts.html")

# Render the template
updated_time = "Last updated: " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
output_html = template.render(videos=videos, makedate=updated_time)

# Save to output folder
os.makedirs(output_folder, exist_ok=True)
with open(os.path.join(output_folder, "fillysoundposts.html"), "w", encoding="utf-8") as f:
    f.write(output_html)

print("Static site generated in 'output/fillysoundposts.html'")
