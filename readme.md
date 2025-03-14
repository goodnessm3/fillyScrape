Script should be scheduled with a cron job:

```commandline
0 */4 * * * cd /media/1tbgreen/filly && /usr/bin/python3 -u /media/1tbgreen/filly/fillyScrape.py >> /media/1tbgreen/filly/log.txt 2>&1
```

Need to use the "cd" command first so that the script can find the .json files in its own directory. Otherwise the cron job will be looking in the wrong place and the script will fail.
Also need to schedule the soundpost downloading script. This runs more frequently, but only saves one soundpost at a time. It moves thread jsons to the "processed" directory when all soundposts have been downloaded.

```commandline
0 */1 * * * cd /media/1tbgreen/filly && /usr/bin/python3 -u /media/1tbgreen/filly/fillySoundDownloader.py >> /media/1tbgreen/filly/log.txt 2>&1
```

A cronjob is used to build the site every night:

```commandline
0 23 * * * cd /media/1tbgreen/filly && /usr/bin/python3 -u /media/1tbgreen/filly/fillyPageBuilder.py
```

After the page build, the page and all content folders need to be rsynced to a web server to the appropriate locations.

nginx needs configuration to provide the correct filenames in the content header. The filename is provided in the URL as a parameter.

```commandline
location /named/video/ {
    alias /var/www/html/filly/video/;
    add_header Content-Disposition 'attachment; filename=\"$arg_filename\"';
}
```
