"""
MedCrypt Flask API
Endpoints:
  POST /api/encrypt  - encrypt patient text + embed in DICOM + encrypt DICOM image
  POST /api/decrypt  - decrypt DICOM, extract text, decrypt text
"""

import os
import json
import base64
import struct
import numpy as np
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

from crypto_engine import (
    GANKeyGenerator,
    derive_chaotic_params,
    encrypt_text,
    decrypt_text,
    pee_embed,
    pee_extract,
    encrypt_dicom_pixels,
    decrypt_dicom_pixels,
)
from dicom_handler import (
    load_dicom,
    get_pixel_array,
    get_single_frame_2d,
    set_pixel_array,
    dataset_to_bytes,
    embed_metadata,
    extract_metadata,
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ─── Helpers ──────────────────────────────────────────────────────────────────

def encode_key(key_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(key_bytes).decode('ascii')


def decode_key(key_str: str) -> bytes:
    return base64.urlsafe_b64decode(key_str.encode('ascii'))


def pack_payload(ciphertext: bytes, perm: list, pad_len: int) -> bytes:
    """
    Pack encrypted text + its permutation + pad_len into a single byte blob
    for embedding into the DICOM image via PEE.
    Format:
      [4 bytes: len(ciphertext)]
      [4 bytes: pad_len]
      [4 bytes: len(perm)]
      [ciphertext]
      [perm as int32 array]
    """
    perm_arr = np.array(perm, dtype=np.int32)
    perm_bytes = perm_arr.tobytes()
    header = struct.pack('>III', len(ciphertext), pad_len, len(perm))
    return header + ciphertext + perm_bytes


def unpack_payload(payload: bytes) -> tuple:
    """Reverse of pack_payload."""
    ct_len, pad_len, perm_len = struct.unpack('>III', payload[:12])
    ciphertext = payload[12: 12 + ct_len]
    perm_bytes = payload[12 + ct_len: 12 + ct_len + perm_len * 4]
    perm = np.frombuffer(perm_bytes, dtype=np.int32).tolist()
    return ciphertext, perm, pad_len


# ─── Encrypt Endpoint ─────────────────────────────────────────────────────────

@app.route('/api/encrypt', methods=['POST'])
def encrypt():
    try:
        # ── Parse form data ──────────────────────────────────────────────
        patient_name    = request.form.get('patient_name', '').strip()
        patient_id      = request.form.get('patient_id', '').strip()
        patient_age     = request.form.get('patient_age', '').strip()
        diagnosis       = request.form.get('diagnosis', '').strip()
        notes           = request.form.get('notes', '').strip()

        if 'dicom_file' not in request.files:
            return jsonify({'error': 'No DICOM file uploaded'}), 400

        dicom_file = request.files['dicom_file']
        dicom_bytes = dicom_file.read()

        # Compose patient record
        patient_text = (
            f"PATIENT NAME: {patient_name}\n"
            f"PATIENT ID: {patient_id}\n"
            f"AGE: {patient_age}\n"
            f"DIAGNOSIS: {diagnosis}\n"
            f"CLINICAL NOTES: {notes}"
        )

        # ── Step 1: GAN Key Generation ───────────────────────────────────
        gan_gen = GANKeyGenerator()
        text_key_bytes  = gan_gen.generate_key(256)
        image_key_bytes = gan_gen.generate_key(256)

        text_key_b64  = encode_key(text_key_bytes)
        image_key_b64 = encode_key(image_key_bytes)

        # ── Step 2: Encrypt patient text (Confusion + Diffusion) ─────────
        enc_result = encrypt_text(patient_text, text_key_bytes)
        ciphertext = enc_result['ciphertext']
        perm       = enc_result['perm']
        pad_len    = enc_result['pad_len']
        sbox       = enc_result['sbox']

        # Hex preview of encrypted text
        encrypted_text_hex = ciphertext.hex().upper()

        # ── Step 3: Load DICOM ───────────────────────────────────────────
        ds = load_dicom(dicom_bytes)
        pixel_arr = get_single_frame_2d(ds)

        # Normalise to uint8 for PEE (PEE works on 8-bit)
        orig_dtype = pixel_arr.dtype
        vmin_orig = float(pixel_arr.min())
        vmax_orig = float(pixel_arr.max())
        if vmax_orig == vmin_orig:
            pixel_8bit = np.zeros_like(pixel_arr, dtype=np.uint8)
        else:
            pixel_8bit = (
                (pixel_arr.astype(np.float64) - vmin_orig) /
                (vmax_orig - vmin_orig) * 255
            ).astype(np.uint8)

        # ── Step 4: Embed encrypted text into image via PEE ─────────────
        payload_blob = pack_payload(ciphertext, perm, pad_len)
        stego_pixels, bits_used, _ = pee_embed(pixel_8bit, payload_blob)

        # ── Step 5: Encrypt the stego image pixels via PEE+Chaotic XOR ──
        enc_pixels, img_perm, enc_vmin, enc_vmax = encrypt_dicom_pixels(
            stego_pixels, image_key_bytes
        )

        # ── Step 6: Write back to DICOM ──────────────────────────────────
        meta = {
            'payload_len':   len(payload_blob),
            'img_perm':      img_perm.tolist(),
            'enc_vmin':      enc_vmin,
            'enc_vmax':      enc_vmax,
            'orig_dtype':    str(orig_dtype),
            'vmin_orig':     vmin_orig,
            'vmax_orig':     vmax_orig,
            'version':       '1.0',
        }

        ds_stego = set_pixel_array(ds, enc_pixels)
        ds_final = embed_metadata(ds_stego, meta)
        output_bytes = dataset_to_bytes(ds_final)

        output_b64 = base64.b64encode(output_bytes).decode('ascii')

        return jsonify({
            'success': True,
            'encrypted_text_hex': encrypted_text_hex[:256] + ('...' if len(encrypted_text_hex) > 256 else ''),
            'text_key':   text_key_b64,
            'image_key':  image_key_b64,
            'dicom_b64':  output_b64,
            'bits_embedded': bits_used,
            'image_shape': list(pixel_arr.shape),
            'sbox_preview': sbox[:16],
            'chaotic_params': {
                k: {kk: round(vv, 6) for kk, vv in v.items()}
                for k, v in derive_chaotic_params(text_key_bytes).items()
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ─── Decrypt Endpoint ─────────────────────────────────────────────────────────

@app.route('/api/decrypt', methods=['POST'])
def decrypt():
    try:
        text_key_b64  = request.form.get('text_key', '').strip()
        image_key_b64 = request.form.get('image_key', '').strip()

        if not text_key_b64 or not image_key_b64:
            return jsonify({'error': 'Both text_key and image_key are required'}), 400

        if 'dicom_file' not in request.files:
            return jsonify({'error': 'No encrypted DICOM file uploaded'}), 400

        dicom_file = request.files['dicom_file']
        dicom_bytes = dicom_file.read()

        text_key_bytes  = decode_key(text_key_b64)
        image_key_bytes = decode_key(image_key_b64)

        # ── Load DICOM and metadata ──────────────────────────────────────
        ds = load_dicom(dicom_bytes)
        meta = extract_metadata(ds)

        payload_len  = meta['payload_len']
        img_perm     = np.array(meta['img_perm'], dtype=np.int64)
        enc_vmin     = meta['enc_vmin']
        enc_vmax     = meta['enc_vmax']
        orig_dtype   = np.dtype(meta['orig_dtype'])
        vmin_orig    = meta['vmin_orig']
        vmax_orig    = meta['vmax_orig']

        # ── Step 1: Get encrypted pixel array ───────────────────────────
        enc_pixels = get_single_frame_2d(ds)
        # Ensure uint8
        if enc_pixels.dtype != np.uint8:
            enc_pixels = enc_pixels.astype(np.uint8)

        # ── Step 2: Decrypt image pixels ────────────────────────────────
        stego_pixels = decrypt_dicom_pixels(
            enc_pixels, image_key_bytes,
            img_perm, enc_vmin, enc_vmax, np.uint8
        )

        # ── Step 3: PEE Extract payload ──────────────────────────────────
        payload_blob, restored_pixels = pee_extract(stego_pixels, payload_len)

        # ── Step 4: Unpack payload ───────────────────────────────────────
        ciphertext, perm, pad_len = unpack_payload(payload_blob)

        # ── Step 5: Decrypt patient text ─────────────────────────────────
        plaintext = decrypt_text(ciphertext, text_key_bytes, perm, pad_len)

        # ── Step 6: Restore original DICOM pixel values ──────────────────
        if vmax_orig == vmin_orig:
            restored_orig = np.full_like(restored_pixels, vmin_orig, dtype=orig_dtype)
        else:
            restored_orig = (
                (restored_pixels.astype(np.float64) / 255.0) *
                (vmax_orig - vmin_orig) + vmin_orig
            ).astype(orig_dtype)

        ds_restored = set_pixel_array(ds, restored_orig)
        # Remove private tags
        try:
            del ds_restored[0x0009, 0x0010]
            del ds_restored[0x0009, 0x1001]
        except KeyError:
            pass
        restored_bytes = dataset_to_bytes(ds_restored)
        restored_b64 = base64.b64encode(restored_bytes).decode('ascii')

        return jsonify({
            'success': True,
            'patient_text': plaintext,
            'restored_dicom_b64': restored_b64,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ─── Health check ─────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'MedCrypt API'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)