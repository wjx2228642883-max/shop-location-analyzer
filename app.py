import streamlit as st
import requests
import pandas as pd
import os
from dotenv import load_dotenv

# 加载环境变量（如果没配置.env，可以手动把Key填在下面）
load_dotenv()
AMAP_KEY = os.getenv("AMAP_KEY") 

# --- 1. 地理编码：把地址转成经纬度 ---
def geocode(address):
    url = f"https://restapi.amap.com/v3/geocode/geo?address={address}&output=json&key={AMAP_KEY}"
    resp = requests.get(url).json()
    if resp['geocodes']:
        loc = resp['geocodes'][0]['location'].split(',')
        return float(loc[0]), float(loc[1])
    return None, None

# --- 2. 查询周边POI（兴趣点） ---
def search_nearby(lon, lat, keyword, radius=500):
    url = f"https://restapi.amap.com/v3/place/around?location={lon},{lat}&keywords={keyword}&radius={radius}&output=json&key={AMAP_KEY}"
    resp = requests.get(url).json()
    return resp.get('pois', [])

# --- 3. 核心打分逻辑（照搬PDF里的标准） ---
def calculate_score(competitor_count, metro_distance, has_office, has_school, has_food, has_store):
    score = 0
    # 竞品 (30)
    if competitor_count <= 1: score += 30
    elif competitor_count <= 3: score += 20
    elif competitor_count <= 5: score += 10
    # 交通 (25)
    if metro_distance < 200: score += 25
    elif metro_distance < 500: score += 20
    elif metro_distance < 1000: score += 10
    else: score += 5
    # 客流 (25)
    if has_office: score += 15
    if has_school: score += 10
    # 配套 (20)
    if has_food: score += 10
    if has_store: score += 10
    return min(score, 100)  # 上限100

# --- 4. 主界面（Streamlit渲染） ---
st.set_page_config(page_title="AI门店选址专家", layout="wide")
st.title("🏪 AI 智能门店选址分析系统")
st.markdown("输入店铺类型和候选地址，系统自动查数据、算分、排名。")

# 侧边栏输入
with st.sidebar:
    st.header("⚙️ 分析参数")
    shop_type = st.text_input("店铺类型", value="奶茶店")
    address_input = st.text_area("候选地址（每行一个）", 
                                 value="北京市朝阳区三里屯太古里\n北京市海淀区五道口地铁站\n北京市西城区西单大悦城")
    analyze_btn = st.button("🚀 开始智能分析")

# 主区域结果显示
if analyze_btn:
    addresses = [addr.strip() for addr in address_input.split('\n') if addr.strip()]
    results = []
    
    with st.spinner("正在调用高德地图获取周边数据..."):
        for addr in addresses:
            lon, lat = geocode(addr)
            if not lon:
                results.append({"地址": addr, "错误": "无法识别该地址"})
                continue
            
            # 获取各类数据
            competitors = search_nearby(lon, lat, shop_type)
            metros = search_nearby(lon, lat, "地铁站")  # 取最近距离
            offices = search_nearby(lon, lat, "写字楼")
            schools = search_nearby(lon, lat, "中学|大学")
            foods = search_nearby(lon, lat, "餐饮")
            stores = search_nearby(lon, lat, "便利店|超市")
            
            # 提取指标
            comp_count = len(competitors)
            metro_dist = metros[0]['distance'] if metros else 9999
            has_office = len(offices) > 0
            has_school = len(schools) > 0
            has_food = len(foods) > 0
            has_store = len(stores) > 0
            
            # 计算总分
            total = calculate_score(comp_count, float(metro_dist), has_office, has_school, has_food, has_store)
            
            # 评级
            if total >= 85: level = "🔥 强烈推荐"
            elif total >= 70: level = "✅ 推荐"
            elif total >= 55: level = "📌 一般"
            else: level = "❌ 不推荐"
            
            results.append({
                "地址": addr,
                "竞品数(30分)": min(comp_count, 5),
                "地铁距离(m)": int(float(metro_dist)),
                "总分": total,
                "评级": level
            })
    
    # 展示结果表格
    st.subheader("📊 候选地址评分排名")
    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)
    
    # 显示推荐结论
    if not df.empty and "总分" in df.columns:
        best = df.loc[df["总分"].idxmax()]
        st.success(f"🏆 综合推荐：**{best['地址']}** (得分 {best['总分']})")
