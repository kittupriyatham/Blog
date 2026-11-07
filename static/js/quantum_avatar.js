/**
 * Quantum Avatar — Interactive 3D WebGL Hologram Badge & Orbital Rings
 * Built with Three.js for Potluri Krishna Priyatham (Kittu Priyatham)
 * PhD Scholar in Quantum Technologies @ SRM AP University
 */

(function () {
  function initQuantumAvatar(options) {
    var config = (typeof options === 'string')
      ? { stageId: arguments[0], canvasContainerId: arguments[1] }
      : (options || {});

    var stageId = config.stageId || 'quantum-avatar-stage';
    var canvasContainerId = config.canvasContainerId || 'quantum-avatar-canvas';
    var avatarContainerId = config.avatarContainerId || 'avatar-3d-container';
    var posterId = config.posterId || 'avatar-poster';
    var modelUrl = config.modelUrl || '/static/models/avatar_holo_opt.glb';
    var toggleBtnId = config.toggleBtnId || 'toggle-hologram-btn';
    var toggleLabelId = config.toggleLabelId || 'hologram-toggle-label';
    var toggleDotId = config.toggleDotId || 'hologram-dot';

    var stage = document.getElementById(stageId);
    if (!stage) return;

    var canvasContainer = (canvasContainerId && document.getElementById(canvasContainerId)) || stage;
    var avatarContainer = document.getElementById(avatarContainerId);
    var posterEl = posterId ? document.getElementById(posterId) : null;
    var toggleBtn = toggleBtnId ? document.getElementById(toggleBtnId) : null;
    var toggleLabel = toggleLabelId ? document.getElementById(toggleLabelId) : null;
    var toggleDot = toggleDotId ? document.getElementById(toggleDotId) : null;

    function hasWebGL() {
      try {
        var canvas = document.createElement('canvas');
        return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
      } catch (e) {
        return false;
      }
    }
    if (!hasWebGL() || typeof THREE === 'undefined') return;

    // 1. Outer Stage: Bloch sphere quantum orbital rings and particles
    setupOuterStage(stage, canvasContainer);

    // 2. Avatar Viewer: Tripo Hologram shader + Photorealistic 3D toggle
    if (avatarContainer) {
      setupAvatarViewer(avatarContainer, posterEl, modelUrl);
    }
  }

  function setupOuterStage(stage, canvasContainer) {
    var width = stage.clientWidth || 290;
    var height = stage.clientHeight || 290;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 4.2;

    var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

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

    // Outer Glowing Bevel Ring
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

    // Nested Quantum Orbital Rings (Bloch / Atom Qubit geometry)
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

    // Ambient Quantum Particle Cloud
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

    var ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
    scene.add(ambientLight);
    var pointLight = new THREE.PointLight(0x818cf8, 1.8, 20);
    pointLight.position.set(2, 3, 4);
    scene.add(pointLight);

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

      targetRotY = x * 0.35;
      targetRotX = -y * 0.35;
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

    var parentCard = stage.closest('section');
    if (parentCard) {
      parentCard.addEventListener('mousemove', function (e) {
        if (!isHovered) onPointerMove(e);
      });
      parentCard.addEventListener('mouseleave', function () {
        if (!isHovered) {
          targetRotX = 0;
          targetRotY = 0;
        }
      });
    }

    window.addEventListener('resize', function () {
      if (!stage.clientWidth || !stage.clientHeight) return;
      var newW = stage.clientWidth;
      var newH = stage.clientHeight;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    });

    var clock = new THREE.Clock();
    function animateStage() {
      requestAnimationFrame(animateStage);
      var time = clock.getElapsedTime();

      group.rotation.x += (targetRotX - group.rotation.x) * 0.08;
      group.rotation.y += (targetRotY - group.rotation.y) * 0.08;

      if (!isHovered) {
        group.position.y = Math.sin(time * 1.5) * 0.03;
      }

      rings.forEach(function (r) {
        r.mesh.rotation.z += r.cfg.speed;
        r.mesh.rotation.x += r.cfg.speed * 0.5;

        r.angle += r.cfg.speed * 2.2;
        r.particle.position.x = Math.cos(r.angle) * r.cfg.radius;
        r.particle.position.y = Math.sin(r.angle) * r.cfg.radius;
      });

      pointCloud.rotation.y = time * 0.05;
      renderer.render(scene, camera);
    }
    animateStage();
  }

  function setupAvatarViewer(container, posterEl, modelUrl) {
    if (typeof THREE.GLTFLoader === 'undefined') return;

    var width = container.clientWidth || 192;
    var height = container.clientHeight || 192;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(36, width / height, 0.1, 100);
    camera.position.set(0, 0, 2.3);

    var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    renderer.domElement.style.position = 'absolute';
    renderer.domElement.style.top = '0';
    renderer.domElement.style.left = '0';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.borderRadius = '50%';
    renderer.domElement.style.opacity = '0';
    renderer.domElement.style.transition = 'opacity 0.6s ease';
    renderer.domElement.style.cursor = 'grab';

    container.appendChild(renderer.domElement);

    var avatarRoot = new THREE.Group();
    scene.add(avatarRoot);

    // Warm, natural studio lighting for authentic skin tones and crisp fabric textures
    var ambientLight = new THREE.AmbientLight(0xffffff, 0.95);
    scene.add(ambientLight);

    var keyLight = new THREE.DirectionalLight(0xffffff, 1.25);
    keyLight.position.set(2, 4, 3);
    scene.add(keyLight);

    var fillLight = new THREE.DirectionalLight(0xe0f2fe, 0.65);
    fillLight.position.set(-2, 1, 2);
    scene.add(fillLight);

    var loader = new THREE.GLTFLoader();
    if (window.MeshoptDecoder) {
      loader.setMeshoptDecoder(window.MeshoptDecoder);
    }

    loader.load(modelUrl, function (gltf) {
      var model = gltf.scene;

      // Centered framing: face strictly above diameter, shoulders frame bottom curve
      model.position.set(0, -0.56, 0);
      model.rotation.y = 0; // facing directly forward towards viewer!

      model.traverse(function (child) {
        if (child.isMesh) {
          if (child.material) {
            child.material.roughness = 0.72;
            child.material.metalness = 0.08;
            child.material.needsUpdate = true;
          }
        }
      });

      avatarRoot.add(model);

      renderer.domElement.style.opacity = '1';
      if (posterEl) {
        posterEl.style.opacity = '0';
        setTimeout(function () {
          if (posterEl.parentElement) posterEl.style.display = 'none';
        }, 700);
      }
    });

    // Strict horizontal yaw drag — vertical tilt strictly locked
    var isDragging = false;
    var prevX = 0;
    var baseRotY = 0;

    function onDragStart(clientX) {
      isDragging = true;
      prevX = clientX;
      renderer.domElement.style.cursor = 'grabbing';
    }

    function onDragMove(clientX) {
      if (!isDragging) return;
      var deltaX = clientX - prevX;
      prevX = clientX;

      baseRotY += deltaX * 0.012;
      avatarRoot.rotation.y = baseRotY;

      // Strict vertical lock: no vertical movement allowed
      avatarRoot.rotation.x = 0;
      avatarRoot.rotation.z = 0;
    }

    function onDragEnd() {
      if (!isDragging) return;
      isDragging = false;
      renderer.domElement.style.cursor = 'grab';
    }

    container.addEventListener('mousedown', function (e) {
      onDragStart(e.clientX);
    });
    window.addEventListener('mousemove', function (e) {
      onDragMove(e.clientX);
    });
    window.addEventListener('mouseup', onDragEnd);

    container.addEventListener('touchstart', function (e) {
      if (e.touches.length === 1) {
        onDragStart(e.touches[0].clientX);
      }
    }, { passive: true });
    window.addEventListener('touchmove', function (e) {
      if (isDragging && e.touches.length === 1) {
        onDragMove(e.touches[0].clientX);
      }
    }, { passive: true });
    window.addEventListener('touchend', onDragEnd);

    window.addEventListener('resize', function () {
      if (!container.clientWidth || !container.clientHeight) return;
      var newW = container.clientWidth;
      var newH = container.clientHeight;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    });

    var avatarClock = new THREE.Clock();
    function animateAvatar() {
      requestAnimationFrame(animateAvatar);
      var time = avatarClock.getElapsedTime();

      if (!isDragging) {
        // Natural subtle ambient sway ±13 deg: keeps face prominently facing forward
        avatarRoot.rotation.y = baseRotY + Math.sin(time * 0.8) * 0.22;
      }

      avatarRoot.rotation.x = 0;
      avatarRoot.rotation.z = 0;

      renderer.render(scene, camera);
    }
    animateAvatar();
  }

  window.initQuantumAvatar = initQuantumAvatar;
})();
