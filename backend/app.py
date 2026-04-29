"""
MedCrypt Flask API — FINAL STABLE VERSION
(Reversible RDH + Safe High BPP)
"""

import base64
import struct
import os
import io
import math
import zlib

import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image

from crypto_engine import (
    GANKeyGenerator, derive_chaotic_params,
    encrypt_text, decrypt_text,
    pee_embed, pee_extract,
    encrypt_dicom_pixels, decrypt_dicom_pixels
)

from dicom_handler import (
    load_dicom_or_image, load_dicom, get_all_frames,
    set_pixel_array_multiframe,
    dataset_to_bytes, embed_metadata, extract_metadata,
)

app = Flask(__name__)
CORS(app)

CRYPTO_VERSION = "2.1"


# ─────────────────────────────────────────────

def encode_key(b): return base64.urlsafe_b64encode(b).decode()
def decode_key(s): return base64.urlsafe_b64decode(s.encode())


def pack_payload(ciphertext, perm, pad_len):
    return struct.pack('>III', len(ciphertext), pad_len, len(perm)) \
           + ciphertext + np.array(perm, dtype=np.int32).tobytes()


def unpack_payload(payload):
    ct_len, pad_len, pm_len = struct.unpack('>III', payload[:12])
    ct = payload[12: 12 + ct_len]
    perm = np.frombuffer(payload[12 + ct_len: 12 + ct_len + pm_len * 4],
                         dtype=np.int32).tolist()
    return ct, perm, pad_len


def encode_png_b64(arr):
    img = Image.fromarray(arr.astype(np.uint8), mode='L')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────

def compute_embed_metrics(orig, stego):
    o = orig.astype(np.float64)
    s = stego.astype(np.float64)

    diff = o - s

    mse = float(np.mean(diff * diff))
    mae = float(np.mean(np.abs(diff)))

    if mse == 0:
        psnr = float('inf')
    else:
        psnr = 20 * math.log10(255.0 / math.sqrt(mse))

    # SSIM (simple global)
    mu_o = float(np.mean(o))
    mu_s = float(np.mean(s))
    var_o = float(np.var(o))
    var_s = float(np.var(s))
    cov = float(np.mean((o - mu_o) * (s - mu_s)))

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    denom = (mu_o**2 + mu_s**2 + C1) * (var_o + var_s + C2)
    ssim = None if denom == 0 else (
        (2 * mu_o * mu_s + C1) * (2 * cov + C2) / denom
    )

    pixel_match_pct = float(np.mean(orig == stego) * 100)

    return {
        "pixel_match_pct": round(pixel_match_pct, 4),
        "mse": round(mse, 6),
        "mae": round(mae, 6),
        "psnr_db": None if psnr == float('inf') else round(psnr, 6),
        "psnr_is_inf": bool(psnr == float('inf')),
        "ssim_global": round(ssim, 8) if ssim is not None else None
    }


# ─────────────────────────────────────────────
# ENCRYPT
# ─────────────────────────────────────────────

@app.route('/api/encrypt', methods=['POST'])
def encrypt():
    try:
        # ─── Patient text ───
        text = (
            f"PATIENT NAME: {request.form.get('patient_name','')}\n"
            f"PATIENT ID: {request.form.get('patient_id','')}\n"
            f"AGE: {request.form.get('patient_age','')}\n"
            f"DIAGNOSIS: {request.form.get('diagnosis','')}\n"
            f"NOTES: {request.form.get('notes','')}"
        )

        file = request.files['dicom_file']
        dicom_bytes = file.read()

        # ─── Keys ───
        gan = GANKeyGenerator()
        text_key = gan.generate_key(256)
        image_key = gan.generate_key(256)

        # ─── Encrypt text ───
        enc = encrypt_text(text, text_key)
        payload = pack_payload(enc['ciphertext'], enc['perm'], enc['pad_len'])

        # 🔥 Compress payload
        payload = zlib.compress(payload, level=9)
        
        # ─── Load DICOM ───
        ds = load_dicom_or_image(dicom_bytes, file.filename)
        frames = get_all_frames(ds)

        vmin, vmax = frames.min(), frames.max()
        frames_8 = ((frames - vmin) / (vmax - vmin) * 255).astype(np.uint8)

        frame0 = frames_8[0].copy()

        # ─── SAFE EMBEDDING ───

        total_pixels = frame0.size

        # Try embedding
        try:
            stego, bits_used, _ = pee_embed(frame0, payload)

        except ValueError:
            # reduce payload until it fits
            while True:
                try:
                    stego, bits_used, _ = pee_embed(frame0, payload)
                except ValueError:
                    return jsonify({
                        "error": "Payload too large for this image. Please reduce input text."
                    }), 400

        # compute BPP
        bpp = bits_used / total_pixels

        # 🔥 VERY IMPORTANT
        actual_payload_bytes = len(payload)
        # ─── Metrics ───
        metrics = compute_embed_metrics(frame0, stego)
        bpp = bits_used / total_pixels

        # Store the embedded first frame before encrypting the DICOM
        frames_8[0] = stego

        # ─── Encrypt image ───
        enc_frames = []
        perms = None   # 🔥 store permutation
        encrypt_vmin = None
        encrypt_vmax = None

        for f in frames_8:
            ef, perm, ef_vmin, ef_vmax = encrypt_dicom_pixels(f, image_key)
            enc_frames.append(ef)

            if perms is None:
                perms = perm   # store first frame perm
                encrypt_vmin = ef_vmin
                encrypt_vmax = ef_vmax

        enc_frames = np.array(enc_frames)

        # ─── Metadata ───
        meta = {
            "payload_len": len(payload),
            "perm": perms.tolist(),
            "vmin": float(encrypt_vmin),
            "vmax": float(encrypt_vmax),
            "dtype": str(frames_8.dtype),
        }

        ds_out = set_pixel_array_multiframe(ds, enc_frames)
        ds_out = embed_metadata(ds_out, meta)

        return jsonify({
            "success": True,
            "encrypted_text_hex": enc['ciphertext'].hex().upper()[:256],

            # 🔑 Keys
            "text_key": encode_key(text_key),
            "image_key": encode_key(image_key),

            # 📊 Metrics (FIXED NAMES)
            "bpp": round(bpp, 6),
            "bits_embedded": bits_used,
            "image_shape": list(frames_8.shape),

            # 🖼️ Image previews (FIXED NAMES)
            "original_frame0_png_b64": encode_png_b64(frame0),
            "embedded_frame0_png_b64": encode_png_b64(stego),

            "embed_metrics": metrics,

            # 📦 DICOM
            "dicom_b64": base64.b64encode(dataset_to_bytes(ds_out)).decode()
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# DECRYPT
# ─────────────────────────────────────────────
@app.route('/api/decrypt', methods=['POST'])
def decrypt():
    try:
        import base64
        from dicom_handler import dataset_to_bytes, set_pixel_array_multiframe

        text_key = decode_key(request.form['text_key'])
        image_key = decode_key(request.form['image_key'])
        dicom_bytes = request.files['dicom_file'].read()

        ds = load_dicom(dicom_bytes)
        meta = extract_metadata(ds)

        frames = get_all_frames(ds).astype(np.uint8)

        # ─── Decrypt image (FIXED) ───
        dec_frames = []
        for f in frames:
            dec = decrypt_dicom_pixels(
                f,
                image_key,
                np.array(meta['perm']),   # ✅ now works
                meta['vmin'],
                meta['vmax'],
                np.uint8
            )
            dec_frames.append(dec)

        dec_frames = np.array(dec_frames)

        # ─── Extract payload ───
        payload, restored = pee_extract(dec_frames[0], meta['payload_len'])
        dec_frames[0] = restored

        payload = payload[:meta['payload_len']]

        try:
            payload = zlib.decompress(payload)
        except zlib.error:
            return jsonify({"error": "Payload corrupted"}), 500

        ct, perm, pad_len = unpack_payload(payload)

        text = decrypt_text(ct, text_key, perm, pad_len)

        # ─── Rebuild DICOM (NEW) ───
        restored_ds = set_pixel_array_multiframe(ds, dec_frames)

        dicom_bytes_out = dataset_to_bytes(restored_ds)
        dicom_b64 = base64.b64encode(dicom_bytes_out).decode('utf-8')

        # ─── FINAL RESPONSE ───
        return jsonify({
            "success": True,
            "patient_text": text,
            "restored_dicom_b64": dicom_b64,
            "dicom_b64": dicom_b64
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)