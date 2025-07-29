import io
import logging
import iptcinfo3
from struct import unpack

logger = logging.getLogger(__name__)


def default_handler(value) -> str:
    if value is None:
        return ""
    elif type(value) is bytes:
        return value.decode()
    elif isinstance(value, list):
        return ", ".join(value)
    return str(value)


def collectIIMInfo(fh):
    """
    Taken and modified from iptcinfo3. Used for png chunk metadata extraction.

    Assuming file is seeked to start of IIM data (using above),
    this reads all the data into our object's hashes"""
    # NOTE: file should already be at the start of the first
    # IPTC code: record 2, dataset 0.

    _data = iptcinfo3.IPTCData(
        {
            "supplemental category": [],
            "keywords": [],
            "contact": [],
        }
    )

    while True:
        try:
            header = iptcinfo3.read_exactly(fh, 5)
        except iptcinfo3.EOFException:
            return _data

        (tag, record, dataset, length) = unpack("!BBBH", header)
        # bail if we're past end of IIM record 2 data
        if not (tag == 0x1C and record == 2):
            return _data

        alist = {
            "tag": tag,
            "record": record,
            "dataset": dataset,
            "length": length,
        }
        logger.debug("\t".join("%s: %s" % (k, v) for k, v in alist.items()))
        value = fh.read(length)

        # try to extract first into _listdata (keywords, categories)
        # and, if unsuccessful, into _data. Tags which are not in the
        # current IIM spec (version 4) are currently discarded.
        if dataset in _data and hasattr(_data[dataset], "append"):
            _data[dataset].append(value)
        elif dataset != 0:
            _data[dataset] = value


def prepare_data(info_dict: iptcinfo3.IPTCInfo | iptcinfo3.IPTCData):
    extracted_info = dict()
    for key in info_dict:
        key_str = iptcinfo3.c_datasets.get(key, str(key))
        extracted_info[key_str] = default_handler(info_dict[key])
    result = {}
    for key in extracted_info:
        if extracted_info[key] != "":
            result[key] = extracted_info[key]
    return result


def read_png_chunk(chunk_data: bytes) -> dict[str, str]:
    header_position = chunk_data.index(b"3842494d0404")
    text_hex_sequence = (chunk_data[header_position + 12 * 2 :]).decode()
    file_interface = io.BytesIO(
        bytes.fromhex(text_hex_sequence.replace("\n", ""))
    )
    print("file_interface", file_interface.getvalue())
    info_dict = collectIIMInfo(file_interface)
    return prepare_data(info_dict)


def read(source) -> dict[str, str]:
    if isinstance(source, (bytes, bytearray)):
        file_interface = io.BytesIO(source)
        info_object = iptcinfo3.IPTCInfo(file_interface)
    else:
        info_object = iptcinfo3.IPTCInfo(str(source))
    return prepare_data(info_object)
