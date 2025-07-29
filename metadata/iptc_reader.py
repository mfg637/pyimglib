import io
import logging
import iptcinfo3

logger = logging.getLogger(__name__)


def default_handler(value) -> str:
    if value is None:
        return ""
    elif type(value) is bytes:
        try:
            return value.decode()
        except UnicodeDecodeError:
            return value.decode("latin-1", errors="replace")
    elif isinstance(value, list):
        return ", ".join(value)
    return str(value)


def prepare_data(info_dict: iptcinfo3.IPTCData):
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
    info_object = iptcinfo3.IPTCInfo(io.BytesIO(b""))
    info_object.collectIIMInfo(file_interface)
    return prepare_data(info_object._data)


def read(source) -> dict[str, str]:
    if isinstance(source, (bytes, bytearray)):
        file_interface = io.BytesIO(source)
        info_object = iptcinfo3.IPTCInfo(file_interface)
    else:
        info_object = iptcinfo3.IPTCInfo(str(source))
    return prepare_data(info_object._data)
