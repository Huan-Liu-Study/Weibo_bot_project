// ==================== THREE.JS GOLD PARTICLE SPHERE ====================

(function initParticleSphere() {
    const canvas = document.getElementById('particleCanvas');
    if (!canvas) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0xf5f0eb, 1);  // warm cream background

    // Create confetti-like particles using small planes
    const PARTICLE_COUNT = 2500;
    const radius = 3.2;
    const group = new THREE.Group();

    // Gold color palette
    const goldColors = [
        new THREE.Color(0xC9A84C),  // dark gold
        new THREE.Color(0xD4B95A),  // medium gold
        new THREE.Color(0xE0CA68),  // light gold
        new THREE.Color(0xB8943D),  // bronze
        new THREE.Color(0xCFBE7A),  // pale gold
        new THREE.Color(0xA88734),  // deep bronze
    ];

    // Store particle data for animation
    const particleData = [];

    for (let i = 0; i < PARTICLE_COUNT; i++) {
        // Random position on sphere surface
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = radius + (Math.random() - 0.5) * 0.8;

        const x = r * Math.sin(phi) * Math.cos(theta);
        const y = r * Math.sin(phi) * Math.sin(theta);
        const z = r * Math.cos(phi);

        // Small square geometry (confetti)
        const size = 0.02 + Math.random() * 0.04;
        const geo = new THREE.PlaneGeometry(size, size * (0.6 + Math.random() * 0.8));
        const color = goldColors[Math.floor(Math.random() * goldColors.length)];

        const mat = new THREE.MeshBasicMaterial({
            color: color,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.5 + Math.random() * 0.45,
        });

        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(x, y, z);

        // Random initial rotation
        mesh.rotation.set(
            Math.random() * Math.PI * 2,
            Math.random() * Math.PI * 2,
            Math.random() * Math.PI * 2
        );

        group.add(mesh);

        particleData.push({
            mesh,
            basePos: { x, y, z },
            rotSpeed: {
                x: (Math.random() - 0.5) * 0.02,
                y: (Math.random() - 0.5) * 0.02,
                z: (Math.random() - 0.5) * 0.02,
            },
            floatPhase: Math.random() * Math.PI * 2,
            floatSpeed: 0.3 + Math.random() * 0.5,
            floatAmp: 0.03 + Math.random() * 0.05,
        });
    }

    scene.add(group);
    camera.position.z = 7;

    // Mouse interaction
    let mouseX = 0, mouseY = 0;
    let targetRotX = 0, targetRotY = 0;
    document.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    });

    // Speed control
    let rotationSpeed = 0.0008;
    window._setParticleSpeed = function(speed) { rotationSpeed = speed; };

    // Animation loop
    function animate(time) {
        requestAnimationFrame(animate);
        const t = time * 0.001;

        // Slow sphere rotation
        group.rotation.y += rotationSpeed;
        group.rotation.x += rotationSpeed * 0.3;

        // Smooth mouse follow
        targetRotY += (mouseX * 0.3 - targetRotY) * 0.02;
        targetRotX += (-mouseY * 0.2 - targetRotX) * 0.02;
        group.rotation.y += targetRotY * 0.01;
        group.rotation.x += targetRotX * 0.01;

        // Animate each particle (flutter effect)
        for (let i = 0; i < particleData.length; i++) {
            const pd = particleData[i];
            const m = pd.mesh;

            // Gentle floating
            const floatOffset = Math.sin(t * pd.floatSpeed + pd.floatPhase) * pd.floatAmp;
            m.position.x = pd.basePos.x + floatOffset;
            m.position.y = pd.basePos.y + Math.cos(t * pd.floatSpeed * 0.7 + pd.floatPhase) * pd.floatAmp;
            m.position.z = pd.basePos.z + Math.sin(t * pd.floatSpeed * 0.5 + pd.floatPhase * 1.3) * pd.floatAmp;

            // Tumble rotation (confetti flutter)
            m.rotation.x += pd.rotSpeed.x;
            m.rotation.y += pd.rotSpeed.y;
            m.rotation.z += pd.rotSpeed.z;
        }

        renderer.render(scene, camera);
    }
    animate(0);

    // Make group accessible for external animations
    window._particleGroup = group;
    
    // Resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
})();
