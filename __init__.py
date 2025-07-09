import PIL.Image

from . import decoders, transcoding, ACLMMP, config, exceptions, metadata


def calc_image_hash(img: PIL.Image.Image) -> tuple[float, bytes, int, int]:
    import imagehash
    import numpy
    hsv_image = img.convert(mode="HSV")
    aspect_ratio = img.width / img.height
    hue_hash_obj = imagehash.phash(hsv_image.getchannel("H"), hash_size=8)
    saturation_hash_obj = imagehash.phash(hsv_image.getchannel("S"), hash_size=8)
    value_hash_obj = imagehash.phash(hsv_image.getchannel("V"), hash_size=16)
    hue_hash_array = numpy.packbits(hue_hash_obj.hash)
    saturation_hash_array = numpy.packbits(saturation_hash_obj.hash)
    value_hash_array = numpy.packbits(value_hash_obj.hash)
    hue_hash_array.dtype = numpy.int64
    saturation_hash_array.dtype = numpy.int64
    return aspect_ratio, value_hash_array.tobytes(), int(hue_hash_array[0]), int(saturation_hash_array[0])
