
sumos = 0
sumsize = 0
avq = 0
items = 0


def print_stats():
    if items:
        print(('total save: {} MBytes ({}%) from {} total MBytes \n'
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
