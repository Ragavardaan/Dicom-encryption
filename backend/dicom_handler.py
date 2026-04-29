"""
DICOM I/O handler.
Reads DICOM pixel arrays, manages metadata, writes stego+encrypted DICOM output.
"""

from flask import json
import pydicom
import numpy as np
import io
import copy
import os
import datetime
from PIL import Image
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid
from pydicom.encaps import encapsulate
import pydicom.uid


def load_dicom(file_bytes: bytes) -> pydicom.Dataset:
    """Load a DICOM dataset from raw bytes."""
    buf = io.BytesIO(file_bytes)
    ds = pydicom.dcmread(buf, force=True)
    return ds


def _image_bytes_to_grayscale_frames(file_bytes: bytes):
    img = Image.open(io.BytesIO(file_bytes))
    img = img.convert('L')
    arr = np.array(img)
    if arr.ndim != 2:
        raise ValueError(f"Expected grayscale 2D image, got shape {arr.shape}")
    return arr[None, :, :].astype(np.uint8)  # (1, H, W)


def _new_secondary_capture_from_frames(frames_u8: np.ndarray) -> pydicom.Dataset:
    if frames_u8.ndim != 3:
        raise ValueError(f"Expected frames (n,H,W), got shape {frames_u8.shape}")

    n_frames, h, w = frames_u8.shape
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    now = datetime.datetime.now()
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")

    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "OT"

    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = int(h)
    ds.Columns = int(w)
    if n_frames > 1:
        ds.NumberOfFrames = str(int(n_frames))

    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0

    ds.PixelData = frames_u8.tobytes()
    ds._pixel_array = None
    return ds


def load_dicom_or_image(file_bytes: bytes, filename: str = "") -> pydicom.Dataset:
    """
    Load either a DICOM file or a standard image (PNG/JPG/JPEG) and return a DICOM dataset.
    For standard images, wraps the pixels in a minimal Secondary Capture DICOM.
    """
    ext = (os.path.splitext(filename)[1] or "").lower()
    if ext in (".png", ".jpg", ".jpeg"):
        frames = _image_bytes_to_grayscale_frames(file_bytes)
        return _new_secondary_capture_from_frames(frames)

    # Default: treat as DICOM
    return load_dicom(file_bytes)


def get_pixel_array(ds: pydicom.Dataset) -> np.ndarray:
    """
    Extract pixel array from DICOM dataset.
    Returns 2D array for single-frame, 3D for multi-frame.
    Converts to uint16 if needed.
    """
    arr = ds.pixel_array
    return arr


def get_all_frames(ds: pydicom.Dataset) -> np.ndarray:
    """
    Return pixel data as (n_frames, H, W). Single-frame becomes (1, H, W).
    """
    arr = get_pixel_array(ds)
    if arr.ndim == 2:
        return arr[None, :, :]
    if arr.ndim == 3:
        return arr
    raise ValueError(f"Unexpected pixel array shape: {arr.shape}")


def set_pixel_array(ds: pydicom.Dataset, arr: np.ndarray) -> pydicom.Dataset:
    """
    Replace the pixel data in the dataset with the given array.
    Handles uint8 / uint16 accordingly.
    """
    ds2 = copy.deepcopy(ds)

    if arr.dtype == np.uint8:
        ds2.BitsAllocated = 8
        ds2.BitsStored = 8
        ds2.HighBit = 7
        ds2.PixelRepresentation = 0
    elif arr.dtype == np.uint16:
        ds2.BitsAllocated = 16
        ds2.BitsStored = 16
        ds2.HighBit = 15
        ds2.PixelRepresentation = 0
    else:
        arr = arr.astype(np.uint16)
        ds2.BitsAllocated = 16
        ds2.BitsStored = 16
        ds2.HighBit = 15
        ds2.PixelRepresentation = 0

    # Remove compression transfer syntax if present
    ds2.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds2.is_implicit_VR = False
    ds2.is_little_endian = True

    # Flatten to bytes
    ds2.PixelData = arr.tobytes()
    ds2._pixel_array = None  # invalidate cache

    return ds2


def set_pixel_array_multiframe(ds: pydicom.Dataset, frames: np.ndarray) -> pydicom.Dataset:
    """
    Replace pixel data for single or multi-frame datasets.
    Accepts frames as (H,W) or (n_frames,H,W).
    """
    if frames.ndim == 2:
        return set_pixel_array(ds, frames)
    if frames.ndim != 3:
        raise ValueError(f"Expected (n,H,W), got shape {frames.shape}")

    ds2 = copy.deepcopy(ds)
    n_frames, h, w = frames.shape

    if frames.dtype == np.uint8:
        ds2.BitsAllocated = 8
        ds2.BitsStored = 8
        ds2.HighBit = 7
        ds2.PixelRepresentation = 0
    elif frames.dtype == np.uint16:
        ds2.BitsAllocated = 16
        ds2.BitsStored = 16
        ds2.HighBit = 15
        ds2.PixelRepresentation = 0
    else:
        frames = frames.astype(np.uint16)
        ds2.BitsAllocated = 16
        ds2.BitsStored = 16
        ds2.HighBit = 15
        ds2.PixelRepresentation = 0

    ds2.SamplesPerPixel = 1
    ds2.PhotometricInterpretation = getattr(ds2, "PhotometricInterpretation", "MONOCHROME2") or "MONOCHROME2"
    ds2.Rows = int(h)
    ds2.Columns = int(w)
    ds2.NumberOfFrames = str(int(n_frames))

    ds2.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds2.is_implicit_VR = False
    ds2.is_little_endian = True

    ds2.PixelData = frames.tobytes()
    ds2._pixel_array = None
    return ds2


def dataset_to_bytes(ds: pydicom.Dataset) -> bytes:
    """Serialise a DICOM dataset to bytes."""
    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)
    buf.seek(0)
    return buf.read()


def get_single_frame_2d(ds: pydicom.Dataset) -> np.ndarray:
    """
    Return a single 2D grayscale frame suitable for PEE embedding.
    For multi-frame DICOM, returns the first frame.
    """
    arr = get_pixel_array(ds)
    if arr.ndim == 3:
        # Multi-frame: take first frame
        arr = arr[0]
    if arr.ndim == 2:
        return arr
    raise ValueError(f"Unexpected pixel array shape: {arr.shape}")


def embed_metadata(ds: pydicom.Dataset, meta: dict) -> pydicom.Dataset:
    """
    Embed steganography metadata into private DICOM tags so decryption knows
    how many bytes to extract. Uses a raw private OB tag for reliability.
    """
    ds2 = copy.deepcopy(ds)
    import json
    meta_json = json.dumps(meta).encode('utf-8')

    # Private creator tag
    ds2.add_new([0x0009, 0x0010], 'LO', 'MedCrypt')
    # Private data tag stored as raw bytes for safer DICOM writing
    ds2.add_new([0x0009, 0x1001], 'OB', meta_json)

    return ds2


def extract_metadata(ds: pydicom.Dataset) -> dict:
    """
    Read steganography metadata from private DICOM tags.
    """
    import json
    try:
        raw = ds[0x0009, 0x1001].value

        if isinstance(raw, str):
            raw = raw.encode('utf-8', errors='ignore')
        elif isinstance(raw, pydicom.multival.MultiValue):
            raw = bytes(raw)

        return json.loads(raw.decode('utf-8', errors='ignore'))
    except (KeyError, Exception) as e:
        raise ValueError(f"Could not read MedCrypt metadata from DICOM: {e}")
