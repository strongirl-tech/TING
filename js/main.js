// Mobile navigation toggle
document.addEventListener('DOMContentLoaded', function() {
  const toggle = document.querySelector('.nav-toggle');
  const links = document.querySelector('.nav-links');

  if (toggle && links) {
    toggle.addEventListener('click', function() {
      links.classList.toggle('open');
    });
  }
});

// ═══════════════════════════════════════════════════
//  Botanical Leaf Particle System
//  飘落叶片粒子系统 — 轻盈、有机、层次丰富
// ═══════════════════════════════════════════════════
(function () {
  const canvas = document.getElementById('leaf-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let W = 0, H = 0;
  let leaves = [];
  let running = true;

  // ── Green tones: [R, G, B] ──
  const palette = [
    [42,  82,  57],   // deep forest
    [58,  107, 71],   // canopy green
    [74,  124, 90],   // botanical leaf
    [61,  130, 82],   // fresh mid-green
    [50,  95,  68],   // forest shadow
    [123, 174, 138],  // soft mint
    [90,  148, 108],  // medium leaf
    [35,  88,  55],   // evergreen
  ];

  function resize() {
    const hero = canvas.parentElement;
    W = canvas.width  = hero ? hero.offsetWidth  : window.innerWidth;
    H = canvas.height = hero ? hero.offsetHeight : window.innerHeight;
  }

  // ── Draw a single leaf (organic bezier ellipse) ──
  function drawLeaf(leaf) {
    const { x, y, size, angle, r, g, b, alpha, warp } = leaf;

    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.globalAlpha = alpha;

    // Body
    const w = size * (0.55 + warp * 0.2);
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.bezierCurveTo( w, -size * 0.35,  w,  size * 0.35, 0,  size);
    ctx.bezierCurveTo(-w,  size * 0.35, -w, -size * 0.35, 0, -size);
    ctx.closePath();
    ctx.fill();

    // Lighter inner highlight
    const lighter = `rgba(${Math.min(r + 50, 255)},${Math.min(g + 50, 255)},${Math.min(b + 45, 255)},0.18)`;
    ctx.fillStyle = lighter;
    ctx.beginPath();
    ctx.ellipse(0, -size * 0.15, w * 0.38, size * 0.52, 0, 0, Math.PI * 2);
    ctx.fill();

    // Central vein
    ctx.strokeStyle = `rgba(255,255,255,0.22)`;
    ctx.lineWidth = 0.55;
    ctx.beginPath();
    ctx.moveTo(0, -size * 0.88);
    ctx.lineTo(0,  size * 0.88);
    ctx.stroke();

    // Side veins (subtle)
    ctx.lineWidth = 0.35;
    ctx.strokeStyle = `rgba(255,255,255,0.12)`;
    for (let i = -1; i <= 1; i += 2) {
      ctx.beginPath();
      ctx.moveTo(0, -size * 0.3);
      ctx.quadraticCurveTo(i * w * 0.55, 0, i * w * 0.4, size * 0.4);
      ctx.stroke();
    }

    ctx.restore();
  }

  // ── Spawn a new leaf ──
  function spawn(yOverride) {
    const c = palette[Math.floor(Math.random() * palette.length)];
    const size = 4.5 + Math.random() * 10;
    return {
      x:       W * (0.04 + Math.random() * 0.92),
      y:       yOverride !== undefined ? yOverride : -size * 2,
      size,
      angle:   Math.random() * Math.PI * 2,
      rotSpd:  (Math.random() - 0.5) * 0.016,
      vx:      (Math.random() - 0.5) * 0.38,
      vy:      0.32 + Math.random() * 0.52,
      sway:    Math.random() * Math.PI * 2,
      swaySpd: 0.007 + Math.random() * 0.011,
      swayAmp: 0.55  + Math.random() * 1.15,
      r: c[0], g: c[1], b: c[2],
      alpha:    0,
      maxAlpha: 0.28 + Math.random() * 0.32,
      warp:     0.6  + Math.random() * 0.8,
    };
  }

  function init() {
    resize();
    // Pre-seed leaves already in flight
    for (let i = 0; i < 18; i++) {
      const leaf = spawn(Math.random() * H);
      leaf.alpha = leaf.maxAlpha * (0.3 + Math.random() * 0.7);
      leaves.push(leaf);
    }
    window.addEventListener('resize', () => {
      resize();
    });
    // Pause when tab hidden (save CPU)
    document.addEventListener('visibilitychange', () => {
      running = !document.hidden;
      if (running) tick();
    });
    tick();
  }

  function tick() {
    if (!running) return;
    requestAnimationFrame(tick);

    ctx.clearRect(0, 0, W, H);

    // Spawn logic: gently trickle in
    if (Math.random() < 0.014 && leaves.length < 24) {
      leaves.push(spawn());
    }

    leaves = leaves.filter(leaf => {
      // Physics
      leaf.sway  += leaf.swaySpd;
      leaf.x     += leaf.vx + Math.sin(leaf.sway) * leaf.swayAmp;
      leaf.y     += leaf.vy;
      leaf.angle += leaf.rotSpd;

      // Gentle fade-in
      if (leaf.alpha < leaf.maxAlpha) {
        leaf.alpha = Math.min(leaf.alpha + 0.003, leaf.maxAlpha);
      }

      // Cull off-screen
      if (leaf.y > H + 40 || leaf.x < -40 || leaf.x > W + 40) return false;

      drawLeaf(leaf);
      return true;
    });
  }

  init();
})();
