import pandas as pd
import requests
import json
import time

# 爬虫结果文件路径
csv_path = 'weibo-search/结果文件/中东局势彻底失控/中东局势彻底失控.csv'
output_path = 'weibo-search/结果文件/中东局势彻底失控/中东局势彻底失控_特征完整版.csv'

# 你刚才提供的配置了登录态的新版Cookie
HEADERS = {
    'cookie': 'XSRF-TOKEN=OPTLt0wnBIv60Npc8UGBbP2c; SCF=AnFfovmVqWfOiysGH5K8YEZG75LUWuxKHDtCe7A84TK5JMgkZCbzT3CBx7cqoCZ6j1NdB7GiuobOlJF8jK2WXig.; SUB=_2A25Eo4INDeRhGeBI6VcV9i7IwjWIHXVnwJvFrDV8PUNbmtAYLRj3kW9NRoLB_lC_ATyoVU39pavwFkWmpUldY9kK; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9W52Vg9Ya1DhanH05GzCg9Rk5NHD95QcSozfShq7Sh.4Ws4DqcjUi--NiK.Xi-2Ri--ciKnRi-zNP0qceo-XSo5X1K.t; ALF=02_1775206237;',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Referer': 'https://weibo.com/'
}

def get_user_profile(user_id):
    info_url = f'https://weibo.com/ajax/profile/info?custom={user_id}'
    detail_url = f'https://weibo.com/ajax/profile/detail?custom={user_id}'
    
    result = {'粉丝数': 0, '关注数': 0, '发博数': 0, '注册时间': '', '个人简介': ''}
    try:
        res_info = requests.get(info_url, headers=HEADERS, timeout=10)
        user_info = res_info.json().get('data', {}).get('user', {})
        if user_info:
            result['粉丝数'] = user_info.get('followers_count', 0)
            result['关注数'] = user_info.get('friends_count', 0)
            result['发博数'] = user_info.get('statuses_count', 0)
            result['个人简介'] = user_info.get('description', '')
            
        res_detail = requests.get(detail_url, headers=HEADERS, timeout=10)
        detail_data = res_detail.json().get('data', {})
        if detail_data and 'created_at' in detail_data:
            result['注册时间'] = detail_data.get('created_at', '')
            
    except Exception as e:
        print(f"获取用户 {user_id} 失败: {e}")
    return result

def main():
    print("开始加载原始 CSV 数据...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print("未找到文件，请确认爬虫已成功运行:", e)
        return

    # 为了防止重复请求相同的作者
    unique_users = df['user_id'].unique()
    print(f"共发现 {len(unique_users)} 个独立用户，准备开始获取主页特征...")
    
    user_features = {}
    for i, user_id in enumerate(unique_users):
        print(f"[{i+1}/{len(unique_users)}] 正在获取用户 {user_id} 的数据...")
        user_features[user_id] = get_user_profile(user_id)
        time.sleep(0.5)  # 礼貌延时，适度加快速度

    # 将获取到的特征合并回原始 DataFrame
    print("获取完毕，正在合并数据字段...")
    def map_feature(uid, feature_name):
        return user_features.get(uid, {}).get(feature_name, '')
        
    df['followers_count'] = df['user_id'].apply(lambda x: map_feature(x, '粉丝数'))
    df['friends_count'] = df['user_id'].apply(lambda x: map_feature(x, '关注数'))
    df['statuses_count'] = df['user_id'].apply(lambda x: map_feature(x, '发博数'))
    df['account_created_at'] = df['user_id'].apply(lambda x: map_feature(x, '注册时间'))
    df['description'] = df['user_id'].apply(lambda x: map_feature(x, '个人简介'))
    
    # 填补可能存在的缺失值并保存
    df = df.fillna('')
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n太棒了！特征扩充已完成，新数据已保存至：\n{output_path}")

if __name__ == '__main__':
    main()
