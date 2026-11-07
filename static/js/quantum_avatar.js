/**
 * Quantum Gyroscope Avatar — Interactive 3D WebGL Avatar & Dynamic 3-Axis Gyroscope
 * Built with Three.js for Potluri Krishna Priyatham (Kittu Priyatham)
 * PhD Scholar in Quantum Technologies @ SRM AP University
 */

(function () {
  function initQuantumAvatar(options) {
    var config = options || {};
    var stageId = config.stageId || 'quantum-avatar-stage';
    var canvasContainerId = config.canvasContainerId || 'quantum-avatar-canvas';
    var posterId = config.posterId || 'avatar-poster';
    var modelUrl = config.modelUrl || '/static/models/avatar_holo_opt.glb';

    var stage = document.getElementById(stageId);
    if (!stage) return;
    var container = (canvasContainerId && document.getElementById(canvasContainerId)) || stage;
    var posterEl = posterId ? document.getElementById(posterId) : null;

    function hasWebGL() {
      try {
        var canvas = document.createElement('canvas');
        return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
      } catch (e) {
        return false;
      }
    }
    if (!hasWebGL() || typeof THREE === 'undefined') return;

    var width = stage.clientWidth || 320;
    var height = stage.clientHeight || 320;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
    camera.position.set(0, 0, 4.3);

    var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.opacity = '0';
    renderer.domElement.style.transition = 'opacity 0.6s ease';
    renderer.domElement.style.cursor = 'grab';

    container.innerHTML = '';
    if (posterEl) container.appendChild(posterEl);
    container.appendChild(renderer.domElement);

    // Warm, natural studio lighting for authentic skin tones and crisp fabric textures
    var ambientLight = new THREE.AmbientLight(0xffffff, 0.95);
    scene.add(ambientLight);

    var keyLight = new THREE.DirectionalLight(0xffffff, 1.25);
    keyLight.position.set(2, 4, 3);
    scene.add(keyLight);

    var fillLight = new THREE.DirectionalLight(0xe0f2fe, 0.65);
    fillLight.position.set(-2, 1, 2);
    scene.add(fillLight);

    // Subtle colored rim lights for quantum aesthetic
    var cyanRim = new THREE.PointLight(0x06b6d4, 0.8, 6);
    cyanRim.position.set(-2, 1.5, 1);
    scene.add(cyanRim);

    var purpleRim = new THREE.PointLight(0xa855f7, 0.7, 6);
    purpleRim.position.set(2, -1.2, 1);
    scene.add(purpleRim);

    // Master Gyroscope Root
    var gyroRoot = new THREE.Group();
    scene.add(gyroRoot);

    // Avatar Root (Nested in center, stays prominently facing forward)
    var avatarRoot = new THREE.Group();
    gyroRoot.add(avatarRoot);

    // Dynamic Gyroscope Frame (Rotates, precesses, and tumbles in 3D space)
    var gyroFrame = new THREE.Group();
    gyroRoot.add(gyroFrame);

    // -----------------------------------------------------------------
    // 3-Axis Gyroscope Architecture
    // Radii enlarged (1.68 - 1.98) so circles NEVER obstruct the face!
    // The 3 rings are mutually perpendicular at all times (90 deg).
    // -----------------------------------------------------------------
    var r1Radius = 1.98; // Ring 1: Outer Cyan
    var r2Radius = 1.83; // Ring 2: Middle Electric Purple
    var r3Radius = 1.68; // Ring 3: Inner Golden Amber

    // Ring 1: Cyan Gimbal (in XY plane, normal = Z)
    var ring1Group = new THREE.Group();
    var ring1Geo = new THREE.TorusGeometry(r1Radius, 0.016, 16, 120);
    var ring1Mat = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      emissive: 0x0891b2,
      emissiveIntensity: 0.9,
      metalness: 0.85,
      roughness: 0.18
    });
    var ring1Mesh = new THREE.Mesh(ring1Geo, ring1Mat);
    ring1Group.add(ring1Mesh);

    // Bearing caps on Ring 1
    var bearingMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, metalness: 0.95, roughness: 0.1 });
    var bearingGeo = new THREE.SphereGeometry(0.046, 16, 16);
    var p1a = new THREE.Mesh(bearingGeo, bearingMat);
    p1a.position.set(r1Radius, 0, 0);
    ring1Group.add(p1a);
    var p1b = new THREE.Mesh(bearingGeo, bearingMat);
    p1b.position.set(-r1Radius, 0, 0);
    ring1Group.add(p1b);

    // Orbiting electron on Ring 1
    var electronGeo = new THREE.SphereGeometry(0.052, 16, 16);
    var electron1Mat = new THREE.MeshStandardMaterial({ color: 0x22d3ee, emissive: 0x06b6d4, emissiveIntensity: 1.8 });
    var electron1 = new THREE.Mesh(electronGeo, electron1Mat);
    ring1Group.add(electron1);

    gyroFrame.add(ring1Group);

    // Ring 2: Electric Purple Gimbal (in YZ plane, normal = X, strictly perp to Ring 1)
    var ring2Group = new THREE.Group();
    var ring2Geo = new THREE.TorusGeometry(r2Radius, 0.015, 16, 120);
    var ring2Mat = new THREE.MeshStandardMaterial({
      color: 0xa855f7,
      emissive: 0x7c3aed,
      emissiveIntensity: 0.9,
      metalness: 0.85,
      roughness: 0.18
    });
    var ring2Mesh = new THREE.Mesh(ring2Geo, ring2Mat);
    ring2Mesh.rotation.y = Math.PI / 2; // Normal is X axis -> dot(Z, X) = 0!
    ring2Group.add(ring2Mesh);

    var p2a = new THREE.Mesh(bearingGeo, bearingMat);
    p2a.position.set(0, 0, r2Radius);
    ring2Group.add(p2a);
    var p2b = new THREE.Mesh(bearingGeo, bearingMat);
    p2b.position.set(0, 0, -r2Radius);
    ring2Group.add(p2b);

    var electron2Mat = new THREE.MeshStandardMaterial({ color: 0xc084fc, emissive: 0xa855f7, emissiveIntensity: 1.8 });
    var electron2 = new THREE.Mesh(electronGeo, electron2Mat);
    ring2Group.add(electron2);

    gyroFrame.add(ring2Group);

    // Ring 3: Golden Amber Gimbal (in ZX plane, normal = Y, strictly perp to Ring 1 & Ring 2)
    var ring3Group = new THREE.Group();
    var ring3Geo = new THREE.TorusGeometry(r3Radius, 0.014, 16, 120);
    var ring3Mat = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      emissive: 0xd97706,
      emissiveIntensity: 0.9,
      metalness: 0.85,
      roughness: 0.18
    });
    var ring3Mesh = new THREE.Mesh(ring3Geo, ring3Mat);
    ring3Mesh.rotation.x = Math.PI / 2; // Normal is Y axis -> dot(Z, Y) = 0, dot(X, Y) = 0!
    ring3Group.add(ring3Mesh);

    var electron3Mat = new THREE.MeshStandardMaterial({ color: 0xfde047, emissive: 0xf59e0b, emissiveIntensity: 1.8 });
    var electron3 = new THREE.Mesh(electronGeo, electron3Mat);
    ring3Group.add(electron3);

    gyroFrame.add(ring3Group);

    // Ambient Quantum Particle Cloud
    var particleCount = 45;
    var partGeom = new THREE.BufferGeometry();
    var positions = new Float32Array(particleCount * 3);
    var colors = new Float32Array(particleCount * 3);
    for (var i = 0; i < particleCount; i++) {
      var rad = 1.45 + Math.random() * 0.9;
      var theta = Math.random() * Math.PI * 2;
      var phi = (Math.random() - 0.5) * Math.PI * 0.8;
      positions[i * 3] = rad * Math.cos(theta) * Math.cos(phi);
      positions[i * 3 + 1] = rad * Math.sin(theta) * Math.cos(phi);
      positions[i * 3 + 2] = rad * Math.sin(phi);

      var mix = Math.random();
      colors[i * 3] = 0.05 * mix + 0.65 * (1 - mix);
      colors[i * 3 + 1] = 0.75 * mix + 0.35 * (1 - mix);
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
    gyroRoot.add(pointCloud);

    // -------------------------------------------------------------
    // Load Model: Positioned in the Center of the Gyroscope
    // With enlarged radii, face sits clear and completely unobstructed!
    // -------------------------------------------------------------
    var loader = new THREE.GLTFLoader();
    if (window.MeshoptDecoder) {
      loader.setMeshoptDecoder(window.MeshoptDecoder);
    }

    loader.load(modelUrl, function (gltf) {
      var model = gltf.scene;

      // Perfectly centered: face sits clear in the hollow, shoulders framed by the lower curves
      model.position.set(0, -0.62, 0);
      model.rotation.y = 0; // facing forward towards viewer

      model.traverse(function (child) {
        if (child.isMesh) {
          child.castShadow = true;
          child.receiveShadow = true;
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

    // -------------------------------------------------------------
    // Interactive Controls & Dynamic Coupled Gyroscope Motion
    // -------------------------------------------------------------
    var isDragging = false;
    var prevX = 0;
    var baseYaw = 0;
    var dragVelocity = 0;

    // Mouse tilt parallax on hover
    var mouseX = 0;
    var mouseY = 0;
    var tiltX = 0;
    var tiltY = 0;

    // Spring physics compliance for the 3 gimbals
    // Allows flexible organic response (+/- 3 to 6 deg) before returning to 90 deg orthogonality
    var g1 = { val: 0, target: 0, vel: 0 };
    var g2 = { val: 0, target: 0, vel: 0 };
    var g3 = { val: 0, target: 0, vel: 0 };

    function onDragStart(clientX) {
      isDragging = true;
      prevX = clientX;
      dragVelocity = 0;
      renderer.domElement.style.cursor = 'grabbing';
    }

    function onDragMove(clientX) {
      if (!isDragging) return;
      var deltaX = clientX - prevX;
      prevX = clientX;

      dragVelocity = deltaX * 0.015;
      baseYaw += dragVelocity;

      // Dynamic torque transmission: moving one ring flexes the others with spring inertia!
      g1.vel += dragVelocity * 1.2;
      g2.vel += dragVelocity * 0.85;
      g3.vel -= dragVelocity * 0.65;
    }

    function onDragEnd() {
      if (!isDragging) return;
      isDragging = false;
      renderer.domElement.style.cursor = 'grab';
    }

    stage.addEventListener('mousedown', function (e) {
      onDragStart(e.clientX);
    });
    window.addEventListener('mousemove', function (e) {
      onDragMove(e.clientX);
      var rect = stage.getBoundingClientRect();
      var x = (e.clientX - rect.left) / rect.width - 0.5;
      var y = (e.clientY - rect.top) / rect.height - 0.5;
      if (Math.abs(x) < 2 && Math.abs(y) < 2) {
        mouseX = x;
        mouseY = y;
      }
    });
    window.addEventListener('mouseup', onDragEnd);

    stage.addEventListener('touchstart', function (e) {
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
      if (!stage.clientWidth || !stage.clientHeight) return;
      var newW = stage.clientWidth;
      var newH = stage.clientHeight;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    });

    // Spring-damper physics solver for flexible mechanical coupling
    function updateSpring(state, target, k, damping, dt) {
      var force = -k * (state.val - target) - damping * state.vel;
      state.vel += force * dt;
      state.val += state.vel * dt;
    }

    var clock = new THREE.Clock();
    var lastTime = 0;
    var eAngle1 = 0;
    var eAngle2 = 0;
    var eAngle3 = 0;

    function animate() {
      requestAnimationFrame(animate);
      var time = clock.getElapsedTime();
      var dt = Math.min(time - lastTime, 0.05) || 0.016;
      lastTime = time;

      // Soft perspective tilt on gyroRoot based on cursor
      tiltX += (mouseY * 0.28 - tiltX) * 0.06;
      tiltY += (mouseX * 0.38 - tiltY) * 0.06;
      gyroRoot.rotation.x = tiltX;
      gyroRoot.rotation.y = tiltY;

      // Idle precession and spin: continuous graceful tumbling
      if (!isDragging) {
        dragVelocity *= 0.94;
        baseYaw += 0.0035 + dragVelocity;
      }

      // -------------------------------------------------------------
      // Dynamic Gyroscope Frame Precession
      // Tumble axes freely in 3D space at dynamic celestial angles!
      // The 3 internal rings are ALWAYS mutually perpendicular (90 deg)
      // no matter what 3D orientation gyroFrame assumes!
      // -------------------------------------------------------------
      gyroFrame.rotation.y = baseYaw + Math.sin(time * 0.42) * 0.25;
      gyroFrame.rotation.x = Math.sin(time * 0.35) * 0.32 + 0.38; // Tilted dynamic pitch
      gyroFrame.rotation.z = Math.cos(time * 0.28) * 0.22 - 0.22; // Tilted dynamic roll

      // Dynamic mechanical coupling with spring flex:
      // When one ring is moved, momentum transfers to the other rings with organic compliance
      var speed1 = dragVelocity * 2.0 + Math.sin(time * 0.9) * 0.08;
      var speed2 = dragVelocity * 1.5 + Math.cos(time * 1.1) * 0.06;
      var speed3 = -dragVelocity * 1.2 + Math.sin(time * 0.7) * 0.05;

      updateSpring(g1, speed1, 15.0, 4.5, dt);
      updateSpring(g2, speed2, 13.0, 4.0, dt);
      updateSpring(g3, speed3, 11.0, 3.5, dt);

      // Apply spring flex offsets (within +/- 3-6 deg) around each ring's orthogonal plane
      ring1Group.rotation.z = g1.val;
      ring2Group.rotation.x = g2.val;
      ring3Group.rotation.y = g3.val;

      // Avatar follows the primary yaw smoothly while staying gracefully facing forward
      avatarRoot.rotation.y = baseYaw * 0.75 + Math.sin(time * 0.6) * 0.06;
      avatarRoot.rotation.x = 0;
      avatarRoot.rotation.z = 0;

      // Orbiting quantum electron beads along the circumference of each ring
      eAngle1 += 0.024;
      electron1.position.set(Math.cos(eAngle1) * r1Radius, Math.sin(eAngle1) * r1Radius, 0);

      eAngle2 += 0.019;
      electron2.position.set(0, Math.cos(eAngle2) * r2Radius, Math.sin(eAngle2) * r2Radius);

      eAngle3 += 0.026;
      electron3.position.set(Math.cos(eAngle3) * r3Radius, 0, Math.sin(eAngle3) * r3Radius);

      // Quantum particle cloud drift
      pointCloud.rotation.y = time * 0.035;

      renderer.render(scene, camera);
    }
    animate();
  }

  window.initQuantumAvatar = initQuantumAvatar;
})();
