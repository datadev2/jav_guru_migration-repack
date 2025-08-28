from io import BytesIO
import hashlib
from urllib.parse import urlparse



def calculate_md5(file: BytesIO, chunk_size: int = 65536) -> str:
    pos = file.tell()
    file.seek(0)

    md5_hash = hashlib.md5()
    while chunk := file.read(chunk_size):
        md5_hash.update(chunk)

    file.seek(pos)
    return md5_hash.hexdigest()


def extract_filename(url: str) -> str:
    parsed = urlparse(url)
    filename = parsed.path.split("/")[-1]

    if "?" in filename:
        filename = filename.split("?")[0]

    return filename if filename else "download"
