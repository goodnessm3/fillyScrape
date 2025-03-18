import datetime
import os
import logging

logging.basicConfig(
    format="%(asctime)s\t%(module)s\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def my_log(s):
    logging.info(s)
