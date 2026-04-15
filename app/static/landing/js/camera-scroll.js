/**
 * camera-scroll.js
 * ─────────────────
 * Core scrollytelling engine for the DEMACIA HONOR hero.
 * - Fetches frame manifest and preloads all images
 * - Renders frames on a sticky <canvas> synchronized to scroll progress
 * - Handles "contain" aspect-ratio drawing, DPR scaling, and resize
 * - Controls narrative overlay visibility based on scroll position
 */

(function () {
    'use strict';

    // ─── DOM References ───
    const container = document.getElementById('camera-scroll-container');
    const canvas = document.getElementById('camera-canvas');
    const maskGlow = document.getElementById('camera-glow'); // New ref
    const loader = document.getElementById('camera-loader');
    const progressBar = document.getElementById('camera-progress-bar');
    const progressTxt = document.getElementById('camera-progress-text');
    const scrollHint = document.getElementById('scroll-indicator');
    const ctx = canvas ? canvas.getContext('2d') : null;

    // ... (rest of DOM refs) ...

    // ... (state, config, helpers) ...

    // ─── Render Loop Update ───
    function renderLoop() {
        if (state.isReady) {
            const frameIndex = Math.min(
                Math.round(state.progress * (state.totalFrames - 1)),
                state.totalFrames - 1
            );
            drawFrame(frameIndex);
            updateOverlays(state.progress);

            // Update Glow Intensity
            if (maskGlow) {
                // Opacity increases from 0.1 to 0.8 based on progress
                const glowOpacity = 0.1 + (state.progress * 0.7);
                // Scale pulses slightly and grows
                const glowScale = 1 + (state.progress * 0.2);

                maskGlow.style.opacity = glowOpacity.toFixed(2);
                maskGlow.style.transform = `translateZ(0) scale(${glowScale.toFixed(2)})`;

                // Optional: Change color slightly towards end (more cyan -> white)
                // maskGlow.style.background = ...
            }
        }
        state.rafId = requestAnimationFrame(renderLoop);
    }

    // ... (initScrollTrigger and initFallbackScroll use this loop) ...

    // Overlays
    const overlay1 = document.getElementById('overlay-1');
    const overlay2 = document.getElementById('overlay-2');
    const overlay3 = document.getElementById('overlay-3');
    const overlay4 = document.getElementById('overlay-4');

    if (!container || !canvas || !ctx) {
        console.error('[CameraScroll] Missing required DOM elements.');
        return;
    }

    // ─── State (refs — mutable, no re-render) ───
    const state = {
        frames: [],          // Image[] — preloaded images
        totalFrames: 0,
        currentFrame: -1,    // Last drawn frame index
        isReady: false,
        rafId: null,
        progress: 0,         // 0..1 scroll progress
    };

    // ─── Config ───
    const DPR_CAP = 2;
    const MANIFEST_URL = '/frames/manifest.json';

    // ─── Helpers ───

    /**
     * Get capped device pixel ratio (≤2 on mobile to save GPU).
     */
    function getDPR() {
        const dpr = window.devicePixelRatio || 1;
        return Math.min(dpr, DPR_CAP);
    }

    /**
     * Size the canvas to match its CSS size × DPR.
     */
    function resizeCanvas() {
        const dpr = getDPR();
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.round(rect.width * dpr);
        canvas.height = Math.round(rect.height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        // Re-draw current frame after resize
        if (state.isReady && state.currentFrame >= 0) {
            drawFrame(state.currentFrame);
        }
    }

    /**
     * Draw an image on canvas using "contain" fitting.
     * The image is centered and scaled to fit fully inside the canvas.
     */
    function drawContain(img) {
        const cw = canvas.width / getDPR();
        const ch = canvas.height / getDPR();
        const iw = img.naturalWidth;
        const ih = img.naturalHeight;

        const scale = Math.min(cw / iw, ch / ih);
        const dw = iw * scale;
        const dh = ih * scale;
        const dx = (cw - dw) / 2;
        const dy = (ch - dh) / 2;

        ctx.clearRect(0, 0, cw, ch);
        ctx.drawImage(img, dx, dy, dw, dh);
    }

    /**
     * Draw a specific frame (by index) on the canvas.
     * Skips if same frame is already rendered (perf).
     */
    function drawFrame(index) {
        if (index === state.currentFrame) return;
        state.currentFrame = index;
        const img = state.frames[index];
        if (img && img.complete) {
            drawContain(img);
        }
    }

    // ─── Overlay Control ───

    /**
     * Update overlay visibility based on scroll progress (0..1).
     * Each overlay has a fade-in / visible / fade-out range.
     */
    function updateOverlays(progress) {
        const stages = [
            // Stage 1 (Title): Visible start (peak=0), longer duration (end=0.40)
            { el: overlay1, start: 0.00, peak: 0.00, end: 0.40 },
            // Stage 2: Earlier start, longer duration (overlaps with S1/S3)
            { el: overlay2, start: 0.20, peak: 0.35, end: 0.50 },
            // Stage 3: Earlier start, longer duration
            { el: overlay3, start: 0.50, peak: 0.65, end: 0.80 },
            // Stage 4 (Buttons): Start at 80%, stay visible indefinitely (end=1.2)
            { el: overlay4, start: 0.80, peak: 0.95, end: 1.20 },
        ];

        stages.forEach(({ el, start, peak, end }) => {
            if (!el) return;
            let opacity = 0;
            let ty = 20;       // translateY (px)
            let blur = 4;      // filter blur (px)

            // Special handling for Stage 1 (Title) to ensure it's visible at p=0
            if (peak === 0 && progress === 0) {
                opacity = 1;
                ty = 0;
                blur = 0;
            } else if (progress >= start && progress <= end) {
                if (progress < peak) {
                    // Fade in
                    const t = (progress - start) / (peak - start);
                    opacity = t;
                    ty = 20 * (1 - t);
                    blur = 4 * (1 - t);
                } else {
                    // Visible → fade out
                    const t = (progress - peak) / (end - peak);
                    // For buttons (Stage 4), likely want them to stay visible if end > 1
                    if (end > 1) {
                        opacity = 1;
                        ty = 0;
                        blur = 0;
                    } else {
                        opacity = 1 - t * 0.7; // Standard fade out
                        ty = 0;
                        blur = t * 2;
                        if (progress > end - 0.02) {
                            opacity = Math.max(0, 1 - ((progress - (end - 0.02)) / 0.02));
                        }
                    }
                }
            } else if (end > 1 && progress > end) {
                opacity = 1;
                ty = 0;
                blur = 0;
            }

            el.style.opacity = opacity;
            el.style.transform = `translateY(${ty}px)`;
            el.style.filter = blur > 0.1 ? `blur(${blur}px)` : 'none';
        });

        // Scroll indicator: visible only in first 10%, then fades
        if (scrollHint) {
            scrollHint.style.opacity = progress < 0.08 ? 1 - (progress / 0.08) * 0.7 : 0;
        }
    }

    // ─── Render Loop ───
    function renderLoop() {
        if (state.isReady) {
            const frameIndex = Math.min(
                Math.round(state.progress * (state.totalFrames - 1)),
                state.totalFrames - 1
            );
            drawFrame(frameIndex);
            updateOverlays(state.progress);

            // Update Glow Intensity
            if (maskGlow) {
                // Opacity increases from 0.1 to 0.8 based on progress
                const glowOpacity = 0.1 + (state.progress * 0.7);
                // Scale pulses slightly and grows
                const glowScale = 1 + (state.progress * 0.2);

                maskGlow.style.opacity = glowOpacity.toFixed(2);
                maskGlow.style.transform = `translateZ(0) scale(${glowScale.toFixed(2)})`;
            }
        }
        state.rafId = requestAnimationFrame(renderLoop);
    }

    // ─── Scroll → Frame Mapping (GSAP ScrollTrigger) ───

    function initScrollTrigger() {
        if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') {
            console.warn('[CameraScroll] GSAP/ScrollTrigger not loaded. Falling back to IntersectionObserver.');
            initFallbackScroll();
            return;
        }

        gsap.registerPlugin(ScrollTrigger);

        ScrollTrigger.create({
            trigger: container,
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.1,        // Ultra-smooth scrub (0.1s lag)
            onUpdate: (self) => {
                state.progress = self.progress;
            },
        });

        // Start the loop
        renderLoop();
    }

    /**
     * Fallback for environments without GSAP.
     */
    function initFallbackScroll() {
        function onScroll() {
            const rect = container.getBoundingClientRect();
            const scrollHeight = container.offsetHeight - window.innerHeight;
            const scrolled = -rect.top;
            state.progress = Math.max(0, Math.min(1, scrolled / scrollHeight));
        }

        window.addEventListener('scroll', onScroll, { passive: true });

        // Start the loop
        renderLoop();
    }

    // ─── Frame Preloading ───

    /**
     * Preload all frames from the manifest.
     * Returns a Promise that resolves when all images are loaded.
     */
    function preloadFrames(urls) {
        return new Promise((resolve) => {
            const images = new Array(urls.length);
            let loaded = 0;

            urls.forEach((url, i) => {
                const img = new Image();
                img.decoding = 'async';

                // Handle both success and error to ensure loader progresses
                img.onload = img.onerror = () => {
                    loaded++;
                    images[i] = img;

                    // Update progress UI
                    const pct = Math.round((loaded / urls.length) * 100);
                    if (progressBar) progressBar.style.width = pct + '%';
                    if (progressTxt) progressTxt.textContent = pct + '%';

                    if (loaded === urls.length) {
                        resolve(images);
                    }
                };

                img.src = url;
            });
        });
    }

    /**
     * Show error in loader UI when manifest fetch fails.
     */
    function showManifestError() {
        if (loader) {
            loader.innerHTML = `
        <div class="text-center space-y-4 px-6">
          <div class="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto">
            <svg class="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-white/90">Manifest no encontrado</h2>
          <p class="text-sm text-white/40 max-w-sm">
            Ejecuta <code class="px-2 py-0.5 bg-white/[0.06] rounded text-xs font-mono">npm run manifest</code> para generar el archivo de frames.
          </p>
        </div>
      `;
        }
    }

    // ─── Init ───

    async function init() {
        // DIAGNOSTIC START
        window.loadTimeout = setTimeout(() => {
            if (!state.isReady) {
                console.error('[CameraScroll] TIMEOUT: Init took > 8s');
                if (loader) loader.innerHTML = '<div class="text-center text-red-500 font-mono text-xs p-4">TIMEOUT: Check /frames/ access<br>Is NGINX proxying correctly?<br>Check Console (F12)</div>';
            }
        }, 8000);

        // 1. Size canvas
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        // 2. Fetch manifest
        let manifest;
        try {
            const resp = await fetch(MANIFEST_URL);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            manifest = await resp.json();
            if (!Array.isArray(manifest) || manifest.length === 0) {
                throw new Error('Empty manifest');
            }
        } catch (err) {
            console.error('[CameraScroll] Failed to load manifest:', err);
            showManifestError();
            return;
        }

        state.totalFrames = manifest.length;

        // 3. Preload all frames
        state.frames = await preloadFrames(manifest);

        // 4. Hide loader
        if (loader) {
            loader.style.opacity = '0';
            loader.style.pointerEvents = 'none';
            setTimeout(() => {
                loader.style.display = 'none';
            }, 700);
        }

        // 5. Show scroll indicator
        if (scrollHint) {
            scrollHint.style.opacity = '1';
        }

        // 6. Draw first frame
        state.isReady = true;

        // DIAGNOSTIC: Clear timeout if successful
        if (window.loadTimeout) clearTimeout(window.loadTimeout);

        drawFrame(0);
        updateOverlays(0);

        // 7. Init scroll → frame mapping
        initScrollTrigger();
    }

    // ─── Boot ───
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
