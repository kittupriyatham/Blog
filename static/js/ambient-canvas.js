/**
 * Ambient Living Quantum Canvas
 * Krishna Priyatham Portfolio & Blog Design System
 * 
 * Features:
 * - Ambient floating aurora glows (indigo & cyan)
 * - Micro-dot precision grid
 * - Interactive constellation particles with cursor proximity tracking
 * - GPU-efficient requestAnimationFrame loop with auto-pause on hidden tab
 * - Zero DOM layout disruption (fixed background, pointer-events: none)
 */

(function () {
  'use strict';

  if (typeof window === 'undefined') return;

  function initAmbientCanvas() {
    // Avoid double injection
    if (document.getElementById('ambient-canvas')) return;

    // Inject styles for background elements
    var style = document.createElement('style');
    style.id = 'ambient-canvas-styles';
    style.textContent = `
      #ambient-canvas-wrapper {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 0;
        overflow: hidden;
      }
      #ambient-canvas {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
      }
      .aurora-glow-blob {
        position: absolute;
        border-radius: 50%;
        filter: blur(100px);
        opacity: 0.16;
        pointer-events: none;
        animation: floatAuroraGlow 14s ease-in-out infinite alternate;
      }
      .aurora-glow-1 {
        top: -10%;
        right: 5%;
        width: 520px;
        height: 520px;
        background: radial-gradient(circle, #6366f1 0%, transparent 70%);
      }
      .aurora-glow-2 {
        bottom: 5%;
        left: -5%;
        width: 600px;
        height: 600px;
        background: radial-gradient(circle, #06b6d4 0%, transparent 70%);
        animation-delay: -7s;
      }
      .aurora-glow-3 {
        top: 45%;
        left: 45%;
        width: 380px;
        height: 380px;
        background: radial-gradient(circle, #8b5cf6 0%, transparent 70%);
        opacity: 0.10;
        animation-delay: -3.5s;
      }
      .grid-dot-overlay {
        position: fixed;
        inset: 0;
        background-image: radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px);
        background-size: 28px 28px;
        pointer-events: none;
        z-index: 1;
        mask-image: radial-gradient(ellipse at center, black 40%, transparent 85%);
        -webkit-mask-image: radial-gradient(ellipse at center, black 40%, transparent 85%);
      }
      body:not(.dark-mode) .grid-dot-overlay {
        background-image: radial-gradient(rgba(15, 23, 42, 0.06) 1px, transparent 1px);
      }
      body:not(.dark-mode) .aurora-glow-blob {
        opacity: 0.08;
      }
      @keyframes floatAuroraGlow {
        0% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(30px, -25px) scale(1.06); }
        100% { transform: translate(-25px, 25px) scale(0.95); }
      }
      @media (prefers-reduced-motion: reduce) {
        .aurora-glow-blob { animation: none !important; }
      }
    `;
    document.head.appendChild(style);

    // Create container
    var wrapper = document.createElement('div');
    wrapper.id = 'ambient-canvas-wrapper';
    wrapper.setAttribute('aria-hidden', 'true');

    // Aurora blobs
    var blob1 = document.createElement('div');
    blob1.className = 'aurora-glow-blob aurora-glow-1';
    var blob2 = document.createElement('div');
    blob2.className = 'aurora-glow-blob aurora-glow-2';
    var blob3 = document.createElement('div');
    blob3.className = 'aurora-glow-blob aurora-glow-3';
    wrapper.appendChild(blob1);
    wrapper.appendChild(blob2);
    wrapper.appendChild(blob3);

    // Grid overlay
    var gridOverlay = document.createElement('div');
    gridOverlay.className = 'grid-dot-overlay';
    wrapper.appendChild(gridOverlay);

    // Canvas
    var canvas = document.createElement('canvas');
    canvas.id = 'ambient-canvas';
    wrapper.appendChild(canvas);

    // Insert wrapper at the very beginning of body
    document.body.insertBefore(wrapper, document.body.firstChild);

    var ctx = canvas.getContext('2d');
    var width = 0;
    var height = 0;
    var particles = [];
    var mouse = { x: -2000, y: -2000, radius: 130 };
    var animFrameId = null;
    var isRunning = true;

    function resize() {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      buildParticles();
    }

    function buildParticles() {
      particles = [];
      // Budget particle count according to screen size
      var count = Math.min(Math.floor((width * height) / 18000), 70);
      var isDark = document.body.classList.contains('dark-mode') || document.documentElement.classList.contains('dark');
      
      for (var i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          radius: Math.random() * 1.6 + 0.9,
          isCyan: Math.random() > 0.45
        });
      }
    }

    window.addEventListener('resize', resize, { passive: true });

    window.addEventListener('mousemove', function (e) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    }, { passive: true });

    window.addEventListener('mouseleave', function () {
      mouse.x = -2000;
      mouse.y = -2000;
    }, { passive: true });

    // Handle tab visibility to pause RAF
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        isRunning = false;
        if (animFrameId) cancelAnimationFrame(animFrameId);
      } else {
        if (!isRunning) {
          isRunning = true;
          animFrameId = requestAnimationFrame(render);
        }
      }
    });

    resize();

    function render() {
      if (!isRunning) return;
      ctx.clearRect(0, 0, width, height);

      var isDark = document.body.classList.contains('dark-mode') || document.documentElement.classList.contains('dark');
      var cyanBase = isDark ? 'rgba(6, 182, 212, ' : 'rgba(14, 165, 233, ';
      var indigoBase = isDark ? 'rgba(99, 102, 241, ' : 'rgba(79, 70, 229, ';

      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];

        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        // Interactive cursor gentle deflection
        var dx = mouse.x - p.x;
        var dy = mouse.y - p.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < mouse.radius) {
          var force = (1 - dist / mouse.radius) * 1.4;
          p.x -= (dx / dist) * force;
          p.y -= (dy / dist) * force;
        }

        // Draw particle dot
        var colorPrefix = p.isCyan ? cyanBase : indigoBase;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = colorPrefix + (isDark ? '0.65)' : '0.45)');
        ctx.fill();

        // Connect nearby nodes
        for (var j = i + 1; j < particles.length; j++) {
          var p2 = particles[j];
          var dxx = p.x - p2.x;
          var dyy = p.y - p2.y;
          var distance = Math.sqrt(dxx * dxx + dyy * dyy);

          if (distance < 115) {
            var alpha = (1 - distance / 115) * (isDark ? 0.20 : 0.12);
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = colorPrefix + alpha + ')';
            ctx.lineWidth = 0.75;
            ctx.stroke();
          }
        }
      }

      animFrameId = requestAnimationFrame(render);
    }

    animFrameId = requestAnimationFrame(render);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAmbientCanvas);
  } else {
    initAmbientCanvas();
  }
})();
