/* ============================================================
   AmpyPay — interactions & motion
   GSAP + ScrollTrigger · Lenis · Three.js
   Everything degrades gracefully: content is visible without JS,
   and animation only adds hidden states once libraries exist.
   ============================================================ */

(function () {
  'use strict';

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const hasGsap = typeof window.gsap !== 'undefined';
  const hasST = typeof window.ScrollTrigger !== 'undefined';
  const hasThree = typeof window.THREE !== 'undefined';
  const finePointer = window.matchMedia('(pointer: fine)').matches;

  if (hasGsap && hasST) gsap.registerPlugin(ScrollTrigger);

  /* ---------------- Smooth scroll (Lenis) ---------------- */
  let lenis = null;
  if (!reduced && typeof window.Lenis !== 'undefined' && hasGsap && hasST) {
    lenis = new Lenis({ duration: 1.1, smoothWheel: true });
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((time) => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
  }

  // Anchor navigation that respects Lenis
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const id = a.getAttribute('href');
      if (id.length < 2) return;
      const target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      closeMobileMenu();
      if (lenis) lenis.scrollTo(target, { offset: -70 });
      else target.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
    });
  });

  /* ---------------- Confidence rings setup ---------------- */
  document.querySelectorAll('.ring-val').forEach((c) => {
    const r = parseFloat(c.getAttribute('r'));
    const circ = 2 * Math.PI * r;
    c.style.setProperty('--circ', circ);
    c.dataset.circ = circ;
  });

  /* ---------------- Split text into masked words ---------------- */
  function splitWords(el) {
    const nodes = Array.from(el.childNodes);
    el.innerHTML = '';
    nodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        node.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { el.appendChild(document.createTextNode(' ')); return; }
          const w = document.createElement('span');
          w.className = 'w';
          const wi = document.createElement('span');
          wi.className = 'wi';
          wi.textContent = part;
          w.appendChild(wi);
          el.appendChild(w);
        });
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const wrap = document.createElement('span');
        wrap.className = node.className;
        if (node.style.cssText) wrap.style.cssText = node.style.cssText;
        node.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { wrap.appendChild(document.createTextNode(' ')); return; }
          const w = document.createElement('span');
          w.className = 'w';
          const wi = document.createElement('span');
          wi.className = 'wi';
          wi.textContent = part;
          w.appendChild(wi);
          wrap.appendChild(w);
        });
        el.appendChild(wrap);
      }
    });
    return el.querySelectorAll('.wi');
  }

  /* ---------------- Preloader + hero intro ---------------- */
  const preloader = document.getElementById('preloader');
  const heroTitle = document.getElementById('heroTitle');

  function heroIntro() {
    if (!hasGsap) return;
    const words = splitWords(heroTitle);
    gsap.set(words, { yPercent: 110 });
    const tl = gsap.timeline({ defaults: { ease: 'power4.out' } });
    tl.to(words, { yPercent: 0, duration: 1.1, stagger: 0.06 }, 0.1)
      .from('.hero-eyebrow', { opacity: 0, x: -24, duration: 0.8 }, 0.3)
      .from('#heroSub', { opacity: 0, y: 24, duration: 0.9 }, 0.55)
      .from('#heroCtas', { opacity: 0, y: 24, duration: 0.9 }, 0.7)
      .from('#heroBadges', { opacity: 0, y: 18, duration: 0.8 }, 0.85)
      .from('#mockPanel', { opacity: 0, y: 56, rotateX: 8, duration: 1.0, ease: 'power3.out' }, 0.3)
      .from('.float-chip', { opacity: 0, y: 26, scale: 0.92, duration: 0.8, stagger: 0.12 }, 0.9);
  }

  // Failsafe: never trap the page behind the preloader (e.g. throttled rAF)
  setTimeout(() => {
    if (preloader && preloader.style.display !== 'none') {
      preloader.style.transition = 'opacity 0.4s';
      preloader.style.opacity = '0';
      setTimeout(() => { preloader.style.display = 'none'; }, 450);
    }
  }, 4000);

  if (reduced || !hasGsap) {
    if (preloader) preloader.style.display = 'none';
  } else {
    const count = { v: 0 };
    const countEl = document.getElementById('preCount');
    const preTl = gsap.timeline({
      onComplete: () => {
        gsap.to(preloader, {
          yPercent: -100, duration: 0.8, ease: 'power4.inOut', delay: 0.1,
          onComplete: () => { preloader.style.display = 'none'; },
        });
        heroIntro();
      },
    });
    preTl.to(count, {
      v: 100, duration: 0.75, ease: 'power2.inOut',
      onUpdate: () => { countEl.textContent = Math.round(count.v); },
    })
      .from('.preloader-spinner', { scale: 0.7, opacity: 0, duration: 0.5, ease: 'back.out(1.7)' }, 0);
  }

  /* ---------------- Counters ---------------- */
  const animatedCounters = new WeakSet();
  function animateCounter(el) {
    if (!el || animatedCounters.has(el)) return;
    animatedCounters.add(el);
    const end = parseFloat(el.dataset.count);
    const decimals = parseInt(el.dataset.decimals || '0', 10);
    if (reduced || !hasGsap) { el.textContent = end.toFixed(decimals); return; }
    const obj = { v: 0 };
    gsap.to(obj, {
      v: end, duration: 1.6, ease: 'power2.out',
      onUpdate: () => { el.textContent = obj.v.toFixed(decimals); },
    });
  }

  const animatedRings = new WeakSet();
  function animateRing(circle) {
    if (!circle || animatedRings.has(circle)) return;
    animatedRings.add(circle);
    const circ = parseFloat(circle.dataset.circ);
    const ratio = parseFloat(circle.dataset.ring || '0.9');
    const target = circ * (1 - ratio);
    if (reduced || !hasGsap) { circle.style.strokeDashoffset = target; return; }
    gsap.to(circle, { strokeDashoffset: target, duration: 1.8, ease: 'power3.inOut' });
  }

  /* ---------------- Scroll-driven reveals ---------------- */
  if (hasGsap && hasST && !reduced) {

    // Generic fade-up reveals
    gsap.utils.toArray('[data-reveal]').forEach((el) => {
      gsap.from(el, {
        opacity: 0, y: 44, duration: 1, ease: 'power3.out',
        scrollTrigger: { trigger: el, start: 'top 88%', once: true },
      });
    });

    // Headline word reveals
    gsap.utils.toArray('[data-split]').forEach((el) => {
      const words = splitWords(el);
      gsap.set(words, { yPercent: 110 });
      gsap.to(words, {
        yPercent: 0, duration: 0.9, ease: 'power4.out', stagger: 0.045,
        scrollTrigger: { trigger: el, start: 'top 85%', once: true },
      });
    });

    // Counters + rings outside the hero
    gsap.utils.toArray('[data-count]').forEach((el) => {
      if (el.closest('.hero')) return;
      ScrollTrigger.create({
        trigger: el, start: 'top 88%', once: true,
        onEnter: () => animateCounter(el),
      });
    });
    gsap.utils.toArray('.ring-val').forEach((el) => {
      if (el.closest('.hero')) return;
      ScrollTrigger.create({
        trigger: el, start: 'top 85%', once: true,
        onEnter: () => animateRing(el),
      });
    });

    const mm = gsap.matchMedia();

    // Compliance collage: layered parallax (desktop overlap layout only)
    mm.add('(min-width: 961px)', () => {
      const tweens = [
        ['.comp-shot--audit', -40],
        ['.comp-shot--tax', -90],
        ['.comp-shot--receipt', -140],
      ].map(([sel, dist]) => gsap.to(sel, {
        y: dist, ease: 'none',
        scrollTrigger: {
          trigger: '.comp-visuals', start: 'top bottom', end: 'bottom top', scrub: 1,
        },
      }));
      return () => tweens.forEach((t) => { t.scrollTrigger && t.scrollTrigger.kill(); t.kill(); });
    });

    // Hero parallax on scroll
    gsap.to('.hero-visual', {
      y: -60, ease: 'none',
      scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true },
    });
    gsap.to('.hero-content', {
      y: 40, opacity: 0.4, ease: 'none',
      scrollTrigger: { trigger: '.hero', start: '40% top', end: 'bottom top', scrub: true },
    });

    // Recompute trigger positions once images finish loading
    window.addEventListener('load', () => ScrollTrigger.refresh());

    // Floating chips idle motion
    gsap.utils.toArray('.float-chip').forEach((chip, i) => {
      gsap.to(chip, {
        y: i % 2 ? 12 : -12, duration: 2.6 + i * 0.4,
        ease: 'sine.inOut', yoyo: true, repeat: -1, delay: i * 0.3,
      });
    });
  } else {
    // No animation environment: make sure final values render
    document.querySelectorAll('[data-count]').forEach(animateCounter);
    document.querySelectorAll('.ring-val').forEach(animateRing);
  }

  /* ---------------- Nav state + mobile menu ---------------- */
  const nav = document.getElementById('nav');
  const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 24);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  const burger = document.getElementById('navBurger');
  const mobileMenu = document.getElementById('mobileMenu');
  function closeMobileMenu() {
    burger.classList.remove('open');
    mobileMenu.classList.remove('open');
    burger.setAttribute('aria-expanded', 'false');
    mobileMenu.setAttribute('aria-hidden', 'true');
    if (lenis) lenis.start();
  }
  burger.addEventListener('click', () => {
    const open = !mobileMenu.classList.contains('open');
    burger.classList.toggle('open', open);
    mobileMenu.classList.toggle('open', open);
    burger.setAttribute('aria-expanded', String(open));
    mobileMenu.setAttribute('aria-hidden', String(!open));
    if (lenis) open ? lenis.stop() : lenis.start();
  });

  /* ---------------- Custom cursor ---------------- */
  if (finePointer && !reduced && hasGsap) {
    const cursor = document.getElementById('cursor');
    const dot = document.getElementById('cursorDot');
    const pos = { x: innerWidth / 2, y: innerHeight / 2 };
    const target = { x: pos.x, y: pos.y };
    window.addEventListener('mousemove', (e) => {
      target.x = e.clientX; target.y = e.clientY;
      gsap.set(dot, { x: e.clientX, y: e.clientY });
    });
    gsap.ticker.add(() => {
      pos.x += (target.x - pos.x) * 0.14;
      pos.y += (target.y - pos.y) * 0.14;
      gsap.set(cursor, { x: pos.x, y: pos.y });
    });
    document.querySelectorAll('a, button, .chip, .conf-card, .exc-card').forEach((el) => {
      el.addEventListener('mouseenter', () => cursor.classList.add('is-hover'));
      el.addEventListener('mouseleave', () => cursor.classList.remove('is-hover'));
    });
  }

  /* ---------------- Magnetic buttons ---------------- */
  if (finePointer && !reduced && hasGsap) {
    document.querySelectorAll('[data-magnetic]').forEach((btn) => {
      btn.addEventListener('mousemove', (e) => {
        const r = btn.getBoundingClientRect();
        const x = e.clientX - r.left - r.width / 2;
        const y = e.clientY - r.top - r.height / 2;
        gsap.to(btn, { x: x * 0.3, y: y * 0.35, duration: 0.4, ease: 'power3.out' });
      });
      btn.addEventListener('mouseleave', () => {
        gsap.to(btn, { x: 0, y: 0, duration: 0.7, ease: 'elastic.out(1, 0.4)' });
      });
    });
  }

  /* ---------------- Hero panel tilt ---------------- */
  if (finePointer && !reduced && hasGsap) {
    const visual = document.getElementById('heroVisual');
    const panel = document.getElementById('mockPanel');
    if (visual && panel) {
      visual.addEventListener('mousemove', (e) => {
        const r = visual.getBoundingClientRect();
        const rx = ((e.clientY - r.top) / r.height - 0.5) * -7;
        const ry = ((e.clientX - r.left) / r.width - 0.5) * 9;
        gsap.to(panel, { rotateX: rx, rotateY: ry, duration: 0.6, ease: 'power2.out' });
      });
      visual.addEventListener('mouseleave', () => {
        gsap.to(panel, { rotateX: 0, rotateY: 0, duration: 0.9, ease: 'power3.out' });
      });
    }
  }

  /* ============================================================
     THREE.JS — hero particle wave
     ============================================================ */
  function webglAvailable() {
    try {
      const c = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl')));
    } catch (e) { return false; }
  }

  function initThreeJS() {
    if (!window.THREE || !webglAvailable()) return;
    {
    const canvas = document.getElementById('hero-canvas');
    if (canvas) {
      const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      const scene = new THREE.Scene();
      scene.fog = new THREE.Fog(0x0a1f44, 10, 34);
      const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
      camera.position.set(0, 5.2, 13);
      camera.lookAt(0, 0, 0);

      const COLS = 130, ROWS = 70;
      const count = COLS * ROWS;
      const positions = new Float32Array(count * 3);
      let i = 0;
      for (let xi = 0; xi < COLS; xi++) {
        for (let yi = 0; yi < ROWS; yi++) {
          positions[i * 3] = (xi / (COLS - 1) - 0.5) * 44;
          positions[i * 3 + 1] = 0;
          positions[i * 3 + 2] = (yi / (ROWS - 1) - 0.5) * 26;
          i++;
        }
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      const mat = new THREE.PointsMaterial({
        color: 0x2563ea, size: 0.05, transparent: true, opacity: 0.75,
        blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
      });
      const points = new THREE.Points(geo, mat);
      points.position.y = -2.2;
      scene.add(points);

      const mouse = { x: 0, y: 0 };
      if (finePointer) {
        window.addEventListener('mousemove', (e) => {
          mouse.x = (e.clientX / innerWidth - 0.5) * 2;
          mouse.y = (e.clientY / innerHeight - 0.5) * 2;
        });
      }

      function resize() {
        const w = canvas.clientWidth, h = canvas.clientHeight;
        if (canvas.width !== w * renderer.getPixelRatio() || canvas.height !== h * renderer.getPixelRatio()) {
          renderer.setSize(w, h, false);
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
        }
      }

      let visible = true;
      new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0 })
        .observe(canvas);

      let t = 0;
      function tick() {
        requestAnimationFrame(tick);
        if (!visible) return;
        resize();
        t += reduced ? 0 : 0.012;
        const pos = geo.attributes.position.array;
        for (let p = 0; p < count; p++) {
          const x = pos[p * 3], z = pos[p * 3 + 2];
          pos[p * 3 + 1] =
            Math.sin(x * 0.32 + t) * 0.55 +
            Math.cos(z * 0.38 + t * 0.85) * 0.45 +
            Math.sin((x + z) * 0.18 + t * 0.6) * 0.3;
        }
        geo.attributes.position.needsUpdate = true;
        camera.position.x += (mouse.x * 1.6 - camera.position.x) * 0.04;
        camera.position.y += (5.2 - mouse.y * 0.9 - camera.position.y) * 0.04;
        camera.lookAt(0, 0, 0);
        renderer.render(scene, camera);
      }
      tick();
    }

    /* ============================================================
       THREE.JS — security globe with data-center arcs
       ============================================================ */
    const globeCanvas = document.getElementById('globe-canvas');
    if (globeCanvas) {
      const renderer2 = new THREE.WebGLRenderer({ canvas: globeCanvas, alpha: true, antialias: true });
      renderer2.setPixelRatio(Math.min(devicePixelRatio, 2));
      const scene2 = new THREE.Scene();
      const camera2 = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
      camera2.position.set(0, 0.6, 7.2);
      camera2.lookAt(0, 0, 0);

      const globe = new THREE.Group();
      globe.rotation.z = 0.18;
      scene2.add(globe);

      const R = 2.5;
      function latLon(lat, lon, radius) {
        const phi = (90 - lat) * (Math.PI / 180);
        const theta = (lon + 180) * (Math.PI / 180);
        return new THREE.Vector3(
          -radius * Math.sin(phi) * Math.cos(theta),
          radius * Math.cos(phi),
          radius * Math.sin(phi) * Math.sin(theta)
        );
      }

      // Land mask: rasterise bundled Natural Earth polygons (js/world-land.js)
      // onto an offscreen equirectangular canvas, then sample per dot.
      function buildLandTest() {
        if (!window.WORLD_LAND) return null;
        const W = 1024, H = 512;
        const cv = document.createElement('canvas');
        cv.width = W; cv.height = H;
        const ctx = cv.getContext('2d');
        ctx.fillStyle = '#fff';
        window.WORLD_LAND.forEach((rings) => {
          ctx.beginPath();
          rings.forEach((ring) => {
            ring.forEach(([lon, lat], i) => {
              const x = ((lon + 180) / 360) * W;
              const y = ((90 - lat) / 180) * H;
              i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
            });
            ctx.closePath();
          });
          ctx.fill('evenodd');
        });
        const px = ctx.getImageData(0, 0, W, H).data;
        return (lat, lon) => {
          const x = Math.min(W - 1, Math.max(0, Math.round(((lon + 180) / 360) * W)));
          const y = Math.min(H - 1, Math.max(0, Math.round(((90 - lat) / 180) * H)));
          return px[(y * W + x) * 4 + 3] > 0;
        };
      }
      const isLand = buildLandTest();

      // Dotted sphere (fibonacci distribution) — bright dots on land
      // (continents), faint sparse dots on ocean to keep the silhouette.
      const DOTS = isLand ? 14000 : 2400;
      const landPts = [], oceanPts = [];
      const golden = Math.PI * (3 - Math.sqrt(5));
      for (let d = 0; d < DOTS; d++) {
        const y = 1 - (d / (DOTS - 1)) * 2;
        const rad = Math.sqrt(1 - y * y);
        const th = golden * d;
        const px = Math.cos(th) * rad * R;
        const py = y * R;
        const pz = Math.sin(th) * rad * R;
        if (isLand) {
          // Invert latLon(): x = -sinφcosθ, z = sinφsinθ, θ = lon + 180
          const lat = 90 - Math.acos(py / R) * (180 / Math.PI);
          const lon = ((Math.atan2(pz, -px) * (180 / Math.PI) - 180) + 540) % 360 - 180;
          if (isLand(lat, lon)) { landPts.push(px, py, pz); continue; }
          if (d % 7 === 0) oceanPts.push(px, py, pz);
        } else {
          landPts.push(px, py, pz);
        }
      }
      function addDots(pts, color, size, opacity) {
        if (!pts.length) return;
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pts), 3));
        globe.add(new THREE.Points(g, new THREE.PointsMaterial({
          color, size, transparent: true, opacity, depthWrite: false,
        })));
      }
      addDots(landPts, 0x5d8bf4, 0.032, 0.85);
      addDots(oceanPts, 0x3b74f0, 0.022, 0.18);

      // Data-center markers: US (Dallas), France (Paris), Thailand (Bangkok), Singapore
      const sites = [
        latLon(32.8, -96.8, R),
        latLon(48.85, 2.35, R),
        latLon(13.75, 100.5, R),
        latLon(1.35, 103.8, R),
      ];
      const markerGeo = new THREE.SphereGeometry(0.06, 12, 12);
      const markerMat = new THREE.MeshBasicMaterial({ color: 0x6e96f5 });
      const haloMat = new THREE.MeshBasicMaterial({ color: 0x2563ea, transparent: true, opacity: 0.35 });
      const halos = [];
      sites.forEach((v) => {
        const m = new THREE.Mesh(markerGeo, markerMat);
        m.position.copy(v);
        globe.add(m);
        const halo = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 12), haloMat.clone());
        halo.position.copy(v);
        globe.add(halo);
        halos.push(halo);
      });

      // Arcs between regions (France↔US, France↔Thailand, Thailand↔Singapore)
      const pairs = [[1, 0], [1, 2], [2, 3]];
      pairs.forEach(([a, b]) => {
        const va = sites[a], vb = sites[b];
        const mid = va.clone().add(vb).multiplyScalar(0.5).normalize()
          .multiplyScalar(R * (1.18 + va.distanceTo(vb) * 0.07));
        const curve = new THREE.QuadraticBezierCurve3(va, mid, vb);
        const pts = curve.getPoints(64);
        const arcGeo = new THREE.BufferGeometry().setFromPoints(pts);
        const arc = new THREE.Line(arcGeo, new THREE.LineBasicMaterial({
          color: 0x2563ea, transparent: true, opacity: 0.55,
        }));
        globe.add(arc);
      });

      function resize2() {
        const w = globeCanvas.clientWidth, h = globeCanvas.clientHeight;
        if (globeCanvas.width !== w * renderer2.getPixelRatio() || globeCanvas.height !== h * renderer2.getPixelRatio()) {
          renderer2.setSize(w, h, false);
          camera2.aspect = w / h;
          camera2.updateProjectionMatrix();
        }
      }

      let visible2 = false;
      new IntersectionObserver(([e]) => { visible2 = e.isIntersecting; }, { threshold: 0 })
        .observe(globeCanvas);

      let t2 = 0;
      function tick2() {
        requestAnimationFrame(tick2);
        if (!visible2) return;
        resize2();
        if (!reduced) {
          t2 += 0.016;
          globe.rotation.y += 0.0016;
          halos.forEach((h, idx) => {
            const s = 1 + Math.sin(t2 * 2.4 + idx * 1.4) * 0.35;
            h.scale.setScalar(s);
            h.material.opacity = 0.18 + Math.abs(Math.sin(t2 * 2.4 + idx * 1.4)) * 0.25;
          });
        }
        renderer2.render(scene2, camera2);
      }
      tick2();
    }
  }
  }

  if (hasThree) {
    initThreeJS();
  } else {
    const heroImg = document.getElementById('mockPanel');
    function _loadThree() {
      function _s(src, cb) {
        const s = document.createElement('script');
        s.src = src; s.onload = cb;
        document.body.appendChild(s);
      }
      _s('js/vendor/three.min.js', () => _s('js/world-land.js', initThreeJS));
    }
    if (heroImg && heroImg.complete && heroImg.naturalWidth) {
      _loadThree();
    } else if (heroImg) {
      heroImg.addEventListener('load', _loadThree, { once: true });
      heroImg.addEventListener('error', _loadThree, { once: true });
    } else {
      window.addEventListener('load', _loadThree, { once: true });
    }
  }

  /* ============================================================
     DEMO MODAL
     ============================================================ */
  const BACKEND = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:3001'
    : 'https://ampypay-backend.onrender.com';
  const DEMO_API = BACKEND + '/api/demo';

  const overlay   = document.getElementById('demoOverlay');
  const demoForm  = document.getElementById('demoForm');
  const demoClose = document.getElementById('demoClose');
  const demoSuccess = document.getElementById('demoSuccess');
  const demoSubmit  = document.getElementById('demoSubmit');

  function openDemoModal() {
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    overlay.querySelector('input:not([type=hidden]):not([style])').focus();
  }
  function closeDemoModal() {
    overlay.hidden = true;
    document.body.style.overflow = '';
  }

  document.querySelectorAll('[data-demo]').forEach((el) => {
    el.addEventListener('click', (e) => { e.preventDefault(); openDemoModal(); });
  });

  demoClose.addEventListener('click', closeDemoModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDemoModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !overlay.hidden) closeDemoModal(); });

  function setError(id, msg) {
    const el = document.getElementById(id);
    if (el) el.textContent = msg;
  }
  function clearErrors() {
    ['errName','errCompany','errEmail','errGlobal'].forEach(id => setError(id, ''));
    demoForm.querySelectorAll('.is-error').forEach(el => el.classList.remove('is-error'));
  }

  demoForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();

    const name    = document.getElementById('demoName').value.trim();
    const company = document.getElementById('demoCompany').value.trim();
    const email   = document.getElementById('demoEmail').value.trim();
    const phone   = document.getElementById('demoPhone').value.trim();
    const hp      = demoForm.querySelector('[name="_hp"]').value;

    let valid = true;
    if (!name)    { setError('errName', 'Required'); document.getElementById('demoName').classList.add('is-error'); valid = false; }
    if (!company) { setError('errCompany', 'Required'); document.getElementById('demoCompany').classList.add('is-error'); valid = false; }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('errEmail', 'Valid email required');
      document.getElementById('demoEmail').classList.add('is-error');
      valid = false;
    }
    if (!valid) return;

    demoSubmit.disabled = true;
    demoSubmit.textContent = 'Sending…';

    try {
      const res = await fetch(DEMO_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, company, email, phone, _hp: hp }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError('errGlobal', data.error || 'Something went wrong. Please try again.');
        demoSubmit.disabled = false;
        demoSubmit.textContent = 'Request a demo';
        return;
      }
      demoForm.hidden = true;
      demoSuccess.hidden = false;
      document.getElementById('demoSuccessEmail').textContent = email;
    } catch {
      setError('errGlobal', 'Network error. Please check your connection and try again.');
      demoSubmit.disabled = false;
      demoSubmit.textContent = 'Request a demo';
    }
  });

})();
