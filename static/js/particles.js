// ==================== PREMIUM NEURAL NETWORK SPHERE (THREE.JS) ====================
// A sophisticated, connected particle network with gold/bronze aesthetics

(function initRefinedParticles() {
    const canvas = document.getElementById('particleCanvas');
    if (!canvas) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ 
        canvas, 
        antialias: true, 
        alpha: true,
        powerPreference: "high-performance" 
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0xf5f0eb, 1); // Maintain the warm cream background

    // Create a group to hold everything (for easier global animation/scale)
    const group = new THREE.Group();
    scene.add(group);

    // --- Configuration ---
    const PARTICLE_COUNT = 850;
    const CONNECT_DISTANCE = 0.8;
    const SPHERE_RADIUS = 3.5;
    
    // Gold/Bronze Color Palette
    const colors = [
        0xC9A84C, // Gold
        0xD4B95A, // Light Gold
        0xB8943D, // Bronze
        0xCFBE7A  // Pale Gold
    ];

    // --- Geometries ---
    const particlesGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    const particleVelocities = [];

    for (let i = 0; i < PARTICLE_COUNT; i++) {
        // Distribute points on a sphere surface with some volume depth
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = SPHERE_RADIUS * (0.85 + Math.random() * 0.3);

        const x = r * Math.sin(phi) * Math.cos(theta);
        const y = r * Math.sin(phi) * Math.sin(theta);
        const z = r * Math.cos(phi);

        positions[i * 3] = x;
        positions[i * 3 + 1] = y;
        positions[i * 3 + 2] = z;

        // Velocity for drift animation
        particleVelocities.push(new THREE.Vector3(
            (Math.random() - 0.5) * 0.002,
            (Math.random() - 0.5) * 0.002,
            (Math.random() - 0.5) * 0.002
        ));
    }

    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage));

    // --- Helper: Create a glowy circle texture for premium nodes ---
    const createNodeTexture = () => {
        const canvas = document.createElement('canvas');
        canvas.width = 64; canvas.height = 64;
        const ctx = canvas.getContext('2d');
        const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
        grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
        grad.addColorStop(0.2, 'rgba(212, 185, 90, 0.8)');
        grad.addColorStop(0.5, 'rgba(184, 148, 61, 0.2)');
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 64, 64);
        const tex = new THREE.CanvasTexture(canvas);
        return tex;
    };

    // --- Points (Nodes) ---
    const pMaterial = new THREE.PointsMaterial({
        color: 0xffffff,
        size: 0.12,
        map: createNodeTexture(),
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending,
        depthWrite: false, 
        sizeAttenuation: true
    });
    const points = new THREE.Points(particlesGeometry, pMaterial);
    group.add(points);

    // --- Lines (Connections) ---
    const lineMaterial = new THREE.LineBasicMaterial({
        color: 0xD4B95A,
        transparent: true,
        opacity: 0.22, // Slightly more visible
        blending: THREE.NormalBlending 
    });
    const linesGeometry = new THREE.BufferGeometry();
    const MAX_CONNECTIONS = PARTICLE_COUNT * 40; // Optimize buffer size
    const linePositions = new Float32Array(MAX_CONNECTIONS * 6); 
    linesGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3).setUsage(THREE.DynamicDrawUsage));
    const connections = new THREE.LineSegments(linesGeometry, lineMaterial);
    group.add(connections);

    camera.position.z = 8;

    // --- Interaction & State ---
    let mouseX = 0, mouseY = 0;
    let targetRotX = 0, targetRotY = 0;
    let rotationSpeed = 0.0006;

    document.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    });

    window._setParticleSpeed = function(speed) { rotationSpeed = speed; };
    window._particleGroup = group;

    // --- Animation Loop ---
    function animate() {
        requestAnimationFrame(animate);

        // 1. Automatic sphere rotation
        group.rotation.y += rotationSpeed;
        group.rotation.x += rotationSpeed * 0.4;

        // 2. Mouse parallax effect
        targetRotY += (mouseX * 0.4 - targetRotY) * 0.03;
        targetRotX += (-mouseY * 0.3 - targetRotX) * 0.03;
        group.rotation.y += targetRotY * 0.012;
        group.rotation.x += targetRotX * 0.012;

        // 3. Update particle positions (drift + mouse repulsion)
        const posAttr = particlesGeometry.attributes.position;
        let lineIdx = 0;

        // Mouse projected to 3D roughly
        const mouseVec = new THREE.Vector3(mouseX * 4, -mouseY * 4, 0); 

        for (let i = 0; i < PARTICLE_COUNT; i++) {
            const ix = i * 3, iy = i * 3 + 1, iz = i * 3 + 2;
            
            // 3.1 Velocity drift
            const v = particleVelocities[i];
            posAttr.array[ix] += v.x;
            posAttr.array[iy] += v.y;
            posAttr.array[iz] += v.z;

            // 3.2 Mouse repulsion (Interactive!)
            const pX = posAttr.array[ix], pY = posAttr.array[iy], pZ = posAttr.array[iz];
            const distToMouse = Math.sqrt((pX - mouseVec.x)**2 + (pY - mouseVec.y)**2);
            if (distToMouse < 1.5) {
                const force = (1.5 - distToMouse) * 0.015;
                posAttr.array[ix] += (pX - mouseVec.x) * force;
                posAttr.array[iy] += (pY - mouseVec.y) * force;
            }

            // 3.3 Elastic return to sphere shell
            const currentR = Math.sqrt(pX*pX + pY*pY + pZ*pZ);
            const targetR = SPHERE_RADIUS;
            const pull = (targetR - currentR) * 0.01;
            posAttr.array[ix] += (pX/currentR) * pull;
            posAttr.array[iy] += (pY/currentR) * pull;
            posAttr.array[iz] += (pZ/currentR) * pull;
        }
        posAttr.needsUpdate = true;

        // 4. Update connections (Line segments)
        // Optimization: only connect nearby points
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            for (let j = i + 1; j < PARTICLE_COUNT; j++) {
                const dx = posAttr.array[i * 3] - posAttr.array[j * 3];
                const dy = posAttr.array[i * 3 + 1] - posAttr.array[j * 3 + 1];
                const dz = posAttr.array[i * 3 + 2] - posAttr.array[j * 3 + 2];
                const distSq = dx*dx + dy*dy + dz*dz;

                if (distSq < CONNECT_DISTANCE * CONNECT_DISTANCE) {
                    linePositions[lineIdx++] = posAttr.array[i * 3];
                    linePositions[lineIdx++] = posAttr.array[i * 3 + 1];
                    linePositions[lineIdx++] = posAttr.array[i * 3 + 2];

                    linePositions[lineIdx++] = posAttr.array[j * 3];
                    linePositions[lineIdx++] = posAttr.array[j * 3 + 1];
                    linePositions[lineIdx++] = posAttr.array[j * 3 + 2];
                }
                
                // Safety break to prevent buffer overflow (unlikely with this count)
                if (lineIdx > linePositions.length - 6) break;
            }
        }
        connections.geometry.setDrawRange(0, lineIdx / 3);
        connections.geometry.attributes.position.needsUpdate = true;

        renderer.render(scene, camera);
    }

    animate();

    // Resize Handler
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
})();
