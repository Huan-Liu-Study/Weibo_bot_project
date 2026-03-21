// ==================== CHARTS RENDERING (ECharts) ====================

function renderPieChart(humans, bots, news) {
    const chartDom = document.getElementById('pieChart');
    if (!chartDom) return;
    const chart = echarts.init(chartDom);
    chart.setOption({
        tooltip: { 
            trigger: 'item', 
            backgroundColor: 'rgba(255, 255, 255, 0.9)', 
            borderColor: '#e8e0d4', 
            textStyle: { color: '#2c2418' },
            backdropFilter: 'blur(4px)'
        },
        legend: { bottom: 10, textStyle: { color: '#8a7e6b' } },
        series: [{
            type: 'pie',
            radius: ['45%', '70%'],
            itemStyle: { borderRadius: 6, borderColor: 'rgba(255,255,255,0.4)', borderWidth: 2 },
            label: { show: true, color: '#2c2418', formatter: '{b}\n{d}%' },
            data: [
                { value: humans, name: '正常用户', itemStyle: { color: '#7cb87a' } },
                { value: bots, name: '疑似水军', itemStyle: { color: '#c96b5e' } },
                { value: news, name: '新闻媒体', itemStyle: { color: '#3498db' } }
            ]
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderRadarChart(containerId, humansData, botsData) {
    const chartDom = document.getElementById(containerId);
    if (!chartDom) return;
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

    const chart = echarts.init(chartDom);
    chart.setOption({
        tooltip: { 
            backgroundColor: 'rgba(255, 255, 255, 0.9)', 
            borderColor: '#e8e0d4', 
            textStyle: { color: '#2c2418' },
            backdropFilter: 'blur(4px)'
        },
        legend: { bottom: 5, textStyle: { color: '#8a7e6b' }, data: ['正常用户', '疑似水军'] },
        radar: {
            indicator: indicators,
            axisName: { color: '#8a7e6b', fontSize: 11 },
            splitArea: { show: false },
            axisLine: { lineStyle: { color: 'rgba(184, 148, 61, 0.2)' } },
            splitLine: { lineStyle: { color: 'rgba(184, 148, 61, 0.1)' } }
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

// ==================== WORDCLOUD (v1.9.40) ====================

function renderWordClouds(data) {
    if (!data) return;
    initCloud('humanWordCloud', data.humans || [], '#3498db');
    initCloud('botWordCloud', data.bots || [], '#c96b5e');
}

function initCloud(id, words, baseColor) {
    const chartDom = document.getElementById(id);
    if (!chartDom) return;
    const myChart = echarts.init(chartDom);
    
    // 如果没有数据，显示提示
    if (!words || words.length === 0) {
        myChart.setOption({
            graphic: [{
                type: 'text',
                left: 'center',
                top: 'center',
                style: {
                    text: '暂无足够样本文本',
                    fill: '#999',
                    font: '14px sans-serif'
                }
            }]
        });
        return;
    }

    const option = {
        tooltip: { show: true },
        series: [{
            type: 'wordCloud',
            shape: 'circle',
            left: 'center',
            top: 'center',
            width: '90%',
            height: '90%',
            right: null,
            bottom: null,
            sizeRange: [12, 45],
            rotationRange: [-45, 90],
            rotationStep: 45,
            gridSize: 8,
            drawOutOfBound: false,
            textStyle: {
                fontFamily: 'Outfit, Inter, sans-serif',
                fontWeight: 'bold',
                color: function () {
                    return baseColor;
                }
            },
            emphasis: {
                focus: 'self',
                textStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.1)' }
            },
            data: words
        }]
    };

    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

// ==================== DATABASE VISUALIZATION (v1.9.0) ====================

function renderScatterChart(nodes) {
    const chartDom = document.getElementById('scatterChart');
    if (!chartDom) return;
    const chart = echarts.init(chartDom);
    
    // 构造散点图数据 (v1.9.4 分级体系 + v1.9.20 媒体识别)
    const humansData = [];
    const warningsData = [];
    const botsData = [];
    const newsData = [];
    
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
        
        if (n.is_news_media === 1 || n.is_official_media === 1) { // 兼容 v1.9.40 以后的 is_official_media
            newsData.push(item);
        } else if (n.is_bot_pred === 1) {
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
                if (n.is_news_media === 1 || n.is_official_media === 1) {
                    riskLabel = '<span style="color:#3498db;">媒体/官方</span>';
                    color = '#3498db';
                } else if (n.is_bot_pred === 1) {
                    riskLabel = '<span style="color:#c96b5e;">高危</span>';
                    color = '#c96b5e';
                } else if (n.has_red_flag) {
                    riskLabel = '<span style="color:#f39c12;">预警</span>';
                    color = '#f39c12';
                }
                
                // app.js 中的全局函数 target
                const safeText = window.escapeHtml ? window.escapeHtml(textPreview) : textPreview;
                
                return `
                    <div style="font-weight:600;margin-bottom:6px;border-bottom:1px solid #e8e0d4;padding-bottom:6px;">
                        ${param.data.name} [${riskLabel}] <span style="float:right;color:${color};">${score}</span>
                    </div>
                    <div style="font-size:12px;color:#8a7e6b;max-width:300px;white-space:normal;line-height:1.5;">${safeText}</div>
                    <div style="margin-top:8px;font-size:11px;color:#b8943d;">👉 点击气泡查看由于哪些特征被判定</div>
                `;
            }
        },
        legend: {
            bottom: 10,
            textStyle: { color: '#8a7e6b' },
            data: ['正常用户', '触碰红旗', '疑似水军', '新闻媒体']
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
            },
            {
                name: '新闻媒体',
                type: 'scatter',
                data: newsData,
                symbolSize: (data) => Math.min(Math.log10((data[4].followers_count || 0) + 1) * 6 + 12, 45),
                itemStyle: { color: '#3498db', borderColor: '#fff', borderWidth: 1 }
            }
        ]

    };
    
    chart.setOption(option, true);
    
    // 监听点击事件，打开弹窗
    chart.off('click');
    chart.on('click', function(params) {
        if (params.data && params.data.value) {
            const rawNodeData = params.data.value[4];
            if (window.openNodeModal) {
                window.openNodeModal(rawNodeData);
            }
        }
    });
    
    window.addEventListener('resize', () => chart.resize());
}

function renderUserRadar(features) {
    const chartDom = document.getElementById('userRadar');
    if (!chartDom) return;
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

    const chart = echarts.init(chartDom);
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
