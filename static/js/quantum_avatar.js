/**
 * Quantum Avatar — Interactive 3D WebGL Hologram Badge & Orbital Rings
 * Built with Three.js for Potluri Krishna Priyatham (Kittu Priyatham)
 * PhD Scholar in Quantum Technologies @ SRM AP University
 */

(function () {
  function initQuantumAvatar(stageId, canvasContainerId) {
    var stage = document.getElementById(stageId);
    if (!stage) return;

    var canvasContainer = (canvasContainerId && document.getElementById(canvasContainerId)) || stage;

    // Check if WebGL is available
    function hasWebGL() {
      try {
        var canvas = document.createElement('canvas');
        return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
      } catch (e) {
        return false;
      }
    }

    if (!hasWebGL()) return;

    // Ensure Three.js is loaded
    if (typeof THREE === 'undefined') {
      var script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
      script.onload = function () { setupScene(stage, canvasContainer); };
      document.head.appendChild(script);
    } else {
      setupScene(stage, canvasContainer);
    }
  }

  function setupScene(stage, canvasContainer) {
    var width = stage.clientWidth || 280;
    var height = stage.clientHeight || 280;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 4.2;

    var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;

    // Style canvas
    renderer.domElement.style.position = 'absolute';
    renderer.domElement.style.top = '0';
    renderer.domElement.style.left = '0';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.pointerEvents = 'none';

    canvasContainer.innerHTML = '';
    canvasContainer.appendChild(renderer.domElement);

    var group = new THREE.Group();
    scene.add(group);

    // 1. Outer Glowing Bevel Ring framing the avatar badge perimeter
    var bevelGeo = new THREE.TorusGeometry(1.18, 0.03, 16, 100);
    var bevelMat = new THREE.MeshStandardMaterial({
      color: 0x818cf8,
      emissive: 0x4f46e5,
      emissiveIntensity: 0.75,
      metalness: 0.8,
      roughness: 0.2,
      transparent: true,
      opacity: 0.95
    });
    var bevelMesh = new THREE.Mesh(bevelGeo, bevelMat);
    group.add(bevelMesh);

    // 2. Nested Quantum Orbital Rings (Bloch / Atom Qubit geometry)
    var rings = [];
    var ringConfigs = [
      { radius: 1.44, tube: 0.016, color: 0x06b6d4, emissive: 0x0891b2, rotX: 0.95, rotY: 0.38, speed: 0.012 },
      { radius: 1.66, tube: 0.014, color: 0x818cf8, emissive: 0x6366f1, rotX: -0.72, rotY: 0.82, speed: -0.009 },
      { radius: 1.88, tube: 0.012, color: 0xf59e0b, emissive: 0xd97706, rotX: 1.25, rotY: -0.48, speed: 0.015 }
    ];

    ringConfigs.forEach(function (cfg) {
      var rGeo = new THREE.TorusGeometry(cfg.radius, cfg.tube, 16, 120);
      var rMat = new THREE.MeshStandardMaterial({
        color: cfg.color,
        emissive: cfg.emissive,
        emissiveIntensity: 0.85,
        metalness: 0.6,
        roughness: 0.2,
        transparent: true,
        opacity: 0.88
      });
      var ringMesh = new THREE.Mesh(rGeo, rMat);
      ringMesh.rotation.x = cfg.rotX;
      ringMesh.rotation.y = cfg.rotY;

      // Orbiting Quantum Particle / Electron
      var partGeo = new THREE.SphereGeometry(0.048, 16, 16);
      var partMat = new THREE.MeshStandardMaterial({
        color: cfg.color,
        emissive: cfg.color,
        emissiveIntensity: 1.3,
        roughness: 0.1
      });
      var particle = new THREE.Mesh(partGeo, partMat);
      particle.position.x = cfg.radius;
      ringMesh.add(particle);

      group.add(ringMesh);
      rings.push({ mesh: ringMesh, cfg: cfg, angle: Math.random() * Math.PI * 2, particle: particle });
    });

    // 3. Ambient Quantum Particle Cloud (Sparkles / Quantum foam)
    var particleCount = 45;
    var partGeom = new THREE.BufferGeometry();
    var positions = new Float32Array(particleCount * 3);
    var colors = new Float32Array(particleCount * 3);
    for (var i = 0; i < particleCount; i++) {
      var rad = 1.22 + Math.random() * 0.76;
      var theta = Math.random() * Math.PI * 2;
      var phi = (Math.random() - 0.5) * Math.PI * 0.7;
      positions[i * 3] = rad * Math.cos(theta) * Math.cos(phi);
      positions[i * 3 + 1] = rad * Math.sin(theta) * Math.cos(phi);
      positions[i * 3 + 2] = rad * Math.sin(phi);

      var mix = Math.random();
      colors[i * 3] = 0.05 * mix + 0.5 * (1 - mix);
      colors[i * 3 + 1] = 0.75 * mix + 0.55 * (1 - mix);
      colors[i * 3 + 2] = 1.0;
    }
    partGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    partGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    var partMaterial = new THREE.PointsMaterial({
      size: 0.038,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending
    });
    var pointCloud = new THREE.Points(partGeom, partMaterial);
    group.add(pointCloud);

    // 4. Ambient & Interactive 3D Lighting
    var ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
    scene.add(ambientLight);

    var pointLight = new THREE.PointLight(0x818cf8, 1.8, 20);
    pointLight.position.set(2, 3, 4);
    scene.add(pointLight);

    var cursorLight = new THREE.PointLight(0x06b6d4, 1.3, 10);
    cursorLight.position.set(0, 0, 3);
    scene.add(cursorLight);

    // 5. Mouse and Touch Parallax
    var targetRotX = 0;
    var targetRotY = 0;
    var isHovered = false;

    function onPointerMove(e) {
      var rect = stage.getBoundingClientRect();
      var clientX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      var clientY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0);

      var x = ((clientX - rect.left) / rect.width) * 2 - 1;
      var y = -(((clientY - rect.top) / rect.height) * 2 - 1);

      x = Math.max(-1.5, Math.min(1.5, x));
      y = Math.max(-1.5, Math.min(1.5, y));

      targetRotY = x * 0.42;
      targetRotX = -y * 0.42;

      cursorLight.position.x = x * 2.5;
      cursorLight.position.y = y * 2.5;
    }

    stage.addEventListener('mousemove', function (e) {
      isHovered = true;
      onPointerMove(e);
    });
    stage.addEventListener('mouseleave', function () {
      isHovered = false;
      targetRotX = 0;
      targetRotY = 0;
    });

    stage.addEventListener('touchmove', function (e) {
      isHovered = true;
      onPointerMove(e);
    }, { passive: true });
    stage.addEventListener('touchend', function () {
      isHovered = false;
      targetRotX = 0;
      targetRotY = 0;
    });

    // Also listen on parent card for wider interaction area
    var parentCard = stage.closest('section');
    if (parentCard) {
      parentCard.addEventListener('mousemove', function (e) {
        if (!isHovered) {
          onPointerMove(e);
        }
      });
      parentCard.addEventListener('mouseleave', function () {
        if (!isHovered) {
          targetRotX = 0;
          targetRotY = 0;
        }
      });
    }

    // Handle Resize
    window.addEventListener('resize', function () {
      if (!stage.clientWidth || !stage.clientHeight) return;
      var newW = stage.clientWidth;
      var newH = stage.clientHeight;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    });

    // 6. Animation Loop
    var clock = new THREE.Clock();

    function animate() {
      requestAnimationFrame(animate);
      var time = clock.getElapsedTime();

      // Smooth camera/group tilt
      group.rotation.x += (targetRotX - group.rotation.x) * 0.08;
      group.rotation.y += (targetRotY - group.rotation.y) * 0.08;

      // Subtle breathing float when idle
      if (!isHovered) {
        group.position.y = Math.sin(time * 1.5) * 0.04;
        group.rotation.z = Math.sin(time * 0.8) * 0.02;
      }

      // Quantum rings spin & particles orbit
      rings.forEach(function (r) {
        r.mesh.rotation.z += r.cfg.speed;
        r.mesh.rotation.x += r.cfg.speed * 0.5;

        r.angle += r.cfg.speed * 2.2;
        r.particle.position.x = Math.cos(r.angle) * r.cfg.radius;
        r.particle.position.y = Math.sin(r.angle) * r.cfg.radius;
      });

      // Point cloud gentle rotation
      pointCloud.rotation.y = time * 0.05;
      pointCloud.rotation.z = time * 0.02;

      renderer.render(scene, camera);
    }

    animate();
  }

  window.initQuantumAvatar = initQuantumAvatar;
})();
