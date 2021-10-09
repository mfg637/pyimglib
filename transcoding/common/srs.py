import json


def write_srs(srs_data, tags, metadata, output_file):
    for key in tags:
        srs_data['content']['tags'][key] = list(tags[key])
    srs_data['content'].update(metadata)
    srs_file = open(output_file + '.srs', 'w')
    json.dump(srs_data, srs_file)
    srs_file.close()
