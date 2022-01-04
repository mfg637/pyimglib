import json
import pathlib


def write_srs(srs_data, tags, metadata, output_file):
    for key in tags:
        srs_data['content']['tags'][key] = list(tags[key])
    srs_data['content'].update(metadata)
    file_path = None
    if isinstance(output_file, pathlib.Path):
        file_path = output_file.with_suffix(".srs")
    else:
        file_path = output_file + '.srs'
    srs_file = open(file_path, 'w')
    json.dump(srs_data, srs_file)
    srs_file.close()
    return srs_file
