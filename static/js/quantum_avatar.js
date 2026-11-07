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
      setupAvatarViewer(avatarContainer, posterEl, modelUrl, toggleBtn, toggleLabel, toggleDot);
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

  function setupAvatarViewer(container, posterEl, modelUrl, toggleBtn, toggleLabel, toggleDot) {
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

    var ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    var dirLight = new THREE.DirectionalLight(0xffffff, 1.1);
    dirLight.position.set(2, 4, 3);
    scene.add(dirLight);

    var rimLight = new THREE.PointLight(0x06b6d4, 1.4, 10);
    rimLight.position.set(-2, 1, 2);
    scene.add(rimLight);

    var loader = new THREE.GLTFLoader();
    if (window.MeshoptDecoder) {
      loader.setMeshoptDecoder(window.MeshoptDecoder);
    }

    var avatarMesh = null;
    var holoMaterial = null;
    var photorealMaterial = null;
    var isHologram = false;

    var vertexShader = [
      'varying vec3 vPosition;',
      'varying vec3 vNormal;',
      'varying vec3 vWorldPosition;',
      'varying vec2 vUv;',
      'void main() {',
      '  vPosition = position;',
      '  vNormal = normalize(normalMatrix * normal);',
      '  vec4 worldPos = modelMatrix * vec4(position, 1.0);',
      '  vWorldPosition = worldPos.xyz;',
      '  vUv = uv;',
      '  gl_Position = projectionMatrix * viewMatrix * worldPos;',
      '}'
    ].join('\n');

    var fragmentShader = [
      'uniform sampler2D map;',
      'uniform float time;',
      'varying vec3 vPosition;',
      'varying vec3 vNormal;',
      'varying vec3 vWorldPosition;',
      'varying vec2 vUv;',
      'void main() {',
      '  vec4 tex = texture2D(map, vUv);',
      '  vec3 baseColor = tex.rgb;',
      '  vec3 lightDir = normalize(vec3(0.4, 0.6, 1.0));',
      '  float diff = max(dot(vNormal, lightDir), 0.0) * 0.4 + 0.65;',
      '  vec3 litColor = baseColor * diff;',
      '  float scale = 44.0;',
      '  float lineY = abs(fract(vPosition.y * scale - 0.5) - 0.5) / (fwidth(vPosition.y * scale) * 1.0 + 0.0001);',
      '  float lineX = abs(fract(vPosition.x * scale - 0.5) - 0.5) / (fwidth(vPosition.x * scale) * 1.0 + 0.0001);',
      '  float grid = 1.0 - clamp(min(lineY, lineX), 0.0, 1.0);',
      '  grid = pow(grid, 2.0);',
      '  vec3 viewDir = normalize(cameraPosition - vWorldPosition);',
      '  float fresnel = pow(1.0 - max(dot(vNormal, viewDir), 0.0), 3.0);',
      '  float laserY = sin(time * 1.5) * 0.18 + 0.65;',
      '  float dist = abs(vPosition.y - laserY);',
      '  float laserCore = exp(-pow(dist * 60.0, 2.0));',
      '  float laserGlow = exp(-pow(dist * 16.0, 2.0));',
      '  vec3 cyan = vec3(0.0, 0.94, 0.82);',
      '  vec3 white = vec3(1.0, 1.0, 1.0);',
      '  vec3 color = mix(litColor, cyan, grid * 0.35);',
      '  color += cyan * fresnel * 0.35;',
      '  color += cyan * laserGlow * 0.28 + white * laserCore * 0.65;',
      '  gl_FragColor = vec4(color, 1.0);',
      '}'
    ].join('\n');

    loader.load(modelUrl, function (gltf) {
      var model = gltf.scene;

      // Perfectly centered: face strictly above diameter, shoulders frame bottom curve
      model.position.set(0, -0.56, 0);
      model.rotation.y = 0; // facing directly forward towards viewer!

      var origTexture = null;
      model.traverse(function (child) {
        if (child.isMesh) {
          avatarMesh = child;
          origTexture = child.material.map;
        }
      });

      if (!avatarMesh) return;

      holoMaterial = new THREE.ShaderMaterial({
        vertexShader: vertexShader,
        fragmentShader: fragmentShader,
        uniforms: {
          map: { value: origTexture },
          time: { value: 0 }
        },
        extensions: {
          derivatives: true
        },
        transparent: true
      });

      photorealMaterial = new THREE.MeshStandardMaterial({
        map: origTexture,
        roughness: 0.72,
        metalness: 0.12
      });

      avatarMesh.material = photorealMaterial;
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

    function setAvatarMode(holo) {
      isHologram = holo;
      if (avatarMesh) {
        avatarMesh.material = isHologram ? holoMaterial : photorealMaterial;
      }
      if (toggleLabel) {
        toggleLabel.textContent = isHologram ? '⚡ Quantum Hologram' : '👤 Photorealistic 3D';
      }
      if (toggleDot) {
        toggleDot.className = isHologram
          ? 'w-2 h-2 rounded-full bg-cyan-400 animate-pulse'
          : 'w-2 h-2 rounded-full bg-emerald-500';
      }
    }

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        setAvatarMode(!isHologram);
      });
    }

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

      if (holoMaterial && isHologram) {
        holoMaterial.uniforms.time.value = time;
      }

      if (!isDragging) {
        // High-tech holographic scan swivel ±16 deg: keeps face prominently facing forward
        avatarRoot.rotation.y = baseRotY + Math.sin(time * 0.9) * 0.28;
      }

      avatarRoot.rotation.x = 0;
      avatarRoot.rotation.z = 0;

      renderer.render(scene, camera);
    }
    animateAvatar();
  }

  window.initQuantumAvatar = initQuantumAvatar;
})();
