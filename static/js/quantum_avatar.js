/**
 * Quantum Gyroscope Avatar — Interactive 3D WebGL Avatar & Coupled 3-Axis Gyroscope
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

    var width = stage.clientWidth || 300;
    var height = stage.clientHeight || 300;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    camera.position.set(0, 0, 3.6);

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

    var amberRim = new THREE.PointLight(0xf59e0b, 0.6, 6);
    amberRim.position.set(2, -1, 1);
    scene.add(amberRim);

    // Master Gyroscope Root
    var gyroRoot = new THREE.Group();
    scene.add(gyroRoot);

    // Avatar Root (Nested in the exact physical center of gyroscope)
    var avatarRoot = new THREE.Group();
    gyroRoot.add(avatarRoot);

    // -------------------------------------------------------------
    // 3-Axis Gyroscope Architecture (Mutually Perpendicular at 90 deg)
    // -------------------------------------------------------------
    // Ring 1 (Outer / Yaw / Equatorial): Normal = Y axis (lies in XZ plane)
    // Ring 2 (Middle / Pitch / Meridian): Normal = X axis (lies in YZ plane)
    // Ring 3 (Inner / Roll / Frontal):   Normal = Z axis (lies in XY plane)
    //
    // All 3 normals are mutually orthogonal: dot(n1, n2) = dot(n2, n3) = dot(n1, n3) = 0!
    // -------------------------------------------------------------

    // Ring 1: Outer Cyan Gimbal (Equatorial)
    var r1Radius = 1.48;
    var ring1Group = new THREE.Group();
    var ring1Geo = new THREE.TorusGeometry(r1Radius, 0.018, 16, 120);
    var ring1Mat = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      emissive: 0x0891b2,
      emissiveIntensity: 0.9,
      metalness: 0.85,
      roughness: 0.18
    });
    var ring1Mesh = new THREE.Mesh(ring1Geo, ring1Mat);
    ring1Mesh.rotation.x = Math.PI / 2; // Normal is Y axis
    ring1Group.add(ring1Mesh);

    // Pivot bearings on Ring 1 (mounting for Ring 2 along X-axis)
    var bearingMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.95, roughness: 0.1 });
    var bearingGeo = new THREE.SphereGeometry(0.045, 16, 16);
    var p1a = new THREE.Mesh(bearingGeo, bearingMat);
    p1a.position.set(r1Radius, 0, 0);
    ring1Group.add(p1a);
    var p1b = new THREE.Mesh(bearingGeo, bearingMat);
    p1b.position.set(-r1Radius, 0, 0);
    ring1Group.add(p1b);

    // Orbiting electron on Ring 1
    var electronGeo = new THREE.SphereGeometry(0.05, 16, 16);
    var electron1Mat = new THREE.MeshStandardMaterial({ color: 0x22d3ee, emissive: 0x06b6d4, emissiveIntensity: 1.6 });
    var electron1 = new THREE.Mesh(electronGeo, electron1Mat);
    ring1Group.add(electron1);

    gyroRoot.add(ring1Group);

    // Ring 2: Middle Electric Indigo Gimbal (Meridian)
    var r2Radius = 1.32;
    var ring2Group = new THREE.Group();
    var ring2Geo = new THREE.TorusGeometry(r2Radius, 0.016, 16, 120);
    var ring2Mat = new THREE.MeshStandardMaterial({
      color: 0x818cf8,
      emissive: 0x6366f1,
      emissiveIntensity: 0.9,
      metalness: 0.85,
      roughness: 0.18
    });
    var ring2Mesh = new THREE.Mesh(ring2Geo, ring2Mat);
    ring2Mesh.rotation.y = Math.PI / 2; // Normal is X axis
    ring2Group.add(ring2Mesh);

    // Pivot bearings on Ring 2 (along Z-axis)
    var p2a = new THREE.Mesh(bearingGeo, bearingMat);
    p2a.position.set(0, 0, r2Radius);
    ring2Group.add(p2a);
    var p2b = new THREE.Mesh(bearingGeo, bearingMat);
    p2b.position.set(0, 0, -r2Radius);
    ring2Group.add(p2b);

    var electron2Mat = new THREE.MeshStandardMaterial({ color: 0xa5b4fc, emissive: 0x818cf8, emissiveIntensity: 1.6 });
    var electron2 = new THREE.Mesh(electronGeo, electron2Mat);
    ring2Group.add(electron2);

    gyroRoot.add(ring2Group);

    // Ring 3: Inner Warm Amber Gimbal (Frontal)
    var r3Radius = 1.18;
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
    // Normal is Z axis (unrotated in XY plane)
    ring3Group.add(ring3Mesh);

    var electron3Mat = new THREE.MeshStandardMaterial({ color: 0xfde047, emissive: 0xf59e0b, emissiveIntensity: 1.6 });
    var electron3 = new THREE.Mesh(electronGeo, electron3Mat);
    ring3Group.add(electron3);

    gyroRoot.add(ring3Group);

    // Ambient Quantum Particle Cloud
    var particleCount = 40;
    var partGeom = new THREE.BufferGeometry();
    var positions = new Float32Array(particleCount * 3);
    var colors = new Float32Array(particleCount * 3);
    for (var i = 0; i < particleCount; i++) {
      var rad = 1.25 + Math.random() * 0.7;
      var theta = Math.random() * Math.PI * 2;
      var phi = (Math.random() - 0.5) * Math.PI * 0.8;
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
      size: 0.035,
      vertexColors: true,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending
    });
    var pointCloud = new THREE.Points(partGeom, partMaterial);
    gyroRoot.add(pointCloud);

    // -------------------------------------------------------------
    // Load Model into the Center of the Gyroscope
    // -------------------------------------------------------------
    var loader = new THREE.GLTFLoader();
    if (window.MeshoptDecoder) {
      loader.setMeshoptDecoder(window.MeshoptDecoder);
    }

    loader.load(modelUrl, function (gltf) {
      var model = gltf.scene;

      // Perfectly centered: face inside the rings, shoulders frame bottom curve
      model.position.set(0, -0.58, 0);
      model.rotation.y = 0;

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
    // Interactive Controls & Spring-Coupled Gyroscopic Dynamics
    // -------------------------------------------------------------
    var isDragging = false;
    var prevX = 0;
    var baseYaw = 0;

    // Mouse tilt parallax on hover
    var mouseX = 0;
    var mouseY = 0;
    var tiltX = 0;
    var tiltY = 0;

    // Spring physics state for the 3 gimbals
    // Ring 1 = Yaw, Ring 2 = Pitch, Ring 3 = Roll
    var g1 = { val: 0, target: 0, vel: 0 };
    var g2 = { val: 0, target: 0, vel: 0 };
    var g3 = { val: 0, target: 0, vel: 0 };

    function onDragStart(clientX) {
      isDragging = true;
      prevX = clientX;
      renderer.domElement.style.cursor = 'grabbing';
    }

    function onDragMove(clientX) {
      if (!isDragging) return;
      var deltaX = clientX - prevX;
      prevX = clientX;

      baseYaw += deltaX * 0.014;

      // When user drags Ring 1, torque induces dynamic compliance in Ring 2 and Ring 3!
      // This produces that realistic organic flex / inertia
      var impulse = deltaX * 0.018;
      g2.vel += impulse * 0.65;
      g3.vel -= impulse * 0.45;
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
      // Perspective tilt
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

    // Gyroscope Spring Integrator
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
      tiltX += (mouseY * 0.35 - tiltX) * 0.06;
      tiltY += (mouseX * 0.45 - tiltY) * 0.06;
      gyroRoot.rotation.x = tiltX;
      gyroRoot.rotation.y = tiltY;

      // Idle gyroscopic precession
      if (!isDragging) {
        baseYaw += Math.sin(time * 0.5) * 0.0018;
      }

      // --- Coupled Gyroscopic Dynamics ---
      // Primary Ring 1 (Yaw) target
      var g1Target = baseYaw + Math.sin(time * 0.6) * 0.12;

      // Ring 2 (Pitch): Mechanically coupled to Ring 1 with harmonic lag + gentle nutation
      // When Ring 1 moves fast, it exerts torque on Ring 2!
      var g1Rate = (g1Target - g1.val);
      var g2Target = Math.sin(time * 0.8) * 0.22 + g1Rate * 0.45;

      // Ring 3 (Roll): Mechanically coupled to Ring 2 with harmonic lag + spin
      var g2Rate = (g2Target - g2.val);
      var g3Target = Math.cos(time * 0.95) * 0.18 + g2Rate * 0.35;

      // Update spring-damper physics for realistic instrument flex
      updateSpring(g1, g1Target, 16.0, 4.8, dt);
      updateSpring(g2, g2Target, 14.0, 4.2, dt);
      updateSpring(g3, g3Target, 12.0, 3.8, dt);

      // Apply rotations:
      // Ring 1 rotates around its normal Y:
      ring1Group.rotation.y = g1.val;

      // Ring 2 rotates around its normal X (orthogonal to Ring 1!):
      ring2Group.rotation.x = g2.val;

      // Ring 3 rotates around its normal Z (orthogonal to Ring 1 and Ring 2!):
      ring3Group.rotation.z = g3.val;

      // Avatar follows primary yaw smoothly, keeping face oriented front-facing
      avatarRoot.rotation.y = g1.val * 0.85 + Math.sin(time * 0.7) * 0.08;
      avatarRoot.rotation.x = 0;
      avatarRoot.rotation.z = 0;

      // Orbiting electron beads on each ring
      eAngle1 += 0.022;
      electron1.position.set(Math.cos(eAngle1) * r1Radius, 0, Math.sin(eAngle1) * r1Radius);

      eAngle2 += 0.018;
      electron2.position.set(0, Math.cos(eAngle2) * r2Radius, Math.sin(eAngle2) * r2Radius);

      eAngle3 += 0.025;
      electron3.position.set(Math.cos(eAngle3) * r3Radius, Math.sin(eAngle3) * r3Radius, 0);

      // Starfield slow drift
      pointCloud.rotation.y = time * 0.04;

      renderer.render(scene, camera);
    }
    animate();
  }

  window.initQuantumAvatar = initQuantumAvatar;
})();
