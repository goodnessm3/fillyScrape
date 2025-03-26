import os
import random


def get_stats():

    total_size = 0

    for f in os.listdir("video"):
        stats = os.stat(os.path.join("video", f))
        total_size += stats.st_size

    megs = (round(total_size / 1E6, 2))  # MB of video downloaded
    total_number = len(os.listdir("thumbs"))  # use no. of thumbs as proxy for no. soundposts archived
    processed_count = len(os.listdir("processed"))  # how many threads did we process completely?
    pyl = random.randint(1,100)

    return f'''- scraping since 2025-03-13<br>- {processed_count} threads scraped<br>- {total_number} soundposts archived ({megs} MB)<br>- {pyl} additional pylons constructed'''
