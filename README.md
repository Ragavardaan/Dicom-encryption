# MedCrypt — Medical Image Cryptography System

A full-stack cryptographic steganography system that:
- Generates keys using a **GAN** (Generator-Discriminator loop)
- Expands keys via **Henon Map** and **Tent Map** chaotic systems
- Encrypts patient text via **Confusion** (chaotic S-Box) + **Diffusion** (permutation + XOR)
- Embeds ciphertext inside DICOM images via **Prediction Error Expansion (PEE)**
- Encrypts the DICOM pixel array with chaotic permutation + XOR
- Outputs a valid, downloadable **DICOM (.dcm)** file
- Provides full **decryption** back to the original image and patient text

---

## Folder Structure

```
medcrypt/
├── backend/
│   ├── app.py                ← Flask API server (all endpoints)
│   ├── crypto_engine.py      ← All cryptographic algorithms
│   ├── dicom_handler.py      ← DICOM I/O, metadata embedding
│   ├── requirements.txt      ← Python dependencies
│   └── start_backend.sh      ← Backend startup script (Linux/macOS)
│
├── frontend/
│   ├── public/
│   │   └── index.html        ← HTML entry point
│   ├── src/
│   │   ├── App.js            ← Router
│   │   ├── index.js          ← React entry
│   │   ├── index.css         ← Global styles / CSS variables
│   │   └── pages/
│   │       ├── HomePage.js           ← Landing page
│   │       ├── HomePage.module.css   ← Landing page styles
│   │       ├── DicomPage.js          ← Encrypt/Decrypt workstation
│   │       └── DicomPage.module.css  ← Workstation styles
│   ├── package.json          ← npm config + proxy
│   └── start_frontend.sh     ← Frontend startup script
│
└── README.md
```

---

## Prerequisites

### Backend
- **Python 3.9+** (3.10 or 3.11 recommended)
- `pip` and `venv`

### Frontend
- **Node.js 18+** → https://nodejs.org
- npm (comes with Node.js)

---

## How to Run (Step-by-Step)

### Terminal 1 — Start the Backend

```bash
cd medcrypt/backend
chmod +x start_backend.sh
./start_backend.sh
```

**On Windows (PowerShell):**
```powershell
cd medcrypt\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Wait for:
```
* Running on http://0.0.0.0:5000
```

---

### Terminal 2 — Start the Frontend

```bash
cd medcrypt/frontend
chmod +x start_frontend.sh
./start_frontend.sh
```

**On Windows (PowerShell):**
```powershell
cd medcrypt\frontend
npm install --legacy-peer-deps
npm start
```

Wait for:
```
Compiled successfully!
Local: http://localhost:3000
```

Your browser will open automatically at **http://localhost:3000**.

---

## How to Use

### Encryption

1. Open http://localhost:3000
2. Click **"Open DICOM Workstation"** (or the floating button)
3. Fill in patient information (name, ID, age, diagnosis, notes)
4. Upload a DICOM brain scan file (`.dcm`)
5. Click **"Encrypt Data & Image"**
6. Watch the encryption pipeline run through all 6 steps:
   - GAN Key Generation
   - Chaotic Map Initialization (Henon + Tent parameters derived)
   - Confusion Layer (S-Box substitution)
   - Diffusion Layer (permutation + XOR stream cipher)
   - PEE Embedding (ciphertext embedded in DICOM pixels)
   - Image Encryption (entire pixel array encrypted)
7. **Download** the encrypted `.dcm` file
8. **Copy and save** both keys:
   - **Text Decryption Key** — decrypts the embedded patient text
   - **Image Decryption Key** — decrypts the pixel array

> ⚠ Both keys are shown only once. Store them securely.

---

### Decryption

1. Click the **Decrypt** tab
2. Upload the encrypted `.dcm` file
3. Paste both keys
4. Click **"Decrypt & Recover Data"**
5. View the recovered patient text
6. **Download** the restored original DICOM image

---

## Cryptographic Architecture

```
Patient Text
    │
    ▼ GAN Key Generation (256-byte key)
    │
    ▼ derive_chaotic_params(key)
    │   ├── Henon Map: x₀, y₀, a, b  (from SHA-512 of key)
    │   └── Tent Map: x₀, μ          (from SHA-512 of key)
    │
    ▼ CONFUSION LAYER
    │   build_sbox(key, henon_params)
    │   - 256 values from Henon orbit
    │   - XOR with key bytes
    │   - argsort → bijective S-Box permutation
    │   confused = sbox[plaintext_bytes]
    │
    ▼ DIFFUSION LAYER
    │   build_permutation(n, tent_params)
    │   - Fisher-Yates shuffle seeded by Tent map
    │   permuted = confused[perm_indices]
    │   ciphertext = permuted XOR henon_keystream
    │
    ▼ pack_payload(ciphertext, perm, pad_len)
    │   → binary blob with length header
    │
    ▼ PEE EMBEDDING (into DICOM pixel array)
    │   - MED (Median Edge Detector) predictor
    │   - Expandable pixels: e ∈ {0,1} → expand to 2e or 2e+bit
    │   - Shifted pixels: e > 1 → e+1; e < -1 → e-1
    │
    ▼ IMAGE ENCRYPTION (stego pixel array)
    │   - Tent map permutation of all pixels
    │   - XOR with Henon keystream
    │
    ▼ embed_metadata(ds, meta)
    │   - payload_len, img_perm, vmin, vmax in private DICOM tags
    │
    ▼ Output: encrypted DICOM (.dcm)
```

---

## API Endpoints

| Method | URL              | Description                              |
|--------|------------------|------------------------------------------|
| POST   | `/api/encrypt`   | Encrypt text + DICOM image               |
| POST   | `/api/decrypt`   | Decrypt DICOM + extract text             |
| GET    | `/api/health`    | Health check                             |

### POST /api/encrypt (multipart/form-data)

| Field          | Type   | Required | Description               |
|----------------|--------|----------|---------------------------|
| `patient_name` | string | Yes      | Patient full name         |
| `patient_id`   | string | Yes      | Patient ID                |
| `patient_age`  | string | No       | Patient age               |
| `diagnosis`    | string | No       | Medical diagnosis         |
| `notes`        | string | No       | Clinical notes            |
| `dicom_file`   | file   | Yes      | DICOM (.dcm) file         |

**Response:**
```json
{
  "success": true,
  "encrypted_text_hex": "A3F7...",
  "text_key": "base64-encoded-key",
  "image_key": "base64-encoded-key",
  "dicom_b64": "base64-encoded-dicom-bytes",
  "bits_embedded": 2056,
  "image_shape": [512, 512],
  "chaotic_params": { "henon": {...}, "tent": {...} }
}
```

### POST /api/decrypt (multipart/form-data)

| Field        | Type   | Required |
|--------------|--------|----------|
| `dicom_file` | file   | Yes      |
| `text_key`   | string | Yes      |
| `image_key`  | string | Yes      |

**Response:**
```json
{
  "success": true,
  "patient_text": "PATIENT NAME: ...\nPATIENT ID: ...",
  "restored_dicom_b64": "base64-encoded-dicom-bytes"
}
```

---

## Notes

- DICOM files must be standard `.dcm` format. Use any real or synthetic brain MRI DICOM.
- The PEE algorithm works on the first 2D frame of multi-frame DICOMs.
- Large images (512×512 and above) have plenty of capacity for patient text.
- The system normalises 16-bit DICOM pixels to 8-bit internally for PEE, then restores original range on decryption.
- Pixel encryption uses Tent+Henon on top of the stego layer for double protection.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `pydicom` error reading file | Ensure the file is a real `.dcm` DICOM, not renamed |
| `Image capacity insufficient` | Use a larger DICOM image (at least 256×256) |
| CORS error in browser | Ensure backend is running on port 5000 |
| `npm install` fails | Try `npm install --legacy-peer-deps` |
| Port 5000 already in use | Change port in `app.py` and `package.json` proxy |
