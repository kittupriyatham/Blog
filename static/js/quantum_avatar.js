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
    var camera = new THREE.PerspectiveCamera(44, width / height, 0.1, 100);
    camera.position.set(0, 0, 3.8);

    var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;

    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.opacity = '0';
    renderer.domElement.style.transition = 'opacity 0.6s ease';
    renderer.domElement.style.cursor = 'grab';

    container.innerHTML = '';
    if (posterEl) container.appendChild(posterEl);
    container.appendChild(renderer.domElement);

    // Soft, natural photographic studio lighting tailored for matte, realistic skin tones
    var ambientLight = new THREE.HemisphereLight(0xffffff, 0x334155, 1.0);
    scene.add(ambientLight);

    var keyLight = new THREE.DirectionalLight(0xfff7ed, 0.65);
    keyLight.position.set(1.8, 3.0, 2.5);
    scene.add(keyLight);

    var fillLight = new THREE.DirectionalLight(0xe0f2fe, 0.45);
    fillLight.position.set(-1.8, 1.2, 2.0);
    scene.add(fillLight);

    // Subtle colored rim lights placed BEHIND model to catch silhouette edges without shining directly on face
    var cyanRim = new THREE.PointLight(0x06b6d4, 0.8, 6);
    cyanRim.position.set(-2.0, 1.5, -1.2);
    scene.add(cyanRim);

    var purpleRim = new THREE.PointLight(0xa855f7, 0.7, 6);
    purpleRim.position.set(2.0, -1.0, -1.2);
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
    // Compact radii (1.08 - 1.35) so rings totally fit into the canvas
    // while the 3D model inside is scaled up larger, clearer & prominent!
    // The 3 rings remain strictly mutually perpendicular (90 deg).
    // -----------------------------------------------------------------
    var r1Radius = 1.35; // Ring 1: Outer Cyan (diameter = 2.70)
    var r2Radius = 1.22; // Ring 2: Middle Electric Purple (diameter = 2.44)
    var r3Radius = 1.08; // Ring 3: Inner Golden Amber (diameter = 2.16)

    // Ring 1: Cyan Gimbal (in XY plane, normal = Z)
    var ring1Group = new THREE.Group();
    var ring1Geo = new THREE.TorusGeometry(r1Radius, 0.014, 16, 120);
    var ring1Mat = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      emissive: 0x0891b2,
      emissiveIntensity: 0.95,
      metalness: 0.85,
      roughness: 0.2
    });
    var ring1Mesh = new THREE.Mesh(ring1Geo, ring1Mat);
    ring1Group.add(ring1Mesh);

    // Bearing caps on Ring 1
    var bearingMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, metalness: 0.95, roughness: 0.1 });
    var bearingGeo = new THREE.SphereGeometry(0.036, 16, 16);
    var p1a = new THREE.Mesh(bearingGeo, bearingMat);
    p1a.position.set(r1Radius, 0, 0);
    ring1Group.add(p1a);
    var p1b = new THREE.Mesh(bearingGeo, bearingMat);
    p1b.position.set(-r1Radius, 0, 0);
    ring1Group.add(p1b);

    // Orbiting electron on Ring 1
    var electronGeo = new THREE.SphereGeometry(0.042, 16, 16);
    var electron1Mat = new THREE.MeshStandardMaterial({ color: 0x22d3ee, emissive: 0x06b6d4, emissiveIntensity: 1.8 });
    var electron1 = new THREE.Mesh(electronGeo, electron1Mat);
    ring1Group.add(electron1);

    gyroFrame.add(ring1Group);

    // Ring 2: Electric Purple Gimbal (in YZ plane, normal = X, strictly perp to Ring 1)
    var ring2Group = new THREE.Group();
    var ring2Geo = new THREE.TorusGeometry(r2Radius, 0.013, 16, 120);
    var ring2Mat = new THREE.MeshStandardMaterial({
      color: 0xa855f7,
      emissive: 0x7c3aed,
      emissiveIntensity: 0.95,
      metalness: 0.85,
      roughness: 0.2
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
    var ring3Geo = new THREE.TorusGeometry(r3Radius, 0.012, 16, 120);
    var ring3Mat = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      emissive: 0xd97706,
      emissiveIntensity: 0.95,
      metalness: 0.85,
      roughness: 0.2
    });
    var ring3Mesh = new THREE.Mesh(ring3Geo, ring3Mat);
    ring3Mesh.rotation.x = Math.PI / 2; // Normal is Y axis -> dot(Z, Y) = 0, dot(X, Y) = 0!
    ring3Group.add(ring3Mesh);

    var p3a = new THREE.Mesh(bearingGeo, bearingMat);
    p3a.position.set(r3Radius, 0, 0);
    ring3Group.add(p3a);
    var p3b = new THREE.Mesh(bearingGeo, bearingMat);
    p3b.position.set(-r3Radius, 0, 0);
    ring3Group.add(p3b);

    var electron3Mat = new THREE.MeshStandardMaterial({ color: 0xfde047, emissive: 0xf59e0b, emissiveIntensity: 1.8 });
    var electron3 = new THREE.Mesh(electronGeo, electron3Mat);
    ring3Group.add(electron3);

    gyroFrame.add(ring3Group);

    // Ambient Quantum Particle Cloud (Kept within compact radius)
    var particleCount = 45;
    var partGeom = new THREE.BufferGeometry();
    var positions = new Float32Array(particleCount * 3);
    var colors = new Float32Array(particleCount * 3);
    for (var i = 0; i < particleCount; i++) {
      var rad = 0.88 + Math.random() * 0.46;
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
      size: 0.028,
      vertexColors: true,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending
    });
    var pointCloud = new THREE.Points(partGeom, partMaterial);
    gyroRoot.add(pointCloud);

    // -------------------------------------------------------------
    // Load Model: Scaled Up & Positioned in Center of Gyroscope
    // Matte finish (roughness 0.96, metalness 0.0) eliminates all oily sheen
    // -------------------------------------------------------------
    var loader = new THREE.GLTFLoader();
    if (window.MeshoptDecoder) {
      loader.setMeshoptDecoder(window.MeshoptDecoder);
    }

    loader.load(modelUrl, function (gltf) {
      var model = gltf.scene;

      // Scale model up so the avatar bust is significantly larger and clearer
      model.scale.set(1.42, 1.42, 1.42);
      model.position.set(0, -0.74, 0);
      model.rotation.y = 0; // facing forward towards viewer

      model.traverse(function (child) {
        if (child.isMesh) {
          child.castShadow = true;
          child.receiveShadow = true;
          if (child.material) {
            // Matte, realistic skin and clothing — eliminates all oily/plastic specular reflections
            child.material.roughness = 0.96;
            child.material.metalness = 0.0;
            if (child.material.map) {
              child.material.map.encoding = THREE.sRGBEncoding;
            }
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
    // Interactive Controls & Strict Container-Scoped Mouse Motion
    // The model moves ONLY when the mouse pointer is inside the canvas/container.
    // When pointer is outside, the model is NOT moved by the pointer.
    // -------------------------------------------------------------
    var isDragging = false;
    var isPointerInside = false;
    var prevX = 0;
    var baseYaw = 0;
    var dragVelocity = 0;

    // Mouse tilt parallax on hover (active ONLY when pointer is inside container)
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

    // Check bounds strictly: returns true only when pointer is inside stage/canvas
    function handlePointerMove(clientX, clientY) {
      var rect = stage.getBoundingClientRect();
      var inside = (
        clientX >= rect.left &&
        clientX <= rect.right &&
        clientY >= rect.top &&
        clientY <= rect.bottom
      );

      if (!inside) {
        if (isPointerInside) {
          isPointerInside = false;
          mouseX = 0;
          mouseY = 0;
          if (isDragging) onDragEnd();
        }
        return false;
      }

      isPointerInside = true;
      mouseX = (clientX - rect.left) / rect.width - 0.5;
      mouseY = (clientY - rect.top) / rect.height - 0.5;

      if (isDragging) {
        onDragMove(clientX);
      }
      return true;
    }

    stage.addEventListener('mouseenter', function (e) {
      isPointerInside = true;
      handlePointerMove(e.clientX, e.clientY);
    });

    stage.addEventListener('mouseleave', function () {
      isPointerInside = false;
      mouseX = 0;
      mouseY = 0;
      if (isDragging) onDragEnd();
    });

    stage.addEventListener('mousedown', function (e) {
      isPointerInside = true;
      onDragStart(e.clientX);
    });

    stage.addEventListener('mousemove', function (e) {
      handlePointerMove(e.clientX, e.clientY);
    });

    stage.addEventListener('mouseup', onDragEnd);
    window.addEventListener('mouseup', onDragEnd);

    // Global listener ensures that if dragging moves outside the canvas, it immediately halts
    window.addEventListener('mousemove', function (e) {
      if (isDragging || isPointerInside) {
        handlePointerMove(e.clientX, e.clientY);
      }
    });

    stage.addEventListener('touchstart', function (e) {
      if (e.touches.length === 1) {
        isPointerInside = true;
        onDragStart(e.touches[0].clientX);
      }
    }, { passive: true });

    stage.addEventListener('touchmove', function (e) {
      if (e.touches.length === 1) {
        handlePointerMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    }, { passive: true });

    stage.addEventListener('touchend', function () {
      isPointerInside = false;
      mouseX = 0;
      mouseY = 0;
      onDragEnd();
    });

    stage.addEventListener('touchcancel', function () {
      isPointerInside = false;
      mouseX = 0;
      mouseY = 0;
      onDragEnd();
    });

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

      // Soft perspective tilt on gyroRoot: ONLY when pointer is inside canvas/container!
      // When outside, tilt smoothly eases to 0 so outside mouse movement NEVER moves the model.
      if (isPointerInside) {
        tiltX += (mouseY * 0.28 - tiltX) * 0.08;
        tiltY += (mouseX * 0.38 - tiltY) * 0.08;
      } else {
        tiltX += (0 - tiltX) * 0.08;
        tiltY += (0 - tiltY) * 0.08;
      }
      gyroRoot.rotation.x = tiltX;
      gyroRoot.rotation.y = tiltY;

      // Idle precession and spin: continuous graceful tumbling
      if (!isDragging) {
        dragVelocity *= 0.94;
        baseYaw += 0.003 + dragVelocity;
      }

      // -------------------------------------------------------------
      // Dynamic Gyroscope Frame Precession
      // Tumble axes freely in 3D space at dynamic celestial angles!
      // The 3 internal rings are ALWAYS mutually perpendicular (90 deg)
      // no matter what 3D orientation gyroFrame assumes!
      // -------------------------------------------------------------
      gyroFrame.rotation.y = baseYaw + Math.sin(time * 0.42) * 0.22;
      gyroFrame.rotation.x = Math.sin(time * 0.35) * 0.26 + 0.35; // Tilted dynamic pitch
      gyroFrame.rotation.z = Math.cos(time * 0.28) * 0.18 - 0.18; // Tilted dynamic roll

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
