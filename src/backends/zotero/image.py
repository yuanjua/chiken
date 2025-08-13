import base64
import io

from PIL import Image


def resize_base64_image(base64_string, size=128):
    """
    Resize an image encoded as a Base64 string.

    Args:
    base64_string (str): Base64 string of the original image.
    size (int): Size of short side of the image.

    Returns:
    str: Base64 string of the resized image.
    """
    # Decode the Base64 string
    img_data = base64.b64decode(base64_string)
    img = Image.open(io.BytesIO(img_data))

    # Resize the image
    scale = size / min(img.size)
    resized_img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)

    # Save the resized image to a bytes buffer
    buffered = io.BytesIO()
    resized_img.save(buffered, format=img.format)

    # Encode the resized image to Base64
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def resize_image_bytes_to_base64string(bytes: bytes, size=128):
    """
    Resize an image encoded as a bytes object to a Base64 string.

    Args:
    bytes (bytes): Bytes object of the original image.
    size (int): Size of short side of the image.

    """
    img = Image.open(io.BytesIO(bytes))
    scale = size / min(img.size)
    resized_img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)
    buffered = io.BytesIO()
    resized_img.save(buffered, format=img.format)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def resize_image_bytes_to_image(bytes: bytes, size=128):
    img = Image.open(io.BytesIO(bytes))
    scale = size / min(img.size)
    resized_img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)
    return resized_img
