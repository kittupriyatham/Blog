/**
 * Quantum Avatar — Interactive 3D WebGL Hologram Badge
 * Built with Three.js for Potluri Krishna Priyatham (Kittu Priyatham)
 * PhD Scholar in Quantum Technologies @ SRM AP University
 */

(function () {
  function initQuantumAvatar(containerId, avatarUrl) {
    var container = document.getElementById(containerId);
    if (!container) return;

    // Check if WebGL is available
    function hasWebGL() {
      try {
        var canvas = document.createElement('canvas');
        return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
      } catch (e) {
        return false;
      }
    }

    if (!hasWebGL()) {
      container.innerHTML = '<img src="' + avatarUrl + '" alt="Avatar" class="w-full h-full object-cover rounded-full border-4 border-indigo-500/40 shadow-xl" />';
      return;
    }

    // Ensure Three.js is loaded
    if (typeof THREE === 'undefined') {
      var script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
      script.onload = function () { setupScene(container, avatarUrl); };
      document.head.appendChild(script);
    } else {
      setupScene(container, avatarUrl);
    }
  }

  function setupScene(container, avatarUrl) {
    var width = container.clientWidth || 320;
    var height = container.clientHeight || 320;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 4.2;

    var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    var group = new THREE.Group();
    scene.add(group);

    // 1. Avatar Core Disc
    var textureLoader = new THREE.TextureLoader();
    textureLoader.load(avatarUrl, function (tex) {
      tex.generateMipmaps = true;
      tex.minFilter = THREE.LinearMipmapLinearFilter;

      // Front avatar photo disc
      var circleGeo = new THREE.CircleGeometry(1.08, 64);
      var circleMat = new THREE.MeshBasicMaterial({
        map: tex,
        transparent: true,
        side: THREE.DoubleSide
      });
      var avatarMesh = new THREE.Mesh(circleGeo, circleMat);
      avatarMesh.position.z = 0.05;
      group.add(avatarMesh);

      // Backplate rim disc with subtle glow
      var backGeo = new THREE.CylinderGeometry(1.16, 1.16, 0.08, 64);
      backGeo.rotateX(Math.PI / 2);
      var backMat = new THREE.MeshStandardMaterial({
        color: 0x1e1b4b,
        metalness: 0.8,
        roughness: 0.2,
        emissive: 0x312e81,
        emissiveIntensity: 0.35
      });
      var backMesh = new THREE.Mesh(backGeo, backMat);
      backMesh.position.z = 0.01;
      group.add(backMesh);

      // Outer glowing bevel ring
      var bevelGeo = new THREE.TorusGeometry(1.14, 0.035, 16, 100);
      var bevelMat = new THREE.MeshStandardMaterial({
        color: 0x818cf8,
        emissive: 0x4f46e5,
        emissiveIntensity: 0.7,
        metalness: 0.9,
        roughness: 0.1
      });
      var bevelMesh = new THREE.Mesh(bevelGeo, bevelMat);
      bevelMesh.position.z = 0.06;
      group.add(bevelMesh);
    });

    // 2. Nested Quantum Orbital Rings (Bloch / Atom Qubit geometry)
    var rings = [];
    var ringConfigs = [
      { radius: 1.42, tube: 0.016, color: 0x06b6d4, emissive: 0x0891b2, rotX: 0.9, rotY: 0.4, speed: 0.012 },
      { radius: 1.62, tube: 0.014, color: 0x818cf8, emissive: 0x6366f1, rotX: -0.7, rotY: 0.8, speed: -0.009 },
      { radius: 1.82, tube: 0.012, color: 0xf59e0b, emissive: 0xd97706, rotX: 1.2, rotY: -0.5, speed: 0.015 }
    ];

    ringConfigs.forEach(function (cfg) {
      var rGeo = new THREE.TorusGeometry(cfg.radius, cfg.tube, 16, 100);
      var rMat = new THREE.MeshStandardMaterial({
        color: cfg.color,
        emissive: cfg.emissive,
        emissiveIntensity: 0.8,
        metalness: 0.5,
        roughness: 0.2,
        transparent: true,
        opacity: 0.85
      });
      var ringMesh = new THREE.Mesh(rGeo, rMat);
      ringMesh.rotation.x = cfg.rotX;
      ringMesh.rotation.y = cfg.rotY;

      // Orbiting Quantum Particle / Electron
      var partGeo = new THREE.SphereGeometry(0.045, 16, 16);
      var partMat = new THREE.MeshBasicMaterial({ color: cfg.color });
      var particle = new THREE.Mesh(partGeo, partMat);
      particle.position.x = cfg.radius;
      ringMesh.add(particle);

      group.add(ringMesh);
      rings.push({ mesh: ringMesh, cfg: cfg, angle: Math.random() * Math.PI * 2, particle: particle });
    });

    // 3. Ambient & Interactive 3D Lighting
    var ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    var pointLight = new THREE.PointLight(0x818cf8, 1.8, 20);
    pointLight.position.set(2, 3, 4);
    scene.add(pointLight);

    var cursorLight = new THREE.PointLight(0x06b6d4, 1.2, 10);
    cursorLight.position.set(0, 0, 3);
    scene.add(cursorLight);

    // 4. Mouse and Touch Parallax
    var targetRotX = 0;
    var targetRotY = 0;
    var isHovered = false;

    function onPointerMove(e) {
      var rect = container.getBoundingClientRect();
      var clientX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      var clientY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0);

      var x = ((clientX - rect.left) / rect.width) * 2 - 1;
      var y = -(((clientY - rect.top) / rect.height) * 2 - 1);

      targetRotY = x * 0.45;
      targetRotX = -y * 0.45;

      cursorLight.position.x = x * 2.5;
      cursorLight.position.y = y * 2.5;
    }

    container.addEventListener('mousemove', function (e) {
      isHovered = true;
      onPointerMove(e);
    });
    container.addEventListener('mouseleave', function () {
      isHovered = false;
      targetRotX = 0;
      targetRotY = 0;
    });

    container.addEventListener('touchmove', function (e) {
      isHovered = true;
      onPointerMove(e);
    }, { passive: true });
    container.addEventListener('touchend', function () {
      isHovered = false;
      targetRotX = 0;
      targetRotY = 0;
    });

    // Click / Tap Quantum Pulse
    var pulseFactor = 1.0;
    container.addEventListener('click', function () {
      pulseFactor = 1.25;
    });

    // Handle Resize
    window.addEventListener('resize', function () {
      if (!container.clientWidth || !container.clientHeight) return;
      var newW = container.clientWidth;
      var newH = container.clientHeight;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    });

    // 5. Animation Loop
    var clock = new THREE.Clock();

    function animate() {
      requestAnimationFrame(animate);
      var delta = clock.getDelta();
      var time = clock.getElapsedTime();

      // Smooth camera/group tilt
      group.rotation.x += (targetRotX - group.rotation.x) * 0.08;
      group.rotation.y += (targetRotY - group.rotation.y) * 0.08;

      // Subtle breathing float when idle
      if (!isHovered) {
        group.position.y = Math.sin(time * 1.5) * 0.05;
        group.rotation.z = Math.sin(time * 0.8) * 0.02;
      }

      // Quantum rings spin & particles orbit
      rings.forEach(function (r, idx) {
        r.mesh.rotation.z += r.cfg.speed;
        r.mesh.rotation.x += r.cfg.speed * 0.5;

        r.angle += r.cfg.speed * 2.2;
        r.particle.position.x = Math.cos(r.angle) * r.cfg.radius;
        r.particle.position.y = Math.sin(r.angle) * r.cfg.radius;
      });

      // Pulse decay
      if (pulseFactor > 1.0) {
        pulseFactor += (1.0 - pulseFactor) * 0.05;
      }
      group.scale.set(pulseFactor, pulseFactor, pulseFactor);

      renderer.render(scene, camera);
    }

    animate();
  }

  window.initQuantumAvatar = initQuantumAvatar;
})();
