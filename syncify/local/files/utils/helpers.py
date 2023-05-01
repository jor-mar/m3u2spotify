from __future__ import annotations

from http.client import HTTPResponse
from io import BytesIO
from urllib.error import URLError
from urllib.request import urlopen

from PIL import Image, UnidentifiedImageError
from syncify.local.files.utils.exception import ImageLoadError


def open_image(image_link: str) -> Image.Image:
    """
    Open Image object from a given URL or file path

    :param image_link: URL or file path of the image
    :returns: The loaded image, image bytes
    """

    try:  # open image from link
        if image_link.startswith("http"):
            response: HTTPResponse = urlopen(image_link)
            image = Image.open(response.read())
            response.close()
        else:
            image = Image.open(image_link)

        return image
    except (URLError, FileNotFoundError, UnidentifiedImageError):
        raise ImageLoadError(f"{image_link} | Failed to open image")


def get_image_bytes(image: Image.Image) -> bytes:
    image_bytes_arr = BytesIO()
    image.save(image_bytes_arr, format=image.format)
    return image_bytes_arr.getvalue()
