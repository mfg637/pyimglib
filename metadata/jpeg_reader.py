from fractions import Fraction
import io
import logging
import numbers
from PIL import Image, ExifTags
from collections.abc import Iterable

logger = logging.getLogger(__name__)


def decode_user_comment(raw_bytes: bytes) -> str:
    if len(raw_bytes) < 8:
        return ""

    encoding_header = raw_bytes[:8]
    data = raw_bytes[8:]

    try:
        if encoding_header.startswith(b'ASCII'):
            return data.decode('ascii')
        elif encoding_header.startswith(b'JIS'):
            return data.decode('iso2022_jp')
        elif encoding_header.startswith(b'UNICODE'):
            if len(data) < 2:
                return ""
            if data[0] == 0xFE and data[1] == 0xFF:
                return data[2:].decode('utf-16-be')
            elif data[0] == 0xFF and data[1] == 0xFE:
                return data[2:].decode('utf-16-le')
            else:
                return data.decode('utf-16-be')
        elif encoding_header.startswith(b'UNDEF'):
            return data.decode("utf-16_be")
        else:
            return raw_bytes.decode('latin1', errors='ignore')
    except UnicodeDecodeError:
        logger.warning("Charset decoding error. Discarding.")
        return ""


TAG_TO_ID = {value: key for key, value in ExifTags.TAGS.items()}


def to_sum_and_to_string(value):
    return str(sum(value))


def format_ycbcr_positioning(value):
    positioning_map = {
        1: "Centered",
        2: "Cosited",
    }
    return positioning_map.get(value, "Unknown positioning")


def format_orientation(value):
    ROTATION_VALUES = {
        1: "Regular",
        2: "Mirrored",
        3: "180° rotation",
        4: "180° rotation mirrored",
        5: "270° rotation mirrored",
        6: "270° rotation",
        7: "90° rotation mirrored",
        8: "90° rotation",
    }
    return ROTATION_VALUES.get(value, "Unknown orientation")


def format_metering_mode(value):
    METERING_MODE = {
        1: "Average",
        2: "CounterWeightedAverage",
        3: "Spot",
        4: "MultiSpot",
        5: "Pattern",
        6: "Partial",
        255: "Other"
    }
    return METERING_MODE.get(value, "Unknown")


def format_flash(value):
    FLASH_STATUS = {
        0: "No Flash",
        1: "Fired",
        5: "Fired, Return not detected",
        7: "Fired, Return detected",
        8: "On, Did not fire",
        9: "On, Fired",
        0xd: "On, Return not detected",
        0xf: "On, Return detected",
        0x10: "Off, Did not fire",
        0x14: "Off, Did not fire, Return not detected",
        0x18: "Auto, Did not fire",
        0x19: "Auto, Fired",
        0x1d: "Auto, Fired, Return not detected",
        0x1f: "Auto, Fired, Return detected",
        0x20: "No flash function",
        0x30: "Off, No flash function",
        0x41: "Fired, Red-eye reduction",
        0x45: "Fired, Red-eye reduction, Return not detected",
        0x47: "Fired, Red-eye reduction, Return detected",
        0x49: "On, Red-eye reduction",
        0x4d: "On, Red-eye reduction, Return not detected",
        0x4f: "On, Red-eye reduction, Return detected",
        0x50: "Off, Red-eye reduction",
        0x58: "Auto, Did not fire, Red-eye reduction",
        0x59: "Auto, Fired, Red-eye reduction",
        0x5d: "Auto, Fired, Red-eye reduction, Return not detected",
        0x5f: "Auto, Fired, Red-eye reduction, Return detected"
    }

    def build_status_string(value: int):
        if value & 1:
            status_string = "FlashFired "
        else:
            status_string = "FlashDidNotFire "
        if value & 2:
            status_string += "StrobeReturnLightDetected "
        if value & 4:
            status_string += "StrobeReturnLightNotDetected "
        if value & 8:
            status_string += "CompulsoryFlashMode "
        if value & 16:
            status_string += "AutoMode "
        if value & 32:
            status_string += "NoFlashFunction "
        if value & 64:
            status_string += "RedEyeReductionMode "
        return status_string[:-1]
    return FLASH_STATUS.get(value, build_status_string(value))


def format_exposure_mode(value):
    EXPOSURE_MODES = {
        0: "Auto Exposure",
        1: "Manual Exposure",
        2: "Auto Bracket",
        3: "Program AE (Auto Exposure)"
    }
    return EXPOSURE_MODES.get(value, "Unknown mode")


def format_exposure_program(value):
    EXPOSURE_PROGRAM = {
        1: "Manual",
        2: "Normal program",
        3: "Aperture priority",
        4: "Shutter priority",
        5: "Creative program (biased toward depth of field)",
        6: "Action program (biased toward fast shutter speed)",
        7: (
            "Portrait mode "
            "(for clsoeup photos with the background out of focus)"
        ),
        8: "Landscape mode (for landscapes with the background in focus"
    }
    return EXPOSURE_PROGRAM.get(value, "Not defined")


def check_is_fractions(value):
    return isinstance(value, Fraction) or (
        isinstance(value, Iterable) and
        len(value) == 2 and
        isinstance(value[0], numbers.Rational) and
        isinstance(value[1], numbers.Rational)
    )


# TODO: move to common.utils. Reason: universal function
def fractions_to_float(fraction: Fraction | tuple[int, int]) -> float:
    if isinstance(fraction, Fraction):
        return fraction.numerator / fraction.denominator
    elif isinstance(fraction, Iterable):
        return fraction[0]/fraction[1]
    else:
        return float(fraction)


def to_fractions_or_float(value):
    if check_is_fractions(value):
        if isinstance(value, Fraction):
            return value
        return Fraction(*value)
    elif isinstance(value, (int, float)):
        return value
    else:
        return float(value)


def to_float(value):
    if check_is_fractions(value):
        return fractions_to_float(value)
    elif isinstance(value, (int, float)):
        return value
    else:
        return float(value)


def format_number(value):
    value = to_fractions_or_float(value)
    if isinstance(value, Fraction):
        return str(value)
    else:
        return f"{value:.3f}"


def format_f_number(value):
    if check_is_fractions(value):
        fractions_value = to_fractions_or_float(value)
        if fractions_value.denominator == 1:
            return f"f/{fractions_value}"
        return str(fractions_value)
    else:
        # force convert to float,
        # because IFDRational type does not support formatting
        return f"f/{float(value):.1f}"


def format_exposure_time(value):
    fraction_val = to_fractions_or_float(value)
    if fraction_val != 0 and (1 / fraction_val).is_integer():
        return f"1/{int(1/fraction_val)} s"
    return f"{fraction_val:.3f} s"


def format_focal_length(value):
    float_val = to_float(value)
    return f"{float_val:.1f} mm"


def format_exposure_bias_value(value):
    float_val = to_float(value)
    return f"{float_val:+.1f} EV"


def format_digital_zoom_ratio(value):
    float_val = to_float(value)
    return f"{float_val:.1f}x" if float_val != 0 else "0x"


def empty_string(value):
    return ""


def string_exists(value):
    return "exists"


CUSTOM_PROCESSING = {
    TAG_TO_ID["UserComment"]: decode_user_comment,
    TAG_TO_ID["BitsPerSample"]: to_sum_and_to_string,
    TAG_TO_ID["YCbCrPositioning"]: format_ycbcr_positioning,
    TAG_TO_ID["Orientation"]: format_orientation,
    TAG_TO_ID["MeteringMode"]: format_metering_mode,
    TAG_TO_ID["Flash"]: format_flash,
    TAG_TO_ID["ExposureMode"]: format_exposure_mode,
    TAG_TO_ID["ExposureProgram"]: format_exposure_program,
    TAG_TO_ID["ExposureTime"]: format_exposure_time,
    TAG_TO_ID["FNumber"]: format_f_number,
    TAG_TO_ID["FocalLength"]: format_focal_length,
    TAG_TO_ID["ExposureBiasValue"]: format_exposure_bias_value,
    TAG_TO_ID["DigitalZoomRatio"]: format_digital_zoom_ratio,
    TAG_TO_ID["MakerNote"]: empty_string,
    TAG_TO_ID["ComponentsConfiguration"]: empty_string,
    TAG_TO_ID["ExifOffset"]: empty_string,
    TAG_TO_ID["ExifVersion"]: empty_string,
    TAG_TO_ID["SceneType"]: empty_string,
    TAG_TO_ID["FileSource"]: empty_string,
    TAG_TO_ID["FlashPixVersion"]: empty_string,
    TAG_TO_ID["GPSInfo"]: string_exists,
    TAG_TO_ID["FocalLengthIn35mmFilm"]: lambda v: f"{to_float(v):.0f} mm",
}


def default_processing(value):
    if type(value) is str:
        return value.replace("\x00", "")
    elif check_is_fractions(value):
        return format_number(value)
    elif type(value) is float:
        return f"{value:.3f}"
    else:
        return str(value)


def read_tags(exif_items_view) -> dict[str, str]:
    decoded_exif_data = {}
    for tag_id, value in exif_items_view():
        if tag_id in ExifTags.TAGS:
            tag_name = ExifTags.TAGS[tag_id]
            if tag_id in CUSTOM_PROCESSING:
                decoded_exif_data[tag_name] = CUSTOM_PROCESSING[tag_id](value)
            else:
                decoded_exif_data[tag_name] = default_processing(value)
    return decoded_exif_data


def read_exif_offset(exif: Image.Exif) -> dict[str, str]:
    return read_tags(exif.get_ifd(ExifTags.Base.ExifOffset).items)


def process_and_format_gps_data(exif: Image.Exif) -> str:
    def _convert_dms_to_float_tuple(dms_rational_tuple):
        degrees = to_float(dms_rational_tuple[0])
        minutes = to_float(dms_rational_tuple[1])
        seconds = to_float(dms_rational_tuple[2])
        return degrees, minutes, seconds

    def _format_dms_iso6709(
        dms_values: tuple[float, float, float], ref: str
    ) -> str:
        degrees, minutes, seconds = dms_values

        total_seconds = minutes * 60 + seconds
        rounded_total_seconds = round(total_seconds)

        display_minutes = rounded_total_seconds // 60
        display_seconds = rounded_total_seconds % 60

        # degrees owerflow fix
        display_degrees = int(degrees) + (display_minutes // 60)
        display_minutes = display_minutes % 60

        return (
            f"{display_degrees}°"
            f"{int(display_minutes)}′"
            f"{int(display_seconds)}″"
            f"{ref}"
        )

    try:
        gps_ifd = exif.get_ifd(ExifTags.Base.GPSInfo)
    except KeyError:
        return "parsing error"

    gps_ifd_items = {}

    for tag_id, value in gps_ifd.items():
        if tag_id in ExifTags.GPSTAGS:
            tag_name = ExifTags.GPSTAGS[tag_id]
            gps_ifd_items[tag_name] = value
        else:
            gps_ifd_items[tag_id] = value

    latitude_dms = gps_ifd_items.get("GPSLatitude")
    latitude_ref = gps_ifd_items.get("GPSLatitudeRef")
    longitude_dms = gps_ifd_items.get("GPSLongitude")
    longitude_ref = gps_ifd_items.get("GPSLongitudeRef")

    lat_str = ""
    lon_str = ""

    if latitude_dms and latitude_ref:
        dms_float_tuple = _convert_dms_to_float_tuple(latitude_dms)
        lat_str = _format_dms_iso6709(dms_float_tuple, latitude_ref)

    if longitude_dms and longitude_ref:
        dms_float_tuple = _convert_dms_to_float_tuple(longitude_dms)
        lon_str = _format_dms_iso6709(dms_float_tuple, longitude_ref)

    coords = []
    if lat_str:
        coords.append(lat_str)
    if lon_str:
        coords.append(lon_str)

    return " ".join(coords) if coords else ""


def test_comfyui_metadata(decoded_exif_data: dict[str, str]):
    return (
        "ImageDescription" in decoded_exif_data and
        decoded_exif_data["ImageDescription"].startswith("Workflow:{") and
        "Make" in decoded_exif_data and
        decoded_exif_data["Make"].startswith("Prompt:{")
    )


def comfyui_prompt_extractor(
    decoded_exif_data: dict[str, str]
) -> dict[str, str]:
    result_data = {
        "workflow": decoded_exif_data["ImageDescription"].replace(
            "Workflow:", "", 1
        ),
        "prompt": decoded_exif_data["Make"].replace(
            "Prompt:", "", 1
        ),
        "ImageDescription": "",
        "Make": ""
    }
    return result_data


def read(jpeg_source) -> dict[str, str]:
    if isinstance(jpeg_source, (bytes, bytearray)):
        file_interface = io.BytesIO(jpeg_source)
        img = Image.open(file_interface)
    else:
        img = Image.open(jpeg_source)
    exif = img.getexif()
    if exif is None:
        return {}

    decoded_exif_data: dict[str, str] = read_tags(exif.items)

    decoded_exif_data.update(read_exif_offset(exif))

    if "GPSInfo" in decoded_exif_data:
        decoded_exif_data["GPSInfo"] = process_and_format_gps_data(exif)

    if test_comfyui_metadata(decoded_exif_data):
        decoded_exif_data.update(comfyui_prompt_extractor(decoded_exif_data))

    img.close()

    filtered_exif_data = {}
    for key in decoded_exif_data:
        if decoded_exif_data[key] == "":
            continue
        filtered_exif_data[key] = decoded_exif_data[key]

    return filtered_exif_data
