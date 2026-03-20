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

    // Make group accessible for external animations
    window._particleGroup = group;
    
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
        const tab = btn.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const panel = document.getElementById('tab-' + tab);
        if (panel) panel.classList.add('active');
        
        if (tab === 'history') {
            fetchHistory();
        }
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
        
        // --- Added: Progress UI ---
        const progressArea = document.getElementById('topicProgress');
        const progressFill = document.getElementById('progressFill');
        const progressStatus = document.getElementById('progressStatus');
        const progressTime = document.getElementById('progressTime');
        const resultsArea = document.getElementById('topicResults');
        
        resultsArea.style.display = 'none';
        progressArea.style.display = 'block';
        progressFill.style.width = '0%';
        progressStatus.textContent = '初始化组件中...';
        
        // Estimated time: ~2.2s per item + 8s overhead
        let timeLeft = Math.ceil(depth * 2.2 + 8);
        progressTime.textContent = `预计剩余: ${timeLeft}秒`;
        
        if (window._setParticleSpeed) window._setParticleSpeed(0.008);

        // Progress Timer Logic
        let progressPercent = 0;
        const timer = setInterval(() => {
            if (timeLeft > 0) {
                timeLeft--;
                progressTime.textContent = `预计剩余: ${timeLeft}秒`;
                
                // Fake progress bar increment (nonlinear for realism)
                if (progressPercent < 90) {
                    progressPercent += (90 - progressPercent) * 0.05;
                    progressFill.style.width = progressPercent + '%';
                }
                
                // Status text updates
                if (timeLeft % 5 === 0) {
                    const statuses = ['正在下发采集任务...', '绕过微博反爬验证...', '模型正在实时特征提取...', '计算社交网络相似度...', '解析账号行为特征...'];
                    progressStatus.textContent = statuses[Math.floor(Math.random() * statuses.length)];
                }
            }
        }, 1000);

        try {
            const res = await fetch('/api/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, limit: depth, continue: window._lastCrawlTopic === topic })
            });

            // Remember the topic/depth for continuation
            window._lastCrawlTopic = topic;
            window._lastCrawlDepth = depth;

            const data = await res.json();

            clearInterval(timer);
            progressFill.style.width = '100%';
            progressStatus.textContent = '分析完成！';
            setTimeout(() => { progressArea.style.display = 'none'; }, 500);

            if (data.error) {
                showError('topicResults', data.error);
            } else {
                renderTopicResults(data, data.crawl_info);
            }
        } catch (e) {
            clearInterval(timer);
            progressArea.style.display = 'none';
            showError('topicResults', '请求失败：' + e.message);
        } finally {
            topicBtn.disabled = false;
            topicBtn.querySelector('.btn-text').style.display = '';
            topicBtn.querySelector('.btn-loading').style.display = 'none';
            if (window._setParticleSpeed) window._setParticleSpeed(0.0008);
        }
    });

    // --- v1.7.5: Continue Depth Slider ---
    const continueSlider = document.getElementById('continueDepthSlider');
    const continueVal = document.getElementById('continueDepthVal');
    continueSlider.addEventListener('input', (e) => {
        continueVal.textContent = e.target.value;
    });

    // --- v1.7.0: "继续深入采集" button ---
    document.getElementById('continueBtn').addEventListener('click', () => {
        const topic = window._lastCrawlTopic;
        const depth = continueSlider.value || 20;
        if (!topic) return;

        // Sync main UI inputs so the main handler picks them up
        document.getElementById('topicInput').value = topic;
        document.getElementById('depthSlider').value = depth;
        document.getElementById('depthVal').textContent = depth;

        // Programmatically trigger the detection button
        document.getElementById('topicBtn').click();
    });
}

function showError(containerId, msg) {
    const container = document.getElementById(containerId);
    container.style.display = 'block';
    container.innerHTML = `<div class="error-msg">⚠️ ${msg}</div>`;
}

function renderTopicResults(data, crawlInfo) {
    const container = document.getElementById('topicResults');
    container.style.display = 'block';

    // --- v1.7.0: Update continuation banner ---
    const banner = document.getElementById('crawlBanner');
    const bannerText = document.getElementById('crawlBannerText');
    if (crawlInfo) {
        const newCount = crawlInfo.new_fetched || 0;
        const totalCount = crawlInfo.total_fetched || 0;
        bannerText.textContent = `本次新增 ${newCount} 条数据，该话题下已累计分析 ${totalCount} 条帖子`;
        banner.style.display = 'flex';
    } else {
        banner.style.display = 'none';
    }

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
    
    // v1.9.0
    if (data.all_nodes && data.all_nodes.length > 0) {
        renderScatterChart(data.all_nodes);
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

// ==================== DATABASE VISUALIZATION (v1.9.0) ====================
function renderScatterChart(nodes) {
    const chart = echarts.init(document.getElementById('scatterChart'));
    
    // 构造散点图数据 (v1.9.4 分级体系)
    const humansData = [];
    const warningsData = [];
    const botsData = [];
    
    nodes.forEach(n => {
        const item = {
            name: n.name,
            value: [n.single_sentiment_score || n.sentiment_score, n.suspicion_score, n.user_id, n.text, n],
            itemStyle: {
                opacity: 0.82,
                shadowBlur: 10,
                shadowColor: 'rgba(0,0,0,0.15)'
            }
        };
        
        if (n.is_bot_pred === 1) {
            botsData.push(item);
        } else if (n.has_red_flag) {
            warningsData.push(item);
        } else {
            humansData.push(item);
        }
    });
    
    const option = {
        tooltip: {
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            borderColor: '#e8e0d4',
            textStyle: { color: '#2c2418' },
            formatter: function (param) {
                const data = param.data.value;
                const n = data[4];
                const score = (data[1] * 100).toFixed(0) + '%';
                const textPreview = data[3].substring(0, 50) + (data[3].length > 50 ? '...' : '');
                
                let riskLabel = '<span style="color:#7cb87a;">良好</span>';
                let color = '#7cb87a';
                if (n.is_bot_pred === 1) {
                    riskLabel = '<span style="color:#c96b5e;">高危</span>';
                    color = '#c96b5e';
                } else if (n.has_red_flag) {
                    riskLabel = '<span style="color:#f39c12;">预警</span>';
                    color = '#f39c12';
                }
                
                return `
                    <div style="font-weight:600;margin-bottom:6px;border-bottom:1px solid #e8e0d4;padding-bottom:6px;">
                        ${param.data.name} [${riskLabel}] <span style="float:right;color:${color};">${score}</span>
                    </div>
                    <div style="font-size:12px;color:#8a7e6b;max-width:300px;white-space:normal;line-height:1.5;">${escapeHtml(textPreview)}</div>
                    <div style="margin-top:8px;font-size:11px;color:#b8943d;">👉 点击气泡查看由于哪些特征被判定</div>
                `;
            }
        },
        legend: {
            bottom: 10,
            textStyle: { color: '#8a7e6b' },
            data: ['正常用户', '触碰红旗', '疑似水军']
        },
        xAxis: {
            name: '情感倾向 (越右越积极)',
            nameLocation: 'middle',
            nameGap: 30,
            splitLine: { lineStyle: { type: 'dashed', color: '#e8e0d4' } },
            axisLine: { lineStyle: { color: '#8a7e6b' } },
            min: 0, max: 1
        },
        yAxis: {
            name: '系统嫌疑度',
            nameLocation: 'end',
            splitLine: { lineStyle: { type: 'dashed', color: '#e8e0d4' } },
            axisLine: { lineStyle: { color: '#8a7e6b' } },
            min: 0, max: 1
        },
        series: [
            {
                name: '正常用户',
                type: 'scatter',
                data: humansData,
                // v1.9.5: 使用对数缩放 (log10)，防止大V账号气泡遮挡全景
                symbolSize: (data) => Math.min(Math.log10((data[4].followers_count || 0) + 1) * 6 + 6, 40),
                itemStyle: { color: '#7cb87a', borderColor: '#fff', borderWidth: 1 }
            },
            {
                name: '触碰红旗',
                type: 'scatter',
                data: warningsData,
                symbolSize: (data) => Math.min(Math.log10((data[4].followers_count || 0) + 1) * 6 + 10, 45),
                itemStyle: { color: '#f39c12', borderColor: '#fff', borderWidth: 1 }
            },
            {
                name: '疑似水军',
                type: 'scatter',
                data: botsData,
                symbolSize: (data) => Math.min(Math.log10((data[4].followers_count || 0) + 1) * 6 + 14, 50),
                itemStyle: { color: '#c96b5e', borderColor: '#fff', borderWidth: 1 }
            }
        ]

    };
    
    chart.setOption(option, true);
    
    // 监听点击事件，打开弹窗
    chart.off('click');
    chart.on('click', function(params) {
        if (params.data && params.data.value) {
            const rawNodeData = params.data.value[4];
            openNodeModal(rawNodeData);
        }
    });
    
    window.addEventListener('resize', () => chart.resize());
}

function openNodeModal(node) {
    const modal = document.getElementById('nodeModal');
    if (!modal) return;
    
    // 填充数据
    const name = node.name || 'UID:' + node.user_id;
    const score = (node.suspicion_score * 100).toFixed(0);
    const isBot = node.is_bot_pred === 1;
    
    document.getElementById('nmAvatar').textContent = name.substring(0, 1).toUpperCase();
    document.getElementById('nmName').textContent = name;
    document.getElementById('nmMeta').textContent = `UID: ${node.user_id} | 粉丝: ${node.followers_count} | 发帖: ${node.statuses_count}`;
    
    const scoreEl = document.getElementById('nmScore');
    scoreEl.textContent = `${score}%`;
    scoreEl.className = 'suspect-score ' + (score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low');
    if (score >= 70) {
        scoreEl.style.color = '#c96b5e';
        scoreEl.style.backgroundColor = 'rgba(201, 107, 94, 0.12)';
    } else if (score >= 40) {
        scoreEl.style.color = '#b8943d';
        scoreEl.style.backgroundColor = 'rgba(184, 148, 61, 0.12)';
    } else {
        scoreEl.style.color = '#7cb87a';
        scoreEl.style.backgroundColor = 'rgba(124, 184, 122, 0.12)';
    }
    
    document.getElementById('nmText').innerHTML = escapeHtml(node.text).replace(/\n/g, '<br>');
    
    // 理由
    const reasonsUl = document.getElementById('nmReasons');
    if (node.reasons && node.reasons.length > 0) {
        reasonsUl.innerHTML = node.reasons.map(r => {
            let cls = r.level === 'high' ? 'flag-high' : r.level === 'medium' ? 'flag-medium' : 'flag-low';
            if (r.is_red_flag) cls += ' red-flag';
            const icon = r.is_red_flag ? '🚩 ' : '';
            return `<li class="${cls}">${icon}${escapeHtml(r.text)}</li>`;
        }).join('');
    } else {
        reasonsUl.innerHTML = `<li class="flag-low">该账号行为正常，特征处于健康区间。</li>`;
    }
    
    // 显示弹窗
    modal.style.display = 'flex';
    // 异步添加 active 类以触发 CSS 过渡动画 (opacity & transform)
    setTimeout(() => {
        modal.classList.add('active');
    }, 10);
    document.body.style.overflow = 'hidden'; // 防止背景滚动
}

// 绑定背景和关闭按钮
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('closeNodeModal');
    const bg = document.getElementById('nodeModalBackdrop');
    if (btn) btn.addEventListener('click', closeNodeModal);
    if (bg) bg.addEventListener('click', closeNodeModal);
});

function closeNodeModal() {
    const modal = document.getElementById('nodeModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
        // 延时等待 CSS 动画 (0.4s) 结束后彻底隐藏
        setTimeout(() => {
            modal.style.display = 'none';
        }, 400);
    }
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
        const reasonsHtml = s.reasons && s.reasons.length > 0
            ? s.reasons.map(r => {
                const cls = r.level === 'high' ? 'flag-high' : r.level === 'medium' ? 'flag-medium' : 'flag-low';
                return `<li class="${cls}">${escapeHtml(r.text)}</li>`;
            }).join('')
            : '<li class="flag-low">暂无详细判定理由，仅满足评分阈值</li>';

        return `
            <div class="suspect-item">
                <div class="suspect-main" onclick="toggleSuspect(this)">
                    <div class="suspect-score ${level}">${score}%</div>
                    <div class="suspect-info">
                        <div class="suspect-name">${escapeHtml(name)}</div>
                        <div class="suspect-text">"${escapeHtml(text)}"</div>
                        <div class="suspect-meta">
                            <span>粉丝 ${s.followers_count || 0}</span>
                            <span>发帖 ${s.statuses_count || 0}</span>
                        </div>
                    </div>
                    <svg class="suspect-arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
                </div>
                <div class="suspect-reasons" style="display:none">

                    <ul class="reasons-list">
                        ${reasonsHtml}
                    </ul>
                </div>
            </div>`;
    }).join('');
}

window.toggleSuspect = function(element) {
    const parent = element.closest('.suspect-item');
    const reasonsDiv = parent.querySelector('.suspect-reasons');
    const arrow = parent.querySelector('.suspect-arrow');
    
    if (reasonsDiv.style.display === 'none') {
        reasonsDiv.style.display = 'block';
        arrow.style.transform = 'rotate(180deg)';
        parent.style.borderColor = 'var(--border)';
        parent.style.boxShadow = 'var(--shadow)';
    } else {
        reasonsDiv.style.display = 'none';
        arrow.style.transform = 'rotate(0deg)';
        parent.style.borderColor = 'transparent';
        parent.style.boxShadow = 'none';
    }
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


// ==================== SYSTEM INFO OVERLAY (Sphere Expansion) ====================

(function initInfoOverlay() {
    const infoTrigger = document.getElementById('infoTrigger');
    const closeInfo = document.getElementById('closeInfo');
    const infoOverlay = document.getElementById('infoOverlay');
    const overlayBackdrop = infoOverlay.querySelector('.overlay-backdrop');
    
    if (!infoTrigger || !infoOverlay) return;

    let isOpen = false;

    const toggleInfo = (show) => {
        if (show === isOpen) return;
        isOpen = show;

        if (show) {
            infoOverlay.style.display = 'flex';
            
            // GSAP Animation for the Sphere - FIRST
            if (window._particleGroup && window.gsap) {
                window.gsap.to(window._particleGroup.scale, {
                    x: 3.5, y: 3.5, z: 3.5,
                    duration: 1.2,
                    ease: "power2.inOut",
                    onComplete: () => {
                        // Show modal ONLY after sphere expanded
                        if (isOpen) infoOverlay.classList.add('active');
                    }
                });
                window.gsap.to(window._particleGroup.position, {
                    z: -4,
                    duration: 1.2,
                    ease: "power2.inOut"
                });
                if (window._setParticleSpeed) window._setParticleSpeed(0.004);
            } else {
                // Fallback if GSAP/Sphere missing
                infoOverlay.classList.add('active');
            }
        } else {
            // Hide modal content first
            infoOverlay.classList.remove('active');
            
            // Wait for modal to fade out before shrinking sphere
            setTimeout(() => {
                if (isOpen) return; // Guard if reopened
                
                // GSAP Reset for the Sphere
                if (window._particleGroup && window.gsap) {
                    window.gsap.to(window._particleGroup.scale, {
                        x: 1, y: 1, z: 1,
                        duration: 1,
                        ease: "power2.out"
                    });
                    window.gsap.to(window._particleGroup.position, {
                        z: 0,
                        duration: 1,
                        ease: "power2.out",
                        onComplete: () => {
                            if (!isOpen) infoOverlay.style.display = 'none';
                        }
                    });
                    if (window._setParticleSpeed) window._setParticleSpeed(0.0008);
                } else {
                    infoOverlay.style.display = 'none';
                }
            }, 400); // Wait for CSS transition of .info-overlay (.4s in CSS)
        }
    };

    infoTrigger.addEventListener('click', () => toggleInfo(true));
    closeInfo.addEventListener('click', () => toggleInfo(false));
    overlayBackdrop.addEventListener('click', () => toggleInfo(false));
    
    // ESC key to close
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen) toggleInfo(false);
    });
})();

// ==================== HISTORY MANAGEMENT (v1.9.10) ====================

async function fetchHistory() {
    const list = document.getElementById('historyList');
    if (!list) return;
    
    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        
        if (data.status === 'success') {
            renderHistory(data.topics);
        }
    } catch (err) {
        console.error('Fetch history failed:', err);
    }
}

function renderHistory(topics) {
    const list = document.getElementById('historyList');
    if (topics.length === 0) {
        list.innerHTML = `
            <div class="history-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <p>暂无历史记录</p>
            </div>
        `;
        return;
    }
    
    list.innerHTML = topics.map((t, i) => {
        const date = new Date(t.last_updated).toLocaleString();
        return `
            <div class="history-card" data-index="${i}">
                <div class="history-card-topic">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    ${escapeHtml(t.topic)}
                </div>
                <div class="history-card-meta">
                    <span><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> ${t.total_fetched} 条数据</span>
                    <span><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ${date}</span>
                </div>
                <div class="history-card-actions">
                    <button class="history-load-btn" data-action="load" data-index="${i}">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                        查看历史全景
                    </button>
                    <button class="history-delete-btn" data-action="delete" data-index="${i}">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    // 使用事件委托绑定按钮 (v1.9.13 — 避免 inline onclick 的特殊字符问题)
    window._historyTopics = topics;
    list.querySelectorAll('[data-action="load"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.index);
            loadHistoryTopic(window._historyTopics[idx].topic);
        });
    });
    list.querySelectorAll('[data-action="delete"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.index);
            deleteHistoryTopic(window._historyTopics[idx].topic);
        });
    });
}

async function loadHistoryTopic(topic) {
    // 切换到话题检测 Tab 并加载数据
    document.querySelector('[data-tab="topic"]').click();
    const input = document.getElementById('topicInput');
    if (input) input.value = topic;
    
    // 清理旧结果，准备展示新结果
    document.getElementById('topicResults').style.display = 'none';
    document.getElementById('topicProgress').style.display = 'block';
    document.getElementById('progressStatus').textContent = '正在从本地数据库调取历史全景...';
    document.getElementById('progressFill').style.width = '100%';

    
    // 调用 API 载入
    try {
        const res = await fetch('/api/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, action: 'load' })
        });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
            return;
        }
        
        // 延迟消失加载条，展示结果
        setTimeout(() => {
            // 同步全局变量，使历史话题也能触发“续爬”逻辑 (v1.9.12)
            window._lastCrawlTopic = topic;
            
            document.getElementById('topicProgress').style.display = 'none';
            renderTopicResults(data, data.crawl_info);
        }, 300);
    } catch (err) {
        console.error('Load history topic failed:', err);
    }
}

async function deleteHistoryTopic(topic) {
    if (!confirm(`确定要删除话题 “${topic}” 的所有本地数据吗？此操作不可撤销。`)) return;
    
    try {
        const res = await fetch('/api/delete_topic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });
        const data = await res.json();
        if (data.status === 'success') {
            fetchHistory(); // 刷新列表
        } else {
            alert(data.error || '删除失败');
        }
    } catch (err) {
        console.error('Delete history topic failed:', err);
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

