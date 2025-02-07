#!/usr/bin/python3

import requests
from bs4 import BeautifulSoup
import json
import os

base_url = r'https://a.4cdn.org/vt/thread/{}.json'


def most_recent_op_number():

    """Look through all the .json files in the cwd and return the highest post number, which will correspond
    to the most recent thread OP post number"""

    highest = 0
    
    for x in os.listdir():
        a, b = os.path.splitext(x)
        if b == ".json":
            postno = int(a)
            if postno > highest:
                highest = postno

    return highest
    
    
def get_thread_json(postno):

    resp = requests.get(base_url.format(postno))
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"Error getting JSON for {postno}")  # will fail if we found a link to a non-OP post


def find_next_thread(js):

    '''Step through the posts in a thread JSON, starting at the end and working backwards, and find the first one that leads to a new thread.
    We assume this is the next thread in the chain'''

    for post in js["posts"][::-1]:  # step through backwards
        content = (post.get("com", None))  #  the HTML of the comment, it's not guaranteed to be there though, might just be a pic
        if content:
            #print(content)
            soup = BeautifulSoup(content, "html.parser")
            lnks = (soup.find_all("a"))  # want to further narrow down to quotelinks, and find one that leads to a new OP
            for l in lnks:
                if l.get("class") == ["quotelink"]:
                    hr = l.get("href")
                    # a quotelink to another post ITT will just look like: #p95094652
                    # but a link to a new OP will look like: /vt/thread/95094830#p95094830
                    if hr.startswith(r"/vt/thread/"):
                        return hr[-8:]  # tiny chance someone might link to irrelevant thread last thing, just ignore that for now
                        # we are just returning the post number assuming the structure is consistent, it should be
    
    print("No link to a new thread found.")


def update():

    hi = most_recent_op_number()  # pick up where we left off
    
    with open(f"{hi}.json", "r") as f:
        old_js = json.load(f)
    
    js = get_thread_json(hi)  # download the thread
    
    if js == old_js:  # the thread hasn't changed since we last checked it, assume it's finished
        print(f"Thread {hi} looks to be complete, finding next thread")
        new_op = find_next_thread(js)
        
        if not new_op:
            return  # the find next thread function will log the error but we'll need to manually fix the process
        else:
            print(f"Found a daughter thread: {new_op}")
            
        new_js = get_thread_json(new_op)  # download the first version of this new thread we found

        if not new_js:
            return
        
        with open(f"{new_op}.json", "w") as f:
            json.dump(new_js, f)  # update the file with the most recent thread json
            print(f"Wrote a .json file for thread OP {new_op}")
            
    else:  # thread is still active
        with open(f"{hi}.json", "w") as f:
            json.dump(js, f)  # update the file with the most recent thread json
            print(f"Thread {hi} seems still active, updated the .json")
            
            
if __name__ == "__main__":
    update()
