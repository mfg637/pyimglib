import PIL.Image
from . import jpeg,\
    svg,\
    avif,\
    jpeg_xl,\
    video,\
    srs,\
    YUV4MPEG2


def open_image(file_path, required_size=None):
    if jpeg.is_JPEG(file_path):
        decoder = jpeg.JPEGDecoder(file_path)
        decoded_jpg = decoder.decode(required_size)
        img = PIL.Image.open(decoded_jpg.stdout)
        return img
    elif avif.is_avif(file_path):
        return avif.decode(file_path)
    elif YUV4MPEG2.is_Y4M(file_path):
        return YUV4MPEG2.Y4M_FramesStream(file_path)
    elif jpeg_xl.is_JPEG_XL(file_path):
        return jpeg_xl.decode(file_path)
    elif video.is_video(file_path):
        return video.open_video(file_path)
    elif srs.is_ACLMMP_SRS(file_path):
        return srs.decode(file_path)
    else:
        pil_image = None
        try:
            pil_image = PIL.Image.open(file_path)
        except PIL.Image.UnidentifiedImageError:
            if svg.is_svg(file_path):
                return svg.decode(file_path, required_size)
            else:
                raise ValueError()
        else:
            return pil_image


def get_image_format(file_path) -> str:
    if jpeg.is_JPEG(file_path):
        return "jpeg"
    elif avif.is_avif(file_path):
        return "avif"
    elif YUV4MPEG2.is_Y4M(file_path):
        return "y4m"
    elif jpeg_xl.is_JPEG_XL(file_path):
        return "jpeg xl"
    elif video.is_video(file_path):
        return "video"
    elif srs.is_ACLMMP_SRS(file_path):
        return "SRS sheet"
    else:
        pil_image = None
        try:
            pil_image = PIL.Image.open(file_path)
            return pil_image.format.lower()
        except PIL.Image.UnidentifiedImageError:
            if svg.is_svg(file_path):
                return "svg"
            else:
                raise ValueError()
