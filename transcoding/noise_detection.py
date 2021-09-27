import enum
from PIL import Image, ImageFilter


class NoisyImageEnum(enum.Enum):
    NOISELESS = enum.auto()
    NOISY = enum.auto()


def noise_detection(img:Image.Image) -> NoisyImageEnum:
    img1 = img.filter(
        ImageFilter.Kernel(
            (3, 3),
            (
                0, -1, 0,
                -1, 4, -1,
                0, -1, 0
            ),
            1
        )
    )
    pixels = img.size[0] * img.size[1]
    noise_ratio = 1 - (img1.convert('L').histogram()[0] / pixels)
    print("noise ratio", noise_ratio)
    return NoisyImageEnum.NOISELESS if noise_ratio < 0.2 else NoisyImageEnum.NOISY