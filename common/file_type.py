import re
from .utils import InputSourceFacade

svg_tag = re.compile(r'<svg[^>]*>')


def is_svg(source):
    data = None
    with InputSourceFacade(source) as source_handler:
        file_path = source_handler.get_file_path()
        with open(file_path, 'r') as file:
            try:
                data = file.read()
            except UnicodeDecodeError:
                return False
    return svg_tag.search(data) is not None
