import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from bot_pipeline import run_pipeline

st.set_page_config(page_title="自动化话题涉水军与舆情侦测大屏", page_icon="🌐", layout="wide")

st.sidebar.header("🎯 侦测目标设定")
st.sidebar.markdown("输入微博实时话题，系统将接管 Scrapy 爬虫并进行自然语言情感验证与水军判别。")

topic = st.sidebar.text_input("目标话题 (必填,不带#号)", value="中美博弈")
limit = st.sidebar.slider("设置探针样本数 (受限于演示速度，建议10~50)", 10, 100, 20, 10)

st.sidebar.markdown("---")
st.sidebar.markdown("**AI 驱动说明**：\\n"
                    "- 采用 SnowNLP 分析舆论情感偏移\\n"
                    "- 利用 1300+ 样本训练的随机森林（9 维特征）进行判别")

if st.sidebar.button("🚀 启动自动化全维侦测", type="primary"):
    with st.spinner("⚡ 飞速运转中: 挂载 Scrapy 引擎 -> 实施热点抓包 -> 分析潜水比例 -> 提取情绪权重..."):
        try:
            df = run_pipeline(topic, limit)
            st.session_state['df'] = df
            st.success("✅ 猎捕与模型图谱构造完毕！")
        except Exception as e:
            st.error(f"自动化抓取链断裂，请检查网络或爬虫反抗: {e}")

if 'df' in st.session_state:
    df = st.session_state['df']
    st.title(f"📊 微博态势雷达: #{topic}#")
    
    bot_num = df['is_bot_pred'].sum()
    total_num = len(df)
    bot_ratio = bot_num / total_num if total_num > 0 else 0
    avg_sentiment = df['sentiment_score'].mean()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("雷达扫描存活受众数", total_num, help="本次成功抓取并解析主页的用户数量")
    col2.metric("识别出机器水军数", bot_num, delta=f"水军浓度 {bot_ratio*100:.1f}%", delta_color="inverse")
    
    # 评判情绪
    s_label = "负面与悲观" if avg_sentiment < 0.45 else "极度狂热" if avg_sentiment > 0.8 else "客观中立"
    s_color = "normal" if avg_sentiment >= 0.45 else "inverse"
    col3.metric("话题整体舆情倾向", f"{avg_sentiment*100:.1f} 分", delta=s_label, delta_color=s_color, help="100分为全正向积极，0分为全网戾气")
    
    st.divider()
    
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.subheader("🕵️‍♂️ 被捕获的疑似水军名单与高危发言")
        bot_df = df[df['is_bot_pred'] == 1]
        
        if bot_df.empty:
            st.info("太棒了，本次话题下采样的数据暂未发现大规模引战/引流机器狗。")
        else:
            # 整理用于显示的白名单数据
            show_df = bot_df[['用户昵称', 'bot_probability', 'sentiment_score', '微博正文']].copy()
            show_df['bot_probability'] = show_df['bot_probability'].apply(lambda x: f"{x*100:.1f}%")
            show_df['sentiment_score'] = show_df['sentiment_score'].apply(lambda x: f"{x*100:.1f}")
            show_df.rename(columns={'bot_probability': '机器判决率', 'sentiment_score': '情绪阳性值'}, inplace=True)
            st.dataframe(show_df, use_container_width=True, height=250)
            
    with c2:
        st.subheader("🎭 人类 VS 水军的情绪密度画像")
        st.caption("AI 发现：如果红区往往集中在某一个极值（0分或100分），说明水军是在被设计好的剧本内疯狂带一种节奏的情绪！")
        
        # 汉字字体解决
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.kdeplot(data=df, x='sentiment_score', hue='is_bot_pred', fill=True, 
                    palette={0: 'blue', 1: 'red'}, common_norm=False, ax=ax)
        ax.set_title("红区为机器人情绪分布，蓝区为人类真实反映")
        ax.set_xlim(0, 1)
        ax.set_xlabel("情绪判定极性得分 (0=消极 -> 1=积极)")
        ax.set_ylabel("分布密集度")
        st.pyplot(fig)
        
    st.markdown("<br><center>Weibo Social Bot Intelligence Pipeline ©️ 2026</center>", unsafe_allow_html=True)
