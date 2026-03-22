/* ============================================================ */
/*  Weibo Bot Shield — Main UI Controller                      */
/*  Handles DOM Updates, Events, Pagination, Modals            */
/* ============================================================ */

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Ensure escapeHtml and openNodeModal are globally accessible for charts.js
window.escapeHtml = escapeHtml;

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
        if (tab === 'label') {
            if (_labelUnlocked) fetchLabelQueue();
        }
        if (tab === 'model') {
            fetchModelInfo();
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

let _lastCrawlTopic = '';
let _allSuspects = [];
let _suspectPage = 1;
const _suspectPageSize = 5;

const topicBtn = document.getElementById('topicBtn');

if (topicBtn) {
    topicBtn.addEventListener('click', async () => {
        const topic = document.getElementById('topicInput').value.trim();
        if (!topic) { alert('请输入话题关键词'); return; }

        const depth = parseInt(depthSlider.value);
        const c1 = document.getElementById('cookieInput');
        const c2 = document.getElementById('cookieInputUser');
        const cookie = (c1 && c1.value.trim()) || (c2 && c2.value.trim()) || '';

        if (!cookie) {
            alert('❌ 必须提供微博 Cookie 才能启动检测！\n\n请按照输入框上方的说明获取并粘贴您的 Cookie。');
            if (c1) c1.focus();
            return;
        }

        // UI: loading state
        topicBtn.disabled = true;
        topicBtn.querySelector('.btn-text').style.display = 'none';
        topicBtn.querySelector('.btn-loading').style.display = 'flex';

        const progressArea = document.getElementById('topicProgress');
        const progressFill = document.getElementById('progressFill');
        const progressStatus = document.getElementById('progressStatus');
        const progressTime = document.getElementById('progressTime');
        const resultsArea = document.getElementById('topicResults');

        resultsArea.style.display = 'none';
        progressArea.style.display = 'block';
        progressFill.style.width = '0%';
        progressStatus.textContent = '初始化组件中...';

        let timeLeft = Math.ceil(depth * 2.2 + 8);
        progressTime.textContent = `预计剩余: ${timeLeft}秒`;

        if (window._setParticleSpeed) window._setParticleSpeed(0.008);

        let progressPercent = 0;
        const timer = setInterval(() => {
            if (timeLeft > 0) {
                timeLeft--;
                progressTime.textContent = `预计剩余: ${timeLeft}秒`;

                if (progressPercent < 90) {
                    progressPercent += (90 - progressPercent) * 0.05;
                    progressFill.style.width = progressPercent + '%';
                }

                if (timeLeft % 5 === 0) {
                    const statuses = ['正在下发采集任务...', '绕过微博反爬验证...', '模型正在实时特征提取...', '计算社交网络相似度...', '解析账号行为特征...'];
                    progressStatus.textContent = statuses[Math.floor(Math.random() * statuses.length)];
                }
            }
        }, 1000);

        try {
            const data = await window.api.detectTopic(topic, depth, _lastCrawlTopic === topic, 'fetch', cookie);
            _lastCrawlTopic = topic;
            window._lastCrawlDepth = depth;

            clearInterval(timer);
            progressFill.style.width = '100%';
            progressStatus.textContent = '分析完成！';
            setTimeout(() => { progressArea.style.display = 'none'; }, 500);

            renderTopicResults(data, data.crawl_info);
            // wordclouds rendering moved inside renderTopicResults safely

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

    const continueSlider = document.getElementById('continueDepthSlider');
    const continueVal = document.getElementById('continueDepthVal');
    if (continueSlider) {
        continueSlider.addEventListener('input', (e) => {
            continueVal.textContent = e.target.value;
        });

        document.getElementById('continueBtn').addEventListener('click', () => {
            const topic = _lastCrawlTopic;
            const depth = continueSlider.value || 20;
            if (!topic) return;

            document.getElementById('topicInput').value = topic;
            document.getElementById('depthSlider').value = depth;
            document.getElementById('depthVal').textContent = depth;
            document.getElementById('topicBtn').click();
        });
    }
}

function showError(containerId, msg) {
    const container = document.getElementById(containerId);
    container.style.display = 'block';
    container.innerHTML = `<div class="error-msg">⚠️ ${msg}</div>`;
}

function renderTopicResults(data, crawlInfo) {
    const container = document.getElementById('topicResults');
    container.style.display = 'block';

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

    const s = data.summary || {};
    document.getElementById('stat-total').textContent = s.total_scanned || 0;
    document.getElementById('stat-bots').textContent = s.bot_count || 0;
    document.getElementById('stat-news').textContent = s.news_count || 0;
    document.getElementById('stat-ratio').textContent = (s.bot_ratio || 0) + '%';

    const humans = (s.total_scanned || 0) - (s.bot_count || 0) - (s.news_count || 0);

    if (window.renderPieChart) window.renderPieChart(Math.max(0, humans), s.bot_count || 0, s.news_count || 0);

    if (window.renderRadarChart && data.radar_metrics && data.radar_metrics.humans && data.radar_metrics.bots) {
        window.renderRadarChart('radarChart', data.radar_metrics.humans, data.radar_metrics.bots);
    }

    if (window.renderScatterChart && data.all_nodes && data.all_nodes.length > 0) {
        window.renderScatterChart(data.all_nodes);
    }

    if (window.renderWordClouds && data.wordclouds) {
        setTimeout(() => window.renderWordClouds(data.wordclouds), 200);
    }

    renderSuspects(data.suspects || []);
}


function openNodeModal(node) {
    const modal = document.getElementById('nodeModal');
    if (!modal) return;

    const name = node.name || 'UID:' + node.user_id;
    const score = (node.suspicion_score * 100).toFixed(0);

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

    modal.style.display = 'flex';
    setTimeout(() => {
        modal.classList.add('active');
    }, 10);
    document.body.style.overflow = 'hidden';
}

window.openNodeModal = openNodeModal;

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('closeNodeModal');
    const bg = document.getElementById('nodeModalBackdrop');
    if (btn) btn.addEventListener('click', closeNodeModal);
    if (bg) bg.addEventListener('click', closeNodeModal);

    const prevBtn = document.getElementById('prevSuspectBtn');
    const nextBtn = document.getElementById('nextSuspectBtn');
    if (prevBtn) prevBtn.addEventListener('click', () => goToSuspectPage(_suspectPage - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => goToSuspectPage(_suspectPage + 1));

    // --- Deep Scroll Transition & Parallax Logic ---
    const hero = document.getElementById('hero');
    const appEl = document.getElementById('app');
    const heroContent = document.getElementById('heroContent');
    const scrollHint = document.querySelector('.hero-scroll-hint');

    if (scrollHint) {
        scrollHint.addEventListener('click', () => {
            window.scrollTo({ top: window.innerHeight * 0.8, behavior: 'smooth' });
        });
    }

    // Interactive 3D Parallax tracking on Hero
    if (hero && heroContent) {
        document.addEventListener('mousemove', (e) => {
            if (window.scrollY > window.innerHeight) return; // Prevent calc offscreen
            const rX = (window.innerHeight / 2 - e.clientY) / 45;
            const rY = (e.clientX - window.innerWidth / 2) / 45;
            heroContent.style.setProperty('--rot-x', `${rX}deg`);
            heroContent.style.setProperty('--rot-y', `${rY}deg`);
        });
    }

    window.addEventListener('scroll', () => {
        const scrolled = window.scrollY;
        const vh = window.innerHeight;
        const progress = Math.min(scrolled / (vh * 0.8), 1);

        // 1. Sync Particle Sphere (3D Parallax/Zoom)
        if (window._particleGroup && window.gsap) {
            const scaleVal = 1 + progress * 2.8; // Slightly more zoom
            window._particleGroup.scale.set(scaleVal, scaleVal, scaleVal);
            window._particleGroup.position.z = -progress * 8; // Deeper depth
        }

        // 2. Hero Content Fade & Slide
        if (heroContent) {
            heroContent.style.opacity = Math.max(0, 1 - progress * 1.2);
            heroContent.style.setProperty('--scroll-y', `${-progress * 150}px`);
        }

        // 3. Reveal App Dashboard
        if (progress > 0.4) {
            appEl.classList.add('revealed');
        } else {
            appEl.classList.remove('revealed');
        }

        // 4. Hide scroll hint early
        if (scrollHint) {
            scrollHint.style.opacity = 1 - progress * 4;
        }
    });
});


function closeNodeModal() {
    const modal = document.getElementById('nodeModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
        setTimeout(() => {
            modal.style.display = 'none';
        }, 400);
    }
}

// ==================== SUSPECT LIST ====================
function renderSuspects(suspects) {
    _allSuspects = suspects || [];
    _suspectPage = 1;
    goToSuspectPage(1);
}

function goToSuspectPage(page) {
    const totalPages = Math.ceil(_allSuspects.length / _suspectPageSize);
    if (page < 1) page = 1;
    if (page > totalPages) page = totalPages;
    _suspectPage = page;

    const container = document.getElementById('suspectList');
    const pagination = document.getElementById('suspectPagination');

    if (_allSuspects.length === 0) {
        container.innerHTML = `<div class="empty-hint">暂未发现明显的水军账号特征。</div>`;
        pagination.style.display = 'none';
        return;
    }

    pagination.style.display = 'flex';
    document.getElementById('suspectPageInfo').textContent = `第 ${_suspectPage} / ${totalPages || 1} 页`;
    document.getElementById('prevSuspectBtn').disabled = (_suspectPage <= 1);
    document.getElementById('nextSuspectBtn').disabled = (_suspectPage >= totalPages);

    const start = (_suspectPage - 1) * _suspectPageSize;
    const end = start + _suspectPageSize;
    const pagedSuspects = _allSuspects.slice(start, end);

    container.innerHTML = pagedSuspects.map(s => {
        const score = (parseFloat(s.bot_probability || 0) * 100).toFixed(0);
        const name = s.用户昵称 || s.screen_name;
        const textPreview = s.微博正文 ? `"${escapeHtml(s.微博正文).substring(0, 40)}${s.微博正文.length > 40 ? '...' : ''}"` : '';
        const level = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';

        const reasonsHtml = s.reasons.map(r => {
            let cls = r.level === 'high' ? 'flag-high' : r.level === 'medium' ? 'flag-medium' : 'flag-low';
            if (r.is_red_flag) cls += ' red-flag';
            const icon = r.is_red_flag ? '🚩 ' : '';
            return `<li class="${cls}">${icon}${escapeHtml(r.text)}</li>`;
        }).join('');

        return `
            <div class="suspect-card collapsed" onclick="toggleSuspect(this)">
                <div class="suspect-header">
                    <div class="suspect-score-mini ${level}">${score}%</div>
                    <div class="suspect-info">
                        <div class="suspect-name">${escapeHtml(name)}</div>
                        <div class="suspect-text-mini">${textPreview}</div>
                        <div class="suspect-meta-mini">UID: ${s.user_id || '未知'} | 粉丝 ${s.followers_count || 0} | 发帖 ${s.statuses_count || 0}</div>
                    </div>
                    <div class="suspect-arrow">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
                    </div>
                </div>
                <div class="suspect-details">
                    <ul class="reasons-list">${reasonsHtml}</ul>
                </div>
            </div>
        `;
    }).join('');
}


window.toggleSuspect = function (element) {
    const card = element.closest('.suspect-card');
    if (!card) return;
    const isCollapsed = card.classList.contains('collapsed');
    if (isCollapsed) {
        card.classList.remove('collapsed');
    } else {
        card.classList.add('collapsed');
    }
}

// ==================== SINGLE USER DETECTION ====================

const userBtn = document.getElementById('userBtn');
if (userBtn) {
    userBtn.addEventListener('click', async () => {
        const uid = document.getElementById('uidInput').value.trim();
        if (!uid) { alert('请输入微博用户 UID'); return; }

        const c1 = document.getElementById('cookieInput');
        const c2 = document.getElementById('cookieInputUser');
        const cookie = (c2 && c2.value.trim()) || (c1 && c1.value.trim()) || '';
        if (!cookie) {
            alert('❌ 必须提供微博 Cookie 才能启动单账号检测！\n\n请在输入框中配置您的 Cookie。');
            if (c2) c2.focus();
            return;
        }

        userBtn.disabled = true;
        userBtn.querySelector('.btn-text').style.display = 'none';
        userBtn.querySelector('.btn-loading').style.display = 'flex';
        if (window._setParticleSpeed) window._setParticleSpeed(0.005);

        try {
            const data = await window.api.checkUser(uid, cookie);
            renderUserResults(data);
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
        avatarEl.innerHTML = `<img src="/api/avatar?url=${encodeURIComponent(info.avatar_hd)}" alt="avatar">`;
    } else {
        avatarEl.textContent = (info.screen_name || '?')[0];
    }

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

    if (window.renderUserRadar && data.features) window.renderUserRadar(data.features);
    if (data.reasons) renderReasons(data.reasons);
}

function renderReasons(reasons) {
    const list = document.getElementById('reasonsList');
    list.innerHTML = reasons.map(r => {
        const cls = r.level === 'high' ? 'flag-high' : r.level === 'medium' ? 'flag-medium' : 'flag-low';
        return `<li class="${cls}">${escapeHtml(r.text)}</li>`;
    }).join('');
}


// ==================== SYSTEM INFO OVERLAY ====================

(function initInfoOverlay() {
    const infoTrigger = document.getElementById('infoTrigger');
    const closeInfo = document.getElementById('closeInfo');
    const infoOverlay = document.getElementById('infoOverlay');
    const overlayBackdrop = infoOverlay.querySelector('.overlay-backdrop');

    if (!infoTrigger || !infoOverlay) return;

    let isOpen = false;
    let mdLoaded = false;

    const toggleInfo = async (show) => {
        if (show === isOpen) return;
        isOpen = show;

        if (show) {
            infoOverlay.style.display = 'flex';

            // 动态加载并渲染 Markdown 文档
            if (!mdLoaded && window.marked) {
                try {
                    const res = await fetch('/static/docs/system_guide.md');
                    if (res.ok) {
                        const text = await res.text();
                        const html = window.marked.parse(text);
                        const container = document.getElementById('guideContent');
                        if (container) container.innerHTML = html;
                        mdLoaded = true;
                    } else {
                        const container = document.getElementById('guideContent');
                        if (container) container.innerHTML = '<p style="text-align:center;">无法加载文档说明。</p>';
                    }
                } catch (e) {
                    console.error('Failed to load markdown guide:', e);
                }
            }

            if (window._particleGroup && window.gsap) {
                window.gsap.to(window._particleGroup.scale, {
                    x: 3.5, y: 3.5, z: 3.5,
                    duration: 1.2,
                    ease: "power2.inOut",
                    onComplete: () => {
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
                infoOverlay.classList.add('active');
            }
        } else {
            infoOverlay.classList.remove('active');
            setTimeout(() => {
                if (isOpen) return;

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
            }, 400);
        }
    };

    infoTrigger.addEventListener('click', () => toggleInfo(true));
    closeInfo.addEventListener('click', () => toggleInfo(false));
    overlayBackdrop.addEventListener('click', () => toggleInfo(false));

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen) toggleInfo(false);
    });
})();

// ==================== HISTORY MANAGEMENT ====================

async function fetchHistory() {
    const list = document.getElementById('historyList');
    if (!list) return;

    try {
        const data = await window.api.getHistoryList();
        renderHistory(data.topics);
    } catch (err) {
        console.error('Fetch history failed:', err.message);
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
    document.querySelector('[data-tab="topic"]').click();
    const input = document.getElementById('topicInput');
    if (input) input.value = topic;

    document.getElementById('topicResults').style.display = 'none';
    document.getElementById('topicProgress').style.display = 'block';
    document.getElementById('progressStatus').textContent = '正在从本地数据库调取历史全景...';
    document.getElementById('progressFill').style.width = '100%';

    try {
        const data = await window.api.detectTopic(topic, 0, false, 'load');

        setTimeout(() => {
            _lastCrawlTopic = topic;

            document.getElementById('topicProgress').style.display = 'none';
            renderTopicResults(data, data.crawl_info);

            if (data.wordclouds && window.renderWordClouds) window.renderWordClouds(data.wordclouds);
            if (data.all_nodes && window.renderScatterChart) window.renderScatterChart(data.all_nodes);
        }, 300);

    } catch (err) {
        document.getElementById('topicProgress').style.display = 'none';
        alert('读取历史失败: ' + err.message);
    }
}

async function deleteHistoryTopic(topic) {
    try {
        await window.api.deleteTopic(topic);
        fetchHistory();
    } catch (err) {
        console.error('删除失败:', err.message);
        alert('删除失败: ' + err.message);
    }
}

// ==================== COOKIE GUIDE RENDERING ====================
(async function initCookieGuide() {
    const containers = [
        document.getElementById('cookieGuideContainer'),
        document.getElementById('cookieGuideContainerUser')
    ];
    if (!containers.some(c => c)) return;

    try {
        const res = await fetch('/static/docs/cookie_guide.md');
        if (res.ok) {
            const text = await res.text();
            if (window.marked) {
                const parsedHtml = window.marked.parse(text);
                containers.forEach(container => {
                    if (!container) return;
                    container.innerHTML = parsedHtml;
                    container.querySelectorAll('a').forEach(a => {
                        a.target = "_blank";
                        a.style.color = "#d4af37";
                        a.style.textDecoration = "underline";
                    });
                });
            }
        } else {
            containers.forEach(container => {
                if (container) container.innerHTML = '<p>无法加载说明文档。</p>';
            });
        }
    } catch (e) {
        console.error('Failed to load cookie guide:', e);
    }

    // 同步双端 Cookie 输入框
    const c1 = document.getElementById('cookieInput');
    const c2 = document.getElementById('cookieInputUser');
    if (c1 && c2) {
        c1.addEventListener('input', () => c2.value = c1.value);
        c2.addEventListener('input', () => c1.value = c2.value);
    }
})();

// ==================== DATA LABELING MODULE ====================

let _labelPage = 1;
let _labelTotalPages = 1;
let _labelUnlocked = false;
let _labelView = 'unlabeled'; // 'unlabeled' or 'labeled'

// Password gate logic
function attemptLabelAuth() {
    const pwd = document.getElementById('labelPasswordInput').value;
    const errEl = document.getElementById('labelAuthError');
    errEl.style.display = 'none';

    fetch('/api/label/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pwd })
    }).then(r => {
        if (r.ok) {
            _labelUnlocked = true;
            document.getElementById('labelAuthGate').style.display = 'none';
            document.getElementById('labelWorkbench').style.display = '';
            refreshCurrentLabelView();
        } else {
            errEl.style.display = 'block';
            document.getElementById('labelPasswordInput').value = '';
            document.getElementById('labelPasswordInput').focus();
        }
    }).catch(() => { errEl.style.display = 'block'; });
}

document.getElementById('labelAuthBtn')?.addEventListener('click', attemptLabelAuth);
document.getElementById('labelPasswordInput')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') attemptLabelAuth();
});

// View switching
window.switchLabelView = function(view) {
    if (view === _labelView) return; // Prevent unnecessary refresh
    _labelView = view;
    _labelPage = 1;
    document.querySelectorAll('.stat-chip').forEach(chip => {
        if (chip.dataset.view) {
            chip.classList.toggle('active', chip.dataset.view === view);
        }
    });
    refreshCurrentLabelView();
};

function refreshCurrentLabelView(page) {
    if (page) _labelPage = page;
    if (_labelView === 'labeled') {
        fetchLabeledQueue(_labelPage);
    } else {
        fetchLabelQueue(_labelPage);
    }
}

// ---- Unlabeled Queue ----
async function fetchLabelQueue(page = 1) {
    const container = document.getElementById('labelCardsContainer');
    const topicFilter = document.getElementById('labelTopicFilter');
    const topic = topicFilter ? topicFilter.value : '';

    try {
        const data = await window.api.getLabelQueue(topic, page);
        _labelPage = data.page || 1;
        _labelTotalPages = Math.ceil((data.total || 0) / (data.page_size || 20));

        // Update stats
        const stats = data.stats || {};
        const labeledCount = stats.total_labeled || data.labeled_count || 0;
        const queueCount = data.total || 0;
        const totalAll = labeledCount + queueCount;
        document.getElementById('labelTotalCount').textContent = labeledCount;
        document.getElementById('labelQueueCount').textContent = queueCount;

        const pct = totalAll > 0 ? Math.round((labeledCount / totalAll) * 100) : 0;
        document.getElementById('labelProgressFill').style.width = pct + '%';
        document.getElementById('labelProgressText').textContent = pct + '%';

        // Populate topic filter
        if (data.topics && topicFilter) {
            const currentVal = topicFilter.value;
            topicFilter.innerHTML = '<option value="">全部话题</option>';
            data.topics.forEach(t => {
                topicFilter.innerHTML += `<option value="${escapeHtml(t)}" ${t === currentVal ? 'selected' : ''}>${escapeHtml(t)}</option>`;
            });
        }

        // Render cards
        const users = data.users || [];
        if (users.length === 0) {
            container.innerHTML = `<div class="history-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                    <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                </svg>
                <p>暂无待标注数据。请先进行话题检测。</p>
            </div>`;
        } else {
            container.innerHTML = users.map(u => renderLabelCard(u, 'unlabeled')).join('');
        }

        updateLabelPagination();
    } catch (e) {
        container.innerHTML = `<div class="history-empty"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

// ---- Labeled Queue ----
async function fetchLabeledQueue(page = 1) {
    const container = document.getElementById('labelCardsContainer');
    const topicFilter = document.getElementById('labelTopicFilter');
    const topic = topicFilter ? topicFilter.value : '';

    try {
        const data = await window.api.getLabeledQueue(topic, page);
        _labelPage = data.page || 1;
        _labelTotalPages = Math.ceil((data.total || 0) / (data.page_size || 20));

        const users = data.users || [];
        if (users.length === 0) {
            container.innerHTML = `<div class="history-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                    <path d="M9 12l2 2 4-4"/>
                    <circle cx="12" cy="12" r="10"/>
                </svg>
                <p>暂无已标注数据</p>
            </div>`;
        } else {
            container.innerHTML = users.map(u => renderLabelCard(u, 'labeled')).join('');
        }

        updateLabelPagination();
    } catch (e) {
        container.innerHTML = `<div class="history-empty"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

// ---- Unified Pagination Update ----
function updateLabelPagination() {
    const paginationEl = document.getElementById('labelPagination');
    if (_labelTotalPages > 1) {
        paginationEl.style.display = 'flex';
        document.getElementById('labelPageInfo').textContent = `第 ${_labelPage} / ${_labelTotalPages} 页`;
        document.getElementById('prevLabelBtn').disabled = _labelPage <= 1;
        document.getElementById('nextLabelBtn').disabled = _labelPage >= _labelTotalPages;
    } else {
        paginationEl.style.display = 'none';
    }
}

// ---- Dual-mode Card Rendering ----
function renderLabelCard(user, mode = 'unlabeled') {
    const score = user.ai_pred_score || 0;
    const pct = Math.round(score * 100);
    const cls = score >= 0.7 ? 'high' : score >= 0.4 ? 'medium' : 'low';
    const name = user.screen_name || 'UID:' + user.user_id;
    const avatarHtml = (user.avatar_hd && user.avatar_hd.length > 10)
        ? `<img src="/api/avatar?url=${encodeURIComponent(user.avatar_hd)}" alt="">`
        : name[0];

    const labelNames = {'-1': '新闻媒体', '0': '真人', '1': '大概率真人', '2': '不确定', '3': '可疑', '4': '水军'};
    const currentLabel = user.suspicion_label;

    const labels = ['真人', '大概率真人', '不确定', '可疑', '水军'];
    const buttonsHtml = labels.map((l, i) => {
        const selected = (mode === 'labeled' && currentLabel === i) ? ' selected' : '';
        return `<button class="label-btn${selected}" data-label="${i}" data-uid="${user.user_id}" data-topic="${escapeHtml(user.topic || '')}" data-ai="${score}" data-name="${escapeHtml(user.screen_name || '')}" onclick="handleLabel(this)">${l}</button>`;
    }).join('');

    // Media exclusion button
    const mediaSelected = (mode === 'labeled' && currentLabel === -1) ? ' selected' : '';
    const mediaBtn = `<button class="label-btn${mediaSelected}" data-label="-1" data-uid="${user.user_id}" data-topic="${escapeHtml(user.topic || '')}" data-ai="${score}" data-name="${escapeHtml(user.screen_name || '')}" onclick="handleLabel(this)">新闻媒体</button>`;

    // Current label badge (only in labeled view)
    let badgeHtml = '';
    if (mode === 'labeled' && currentLabel !== undefined && currentLabel !== null) {
        const badgeName = labelNames[String(currentLabel)] || '未知';
        const badgeColors = {'-1': '#607d8b', '0': '#4caf50', '1': '#8bc34a', '2': '#ff9800', '3': '#ef6c00', '4': '#e53935'};
        const bgColor = badgeColors[String(currentLabel)] || '#999';
        badgeHtml = `<span class="label-current-badge" style="background:${bgColor}20;color:${bgColor};border:1px solid ${bgColor}40">${badgeName}</span>`;
    }

    // Feature detail panel
    const featureNames = {
        daily_post_rate: '日均发帖', human_likeness_score: '拟人度',
        exclamation_density: '感叹密度', is_random_name: '乱码昵称',
        engagement_count: '互动量', is_verified: 'V认证',
        sentiment_score: '情感极性', topic_diversity: '话题多样性',
        post_interval_variance: '间隔方差'
    };
    const features = user.features || {};
    let detailItems = '';
    for (const [key, val] of Object.entries(features)) {
        const display = featureNames[key] || key;
        const fmtVal = typeof val === 'number' ? (val < 1 && val > 0 ? (val * 100).toFixed(1) + '%' : val.toFixed(2)) : val;
        detailItems += `<div class="detail-item"><span class="detail-key">${display}</span><span class="detail-val">${fmtVal}</span></div>`;
    }
    if (user.verified_reason) detailItems += `<div class="detail-item"><span class="detail-key">认证信息</span><span class="detail-val">${escapeHtml(user.verified_reason)}</span></div>`;
    if (user.description) detailItems += `<div class="detail-item"><span class="detail-key">简介</span><span class="detail-val">${escapeHtml(user.description)}</span></div>`;

    // Labeled-at info (only for labeled view)
    const labeledAtHtml = (mode === 'labeled' && user.labeled_at) ? `<div class="label-meta-time" style="font-size:0.72rem;color:var(--text-dim);margin-top:4px">标注于 ${escapeHtml(user.labeled_at)}</div>` : '';

    const deleteBtnHtml = `
        <button class="delete-user-btn" onclick="deleteLabelUserCard('${user.user_id}'); event.stopPropagation();" title="永久删除此账号">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 6h18"></path>
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
            </svg>
        </button>
    `;

    return `
    <div class="label-card" id="lcard-${user.user_id}" data-mode="${mode}">
        <div class="label-card-header" onclick="toggleLabelDetail(this)">
            <div class="label-avatar">${avatarHtml}</div>
            <div class="label-user-info">
                <div class="name">${escapeHtml(name)}</div>
                <div class="meta">粉丝 ${user.followers_count || 0} · 关注 ${user.friends_count || 0} · 微博 ${user.statuses_count || 0}</div>
                ${labeledAtHtml}
            </div>
            ${badgeHtml}
            <span class="label-ai-score ${cls}">AI: ${pct}%</span>
            ${deleteBtnHtml}
        </div>
        <div class="label-card-detail">
            <div class="label-detail-grid">${detailItems}</div>
        </div>
        <div class="label-expand-hint" onclick="toggleLabelDetail(this.parentElement.querySelector('.label-card-header'))">▼ 点击展开查看特征详情</div>
        <div class="label-text-preview">${escapeHtml(user.text_preview || '')}</div>
        <div class="label-buttons">${mediaBtn}${buttonsHtml}</div>
    </div>`;
}

window.deleteLabelUserCard = async function(uid) {
    const card = document.getElementById(`lcard-${uid}`);
    if (!card) return;

    const btn = card.querySelector('.delete-user-btn');
    if (btn) btn.disabled = true;

    try {
        const res = await window.api.deleteLabelUser(uid);
        if (res.error) throw new Error(res.error);

        // Success animation
        card.style.transition = 'all 0.3s ease';
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => {
            card.remove();
            
            if (_labelView === 'unlabeled') {
                const countEl = document.getElementById('labelQueueCount');
                if (countEl) countEl.textContent = Math.max(0, parseInt(countEl.textContent || 0) - 1);
            } else {
                const countEl = document.getElementById('labelTotalCount');
                if (countEl) countEl.textContent = Math.max(0, parseInt(countEl.textContent || 0) - 1);
            }

            // Sync progress bar
            const totalEl = document.getElementById('labelTotalCount');
            const queueEl = document.getElementById('labelQueueCount');
            if (totalEl && queueEl) {
                const totalAll = parseInt(totalEl.textContent || 0) + parseInt(queueEl.textContent || 0);
                const pct = totalAll > 0 ? Math.round(parseInt(totalEl.textContent || 0) / totalAll * 100) : 0;
                const fillEl = document.getElementById('labelProgressFill');
                const textEl = document.getElementById('labelProgressText');
                if (fillEl) fillEl.style.width = pct + '%';
                if (textEl) textEl.textContent = pct + '%';
            }

            // Check if empty
            if (document.querySelectorAll('.label-card').length === 0) {
                refreshCurrentLabelView();
            }
        }, 300);
    } catch (e) {
        if (btn) btn.disabled = false;
        alert('删除失败: ' + e.message);
    }
};

window.handleLabel = async function(btn) {
    const label = parseInt(btn.dataset.label);
    const uid = btn.dataset.uid;
    const topic = btn.dataset.topic;
    const ai = parseFloat(btn.dataset.ai);
    const card = btn.closest('.label-card');
    const mode = card.dataset.mode;

    // Visual: highlight selected
    card.querySelectorAll('.label-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    const screenName = btn.dataset.name || '';

    try {
        await window.api.submitLabel(uid, label, topic, ai, {}, screenName);

        if (mode === 'unlabeled') {
            // In unlabeled view: card fades out and disappears
            card.style.transition = 'all 0.4s ease';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.95)';
            setTimeout(() => {
                card.remove();
                // Update stats counters
                const totalEl = document.getElementById('labelTotalCount');
                const queueEl = document.getElementById('labelQueueCount');
                totalEl.textContent = parseInt(totalEl.textContent) + 1;
                const newQueue = Math.max(0, parseInt(queueEl.textContent) - 1);
                queueEl.textContent = newQueue;
                const totalAll = parseInt(totalEl.textContent) + newQueue;
                const pct = totalAll > 0 ? Math.round(parseInt(totalEl.textContent) / totalAll * 100) : 0;
                document.getElementById('labelProgressFill').style.width = pct + '%';
                document.getElementById('labelProgressText').textContent = pct + '%';

                // If no more cards visible, show empty message
                const container = document.getElementById('labelCardsContainer');
                if (!container.querySelector('.label-card')) {
                    container.innerHTML = `<div class="history-empty"><p>当前页已标注完毕，请翻页或切换视图查看</p></div>`;
                }
            }, 450);
        } else {
            // In labeled view: just update badge and highlight (label modified)
            const labelNames = {'-1': '新闻媒体', '0': '真人', '1': '大概率真人', '2': '不确定', '3': '可疑', '4': '水军'};
            const badgeColors = {'-1': '#607d8b', '0': '#4caf50', '1': '#8bc34a', '2': '#ff9800', '3': '#ef6c00', '4': '#e53935'};
            const badge = card.querySelector('.label-current-badge');
            if (badge) {
                const bgColor = badgeColors[String(label)] || '#999';
                badge.textContent = labelNames[String(label)] || '未知';
                badge.style.background = bgColor + '20';
                badge.style.color = bgColor;
                badge.style.borderColor = bgColor + '40';
            }
            // Brief flash effect to confirm change
            card.style.transition = 'box-shadow 0.3s';
            card.style.boxShadow = '0 0 0 2px rgba(184,148,61,0.5)';
            setTimeout(() => { card.style.boxShadow = ''; }, 800);
        }
    } catch (e) {
        alert('标注提交失败: ' + e.message);
    }
};

// Toggle card detail panel
window.toggleLabelDetail = function(headerEl) {
    const card = headerEl.closest('.label-card');
    const detail = card.querySelector('.label-card-detail');
    const hint = card.querySelector('.label-expand-hint');
    const isExpanded = detail.classList.contains('expanded');
    detail.classList.toggle('expanded');
    if (hint) {
        hint.textContent = isExpanded ? '▼ 点击展开查看特征详情' : '▲ 收起详情';
    }
};

// Pagination handlers
document.getElementById('prevLabelBtn')?.addEventListener('click', () => {
    if (_labelPage > 1) refreshCurrentLabelView(_labelPage - 1);
});
document.getElementById('nextLabelBtn')?.addEventListener('click', () => {
    if (_labelPage < _labelTotalPages) refreshCurrentLabelView(_labelPage + 1);
});
document.getElementById('labelTopicFilter')?.addEventListener('change', () => {
    _labelPage = 1;
    refreshCurrentLabelView();
});


// ==================== MODEL WORKSHOP MODULE ====================

async function fetchModelInfo() {
    try {
        const data = await window.api.getModelInfo();

        document.getElementById('modelType').textContent = data.model_type || '未加载';
        document.getElementById('modelEstimators').textContent = data.n_estimators || '—';
        document.getElementById('modelDepth').textContent = data.max_depth || '—';
        document.getElementById('modelSamples').textContent = data.training_samples || 0;
        document.getElementById('modelLastUpdate').textContent = data.last_modified || '未知';

        const newLabelsEl = document.getElementById('modelNewLabels');
        if (newLabelsEl) {
            const cnt = data.new_labels_count || 0;
            newLabelsEl.textContent = cnt > 0 ? `+${cnt} 条` : '0 条';
        }

        // Render Feature Importance chart
        if (data.feature_importances && Object.keys(data.feature_importances).length > 0) {
            renderFeatureImportanceChart(data.feature_importances);
        }

        // Render Label Distribution chart
        if (data.label_distribution && Object.keys(data.label_distribution).length > 0) {
            renderLabelDistChart(data.label_distribution);
        }
    } catch (e) {
        console.error('Model info fetch failed:', e);
    }
}

function renderFeatureImportanceChart(importances) {
    const chartDom = document.getElementById('featureImportanceChart');
    if (!chartDom) return;
    const chart = echarts.init(chartDom);

    const featureNames = {
        daily_post_rate: '发帖频率', human_likeness_score: '语义拟人度',
        exclamation_density: '感叹号密度', is_random_name: '乱码昵称',
        engagement_count: '互动量', is_verified: 'V认证',
        sentiment_score: '情感极性', topic_diversity: '话题多样性',
        post_interval_variance: '间隔方差'
    };

    // Sort by importance descending
    const sorted = Object.entries(importances).sort((a, b) => a[1] - b[1]);
    const names = sorted.map(([k]) => featureNames[k] || k);
    const values = sorted.map(([, v]) => v);

    chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(255,255,255,0.95)', borderColor: '#e8e0d4', textStyle: { color: '#2c2418' } },
        grid: { left: '20%', right: '8%', top: '4%', bottom: '8%' },
        xAxis: { type: 'value', axisLabel: { color: '#8a7e6b', fontSize: 11 }, splitLine: { lineStyle: { color: 'rgba(184,148,61,0.1)' } } },
        yAxis: { type: 'category', data: names, axisLabel: { color: '#8a7e6b', fontSize: 12 }, axisLine: { lineStyle: { color: '#e8e0d4' } } },
        series: [{
            type: 'bar',
            data: values,
            barWidth: '55%',
            itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                    { offset: 0, color: 'rgba(184,148,61,0.3)' },
                    { offset: 1, color: '#b8943d' }
                ]),
                borderRadius: [0, 6, 6, 0]
            },
            label: { show: true, position: 'right', color: '#8a7e6b', fontSize: 11, formatter: p => (p.value * 100).toFixed(1) + '%' }
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderLabelDistChart(distribution) {
    const chartDom = document.getElementById('labelDistChart');
    if (!chartDom) return;
    const chart = echarts.init(chartDom);

    const colorMap = {
        '确定真人': '#7cb87a', '大概率真人': '#a5d6a7',
        '不确定': '#c9a84c', '比较可疑': '#ef6c00', '几乎确定水军': '#c96b5e'
    };

    const pieData = Object.entries(distribution).map(([name, value]) => ({
        name, value, itemStyle: { color: colorMap[name] || '#999' }
    }));

    chart.setOption({
        tooltip: { trigger: 'item', backgroundColor: 'rgba(255,255,255,0.95)', borderColor: '#e8e0d4', textStyle: { color: '#2c2418' } },
        legend: { bottom: 5, textStyle: { color: '#8a7e6b' } },
        series: [{
            type: 'pie',
            radius: ['40%', '68%'],
            itemStyle: { borderRadius: 6, borderColor: 'rgba(255,255,255,0.4)', borderWidth: 2 },
            label: { show: true, color: '#2c2418', formatter: '{b}\n{d}%' },
            data: pieData
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

// Retrain button
document.getElementById('retrainBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('retrainBtn');
    const resultDiv = document.getElementById('retrainResult');
    btn.disabled = true;
    btn.querySelector('.btn-text').style.display = 'none';
    btn.querySelector('.btn-loading').style.display = 'inline';
    resultDiv.style.display = 'none';

    try {
        const data = await window.api.retrainModel();
        resultDiv.style.display = 'block';
        if (data.status === 'success') {
            resultDiv.className = 'retrain-result success';
            resultDiv.innerHTML = `✅ ${data.message}<br>训练样本：${data.training_samples} 条<br>交叉验证 MAE：${data.cv_mae}<br>交叉验证 R²：${data.cv_r2}<br>完成时间：${data.trained_at}`;
            // Refresh model info
            setTimeout(fetchModelInfo, 500);
        } else {
            resultDiv.className = 'retrain-result error';
            resultDiv.textContent = '❌ ' + (data.message || '训练失败');
        }
    } catch (e) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'retrain-result error';
        resultDiv.textContent = '❌ 请求失败: ' + e.message;
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').style.display = '';
        btn.querySelector('.btn-loading').style.display = 'none';
    }
});

// ============================================
// Media DB Management Modal Logic
// ============================================

window.openMediaDbModal = async function() {
    const modal = document.getElementById('mediaDbModal');
    modal.style.display = 'flex';
    setTimeout(() => {
        modal.classList.add('active');
    }, 10);
    document.body.style.overflow = 'hidden';
    await window.renderMediaDbTable();
};

window.closeMediaDbModal = function() {
    const modal = document.getElementById('mediaDbModal');
    modal.classList.remove('active');
    setTimeout(() => {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }, 300);
};

window.renderMediaDbTable = async function() {
    const tbody = document.getElementById('mediaDbTableBody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: var(--text-dim);">加载中...</td></tr>';
    try {
        const mediaList = await window.api.getMediaList();
        if (mediaList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 30px; color: var(--text-dim);">免检白名单当前为空呦~</td></tr>';
            return;
        }
        
        tbody.innerHTML = mediaList.map(item => `
            <tr>
                <td style="padding: 10px 15px; border-bottom: 1px solid var(--border); font-family: monospace;">${escapeHtml(item.user_id)}</td>
                <td style="padding: 10px 15px; border-bottom: 1px solid var(--border);">${escapeHtml(item.screen_name) || `<span style="color:#aaa">未知</span>`}</td>
                <td style="padding: 10px 15px; border-bottom: 1px solid var(--border); font-size: 0.8rem; color: var(--text-dim);">${formatDateString(item.added_at)}</td>
                <td style="padding: 10px 15px; border-bottom: 1px solid var(--border); text-align: right;">
                    <button class="delete-link-btn" onclick="removeMediaAccount('${escapeHtml(item.user_id)}')">移除</button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 20px; color: var(--danger);">加载失败: ${e.message}</td></tr>`;
    }
};

window.addMediaAccount = async function() {
    const uidInput = document.getElementById('mediaAddUid');
    const nameInput = document.getElementById('mediaAddName');
    const uid = uidInput.value.trim();
    const name = nameInput.value.trim();
    if (!uid) {
        alert("请输入必填的账号 UID");
        return;
    }
    
    try {
        const btn = document.querySelector('.media-add-form .primary-btn');
        btn.disabled = true;
        btn.textContent = '录入中...';
        await window.api.addMediaAccount(uid, name);
        uidInput.value = '';
        nameInput.value = '';
        await window.renderMediaDbTable();
    } catch (e) {
        alert("添加失败: " + e.message);
    } finally {
        const btn = document.querySelector('.media-add-form .primary-btn');
        btn.disabled = false;
        btn.textContent = '➕ 手动录入';
    }
};

window.removeMediaAccount = async function(uid) {
    if (!confirm(`确定要将 UID:${uid} 移出免检白名单吗？其后续检测将恢复标准流程。`)) return;
    try {
        await window.api.deleteMediaAccount(uid);
        await window.renderMediaDbTable();
    } catch (e) {
        alert("移除失败: " + e.message);
    }
};

function formatDateString(isoString) {
    if (!isoString) return '';
    try {
        const d = new Date(isoString);
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    } catch {
        return isoString;
    }
}
