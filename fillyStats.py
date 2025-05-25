import os
import random
from datetime import datetime

started = datetime.fromisoformat("2025-03-13T00:00:00")
today = datetime.now()
howlong = (today-started).days

def get_stats():

    total_size = 0

    for f in os.listdir("video"):
        stats = os.stat(os.path.join("video", f))
        total_size += stats.st_size

    megs = int((round(total_size / 1E6, 0)))  # whole MB of video downloaded
    total_number = len(os.listdir("thumbs"))  # use no. of thumbs as proxy for no. soundposts archived
    processed_count = len(os.listdir("processed")) + 445 # how many threads did we process completely?
    # manual offset of 445 = number of archived threads we went back and got
    pyl = random.randint(1,100)

    return f'''- scraping for {howlong} days<br>- {processed_count} threads scraped<br>- {total_number} soundposts archived ({megs} MB)<br>- {pyl} additional pylons constructed'''
