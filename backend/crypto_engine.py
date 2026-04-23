"""
Cryptographic Engine:
- GAN-based key generation
- Henon Map chaotic key expansion
- Tent Map chaotic key expansion
- Confusion matrix (substitution via chaotic S-Box)
- Diffusion matrix (permutation via chaotic sequence)
- Steganography via Prediction Error Expansion (PEE)
"""

import numpy as np
import hashlib
import struct
import os
import math


# ─── GAN-Based Key Generator ──────────────────────────────────────────────────

class GANKeyGenerator:
    """
    Lightweight GAN-inspired key generator.
    Generator: MLP maps noise → pseudo-key vector
    Discriminator: validates statistical uniformity
    We iterate until discriminator score exceeds threshold.
    """

    def __init__(self, seed: int = None):
        rng_seed = seed if seed is not None else int.from_bytes(os.urandom(4), 'big')
        self.rng = np.random.default_rng(rng_seed)
        self.seed_used = rng_seed

    def _generator(self, noise: np.ndarray) -> np.ndarray:
        # Simple MLP-style transform: two hidden layers with tanh activation
        W1 = self.rng.standard_normal((len(noise), 64))
        b1 = self.rng.standard_normal(64)
        h1 = np.tanh(noise @ W1 + b1)

        W2 = self.rng.standard_normal((64, 256))
        b2 = self.rng.standard_normal(256)
        h2 = np.tanh(h1 @ W2 + b2)

        # Map to [0, 255]
        out = ((h2 + 1) / 2 * 255).astype(np.uint8)
        return out

    def _discriminator_score(self, key_bytes: np.ndarray) -> float:
        # Chi-squared uniformity test over byte distribution
        counts = np.bincount(key_bytes.flatten(), minlength=256).astype(float)
        expected = len(key_bytes.flatten()) / 256.0
        chi2 = np.sum((counts - expected) ** 2 / expected)
        # Lower chi2 = more uniform = better key
        # Return normalized score [0,1] where 1 = perfectly uniform
        score = 1.0 / (1.0 + chi2 / (256 * expected))
        return score

    def generate_key(self, key_length: int = 256) -> bytes:
        """
        Iteratively generate a key using GAN loop until
        discriminator approves (score > 0.85) or max 50 iterations.
        """
        best_key = None
        best_score = 0.0

        for _ in range(50):
            noise = self.rng.standard_normal(32)
            key_raw = self._generator(noise)
            # Stretch/truncate to exact key_length bytes
            repeats = (key_length // 256) + 1
            key_bytes = np.tile(key_raw, repeats)[:key_length]
            score = self._discriminator_score(key_bytes)
            if score > best_score:
                best_score = score
                best_key = key_bytes
            if score > 0.85:
                break

        return bytes(best_key.tolist())


# ─── Chaotic Map Key Expansion ────────────────────────────────────────────────

def henon_map_sequence(x0: float, y0: float, a: float, b: float, n: int) -> np.ndarray:
    """
    Henon Map: x_{n+1} = 1 - a*x_n^2 + y_n
               y_{n+1} = b * x_n
    Classic parameters: a=1.4, b=0.3
    Returns n bytes derived from the chaotic orbit.
    Orbit is restarted with a perturbed seed if it diverges.
    """
    x, y = x0, y0
    seq = []
    restart_count = 0
    i = 0
    while i < n:
        x_new = 1.0 - a * x * x + y
        y_new = b * x
        # Detect divergence or NaN
        if not (math.isfinite(x_new) and math.isfinite(y_new)) or abs(x_new) > 1e6:
            # Restart with perturbed initial conditions
            restart_count += 1
            x = (x0 * 1.1 + restart_count * 0.037) % 1.0
            y = (y0 * 0.9 + restart_count * 0.019) % 1.0
            # Warm up for 50 steps
            for _ in range(50):
                xw = 1.0 - a * x * x + y
                yw = b * x
                if math.isfinite(xw) and math.isfinite(yw) and abs(xw) < 1e6:
                    x, y = xw, yw
                else:
                    x, y = 0.1 + restart_count * 0.01, 0.1
            continue
        x, y = x_new, y_new
        # Map to byte: use fractional part of |x| * large prime
        val = int(abs(x) * 1_000_003) % 256
        seq.append(val)
        i += 1
    return np.array(seq, dtype=np.uint8)


def tent_map_sequence(x0: float, mu: float, n: int) -> np.ndarray:
    """
    Tent Map: x_{n+1} = mu * x_n       if x_n < 0.5
              x_{n+1} = mu*(1 - x_n)   if x_n >= 0.5
    For chaos: mu close to 2.0
    Returns n bytes derived from the chaotic orbit.
    """
    x = x0
    seq = []
    for _ in range(n):
        if x < 0.5:
            x = mu * x
        else:
            x = mu * (1.0 - x)
        val = int(x * 256) % 256
        seq.append(val)
    return np.array(seq, dtype=np.uint8)


def derive_chaotic_params(key_bytes: bytes) -> dict:
    """
    Derive chaotic map initial conditions and parameters from GAN key.
    Parameters are clamped to ranges where orbits are guaranteed chaotic
    but bounded (no divergence).
    """
    digest = hashlib.sha512(key_bytes).digest()

    def u(start, end=None):
        """Uniform float in [0,1) from 8 bytes of digest."""
        raw = int.from_bytes(digest[start: start + 8], 'big')
        return raw / (2**64)

    # Henon: keep a in [1.1, 1.4), b in [0.2, 0.31)
    # Initial conditions in (-0.6, 0.6) — avoids divergent fixed points
    x0_henon = (u(0)  * 1.0) - 0.5          # in [-0.5, 0.5)
    y0_henon = (u(8)  * 1.0) - 0.5
    a_henon  = 1.1 + u(16) * 0.29           # in [1.10, 1.39)
    b_henon  = 0.20 + u(24) * 0.10          # in [0.20, 0.30)

    # Tent: x0 in (0.05, 0.95), mu in [1.7, 1.99)
    x0_tent = 0.05 + u(32) * 0.90           # in [0.05, 0.95)
    mu_tent  = 1.70 + u(40) * 0.29          # in [1.70, 1.99)

    # Warm-up Henon 200 steps to enter attractor before use
    x, y = x0_henon, y0_henon
    for _ in range(200):
        xn = 1.0 - a_henon * x * x + y
        yn = b_henon * x
        if math.isfinite(xn) and math.isfinite(yn) and abs(xn) < 10:
            x, y = xn, yn
        else:
            x, y = 0.1, 0.1
    x0_henon, y0_henon = x, y

    # Warm-up Tent 100 steps
    xt = x0_tent
    for _ in range(100):
        xt = mu_tent * xt if xt < 0.5 else mu_tent * (1.0 - xt)
    x0_tent = xt

    return {
        'henon': {'x0': x0_henon, 'y0': y0_henon, 'a': a_henon, 'b': b_henon},
        'tent':  {'x0': x0_tent,  'mu': mu_tent},
    }


# ─── Confusion Layer (Chaotic S-Box Substitution) ─────────────────────────────

def build_sbox(key_bytes: bytes, chaotic_params: dict) -> np.ndarray:
    """
    Build a 256-element S-Box by:
    1. Generating 256 values from Henon map
    2. XOR-mixing with key bytes
    3. Sorting indices by the mixed values → permutation = S-Box
    """
    henon_seq = henon_map_sequence(
        chaotic_params['henon']['x0'],
        chaotic_params['henon']['y0'],
        chaotic_params['henon']['a'],
        chaotic_params['henon']['b'],
        256
    )
    key_arr = np.frombuffer(key_bytes[:256], dtype=np.uint8)
    if len(key_arr) < 256:
        key_arr = np.tile(key_arr, (256 // len(key_arr)) + 1)[:256]

    mixed = (henon_seq.astype(np.uint16) + key_arr.astype(np.uint16)) % 256
    # Build bijective S-Box via argsort
    sbox = np.argsort(mixed).astype(np.uint8)
    # Ensure it's a valid permutation of 0..255
    assert len(set(sbox.tolist())) == 256
    return sbox


def build_inv_sbox(sbox: np.ndarray) -> np.ndarray:
    inv = np.zeros(256, dtype=np.uint8)
    for i, v in enumerate(sbox):
        inv[v] = i
    return inv


def confusion_encrypt(data: bytes, sbox: np.ndarray) -> bytes:
    arr = np.frombuffer(data, dtype=np.uint8)
    return bytes(sbox[arr].tolist())


def confusion_decrypt(data: bytes, inv_sbox: np.ndarray) -> bytes:
    arr = np.frombuffer(data, dtype=np.uint8)
    return bytes(inv_sbox[arr].tolist())


# ─── Diffusion Layer (Chaotic Permutation + XOR Stream) ──────────────────────

def build_permutation(length: int, chaotic_params: dict) -> np.ndarray:
    """
    Build a byte-level permutation using Tent map.
    Fisher-Yates shuffle seeded by tent map values.
    """
    tent_seq = tent_map_sequence(
        chaotic_params['tent']['x0'],
        chaotic_params['tent']['mu'],
        length
    )
    indices = np.arange(length)
    for i in range(length - 1, 0, -1):
        j = int(tent_seq[i]) % (i + 1)
        indices[i], indices[j] = indices[j], indices[i]
    return indices


def diffusion_encrypt(data: bytes, chaotic_params: dict) -> tuple:
    """
    Two-phase diffusion:
    1. Permute bytes using tent-map permutation
    2. XOR with Henon-derived keystream
    Returns (ciphertext, permutation_indices)
    """
    n = len(data)
    arr = np.frombuffer(data, dtype=np.uint8).copy()

    perm = build_permutation(n, chaotic_params)
    permuted = arr[perm]

    # XOR keystream from Henon
    keystream = henon_map_sequence(
        chaotic_params['henon']['x0'],
        chaotic_params['henon']['y0'],
        chaotic_params['henon']['a'],
        chaotic_params['henon']['b'],
        n
    )
    ciphertext = (permuted.astype(np.uint16) ^ keystream.astype(np.uint16)).astype(np.uint8)
    return bytes(ciphertext.tolist()), perm


def diffusion_decrypt(data: bytes, chaotic_params: dict, perm: np.ndarray) -> bytes:
    """
    Reverse diffusion: un-XOR then un-permute.
    """
    n = len(data)
    arr = np.frombuffer(data, dtype=np.uint8).copy()

    keystream = henon_map_sequence(
        chaotic_params['henon']['x0'],
        chaotic_params['henon']['y0'],
        chaotic_params['henon']['a'],
        chaotic_params['henon']['b'],
        n
    )
    un_xored = (arr.astype(np.uint16) ^ keystream.astype(np.uint16)).astype(np.uint8)

    # Inverse permutation
    inv_perm = np.argsort(perm)
    original = un_xored[inv_perm]
    return bytes(original.tolist())


# ─── Full Text Encryption/Decryption ─────────────────────────────────────────

def encrypt_text(plaintext: str, key_bytes: bytes) -> dict:
    """
    Full pipeline: Confusion (S-Box) → Diffusion (permutation+XOR)
    Returns ciphertext bytes and all params needed for decryption.
    """
    data = plaintext.encode('utf-8')
    # Pad to multiple of 16
    pad_len = (16 - len(data) % 16) % 16
    data = data + bytes([pad_len] * pad_len)

    chaotic_params = derive_chaotic_params(key_bytes)

    # Layer 1: Confusion
    sbox = build_sbox(key_bytes, chaotic_params)
    confused = confusion_encrypt(data, sbox)

    # Layer 2: Diffusion
    diffused, perm = diffusion_encrypt(confused, chaotic_params)

    return {
        'ciphertext': diffused,
        'perm': perm.tolist(),
        'pad_len': pad_len,
        'sbox': sbox.tolist(),
    }


def decrypt_text(ciphertext: bytes, key_bytes: bytes, perm_list: list, pad_len: int) -> str:
    """
    Reverse: Diffusion⁻¹ → Confusion⁻¹ → strip padding → decode
    """
    chaotic_params = derive_chaotic_params(key_bytes)
    perm = np.array(perm_list, dtype=np.int64)

    # Reverse diffusion
    un_diffused = diffusion_decrypt(ciphertext, chaotic_params, perm)

    # Reverse confusion
    sbox = build_sbox(key_bytes, chaotic_params)
    inv_sbox = build_inv_sbox(sbox)
    plaindata = confusion_decrypt(un_diffused, inv_sbox)

    # Strip padding
    if pad_len > 0:
        plaindata = plaindata[:-pad_len]

    return plaindata.decode('utf-8')


# ─── Prediction Error Expansion (PEE) Steganography ─────────────────────────

def _median_edge_detector(pixels: np.ndarray, i: int, j: int) -> int:
    """
    MED predictor used in PEE (same as JPEG-LS).
    """
    if i == 0 and j == 0:
        return 128
    if i == 0:
        return int(pixels[i, j - 1])
    if j == 0:
        return int(pixels[i - 1, j])

    west  = int(pixels[i, j - 1])
    north = int(pixels[i - 1, j])
    nw    = int(pixels[i - 1, j - 1])

    lo = min(west, north)
    hi = max(west, north)

    if nw >= hi:
        return lo
    if nw <= lo:
        return hi
    return west + north - nw


def pee_embed(pixel_array: np.ndarray, payload: bytes) -> tuple:
    """
    Embed payload bits into a 2D uint8 pixel array using PEE.
    Returns (stego_array, capacity_used, overflow_map).

    Extended PEE:  errors in {-1, 0, 1, 2} are treated as expandable to
    maximise capacity on smooth (medical) images while still being invertible.
    Errors outside [-T, T+1] are shifted to preserve room for expansion.
    T = 1 (so expandable window is e ∈ {-1, 0, 1}).
    """
    if pixel_array.ndim != 2:
        raise ValueError("PEE requires 2D grayscale array")

    T = 1  # expansion threshold
    h, w = pixel_array.shape
    pixels = pixel_array.astype(np.int32).copy()
    stego = pixels.copy()

    bits = []
    for byte in payload:
        for bit in range(7, -1, -1):
            bits.append((byte >> bit) & 1)

    bit_idx = 0
    total_bits = len(bits)
    overflow_map = []

    for i in range(h):
        for j in range(w):
            if bit_idx >= total_bits:
                # Still shift overflow pixels to keep image invertible
                pred = _median_edge_detector(stego, i, j)
                e = stego[i, j] - pred
                if e > T:
                    new_val = pred + e + 1
                    if 0 <= new_val <= 255:
                        stego[i, j] = new_val
                        overflow_map.append((i, j, 1))
                elif e < -T:
                    new_val = pred + e - 1
                    if 0 <= new_val <= 255:
                        stego[i, j] = new_val
                        overflow_map.append((i, j, -1))
                continue

            pred = _median_edge_detector(stego, i, j)
            e = stego[i, j] - pred

            if -T <= e <= T:
                # Expandable: new_e = 2*e + bit
                new_e = 2 * e + bits[bit_idx]
                new_val = pred + new_e
                if 0 <= new_val <= 255:
                    stego[i, j] = new_val
                    bit_idx += 1
                else:
                    # Boundary pixel — skip embedding, shift instead
                    if e > 0:
                        stego[i, j] = min(255, pred + e + 1)
                        overflow_map.append((i, j, 1))
                    elif e < 0:
                        stego[i, j] = max(0, pred + e - 1)
                        overflow_map.append((i, j, -1))
            elif e > T:
                new_val = pred + e + 1
                if 0 <= new_val <= 255:
                    stego[i, j] = new_val
                overflow_map.append((i, j, 1))
            else:  # e < -T
                new_val = pred + e - 1
                if 0 <= new_val <= 255:
                    stego[i, j] = new_val
                overflow_map.append((i, j, -1))

    capacity_used = bit_idx
    if bit_idx < total_bits:
        raise ValueError(
            f"Image capacity insufficient: embedded {bit_idx}/{total_bits} bits. "
            "Use a larger DICOM image (recommended: >= 256x256 pixels)."
        )

    return stego.astype(np.uint8), capacity_used, overflow_map


def pee_extract(stego_array: np.ndarray, payload_byte_len: int) -> tuple:
    """
    Extract embedded payload from stego image and restore original pixels.
    Returns (payload_bytes, restored_array).
    Must be called with the stego image that was produced by pee_embed.
    """
    T = 1
    h, w = stego_array.shape
    stego = stego_array.astype(np.int32).copy()
    restored = stego.copy()

    bits = []
    target_bits = payload_byte_len * 8
    extracted = 0

    for i in range(h):
        for j in range(w):
            pred = _median_edge_detector(restored, i, j)
            e = restored[i, j] - pred

            if extracted < target_bits and -2 * T <= e <= 2 * T + 1:
                # Within expanded range — recover original error and bit
                orig_e = e // 2
                bit = e - 2 * orig_e  # = e % 2 (for non-negative); handles negatives too
                # Correct for negative expansion: 2*orig_e + bit should equal e
                # For e negative: e = 2*(e//2) + (e%2) in Python's floor division
                bits.append(bit & 1)
                restored[i, j] = pred + orig_e
                extracted += 1
            elif e > T + 1:
                # Was a shifted positive error
                restored[i, j] = pred + e - 1
            elif e < -(T + 1):
                # Was a shifted negative error
                restored[i, j] = pred + e + 1
            # e in {-T..T} that wasn't embedded (boundary skip) — left as-is

    payload = bytearray()
    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i + 8]
        if len(byte_bits) == 8:
            byte_val = sum(b << (7 - k) for k, b in enumerate(byte_bits))
            payload.append(byte_val)

    return bytes(payload), restored.astype(np.uint8)


# ─── Image-level Encryption via PEE + Chaotic XOR ────────────────────────────

def encrypt_dicom_pixels(pixel_array: np.ndarray, key_bytes: bytes) -> np.ndarray:
    """
    Encrypt a DICOM pixel array using:
    1. Chaotic permutation (Tent map) of pixel positions
    2. XOR with Henon keystream
    Works on both 2D (single frame) and 3D (multi-frame) arrays.
    Normalises to uint8 for processing, stores scale factor.
    """
    original_dtype = pixel_array.dtype
    original_shape = pixel_array.shape

    flat = pixel_array.flatten().astype(np.float64)
    vmin, vmax = flat.min(), flat.max()
    if vmax == vmin:
        norm = np.zeros_like(flat, dtype=np.uint8)
    else:
        norm = ((flat - vmin) / (vmax - vmin) * 255).astype(np.uint8)

    chaotic_params = derive_chaotic_params(key_bytes)
    n = len(norm)

    # Permute
    perm = build_permutation(n, chaotic_params)
    permuted = norm[perm]

    # XOR keystream
    keystream = henon_map_sequence(
        chaotic_params['henon']['x0'],
        chaotic_params['henon']['y0'],
        chaotic_params['henon']['a'],
        chaotic_params['henon']['b'],
        n
    )
    encrypted = (permuted.astype(np.uint16) ^ keystream.astype(np.uint16)).astype(np.uint8)

    return encrypted.reshape(original_shape), perm, vmin, vmax


def decrypt_dicom_pixels(
    encrypted_array: np.ndarray,
    key_bytes: bytes,
    perm: np.ndarray,
    vmin: float,
    vmax: float,
    original_dtype
) -> np.ndarray:
    """
    Reverse pixel encryption.
    """
    chaotic_params = derive_chaotic_params(key_bytes)
    flat = encrypted_array.flatten().astype(np.uint16)
    n = len(flat)

    keystream = henon_map_sequence(
        chaotic_params['henon']['x0'],
        chaotic_params['henon']['y0'],
        chaotic_params['henon']['a'],
        chaotic_params['henon']['b'],
        n
    )
    un_xored = (flat ^ keystream.astype(np.uint16)).astype(np.uint8)

    inv_perm = np.argsort(perm)
    unpermuted = un_xored[inv_perm]

    # Denormalise
    if vmax == vmin:
        restored = np.full_like(unpermuted, vmin, dtype=np.float64)
    else:
        restored = (unpermuted.astype(np.float64) / 255.0) * (vmax - vmin) + vmin

    return restored.reshape(encrypted_array.shape).astype(original_dtype)