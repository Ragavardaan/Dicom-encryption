import React, { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import styles from './DicomPage.module.css';

const API = 'http://localhost:5000/api';

// ── Reusable components ──────────────────────────────────────────────────────

function TabBar({ active, onChange }) {
  return (
    <div className={styles.tabBar}>
      <button className={`${styles.tab} ${active === 'encrypt' ? styles.tabActive : ''}`}
        onClick={() => onChange('encrypt')}>
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
          <rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" strokeWidth="2"/>
          <path d="M7 11V7a5 5 0 0110 0v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        Encrypt
      </button>
      <button className={`${styles.tab} ${active === 'decrypt' ? styles.tabActive : ''}`}
        onClick={() => onChange('decrypt')}>
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
          <rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" strokeWidth="2"/>
          <path d="M7 11V7a5 5 0 0110 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeDasharray="4 3"/>
        </svg>
        Decrypt
      </button>
    </div>
  );
}

function DropZone({ label, accept, file, onFile }) {
  const inputRef = useRef();
  const [drag, setDrag] = useState(false);

  const handleDrop = useCallback(e => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }, [onFile]);

  return (
    <div
      className={`${styles.dropZone} ${drag ? styles.dropZoneDrag : ''} ${file ? styles.dropZoneHasFile : ''}`}
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current.click()}
    >
      <input ref={inputRef} type="file" accept={accept} style={{ display: 'none' }}
        onChange={e => { if (e.target.files[0]) onFile(e.target.files[0]); }} />
      {file ? (
        <div className={styles.dropZoneFile}>
          <span className={styles.dropZoneIcon}>⬛</span>
          <span className={styles.dropZoneFileName}>{file.name}</span>
          <span className={styles.dropZoneFileSize}>{(file.size / 1024).toFixed(1)} KB</span>
        </div>
      ) : (
        <div className={styles.dropZoneEmpty}>
          <span className={styles.dropZoneIcon}>⬡</span>
          <span className={styles.dropZoneLabel}>{label}</span>
          <span className={styles.dropZoneHint}>Drag & drop or click</span>
        </div>
      )}
    </div>
  );
}

function FormField({ label, id, type = 'text', value, onChange, placeholder, required }) {
  return (
    <div className={styles.formField}>
      <label htmlFor={id} className={styles.fieldLabel}>
        {label} {required && <span className={styles.req}>*</span>}
      </label>
      {type === 'textarea' ? (
        <textarea id={id} value={value} onChange={e => onChange(e.target.value)}
          placeholder={placeholder} rows={3} />
      ) : (
        <input id={id} type={type} value={value} onChange={e => onChange(e.target.value)}
          placeholder={placeholder} />
      )}
    </div>
  );
}

function Spinner() {
  return (
    <div className={styles.spinner}>
      <div className={styles.spinnerRing} />
      <div className={styles.spinnerRing2} />
    </div>
  );
}

function Step({ num, label, active, done }) {
  return (
    <div className={`${styles.step} ${active ? styles.stepActive : ''} ${done ? styles.stepDone : ''}`}>
      <div className={styles.stepNum}>{done ? '✓' : num}</div>
      <div className={styles.stepLabel}>{label}</div>
    </div>
  );
}

function CopyBtn({ value }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button className={styles.copyBtn} onClick={copy}>
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  );
}

// ── Encrypt Panel ────────────────────────────────────────────────────────────

function EncryptPanel() {
  const [form, setForm] = useState({
    patient_name: '', patient_id: '', patient_age: '',
    diagnosis: '', notes: ''
  });
  const [dicomFile, setDicomFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const steps = [
    'GAN Key Generation',
    'Chaotic Map Init',
    'Confusion Layer',
    'Diffusion Layer',
    'PEE Embedding',
    'Image Encryption',
  ];

  const set = key => val => setForm(f => ({ ...f, [key]: val }));

  const handleEncrypt = async () => {
    if (!dicomFile) { setError('Please upload a DICOM file.'); return; }
    if (!form.patient_name || !form.patient_id) { setError('Patient name and ID are required.'); return; }

    setError('');
    setLoading(true);
    setResult(null);
    setCurrentStep(0);

    // Animate through steps
    const stepInterval = setInterval(() => {
      setCurrentStep(s => {
        if (s >= steps.length - 1) { clearInterval(stepInterval); return s; }
        return s + 1;
      });
    }, 900);

    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    fd.append('dicom_file', dicomFile);

    try {
      const res = await axios.post(`${API}/encrypt`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      clearInterval(stepInterval);
      setCurrentStep(steps.length);
      setResult(res.data);
    } catch (e) {
      clearInterval(stepInterval);
      setError(e.response?.data?.error || e.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadDicom = () => {
    if (!result?.dicom_b64) return;
    const bin = atob(result.dicom_b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const blob = new Blob([arr], { type: 'application/dicom' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'encrypted_output.dcm';
    a.click();
  };

  return (
    <div className={styles.panel}>
      {/* Left: Form */}
      <div className={styles.panelLeft}>
        <div className={styles.panelSection}>
          <div className={styles.panelSectionTitle}>
            <span className={styles.sectionNum}>01</span>
            Patient Information
          </div>
          <div className={styles.formGrid}>
            <FormField label="Patient Name" id="pname" value={form.patient_name}
              onChange={set('patient_name')} placeholder="John Doe" required />
            <FormField label="Patient ID" id="pid" value={form.patient_id}
              onChange={set('patient_id')} placeholder="PT-2024-001" required />
            <FormField label="Age" id="page" value={form.patient_age}
              onChange={set('patient_age')} placeholder="45" />
            <FormField label="Diagnosis" id="pdiag" value={form.diagnosis}
              onChange={set('diagnosis')} placeholder="Glioblastoma Multiforme" />
            <FormField label="Clinical Notes" id="pnotes" type="textarea"
              value={form.notes} onChange={set('notes')}
              placeholder="Additional clinical observations..." />
          </div>
        </div>

        <div className={styles.panelSection}>
          <div className={styles.panelSectionTitle}>
            <span className={styles.sectionNum}>02</span>
            DICOM Image
          </div>
          <DropZone label="Upload DICOM File (.dcm)" accept=".dcm,.dicom"
            file={dicomFile} onFile={setDicomFile} />
        </div>

        {error && <div className={styles.errorBox}>{error}</div>}

        <button className={styles.actionBtn} onClick={handleEncrypt} disabled={loading}>
          {loading ? <><Spinner /> Processing...</> : <>
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
              <rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" strokeWidth="2"/>
              <path d="M7 11V7a5 5 0 0110 0v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Encrypt Data & Image
          </>}
        </button>
      </div>

      {/* Right: Progress + Results */}
      <div className={styles.panelRight}>
        <div className={styles.panelSectionTitle}>
          <span className={styles.sectionNum}>03</span>
          Encryption Pipeline
        </div>

        <div className={styles.stepsContainer}>
          {steps.map((s, i) => (
            <Step key={s} num={i + 1} label={s}
              active={loading && currentStep === i}
              done={result ? true : currentStep > i} />
          ))}
        </div>

        {result && (
          <div className={styles.resultSection}>
            <div className={styles.resultTitle}>
              <span className={styles.successDot} />
              Encryption Complete
            </div>

            <div className={styles.resultBlock}>
              <div className={styles.resultBlockLabel}>Encrypted Text Preview (hex)</div>
              <div className={styles.hexDisplay}>
                {result.encrypted_text_hex}
              </div>
            </div>

            <div className={styles.resultBlock}>
              <div className={styles.resultBlockLabel}>Chaotic Map Parameters</div>
              <div className={styles.chaoticParams}>
                <div className={styles.chaoticGroup}>
                  <span className={styles.chaoticName}>Henon</span>
                  <span>x₀={result.chaotic_params?.henon?.x0}</span>
                  <span>y₀={result.chaotic_params?.henon?.y0}</span>
                  <span>a={result.chaotic_params?.henon?.a}</span>
                  <span>b={result.chaotic_params?.henon?.b}</span>
                </div>
                <div className={styles.chaoticGroup}>
                  <span className={styles.chaoticName}>Tent</span>
                  <span>x₀={result.chaotic_params?.tent?.x0}</span>
                  <span>μ={result.chaotic_params?.tent?.mu}</span>
                </div>
              </div>
            </div>

            <div className={styles.resultBlock}>
              <div className={styles.resultBlockLabel}>PEE Stats</div>
              <div className={styles.statRow}>
                <span>Bits embedded:</span>
                <span className={styles.statVal}>{result.bits_embedded?.toLocaleString()}</span>
              </div>
              <div className={styles.statRow}>
                <span>Image shape:</span>
                <span className={styles.statVal}>{result.image_shape?.join(' × ')} px</span>
              </div>
            </div>

            <div className={styles.keySection}>
              <div className={styles.keyBox}>
                <div className={styles.keyLabel}>
                  <svg width="12" height="12" fill="none" viewBox="0 0 24 24">
                    <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"
                      stroke="#00ff88" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  Text Decryption Key
                </div>
                <div className={styles.keyValue}>{result.text_key}</div>
                <CopyBtn value={result.text_key} />
              </div>

              <div className={styles.keyBox}>
                <div className={styles.keyLabel}>
                  <svg width="12" height="12" fill="none" viewBox="0 0 24 24">
                    <rect x="3" y="3" width="18" height="18" rx="2" stroke="#00d4ff" strokeWidth="2"/>
                    <path d="M9 9h6M9 12h6M9 15h4" stroke="#00d4ff" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  Image Decryption Key
                </div>
                <div className={styles.keyValue}>{result.image_key}</div>
                <CopyBtn value={result.image_key} />
              </div>
            </div>

            <button className={styles.downloadBtn} onClick={downloadDicom}>
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"
                  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Download Encrypted DICOM
            </button>

            <div className={styles.keyWarning}>
              ⚠ Save both keys. They are required for decryption and cannot be recovered.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Decrypt Panel ────────────────────────────────────────────────────────────

function DecryptPanel() {
  const [dicomFile, setDicomFile] = useState(null);
  const [textKey, setTextKey]   = useState('');
  const [imageKey, setImageKey] = useState('');
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState('');
  const [currentStep, setCurrentStep] = useState(0);

  const steps = [
    'Load Encrypted DICOM',
    'Decrypt Image Pixels',
    'PEE Extraction',
    'Unpack Payload',
    'Decrypt Patient Text',
    'Restore DICOM',
  ];

  const handleDecrypt = async () => {
    if (!dicomFile) { setError('Please upload an encrypted DICOM file.'); return; }
    if (!textKey || !imageKey) { setError('Both decryption keys are required.'); return; }

    setError('');
    setLoading(true);
    setResult(null);
    setCurrentStep(0);

    const stepInterval = setInterval(() => {
      setCurrentStep(s => (s >= steps.length - 1 ? s : s + 1));
    }, 700);

    const fd = new FormData();
    fd.append('dicom_file', dicomFile);
    fd.append('text_key', textKey);
    fd.append('image_key', imageKey);

    try {
      const res = await axios.post(`${API}/decrypt`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      clearInterval(stepInterval);
      setCurrentStep(steps.length);
      setResult(res.data);
    } catch (e) {
      clearInterval(stepInterval);
      setError(e.response?.data?.error || e.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadRestoredDicom = () => {
    if (!result?.restored_dicom_b64) return;
    const bin = atob(result.restored_dicom_b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const blob = new Blob([arr], { type: 'application/dicom' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'restored_original.dcm';
    a.click();
  };

  return (
    <div className={styles.panel}>
      {/* Left */}
      <div className={styles.panelLeft}>
        <div className={styles.panelSection}>
          <div className={styles.panelSectionTitle}>
            <span className={styles.sectionNum}>01</span>
            Encrypted DICOM File
          </div>
          <DropZone label="Upload Encrypted DICOM (.dcm)" accept=".dcm,.dicom"
            file={dicomFile} onFile={setDicomFile} />
        </div>

        <div className={styles.panelSection}>
          <div className={styles.panelSectionTitle}>
            <span className={styles.sectionNum}>02</span>
            Decryption Keys
          </div>
          <div className={styles.keyInputGroup}>
            <div className={styles.formField}>
              <label className={styles.fieldLabel}>
                Text Decryption Key <span className={styles.req}>*</span>
              </label>
              <input type="text" value={textKey} onChange={e => setTextKey(e.target.value)}
                placeholder="Paste text key here..." className={styles.keyInput} />
            </div>
            <div className={styles.formField}>
              <label className={styles.fieldLabel}>
                Image Decryption Key <span className={styles.req}>*</span>
              </label>
              <input type="text" value={imageKey} onChange={e => setImageKey(e.target.value)}
                placeholder="Paste image key here..." className={styles.keyInput} />
            </div>
          </div>
        </div>

        {error && <div className={styles.errorBox}>{error}</div>}

        <button className={styles.actionBtn} onClick={handleDecrypt} disabled={loading}
          style={{ '--btn-color': 'var(--accent2)', '--btn-glow': 'var(--glow2)' }}>
          {loading ? <><Spinner /> Decrypting...</> : <>
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
              <rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" strokeWidth="2"/>
              <path d="M7 11V7a5 5 0 0110 0" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeDasharray="4 3"/>
            </svg>
            Decrypt & Recover Data
          </>}
        </button>
      </div>

      {/* Right */}
      <div className={styles.panelRight}>
        <div className={styles.panelSectionTitle}>
          <span className={styles.sectionNum}>03</span>
          Decryption Pipeline
        </div>

        <div className={styles.stepsContainer}>
          {steps.map((s, i) => (
            <Step key={s} num={i + 1} label={s}
              active={loading && currentStep === i}
              done={result ? true : currentStep > i} />
          ))}
        </div>

        {result && (
          <div className={styles.resultSection}>
            <div className={styles.resultTitle}>
              <span className={styles.successDot} style={{ background: 'var(--accent2)' }} />
              Decryption Complete
            </div>

            <div className={styles.resultBlock}>
              <div className={styles.resultBlockLabel}>Recovered Patient Data</div>
              <div className={styles.patientTextDisplay}>
                {result.patient_text?.split('\n').map((line, i) => (
                  <div key={i} className={styles.patientLine}>
                    <span className={styles.patientLineKey}>
                      {line.split(':')[0]}:
                    </span>
                    <span className={styles.patientLineVal}>
                      {line.split(':').slice(1).join(':').trim()}
                    </span>
                  </div>
                ))}
              </div>
              <CopyBtn value={result.patient_text} />
            </div>

            <button className={styles.downloadBtn}
              style={{ '--dl-color': 'var(--accent2)' }}
              onClick={downloadRestoredDicom}>
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"
                  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Download Restored DICOM
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function DicomPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('encrypt');

  return (
    <div className={styles.root}>
      {/* Header */}
      <header className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate('/')}>
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
            <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Home
        </button>
        <div className={styles.headerTitle}>
          <span className={styles.headerIcon}>⬡</span>
          <span>DICOM Cryptography Workstation</span>
        </div>
        <div className={styles.headerStatus}>
          <span className={styles.statusDot} />
          System Online
        </div>
      </header>

      {/* Tech badge row */}
      <div className={styles.techRow}>
        {['GAN Key Gen', 'Henon Map', 'Tent Map', 'Confusion Matrix', 'Diffusion Matrix', 'PEE Steganography', 'DICOM I/O'].map(t => (
          <span key={t} className={styles.techBadge}>{t}</span>
        ))}
      </div>

      {/* Tab bar */}
      <div className={styles.tabContainer}>
        <TabBar active={activeTab} onChange={setActiveTab} />
      </div>

      {/* Main content */}
      <main className={styles.main}>
        {activeTab === 'encrypt' ? <EncryptPanel /> : <DecryptPanel />}
      </main>
    </div>
  );
}