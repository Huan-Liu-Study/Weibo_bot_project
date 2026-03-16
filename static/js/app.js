// DOM Elements
const scanBtn = document.getElementById('scanBtn');
const topicInput = document.getElementById('topicInput');
const limitSlider = document.getElementById('limitSlider');
const limitVal = document.getElementById('limitVal');
const loadingOverlay = document.getElementById('loadingOverlay');
const demoBtn = document.getElementById('demoBtn');

const mTotal = document.getElementById('m-total');
const mBots = document.getElementById('m-bots');
const mRatio = document.getElementById('m-ratio');
const mSentiment = document.getElementById('m-sentiment');
const suspectList = document.getElementById('suspectList');

// ECharts Instance
let radarChart = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Init empty chart
    radarChart = echarts.init(document.getElementById('radarChart'));

    // Default Empty Options
    radarChart.setOption({
        tooltip: {},
        radar: {
            indicator: [
                { name: '感叹号情绪', max: 0.2 },
                { name: '粉丝关注比畸形', max: 10 },
                { name: '日均发帖率', max: 50 },
                { name: '互动率', max: 1 },
                { name: '外链数量', max: 5 },
                { name: '默认虚假头像', max: 1 },
                { name: '乱码机器名', max: 1 },
                { name: '情感极性', max: 1 },
                { name: '话题标签数', max: 10 },
                { name: '发帖间隔方差', max: 100 }
            ],
            splitNumber: 4,
            axisLine: { lineStyle: { color: 'rgba(0, 242, 254, 0.3)' } },
            splitLine: { lineStyle: { color: 'rgba(0, 242, 254, 0.1)' } },
            splitArea: { areaStyle: { color: ['rgba(0,0,0,0)'] } },
            axisName: { color: '#00f2fe' }
        },
        series: []
    });

    // Handle Window Resize
    window.addEventListener('resize', () => {
        if (radarChart) radarChart.resize();
    });
});

// Slider Events
limitSlider.addEventListener('input', (e) => {
    limitVal.innerText = e.target.value;
});

// UI Update Helpers
function updateMetrics(summary) {
    // Count up animation for numbers
    mTotal.innerText = summary.total_scanned;
    mBots.innerText = summary.bot_count;
    mRatio.innerText = `${summary.bot_ratio}%`;
    mSentiment.innerText = summary.overall_sentiment.toFixed(2);

    // Style toggle based on threat level
    if (summary.bot_ratio > 30) {
        mRatio.parentElement.parentElement.classList.add('alert-level');
    } else {
        mRatio.parentElement.parentElement.classList.remove('alert-level');
    }
}

function updateRadar(metrics) {
    if (!metrics || !metrics.humans || !metrics.bots) return;

    const botVals = [
        metrics.bots.exclamation_density,
        metrics.bots.follower_friend_ratio,
        metrics.bots.daily_post_rate,
        metrics.bots.engagement_rate,
        metrics.bots.link_count,
        metrics.bots.is_default_avatar,
        metrics.bots.is_random_name,
        metrics.bots.sentiment_score,
        metrics.bots.topic_count,
        metrics.bots.post_interval_variance
    ];

    const humanVals = [
        metrics.humans.exclamation_density,
        metrics.humans.follower_friend_ratio,
        metrics.humans.daily_post_rate,
        metrics.humans.engagement_rate,
        metrics.humans.link_count,
        metrics.humans.is_default_avatar,
        metrics.humans.is_random_name,
        metrics.humans.sentiment_score,
        metrics.humans.topic_count,
        metrics.humans.post_interval_variance
    ];

    radarChart.setOption({
        legend: {
            data: ['水军机器矩阵', '正常人类样本'],
            textStyle: { color: '#e6edf3' },
            bottom: 0
        },
        series: [{
            name: '威胁分析',
            type: 'radar',
            data: [
                {
                    value: botVals,
                    name: '水军机器矩阵',
                    itemStyle: { color: '#ff003c' },
                    areaStyle: { color: 'rgba(255, 0, 60, 0.3)' },
                    lineStyle: { width: 2 }
                },
                {
                    value: humanVals,
                    name: '正常人类样本',
                    itemStyle: { color: '#00f2fe' },
                    areaStyle: { color: 'rgba(0, 242, 254, 0.2)' },
                    lineStyle: { type: 'dashed' }
                }
            ]
        }]
    });
}

function updateSuspects(suspects) {
    suspectList.innerHTML = '';

    if (!suspects || suspects.length === 0) {
        suspectList.innerHTML = '<li class="empty-state">当前水域无严重污染...</li>';
        return;
    }

    suspects.forEach(bot => {
        const li = document.createElement('li');
        li.className = 'suspect-item';

        // Handle avatar parsing
        const avatarUrl = bot['头像url'] && bot['头像url'] !== 'null' ? bot['头像url'] : 'https://tva1.sinaimg.cn/default/images/default_avatar_male_50.gif';

        li.innerHTML = `
            <div class="avatar-wrapper">
                <img src="${avatarUrl}" alt="Bot Face" onerror="this.src='https://tva1.sinaimg.cn/default/images/default_avatar_male_50.gif'">
            </div>
            <div class="suspect-info">
                <h5>${bot['用户昵称'] || 'Anonymous_Bot'}</h5>
                <p>IP源: ${bot['ip'] || '未知暗网'} | 历史帖子: ${bot['statuses_count'] || 0}</p>
            </div>
            <div class="threat-score">99.9%</div>
        `;
        suspectList.appendChild(li);
    });
}

// Core Execution
scanBtn.addEventListener('click', async () => {
    const topic = topicInput.value.trim();
    const limit = limitSlider.value;

    if (!topic) {
        alert("请输入目标对象！");
        return;
    }

    // Freeze UI
    loadingOverlay.classList.remove('hidden');
    scanBtn.disabled = true;

    try {
        const response = await fetch('/api/detect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ topic, limit })
        });

        const data = await response.json();

        if (data.status === 'success') {
            updateMetrics(data.summary);
            updateRadar(data.radar_metrics);
            updateSuspects(data.suspects);
        } else {
            alert(`防线渗透失败: ${data.error}`);
        }

    } catch (err) {
        console.error(err);
        alert(`网络或引擎故障: ${err.message}`);
    } finally {
        loadingOverlay.classList.add('hidden');
        scanBtn.disabled = false;
    }
});

// Demo Mode - loads pre-existing data without live crawling
demoBtn.addEventListener('click', async () => {
    loadingOverlay.classList.remove('hidden');
    demoBtn.disabled = true;

    try {
        const response = await fetch('/api/demo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        const data = await response.json();

        if (data.status === 'success') {
            updateMetrics(data.summary);
            updateRadar(data.radar_metrics);
            updateSuspects(data.suspects);
        } else {
            alert(`Demo加载失败: ${data.error}`);
        }
    } catch (err) {
        console.error(err);
        alert(`Demo加载失败: ${err.message}`);
    } finally {
        loadingOverlay.classList.add('hidden');
        demoBtn.disabled = false;
    }
});
