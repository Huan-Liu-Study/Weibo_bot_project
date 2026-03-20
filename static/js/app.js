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
            const data = await window.api.detectTopic(topic, depth, _lastCrawlTopic === topic);
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
                        <div class="suspect-meta-mini">粉丝 ${s.followers_count || 0} | 发帖 ${s.statuses_count || 0}</div>
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


window.toggleSuspect = function(element) {
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

        userBtn.disabled = true;
        userBtn.querySelector('.btn-text').style.display = 'none';
        userBtn.querySelector('.btn-loading').style.display = 'flex';
        if (window._setParticleSpeed) window._setParticleSpeed(0.005);

        try {
            const data = await window.api.checkUser(uid);
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
        avatarEl.innerHTML = `<img src="${info.avatar_hd}" alt="avatar">`;
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

    const toggleInfo = (show) => {
        if (show === isOpen) return;
        isOpen = show;

        if (show) {
            infoOverlay.style.display = 'flex';
            
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
    if (!confirm(`确定要删除话题 “${topic}” 的所有本地数据吗？此操作不可撤销。`)) return;
    
    try {
        await window.api.deleteTopic(topic);
        fetchHistory(); 
    } catch (err) {
        alert('删除失败: ' + err.message);
    }
}
