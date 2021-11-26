import logging

sumos = 0
sumsize = 0
avq = 0
items = 0

logger = logging.getLogger(__name__)


def update_stats(local_stats: list[tuple[int, int, int, int]]):
    global sumos, sumsize, avq, items
    for stat in local_stats:
        sumos += stat[0]
        sumsize += stat[1]
        avq += stat[2]
        items += stat[3]


def log_stats():
    if items:
        logger.info(('total save: {} MBytes ({}%) from {} total MBytes \n'
               'final size = {} MByte\n'
               'average quality={} of {} pictures'
               ).format(
            round((sumsize - sumos) / 1024 / 1024, 2),
            round((1 - sumos / sumsize) * 100, 2),
            round(sumsize / 1024 / 1024, 2),
            round(sumos / 1024 / 1024, 2),
            round(avq / items, 1),
            items
        ))
