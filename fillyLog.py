import datetime
import os

def my_log(s):

    now = datetime.datetime.now()
    t = now.strftime("%Y-%m-%d %H:%M:%S")
    print(t + "\t" + os.path.basename(__file__) + "\t" + s)