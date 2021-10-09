import json
import pathlib


def write_srs(srs_data, tags, metadata, output_file):
    for key in tags:
        srs_data['content']['tags'][key] = list(tags[key])
    srs_data['content'].update(metadata)
    if isinstance(output_file, pathlib.Path):
        srs_file = open(output_file.with_suffix(".srs"), 'w')
    else:
        srs_file = open(output_file + '.srs', 'w')
    json.dump(srs_data, srs_file)
    srs_file.close()
