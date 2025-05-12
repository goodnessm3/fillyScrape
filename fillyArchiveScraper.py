import fillySoundDownloader as fs
import re
from urllib.parse import unquote
import os
import requests
from bs4 import BeautifulSoup

thread_root = r'''https://warosu.org/vt/thread/{}'''
sound_file_getter = re.compile(r'''sound=([^\]]*)''')
sound_name_getter = re.compile(r'''[^\[]*''')


def is_flip_thread(soup):

    thespan = soup.find_all("div", {"class":"comment"})[0].find_all("span", {"class": "filetitle"})
    thread_title = thespan[0].text
    if thread_title == r'/flip/':
        return True
    return False


def extract_image_link(post):

    links = post.find_all("a")
    for l in links:
        t = (l.get("href"))
        if t.startswith(r'''https://i.warosu.org/data'''):
            return t


def extract_soundpost_new(post):
    finf = post.find("span", {"class": "fileinfo"})
    if not finf:
        return

    finf = finf.text

    tim = post.find("span", {"class": "posttime"}).get("title")[:-3]  # seconds since epoch milliseconds to seconds
    fname = re.search(r'''([^\n\s]+)\n''', finf).groups()[0]  # pull out a filename from the fileinfo element

    if not r'''[sound=''' in fname:
        return

    sname = sound_file = sound_file_getter.findall(fname)
    sound_link = unquote(sname[0])
    stripped_fname = sound_name_getter.search(fname).group()

    lnk = extract_image_link(post)
    fnumext = lnk.split("/")[-1]
    a, b = os.path.splitext(fnumext)

    if not sound_link[:8] == "https://":
        sound_link = "https://" + sound_link

    for z in post.find_all("a"):
        if z.text == "View same":
            hsh = z.get("href")[10:]  # this is probably their hash
            hsh += "=="  # hashes from the other place seem to have these!???

    return sound_link, lnk, stripped_fname, a, b, hsh, tim


def process_thread(threadno):
    out = []
    thr = requests.get(thread_root.format(threadno))
    soup = BeautifulSoup(thr.text)
    if not is_flip_thread(soup):
        fs.my_log("not a flip thread, bailing")
        return

    replies = soup.find_all("td", {"class": "comment reply"})
    for q in replies:
        if z := extract_soundpost_new(q):
            if fs.sound_heard(z[0]):
                fs.my_log(f"Already seen sound URL {z[0]}, skipping")
                continue
            fs.dl_soundpost(z)
            fs.my_log(f"Downloaded a soundpost: {z[2]}")


def update():

    with open("toget-warosu.txt", "r") as f:
        threads_to_get = set([x.rstrip() for x in f])

    with open("got-warosu.txt", "r") as f:
        threads_got = set([x.rstrip() for x in f])

    to_download = threads_to_get - threads_got

    this = to_download.pop()  # a random thread what we ain't downloaded yet

    process_thread(this)

    with open("got-warosu.txt", "w") as f:
        f.write(this)
        f.write("\n")


if __name__ == "__main__":

    """We are being run by cron to just download a single sound post from the oldest thread .json we have"""

    update()
    fs.my_log(f"Processed a warosu thread")