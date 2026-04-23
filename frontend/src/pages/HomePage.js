import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './HomePage.module.css';

// ── Animated grid background
function GridCanvas() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let raf;
    let t = 0;

    function resize() {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const sz = 48;
      ctx.strokeStyle = 'rgba(26,58,85,0.5)';
      ctx.lineWidth = 1;

      for (let x = 0; x < canvas.width + sz; x += sz) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height + sz; y += sz) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Scanline pulse
      const slY = (t * 0.4) % canvas.height;
      const grad = ctx.createLinearGradient(0, slY - 60, 0, slY + 60);
      grad.addColorStop(0,   'transparent');
      grad.addColorStop(0.5, 'rgba(0,212,255,0.04)');
      grad.addColorStop(1,   'transparent');
      ctx.fillStyle = grad;
      ctx.fillRect(0, slY - 60, canvas.width, 120);

      t++;
      raf = requestAnimationFrame(draw);
    }
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={canvasRef} className={styles.gridCanvas} />;
}

// ── Rotating hex ring decoration
function HexRing({ size = 120, color = '#00d4ff', opacity = 0.15 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" className={styles.hexRing}
      style={{ '--ring-color': color, '--ring-opacity': opacity }}>
      <polygon points="60,5 109,32.5 109,87.5 60,115 11,87.5 11,32.5"
        fill="none" stroke={color} strokeWidth="1" opacity={opacity} />
      <polygon points="60,18 97,39 97,81 60,102 23,81 23,39"
        fill="none" stroke={color} strokeWidth="0.5" opacity={opacity * 0.6} />
    </svg>
  );
}

// ── Floating feature card
function FeatureCard({ icon, title, desc, delay }) {
  return (
    <div className={styles.featureCard} style={{ animationDelay: delay }}>
      <div className={styles.featureIcon}>{icon}</div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const [showBox, setShowBox] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setShowBox(true), 600);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className={styles.root}>
      <GridCanvas />

      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoMark}>⬡</span>
          <span className={styles.logoText}>MED<span>CRYPT</span></span>
        </div>
        <nav className={styles.nav}>
          <a href="#features">Features</a>
          <a href="#pipeline">Pipeline</a>
          <button className={styles.navCta} onClick={() => navigate('/dicom')}>
            Launch System
          </button>
        </nav>
      </header>

      {/* ── Hero ── */}
      <section className={styles.hero}>
        <div className={styles.heroBadge}>
          <span className={styles.heroBadgeDot} />
          GAN · Henon Map · Tent Map · PEE Steganography
        </div>

        <h1 className={styles.heroTitle}>
          <span className={styles.heroLine1}>MEDICAL IMAGE</span>
          <span className={styles.heroLine2}>CRYPTOGRAPHY</span>
          <span className={styles.heroLine3}>SYSTEM</span>
        </h1>

        <p className={styles.heroSub}>
          Encrypt patient data with confusion–diffusion matrices.
          Embed ciphertext inside DICOM images using Prediction Error Expansion.
          GAN-generated keys expanded via chaotic maps.
        </p>

        <div className={styles.heroActions}>
          <button className={styles.primaryBtn} onClick={() => navigate('/dicom')}>
            <span>Open DICOM Workstation</span>
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24">
              <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <button className={styles.secondaryBtn} onClick={() => document.getElementById('features').scrollIntoView({behavior:'smooth'})}>
            Learn More
          </button>
        </div>

        <div className={styles.heroStats}>
          <div className={styles.stat}><span>256-bit</span><small>GAN Keys</small></div>
          <div className={styles.statDiv} />
          <div className={styles.stat}><span>2-Layer</span><small>Confusion + Diffusion</small></div>
          <div className={styles.statDiv} />
          <div className={styles.stat}><span>PEE</span><small>Lossless Embedding</small></div>
          <div className={styles.statDiv} />
          <div className={styles.stat}><span>DICOM</span><small>Medical Standard</small></div>
        </div>
      </section>

      {/* ── Pipeline diagram ── */}
      <section id="pipeline" className={styles.pipelineSection}>
        <h2 className={styles.sectionTitle}>Encryption Pipeline</h2>
        <div className={styles.pipeline}>
          {[
            { n: '01', label: 'GAN Key Gen', sub: 'Generator + Discriminator' },
            { n: '02', label: 'Chaotic Expansion', sub: 'Henon Map + Tent Map' },
            { n: '03', label: 'Confusion', sub: 'Chaotic S-Box substitution' },
            { n: '04', label: 'Diffusion', sub: 'Permutation + XOR stream' },
            { n: '05', label: 'PEE Embed', sub: 'Prediction Error Expansion' },
            { n: '06', label: 'Image Encrypt', sub: 'Pixel permutation + XOR' },
          ].map((step, i) => (
            <React.Fragment key={step.n}>
              <div className={styles.pipeStep}>
                <div className={styles.pipeNum}>{step.n}</div>
                <div className={styles.pipeLabel}>{step.label}</div>
                <div className={styles.pipeSub}>{step.sub}</div>
              </div>
              {i < 5 && <div className={styles.pipeArrow}>→</div>}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className={styles.featuresSection}>
        <h2 className={styles.sectionTitle}>System Capabilities</h2>
        <div className={styles.featuresGrid}>
          <FeatureCard delay="0ms"
            icon="⬡"
            title="GAN Key Generation"
            desc="Adversarial generator-discriminator loop produces statistically optimal 256-byte cryptographic keys with high entropy." />
          <FeatureCard delay="80ms"
            icon="∿"
            title="Chaotic Maps"
            desc="Henon and Tent map chaotic sequences derive S-Box and permutation patterns that are sensitive to initial conditions." />
          <FeatureCard delay="160ms"
            icon="⊕"
            title="Confusion Layer"
            desc="Chaotic S-Box substitution maps each byte through a dynamically generated 256-element bijective substitution table." />
          <FeatureCard delay="240ms"
            icon="⟲"
            title="Diffusion Layer"
            desc="Fisher-Yates shuffle seeded by Tent map permutes byte positions, then XOR stream cipher applies Henon keystream." />
          <FeatureCard delay="320ms"
            icon="▦"
            title="PEE Steganography"
            desc="Prediction Error Expansion with MED predictor embeds encrypted patient data invisibly inside DICOM pixel data." />
          <FeatureCard delay="400ms"
            icon="⬛"
            title="DICOM Compliant"
            desc="Output is a valid DICOM file. Metadata stored in private tags. Fully reversible — original image recovered on decryption." />
        </div>
      </section>

      {/* ── Floating CTA Box ── */}
      <div className={`${styles.floatingBox} ${showBox ? styles.floatingBoxVisible : ''}`}>
        <div className={styles.floatingBoxGlow} />
        <div className={styles.floatingBoxInner}>
          <div className={styles.floatingBoxBadge}>DICOM WORKSTATION</div>
          <h3>Ready to encrypt?</h3>
          <p>Upload a DICOM brain scan and enter patient data to begin the encryption pipeline.</p>
          <button className={styles.floatingBoxBtn} onClick={() => navigate('/dicom')}>
            <span>Open DICOM System</span>
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
              <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <div className={styles.floatingBoxFooter}>
            <span className={styles.onlineDot} />
            API online
          </div>
        </div>
      </div>

      {/* ── Footer ── */}
      <footer className={styles.footer}>
        <span>MedCrypt © 2024 — Medical Cryptography Research System</span>
        <span>GAN · Henon Map · Tent Map · PEE · DICOM</span>
      </footer>
    </div>
  );
}