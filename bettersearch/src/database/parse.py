# System libraries
import pathlib
import logging
import json
from operator import itemgetter
from collections import defaultdict
from itertools import chain

# Installed libraries
from ffmpeg import FFmpeg
from PIL import Image, ExifTags
import pymupdf4llm
import pymupdf as fitz

# Others
from .constants import parsable_exts
from .util import convert_gps_info_to_lat_lon_alt, get_all_exts

logger = logging.getLogger(__name__)


def parse_file_contents(file_path: str):
    """
    Parse the contents of a file based on its extension.

    Args:
        file_path (str): Path to the file to be parsed.

    Returns:
        str or dict: Parsed content of the file, or None if the file is not supported.
    """
    try:
        ext = pathlib.Path(file_path).suffix
        if pathlib.Path(file_path).suffix not in get_all_exts(parsable_exts):
            return None
        else:
            if ext in parsable_exts.get('mupdf'):
                return _parse_pdf(file_path)
            elif ext in chain(parsable_exts.get('ffmpeg_audio'), parsable_exts.get('ffmpeg_image'), parsable_exts.get('ffmpeg_video')):
                return _parse_ffmpeg(file_path, ext)
            elif ext in parsable_exts.get('text'):
                return _parse_txt(file_path)
            else:
                logger.error(f"The given file is not supported for parsing. Try again: {file_path}")
    except:
        pass

def _parse_txt(file_path):
    """
    Parse the contents of a text file.

    Args:
        file_path (str): Path to the text file.

    Returns:
        str: Contents of the text file.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    return content

def _parse_ffmpeg(file_path, ext):
    """
    Parse the contents of a media file (audio, video, or image) using ffmpeg.

    Args:
        file_path (str): Path to the media file.
        ext (str): File extension of the media file.

    Returns:
        dict or tuple: Parsed metadata of the media file.
    """
    parsed = None
    if ext in (parsable_exts.get('ffmpeg_audio') + parsable_exts.get('ffmpeg_video')):
        ffprobe = FFmpeg(executable="ffprobe").input(f'{file_path}',print_format="json",show_streams=None)
        ffprobe_out = json.loads(ffprobe.execute())
        
        # Audio Metadata only
        if len(ffprobe_out) == 1:
            video_metadata = None
            audio_metadata = itemgetter('title','album','genre','duration')(defaultdict(str,ffprobe_out['streams'][0]))
        else:
            video_metadata = itemgetter('title','frame_rate','director','duration')(defaultdict(str,ffprobe_out['streams'][0]))
            video_metadata.update({'dimensions': 'x'.join([str(ffprobe_out['streams'][0].get('width')),str(ffprobe_out['streams'][0].get('width'))])})
            
            audio_metadata = itemgetter('title','album','genre','duration')(defaultdict(str,ffprobe_out['streams'][0]))
        parsed = (video_metadata, audio_metadata)

    elif ext in parsable_exts.get('ffmpeg_image'):
        # Get Exif tags
        exif_tags = defaultdict(str,{ExifTags.TAGS[k]: v for k, v in Image.open(file_path)._getexif().items() if k in ExifTags.TAGS})
        
        # Add dimension as key
        image_metadata = defaultdict(str)
        image_metadata.update({'dimensions': "x".join([str(exif_tags.get("ImageWidth"),exif_tags.get("ImageLength"))])})
        
        # Add rest of keys
        for orig_key, new_key in zip(["GPSInfo", "Model", "DateTime"], ["gps_coordinates", "camera_model", "date_taken"]):
            image_metadata.update(
                {
                    new_key: convert_gps_info_to_lat_lon_alt(exif_tags.get(orig_key)) if orig_key == "GPSInfo" else str(exif_tags.get(orig_key))
                }
            )
        parsed = image_metadata
    else: 
        logging.error(f"Failed to parse file: {file_path}")
        
    return parsed

def _parse_pdf(file_path):
    """
    Parse the contents of a PDF file using pymupdf4llm.

    Args:
        file_path (str): Path to the PDF file.

    Returns:
        str: Parsed content of the PDF file in markdown format.
    """
    doc = fitz.open(file_path)
    if not doc.needs_pass:
        # Parse documents that are not password protected
        return pymupdf4llm.to_markdown(file_path, margins=0)
    else:
        # TODO: Handle parsing of password protected documents
        pass
    