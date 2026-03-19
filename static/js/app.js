/* ============================================================ */
/*  Weibo Bot Shield — Main Application Script                   */
/*  Three.js Gold Confetti Sphere + API + ECharts                */
/* ============================================================ */

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

    // Resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
})();


// ==================== TAB SWITCHING ====================

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
});


// ==================== DEPTH SLIDER ====================

const depthSlider = document.getElementById('depthSlider');
const depthVal = document.getElementById('depthVal');
if (depthSlider) {
    depthSlider.addEventListener('input', () => {
        depthVal.textContent = depthSlider.value;
    });
}


// ==================== TOPIC DETECTION ====================

const topicBtn = document.getElementById('topicBtn');
if (topicBtn) {
    topicBtn.addEventListener('click', async () => {
        const topic = document.getElementById('topicInput').value.trim();
        if (!topic) { alert('请输入话题关键词'); return; }

        const depth = parseInt(depthSlider.value);

        // UI: loading state
        topicBtn.disabled = true;
        topicBtn.querySelector('.btn-text').style.display = 'none';
        topicBtn.querySelector('.btn-loading').style.display = 'flex';
        if (window._setParticleSpeed) window._setParticleSpeed(0.006);

        try {
            const res = await fetch('/api/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, limit: depth })
            });
            const data = await res.json();

            if (data.error) {
                showError('topicResults', data.error);
            } else {
                renderTopicResults(data);
            }
        } catch (e) {
            showError('topicResults', '请求失败：' + e.message);
        } finally {
            topicBtn.disabled = false;
            topicBtn.querySelector('.btn-text').style.display = '';
            topicBtn.querySelector('.btn-loading').style.display = 'none';
            if (window._setParticleSpeed) window._setParticleSpeed(0.0008);
        }
    });
}

function showError(containerId, msg) {
    const container = document.getElementById(containerId);
    container.style.display = 'block';
    container.innerHTML = `<div class="error-msg">⚠️ ${msg}</div>`;
}

function renderTopicResults(data) {
    const container = document.getElementById('topicResults');
    container.style.display = 'block';

    const s = data.summary;
    document.getElementById('stat-total').textContent = s.total_scanned;
    document.getElementById('stat-bots').textContent = s.bot_count;
    document.getElementById('stat-ratio').textContent = s.bot_ratio + '%';

    const sent = s.overall_sentiment;
    const sentEl = document.getElementById('stat-sentiment');
    sentEl.textContent = (sent * 100).toFixed(0);

    renderPieChart(s.total_scanned - s.bot_count, s.bot_count);

    if (data.radar_metrics && data.radar_metrics.humans && data.radar_metrics.bots) {
        renderRadarChart('radarChart', data.radar_metrics.humans, data.radar_metrics.bots);
    }

    renderSuspects(data.suspects || []);
}

function renderPieChart(humans, bots) {
    const chart = echarts.init(document.getElementById('pieChart'));
    chart.setOption({
        tooltip: { trigger: 'item', backgroundColor: '#fff', borderColor: '#e8e0d4', textStyle: { color: '#2c2418' } },
        legend: { bottom: 10, textStyle: { color: '#8a7e6b' } },
        series: [{
            type: 'pie',
            radius: ['45%', '70%'],
            itemStyle: { borderRadius: 6, borderColor: '#f5f0eb', borderWidth: 3 },
            label: { show: true, color: '#2c2418', formatter: '{b}\n{d}%' },
            data: [
                { value: humans, name: '正常用户', itemStyle: { color: '#7cb87a' } },
                { value: bots, name: '疑似水军', itemStyle: { color: '#c96b5e' } }
            ]
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderRadarChart(containerId, humansData, botsData) {
    const featureNames = {
        daily_post_rate: '发帖频率', human_likeness_score: '语义拟人度',
        exclamation_density: '感叹号密度', is_random_name: '乱码昵称',
        engagement_count: '互动量', is_verified: 'V认证',
        sentiment_score: '情感极性', topic_diversity: '话题多样性',
        post_interval_variance: '间隔方差'
    };

    const keys = Object.keys(featureNames);
    const indicators = keys.map(k => ({
        name: featureNames[k],
        max: Math.max(humansData[k] || 0, botsData[k] || 0, 1) * 1.3
    }));

    const chart = echarts.init(document.getElementById(containerId));
    chart.setOption({
        tooltip: { backgroundColor: '#fff', borderColor: '#e8e0d4', textStyle: { color: '#2c2418' } },
        legend: { bottom: 5, textStyle: { color: '#8a7e6b' }, data: ['正常用户', '疑似水军'] },
        radar: {
            indicator: indicators,
            axisName: { color: '#8a7e6b', fontSize: 11 },
            splitArea: { areaStyle: { color: ['transparent'] } },
            axisLine: { lineStyle: { color: '#e8e0d4' } },
            splitLine: { lineStyle: { color: '#e8e0d4' } }
        },
        series: [{
            type: 'radar',
            data: [
                { value: keys.map(k => humansData[k] || 0), name: '正常用户', areaStyle: { color: 'rgba(124,184,122,0.2)' }, lineStyle: { color: '#7cb87a' }, itemStyle: { color: '#7cb87a' } },
                { value: keys.map(k => botsData[k] || 0), name: '疑似水军', areaStyle: { color: 'rgba(201,107,94,0.2)' }, lineStyle: { color: '#c96b5e' }, itemStyle: { color: '#c96b5e' } }
            ]
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderSuspects(suspects) {
    const list = document.getElementById('suspectList');
    if (!suspects.length) {
        list.innerHTML = '<p style="color:var(--text-dim);padding:20px;text-align:center;">未检出高危水军账号 🎉</p>';
        return;
    }
    list.innerHTML = suspects.map(s => {
        const score = (s.bot_probability * 100).toFixed(0);
        const level = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';
        const text = (s['微博正文'] || s.text || '').substring(0, 80);
        const name = s['用户昵称'] || s.screen_name || 'UID:' + s.user_id;
        return `
            <div class="suspect-item">
                <div class="suspect-score ${level}">${score}%</div>
                <div class="suspect-info">
                    <div class="suspect-name">${escapeHtml(name)}</div>
                    <div class="suspect-text">"${escapeHtml(text)}"</div>
                    <div class="suspect-meta">
                        <span>粉丝 ${s.followers_count || 0}</span>
                        <span>发帖 ${s.statuses_count || 0}</span>
                    </div>
                </div>
            </div>`;
    }).join('');
}


// ==================== SINGLE USER DETECTION ====================

const userBtn = document.getElementById('userBtn');
if (userBtn) {
    userBtn.addEventListener('click', async () => {
        const uid = document.getElementById('uidInput').value.trim();
        if (!uid) { alert('请输入微博用户 UID'); return; }

        userBtn.disabled = true;
        userBtn.querySelector('.btn-text').style.display = 'none';
        userBtn.querySelector('.btn-loading').style.display = 'flex';
        if (window._setParticleSpeed) window._setParticleSpeed(0.005);

        try {
            const res = await fetch('/api/check_user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid })
            });
            const data = await res.json();

            if (data.error) {
                showError('userResults', data.error);
            } else {
                renderUserResults(data);
            }
        } catch (e) {
            showError('userResults', '请求失败：' + e.message);
        } finally {
            userBtn.disabled = false;
            userBtn.querySelector('.btn-text').style.display = '';
            userBtn.querySelector('.btn-loading').style.display = 'none';
            if (window._setParticleSpeed) window._setParticleSpeed(0.0008);
        }
    });
}

function renderUserResults(data) {
    const container = document.getElementById('userResults');
    container.style.display = 'block';

    const info = data.user_info || {};
    document.getElementById('userName').textContent = info.screen_name || 'UID: ' + info.uid;
    document.getElementById('userMeta').textContent =
        `粉丝 ${info.followers_count || 0} · 关注 ${info.friends_count || 0} · 微博 ${info.statuses_count || 0}`;

    const avatarEl = document.getElementById('userAvatar');
    if (info.avatar_hd && info.avatar_hd.length > 10) {
        avatarEl.innerHTML = `<img src="${info.avatar_hd}" alt="avatar">`;
    } else {
        avatarEl.textContent = (info.screen_name || '?')[0];
    }

    // Gauge
    const score = data.suspicion_score || 0;
    const pct = Math.round(score * 100);
    const circumference = 2 * Math.PI * 54;
    const offset = circumference * (1 - score);

    const arc = document.getElementById('gaugeArc');
    arc.style.strokeDashoffset = offset;
    arc.style.stroke = score >= 0.7 ? '#c96b5e' : score >= 0.4 ? '#c9a84c' : '#7cb87a';

    const gaugeValue = document.getElementById('gaugeValue');
    gaugeValue.textContent = pct + '%';
    gaugeValue.style.color = score >= 0.7 ? '#c96b5e' : score >= 0.4 ? '#c9a84c' : '#7cb87a';

    const labelMap = { 0: '确定真人', 1: '大概率真人', 2: '不确定', 3: '比较可疑', 4: '几乎确定水军' };
    document.getElementById('gaugeLabel').textContent = labelMap[data.suspicion_label] || '可疑度评分';

    if (data.features) renderUserRadar(data.features);
    if (data.reasons) renderReasons(data.reasons);
}

function renderUserRadar(features) {
    const featureNames = {
        daily_post_rate: '发帖频率', human_likeness_score: '语义拟人度',
        exclamation_density: '感叹号密度', is_random_name: '乱码昵称',
        engagement_count: '互动量', is_verified: 'V认证',
        sentiment_score: '情感极性', topic_diversity: '话题多样性',
        post_interval_variance: '间隔方差'
    };

    const keys = Object.keys(featureNames);
    const maxVals = {
        daily_post_rate: 5, human_likeness_score: 1, exclamation_density: 0.1,
        is_random_name: 1, engagement_count: 100, is_verified: 1,
        sentiment_score: 1, topic_diversity: 1, post_interval_variance: 5
    };

    const indicators = keys.map(k => ({ name: featureNames[k], max: 1 }));
    const values = keys.map(k => Math.min(1, (features[k] || 0) / maxVals[k]));

    const chart = echarts.init(document.getElementById('userRadar'));
    chart.setOption({
        tooltip: { backgroundColor: '#fff', borderColor: '#e8e0d4', textStyle: { color: '#2c2418' } },
        radar: {
            indicator: indicators,
            axisName: { color: '#8a7e6b', fontSize: 11 },
            splitArea: { areaStyle: { color: ['transparent'] } },
            axisLine: { lineStyle: { color: '#e8e0d4' } },
            splitLine: { lineStyle: { color: '#e8e0d4' } }
        },
        series: [{
            type: 'radar',
            data: [{
                value: values, name: '特征画像',
                areaStyle: { color: 'rgba(201,168,76,0.2)' },
                lineStyle: { color: '#c9a84c', width: 2 },
                itemStyle: { color: '#c9a84c' }
            }]
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderReasons(reasons) {
    const list = document.getElementById('reasonsList');
    list.innerHTML = reasons.map(r => {
        const cls = r.level === 'high' ? 'flag-high' : r.level === 'medium' ? 'flag-medium' : 'flag-low';
        return `<li class="${cls}">${escapeHtml(r.text)}</li>`;
    }).join('');
}


// ==================== UTILS ====================

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
