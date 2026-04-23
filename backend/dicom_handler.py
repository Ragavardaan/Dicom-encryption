"""
DICOM I/O handler.
Reads DICOM pixel arrays, manages metadata, writes stego+encrypted DICOM output.
"""

import pydicom
import numpy as np
import io
import copy
from pydicom.uid import generate_uid
from pydicom.encaps import encapsulate
import pydicom.uid


def load_dicom(file_bytes: bytes) -> pydicom.Dataset:
    """Load a DICOM dataset from raw bytes."""
    buf = io.BytesIO(file_bytes)
    ds = pydicom.dcmread(buf, force=True)
    return ds


def get_pixel_array(ds: pydicom.Dataset) -> np.ndarray:
    """
    Extract pixel array from DICOM dataset.
    Returns 2D array for single-frame, 3D for multi-frame.
    Converts to uint16 if needed.
    """
    arr = ds.pixel_array
    return arr


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
    Embed steganography metadata (payload length, permutation etc.)
    into private DICOM tags so decryption knows how many bytes to extract.
    Uses private block 0x0009.
    """
    ds2 = copy.deepcopy(ds)
    import json
    meta_json = json.dumps(meta).encode('utf-8')

    # Private creator tag
    ds2.add_new([0x0009, 0x0010], 'LO', 'MedCrypt')
    # Private data tag
    ds2.add_new([0x0009, 0x1001], 'OB', meta_json)

    return ds2


def extract_metadata(ds: pydicom.Dataset) -> dict:
    """
    Read steganography metadata from private DICOM tags.
    """
    import json
    try:
        meta_bytes = ds[0x0009, 0x1001].value
        if isinstance(meta_bytes, bytes):
            return json.loads(meta_bytes.decode('utf-8'))
        return json.loads(meta_bytes)
    except (KeyError, Exception) as e:
        raise ValueError(f"Could not read MedCrypt metadata from DICOM: {e}")