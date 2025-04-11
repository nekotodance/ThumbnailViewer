import os
from PIL import Image, PngImagePlugin
from PIL.ExifTags import TAGS, GPSTAGS
import piexif
import piexif.helper
import pillow_avif

def get_prompt_from_imgfile(img_file):
    img = Image.open(img_file)
    comment = get_prompt_from_Image(img, img_file)
    return comment

def get_exifcomment_from_Image(img, fname):
    comment = None
    try:
        exif_data = img.info.get("exif")
        if exif_data is None:
            return None
        exif_dict = piexif.load(exif_data)
        comment = exif_dict["Exif"].get(piexif.ExifIFD.UserComment)
        # ComfyUIで作成したwebpアニメーション対応（暫定）
        if not comment or comment == "":
            comment = exif_dict["0th"].get(272)
        #もしtupleで返却されればbytes型に変換
        if isinstance(comment, tuple):
            comment = bytes(comment)
        if comment.startswith(b'UNICODE'):
            comment = comment[len(b'UNICODE'):]
        comment = comment.replace(b'\x00', b'')
        comment = comment.decode('utf-8')
    except Exception as e:
        print(f"Error get_exifcomment_from_Image {fname}: {e}")
        return None
    return comment

def get_pngcomment_from_Image(img, fname):
    comment = None
    try:
        if isinstance(img, PngImagePlugin.PngImageFile):
            comment = img.info.get("parameters", "") #1:sd1111 or forge png
            #--------
            #T.B.C.:変換後のファイルはComfyUIで開けないが、一応exifコメントには格納しておく用に対応
            #--------
            if not comment:
                comment = img.info.get("prompt", "") #2:comfyUI png
    except Exception as e:
        print(f"Error get_pngcomment_from_Image {fname}: {e}")
        return None
    return comment

def get_prompt_from_Image(img, fname):
    fn, ext = os.path.splitext(fname)
    if ext.lower() in (".jpg", ".webp", ".avif"):
        comment = get_exifcomment_from_Image(img, fname)
    elif ext.lower() in (".png"):
        comment = get_pngcomment_from_Image(img, fname)
    else:
        print(f"not support image file type : {ext}")
        return None
    return comment
