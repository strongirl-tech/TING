#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TING 每日研究笔记自动生成脚本
功能：
1. 检查今日是否已更新
2. 登录她乡论坛并抓取最新帖子
3. 筛选与身份认同、性别研究、自我发展、跨文化适应相关的主题
4. 生成研究笔记HTML文件
5. 更新首页(index.html)和博客列表页(blog.html)
"""

import os
import sys
import re
import json
import random
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, quote
from html import escape as html_escape

import requests
from bs4 import BeautifulSoup

# ============ 配置 ============
FORUM_URL = "https://forum.womenoverseas.com"
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(REPO_DIR, "posts")
INDEX_PATH = os.path.join(REPO_DIR, "index.html")
BLOG_PATH = os.path.join(REPO_DIR, "blog.html")

# 感兴趣的主题关键词（用于筛选帖子）
RELEVANT_KEYWORDS = [
    "身份", "认同", "性别", "女性", "自我", "发展", "成长", "文化", "适应",
    "跨文化", "移民", "海外", "华人", "归属感", "边界", "burnout", "焦虑",
    "抑郁", "心理", "情感", "关系", "职场", "工作", "职业", "学术", "博士",
    "论文", "母亲", "生育", "婚姻", "恋爱", "友谊", "孤独", "语言", "身体",
    "健康", "食物", "饮食", "时间", "空间", "家", "回归", "留下", "选择",
    "独立", "自由", "压迫", "歧视", "偏见", "刻板印象", "竹天花板", "玻璃天花板",
    "代际", "创伤", "疗愈", "韧性", "脆弱", "力量", "赋权", "发声", "沉默",
    "visible", "invisible", "belonging", "identity", "gender", "culture",
    "adaptation", "immigration", "diaspora", "boundary", "burnout", "healing"
]

# 笔记标题模板（当无法生成时作为后备）
FALLBACK_TITLES = [
    "离散中的回响：海外华人女性的身份协商与日常实践",
    "跨越边界的自我：移民女性如何在多重文化中锚定自己",
    "温柔的力量：海外华人女性社群中的互助与韧性",
    "在异乡重新学习呼吸：跨文化适应中的身体与情感政治",
    "时间的褶皱：海外华人女性生命节奏中的文化张力",
    "从沉默到发声：海外华人女性的性别经验与主体性建构",
    "流动的归属：离散社群中的联结形式与认同重构",
    "在缝隙中生长：海外华人女性的日常抵抗与自我关怀",
]


def get_today_str():
    """获取今日日期字符串（北京时间）"""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d")


def get_today_display():
    """获取今日显示格式"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return {
        "iso": now.strftime("%Y-%m-%d"),
        "dot": now.strftime("%Y.%m.%d"),
        "cn": now.strftime("%Y年%m月%d日"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
    }


def check_already_updated():
    """检查今日是否已更新"""
    force = os.environ.get("FORCE_UPDATE", "false").lower() == "true"
    if force:
        return False

    today = get_today_str()
    
    # 方法1：检查index.html中最新的文章日期
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        # 查找第一个 time 标签的 datetime 属性
        match = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})"', content)
        if match:
            latest_date = match.group(1)
            if latest_date == today:
                print(f"[{today}] 今日已更新过（最新文章日期: {latest_date}），跳过。")
                return True
    
    # 方法2：检查posts目录中最新的文件
    post_files = sorted(os.listdir(POSTS_DIR)) if os.path.exists(POSTS_DIR) else []
    if post_files:
        # 尝试从文件内容提取日期
        latest_file = os.path.join(POSTS_DIR, post_files[-1])
        with open(latest_file, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"', content)
        if match:
            latest_date = match.group(1)
            if latest_date == today:
                print(f"[{today}] 今日已更新过（最新post日期: {latest_date}），跳过。")
                return True
    
    return False


class DiscourseClient:
    """她乡论坛 Discourse API 客户端"""
    
    def __init__(self, base_url=FORUM_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self.authenticated = False
    
    def login_with_password(self, username, password):
        """使用用户名密码登录（获取会话Cookie）"""
        # 1. 获取CSRF token
        resp = self.session.get(f"{self.base_url}/session/csrf", timeout=30)
        csrf = resp.json().get("csrf")
        self.session.headers["X-CSRF-Token"] = csrf
        
        # 2. 登录
        login_data = {
            "login": username,
            "password": password,
            "second_factor_method": 1,
            "timezone": "Asia/Shanghai",
        }
        resp = self.session.post(
            f"{self.base_url}/session",
            data=login_data,
            timeout=30,
        )
        result = resp.json()
        
        if result.get("error"):
            print(f"登录失败: {result['error']}")
            return False
        
        self.authenticated = True
        print(f"登录成功: {result.get('username', username)}")
        return True
    
    def login_with_api_key(self, api_key, api_username="system"):
        """使用API Key登录"""
        self.session.headers["Api-Key"] = api_key
        self.session.headers["Api-Username"] = api_username
        self.authenticated = True
        print("已设置API Key认证")
        return True
    
    def get_latest_topics(self, page=0):
        """获取最新主题列表"""
        url = f"{self.base_url}/latest.json"
        params = {"page": page, "no_definitions": "true"}
        
        try:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 403 or "not_logged_in" in resp.text:
                print("获取最新主题失败：未登录或权限不足")
                return []
            data = resp.json()
            return data.get("topic_list", {}).get("topics", [])
        except Exception as e:
            print(f"获取最新主题出错: {e}")
            return []
    
    def get_topic_posts(self, topic_id):
        """获取主题的帖子内容"""
        url = f"{self.base_url}/t/{topic_id}.json"
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception as e:
            print(f"获取主题详情出错: {e}")
            return None
    
    def search_topics(self, query, sort="latest"):
        """搜索主题"""
        url = f"{self.base_url}/search.json"
        params = {"q": query, "sort": sort}
        try:
            resp = self.session.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get("topics", [])
        except Exception as e:
            print(f"搜索出错: {e}")
            return []


def score_topic_relevance(topic):
    """评分主题与关注领域的相关度"""
    score = 0
    text = f"{topic.get('title', '')} {topic.get('excerpt', '')} {topic.get('category_id', '')}"
    text = text.lower()
    
    for kw in RELEVANT_KEYWORDS:
        if kw.lower() in text:
            score += 1
    
    # 优先选择有较多回复和浏览的帖子（活跃度）
    score += min(topic.get("posts_count", 0), 10) * 0.1
    score += min(topic.get("views", 0) / 100, 5)
    
    return score


def fetch_forum_content():
    """从论坛获取相关内容"""
    client = DiscourseClient()
    
    # 尝试认证
    username = os.environ.get("FORUM_USERNAME")
    password = os.environ.get("FORUM_PASSWORD")
    api_key = os.environ.get("FORUM_API_KEY")
    
    if api_key:
        client.login_with_api_key(api_key, username or "system")
    elif username and password:
        client.login_with_password(username, password)
    else:
        print("警告：未配置论坛认证信息，尝试以访客身份访问...")
    
    # 获取最新主题
    topics = client.get_latest_topics(page=0)
    if not topics:
        print("未能获取任何主题，请检查认证配置")
        return None
    
    print(f"获取到 {len(topics)} 个最新主题")
    
    # 按相关度排序
    scored = [(t, score_topic_relevance(t)) for t in topics]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # 取最相关的几个主题
    top_topics = scored[:5]
    
    # 获取详细内容
    contents = []
    for topic, score in top_topics:
        tid = topic.get("id")
        detail = client.get_topic_posts(tid)
        if detail:
            posts = detail.get("post_stream", {}).get("posts", [])
            if posts:
                first_post = posts[0]
                contents.append({
                    "title": topic.get("title"),
                    "url": f"{FORUM_URL}/t/{topic.get('slug')}/{tid}",
                    "excerpt": topic.get("excerpt", ""),
                    "body": first_post.get("cooked", ""),
                    "author": first_post.get("username", ""),
                    "views": topic.get("views", 0),
                    "posts_count": topic.get("posts_count", 0),
                    "score": score,
                })
    
    return contents


def clean_html(html_text):
    """清理HTML标签，保留段落结构"""
    soup = BeautifulSoup(html_text, "html.parser")
    # 移除script和style
    for tag in soup(["script", "style", "iframe", "img"]):
        tag.decompose()
    # 获取文本
    text = soup.get_text(separator="\n", strip=True)
    # 清理多余空行
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def generate_note_with_ai(topics_content):
    """使用AI生成研究笔记（当配置了OPENAI_API_KEY时）"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    
    try:
        # 构建提示
        topics_text = "\n\n".join([
            f"【帖子{i+1}】{t['title']}\n{t.get('clean_body', clean_html(t['body']))[:500]}"
            for i, t in enumerate(topics_content[:3])
        ])
        
        prompt = f"""基于以下海外华人女性论坛的最新帖子，撰写一篇500-800字的中文研究笔记。
风格要求：学术但不失个人温度，有理论视角但不堆砌术语，引用帖子内容时自然融入叙述。
主题方向：海外华人女性身份认同、性别研究、自我发展、跨文化适应。

{topics_text}

请输出以下格式的JSON：
{{
  "title": "主标题（10字以内）",
  "subtitle": "副标题（20字左右）",
  "excerpt": "摘要（80-120字，用于博客卡片）",
  "sections": [
    {{"heading": "小节标题1", "content": "正文段落（可包含多个<p>标签的内容）"}},
    {{"heading": "小节标题2", "content": "正文段落"}},
    {{"heading": "小节标题3", "content": "正文段落"}},
    {{"heading": "结语", "content": "结语段落"}}
  ],
  "tags": ["标签1", "标签2", "标签3"],
  "quote": {{"text": "引用文本", "source": "她乡论坛用户"}}
}}
"""
        
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "你是一位研究海外华人女性议题的学者，擅长将论坛讨论转化为有深度的研究笔记。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
        return result
    except Exception as e:
        print(f"AI生成失败: {e}")
        return None


def generate_fallback_note():
    """当无法获取论坛内容时，生成一个模板笔记（需手动填充）"""
    title = random.choice(FALLBACK_TITLES)
    return {
        "title": title.split("：")[0] if "：" in title else title[:10],
        "subtitle": title.split("：")[1] if "：" in title else "海外华人女性的日常与思考",
        "excerpt": "（今日因论坛认证问题未能自动抓取内容，请手动补充或检查认证配置。）",
        "sections": [
            {"heading": "论坛观察", "content": "<p>（请基于今日论坛热门话题补充内容）</p>"},
            {"heading": "理论视角", "content": "<p>（请从学术角度展开分析）</p>"},
            {"heading": "个人回响", "content": "<p>（请加入个人化的思考与温度）</p>"},
            {"heading": "结语", "content": "<p>愿我们在离散中依然能够彼此看见。</p>"},
        ],
        "tags": ["研究笔记", "华人女性", "待补充"],
        "quote": {"text": "在缝隙中生长，向更远的地方伸展。", "source": "她乡论坛"},
    }


def create_post_html(note_data, date_info):
    """创建文章HTML文件"""
    # 生成文件名
    title_slug = note_data.get("subtitle", note_data["title"])
    # 用哈希确保唯一性
    hash_suffix = hashlib.md5(title_slug.encode()).hexdigest()[:6]
    filename = f"posts/note-{date_info['iso']}-{hash_suffix}.html"
    filepath = os.path.join(REPO_DIR, filename)
    
    # 构建TOC和正文
    toc_links = "\n".join([
        f'          <a href="#s-{i}" class="toc-link">{s["heading"]}</a>'
        for i, s in enumerate(note_data["sections"])
    ])
    
    sections_html = ""
    for i, section in enumerate(note_data["sections"]):
        sid = f"s-{i}"
        content = section["content"]
        # 确保内容有p标签
        if not content.strip().startswith("<"):
            content = f"<p>{content}</p>"
        
        sections_html += f'''
      <section id="{sid}" class="post-section">
        <h2 class="section-heading">
          <svg class="s-leaf" viewBox="0 0 14 16" fill="none" aria-hidden="true">
            <path d="M7 15 C7 15 1 11.5 1 6.5 C1 1.5 4 0.5 7 1.5 C10 0.5 13 1.5 13 6.5 C13 11.5 7 15 7 15Z" fill="#4A7C5A" opacity="0.75"/>
            <line x1="7" y1="15" x2="7" y2="1.5" stroke="#2A5239" stroke-width="0.9" opacity="0.5"/>
          </svg>
          {html_escape(section["heading"])}
        </h2>
        {content}
      </section>
'''
    
    # 引用
    quote = note_data.get("quote", {})
    quote_html = ""
    if quote:
        quote_html = f'''
      <blockquote class="lede-quote">
        <span class="lede-mark">"</span>
        {html_escape(quote.get("text", ""))}
        <cite>— {html_escape(quote.get("source", "她乡论坛用户"))}</cite>
      </blockquote>
'''
    
    # 标签
    tags = note_data.get("tags", ["研究笔记"])
    tag_pills = "\n".join([f'        <span class="post-tag-pill">{html_escape(t)}</span>' for t in tags])
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_escape(note_data["title"])}：{html_escape(note_data["subtitle"])} - TING</title>
  <link rel="stylesheet" href="../css/style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400;1,600&family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌿</text></svg>">

  <meta property="og:type" content="website">
  <meta property="og:site_name" content="TING">
  <meta property="og:title" content="{html_escape(note_data["title"])}：{html_escape(note_data["subtitle"])} - TING">
  <meta property="og:description" content="探索 · 记录 · 思考">
  <meta property="og:image" content="https://strongirl-tech.github.io/TING/assets/og-cover.png">
  <meta property="og:url" content="https://strongirl-tech.github.io/TING/{filename}">
  <meta property="og:locale" content="zh_CN">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html_escape(note_data["title"])}：{html_escape(note_data["subtitle"])} - TING">
  <meta name="twitter:description" content="探索 · 记录 · 思考">
  <meta name="twitter:image" content="https://strongirl-tech.github.io/TING/assets/og-cover.png">

<style>
    .qr-float-btn {{
      position: fixed;
      bottom: 28px;
      right: 28px;
      width: 52px;
      height: 52px;
      border-radius: 50%;
      background: linear-gradient(135deg, #3A6B47 0%, #5A8C6A 100%);
      color: #fff;
      border: none;
      cursor: pointer;
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 20px rgba(58,107,71,0.35);
      transition: transform 0.25s, box-shadow 0.25s;
      font-size: 22px;
    }}
    .qr-float-btn:hover {{ transform: scale(1.12); box-shadow: 0 6px 28px rgba(58,107,71,0.5); }}
    .qr-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.55);
      z-index: 10000;
      align-items: center;
      justify-content: center;
    }}
    .qr-overlay.active {{ display: flex; }}
    .qr-popup {{
      background: #fff;
      border-radius: 18px;
      padding: 32px 32px 24px;
      text-align: center;
      box-shadow: 0 12px 48px rgba(0,0,0,0.18);
      position: relative;
      animation: qrPop 0.25s ease-out;
      max-width: 380px;
      width: 90vw;
    }}
    @keyframes qrPop {{ from {{ transform: scale(0.85); opacity: 0; }} to {{ transform: scale(1); opacity: 1; }} }}
    .qr-close {{
      position: absolute;
      top: 10px; right: 16px;
      background: none; border: none;
      font-size: 22px; color: #999; cursor: pointer;
    }}
    .qr-close:hover {{ color: #333; }}
    .qr-tabs {{
      display: flex;
      border-bottom: 2px solid #e8e8e8;
      margin-bottom: 20px;
      gap: 0;
    }}
    .qr-tab-btn {{
      flex: 1;
      padding: 10px 0 8px;
      background: none;
      border: none;
      cursor: pointer;
      font-size: 15px;
      color: #999;
      transition: color 0.2s;
      position: relative;
    }}
    .qr-tab-btn.active {{ color: #2E4A35; }}
    .qr-tab-btn.active::after {{
      content: '';
      position: absolute;
      bottom: -2px;
      left: 10%;
      width: 80%;
      height: 2px;
      background: #3A6B47;
      border-radius: 2px;
    }}
    .qr-tab-content {{ display: none; }}
    .qr-tab-content.active {{ display: block; }}
    .qr-tab-content img.qr-static-img {{
      width: 220px; height: 220px;
      border: 1px solid #e0e0e0; border-radius: 8px;
      margin-bottom: 12px;
    }}
    .qr-tab-content p {{ margin: 0 0 12px; color: #666; font-size: 13px; }}
    .share-btn {{
      display: inline-block;
      padding: 10px 24px;
      background: linear-gradient(135deg, #3A6B47, #5A8C6A);
      color: #fff;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .share-btn:hover {{ transform: scale(1.05); box-shadow: 0 4px 16px rgba(58,107,71,0.3); }}
    @media (max-width: 500px) {{
      .qr-popup {{ padding: 28px 16px 16px; }}
      .qr-tab-content img.qr-static-img {{ width: 180px !important; height: 180px !important; }}
    }}
</style></head>

<body>

  <div class="reading-progress" id="readingProgress"></div>

  <nav class="navbar">
    <div class="nav-container">
      <a href="../index.html" class="nav-logo">TING</a>
      <div class="nav-links">
        <a href="../index.html">首页</a>
        <a href="../blog.html" class="active">博客</a>
        <a href="../growth.html">成长记录</a>
        <a href="about.html">关于</a>
      </div>
      <button class="nav-toggle" aria-label="菜单">
        <span></span>
        <span></span>
        <span></span>
      </button>
    </div>
  </nav>

  <header class="post-hero">
    <svg class="post-hero-deco" viewBox="0 0 260 300" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M130 280 C130 280 18 218 12 128 C6 38 88 8 130 18 C172 8 254 38 248 128 C242 218 130 280 130 280Z" fill="#2A5239"/>
      <path d="M130 280 L130 18" stroke="#7BAE8A" stroke-width="2" opacity="0.5"/>
      <path d="M130 230 C98 210 52 204 30 185" stroke="#7BAE8A" stroke-width="1.5" opacity="0.4" fill="none"/>
      <path d="M130 185 C162 165 208 158 228 138" stroke="#7BAE8A" stroke-width="1.5" opacity="0.4" fill="none"/>
      <path d="M130 140 C104 124 66 116 46 100" stroke="#7BAE8A" stroke-width="1.5" opacity="0.4" fill="none"/>
      <path d="M130 100 C156 86 196 78 214 62" stroke="#7BAE8A" stroke-width="1.5" opacity="0.35" fill="none"/>
    </svg>

    <div class="container post-hero-inner">
      <nav class="post-breadcrumb" aria-label="面包屑导航">
        <a href="../index.html">首页</a>
        <span class="breadcrumb-sep">›</span>
        <a href="../blog.html">博客</a>
        <span class="breadcrumb-sep">›</span>
        <span>研究笔记</span>
      </nav>

      <div class="post-meta-row">
        <span class="post-tag-pill">研究笔记</span>
        <time class="post-meta-time" datetime="{date_info['iso']}">{date_info['cn']}</time>
        <span class="post-read-time">☕ 约 5 分钟阅读</span>
      </div>

      <h1 class="post-hero-title">{html_escape(note_data["title"])}</h1>
      <p class="post-hero-subtitle">{html_escape(note_data["subtitle"])}</p>
    </div>
  </header>

  <div class="post-layout container">

    <aside class="post-toc" id="postToc" aria-label="文章目录">
      <div class="toc-box">
        <p class="toc-label">目录</p>
        <nav>
{toc_links}
        </nav>
      </div>
    </aside>

    <article class="post-article" id="postContent">
{quote_html}
{sections_html}
    </article>
  </div>

  <div class="post-footer-bar">
    <div class="container post-footer-inner">
      <a href="../blog.html" class="post-back-link">
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
          <path d="M9.5 3L5 7.5L9.5 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        返回博客
      </a>
      <div class="post-tag-row">
{tag_pills}
      </div>
    </div>
  </div>

  <footer class="footer">
    <div class="footer-container">
      <p>&copy; 2025 TING. All rights reserved.</p>
      <div class="footer-links">
        <a href="https://github.com/strongirl-tech/TING" target="_blank" rel="noopener">GitHub</a>
      </div>
    </div>
  </footer>

  <script src="../js/main.js"></script>
  <script>
    (function () {{
      var bar = document.getElementById('readingProgress');
      var content = document.getElementById('postContent');
      function tick() {{
        var rect = content.getBoundingClientRect();
        var total = content.offsetHeight;
        var read = -rect.top + window.innerHeight * 0.6;
        var pct = Math.min(Math.max(read / total * 100, 0), 100);
        bar.style.width = pct + '%';
      }}
      window.addEventListener('scroll', tick, {{ passive: true }});
      tick();
    }})();

    (function () {{
      var sections = document.querySelectorAll('.post-section');
      var links = document.querySelectorAll('.toc-link');
      if (!sections.length || !links.length) return;
      var io = new IntersectionObserver(function (entries) {{
        entries.forEach(function (e) {{
          if (e.isIntersecting) {{
            links.forEach(function (l) {{ l.classList.remove('active'); }});
            var al = document.querySelector('.toc-link[href="#' + e.target.id + '"]');
            if (al) al.classList.add('active');
          }}
        }});
      }}, {{ rootMargin: '-20% 0px -65% 0px' }});
      sections.forEach(function (s) {{ io.observe(s); }});
    }})();
  </script>

  <button class="qr-float-btn" onclick="toggleQR()" aria-label="分享二维码">&#x1F517;</button>
  <div class="qr-overlay" id="qrOverlay" onclick="closeQR(event)">
    <div class="qr-popup">
      <button class="qr-close" onclick="closeQR(event)">&times;</button>
      <div class="qr-tabs">
        <button class="qr-tab-btn active" onclick="switchTab('scan')">扫码访问</button>
        <button class="qr-tab-btn" onclick="switchTab('share')">分享卡片</button>
      </div>
      <div class="qr-tab-content active" id="qrScanTab">
        <img src="../assets/site-qrcode.png" alt="扫码访问 TING" class="qr-static-img">
        <p>扫描二维码访问本站</p>
      </div>
      <div class="qr-tab-content" id="qrShareTab">
        <img src="../assets/site-qrcode.png" alt="二维码" class="qr-static-img" style="width:140px;height:140px;">
        <canvas id="shareCardCanvas" width="680" height="960" style="display:none;"></canvas>
        <p>生成精美分享卡片，保存图片后发朋友圈</p>
        <button class="share-btn" onclick="generateAndSave()">保存分享卡片</button>
      </div>
    </div>
  </div>

  <script>
    function toggleQR() {{
      document.getElementById('qrOverlay').classList.add('active');
    }}
    function closeQR(e) {{
      if (e.target === document.getElementById('qrOverlay') || e.target.closest('.qr-close')) {{
        document.getElementById('qrOverlay').classList.remove('active');
      }}
    }}
    document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeQR(e); }});
    function switchTab(tab) {{
      var btns = document.querySelectorAll('.qr-tab-btn');
      var tabs = document.querySelectorAll('.qr-tab-content');
      btns.forEach(function(b, i) {{
        b.classList.toggle('active', i === (tab === 'scan' ? 0 : 1));
      }});
      tabs.forEach(function(t) {{ t.classList.remove('active'); }});
      document.getElementById(tab === 'scan' ? 'qrScanTab' : 'qrShareTab').classList.add('active');
    }}
    function generateAndSave() {{
      var canvas = document.getElementById('shareCardCanvas');
      var ctx = canvas.getContext('2d');
      var ogTitle = document.querySelector('meta[property="og:title"]');
      var ogDesc = document.querySelector('meta[property="og:description"]');
      var pageTitle = ogTitle ? ogTitle.getAttribute('content') : document.title;
      var pageDesc = ogDesc ? ogDesc.getAttribute('content') : '探索 · 记录 · 思考';
      var grad = ctx.createLinearGradient(0, 0, 0, 960);
      grad.addColorStop(0, '#2A5239');
      grad.addColorStop(1, '#4A7C5A');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 680, 960);
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 2;
      for (var i = 0; i < 6; i++) {{
        ctx.beginPath();
        ctx.arc(340, 480, 120 + i * 40, 0, Math.PI * 2);
        ctx.stroke();
      }}
      ctx.fillStyle = '#ffffff';
      ctx.font = 'italic 64px Georgia, serif';
      ctx.textAlign = 'center';
      ctx.fillText('TING', 340, 120);
      ctx.fillStyle = '#ffffff';
      roundRect(ctx, 40, 160, 600, 680, 16);
      ctx.fill();
      ctx.fillStyle = '#2E4A35';
      ctx.font = 'bold 26px "Noto Serif SC", Georgia, serif';
      ctx.textAlign = 'center';
      wrapText(ctx, pageTitle, 340, 210, 520, 32);
      ctx.fillStyle = '#666666';
      ctx.font = '16px "Noto Sans SC", Arial, sans-serif';
      ctx.textAlign = 'center';
      wrapText(ctx, pageDesc, 340, 300, 520, 22);
      var qrImg = new Image();
      qrImg.crossOrigin = 'anonymous';
      var qrSrc = document.querySelector('.qr-static-img').src;
      qrImg.onload = function() {{
        ctx.drawImage(qrImg, 240, 520, 200, 200);
        ctx.fillStyle = '#999999';
        ctx.font = '14px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('扫码阅读全文', 340, 740);
        ctx.fillStyle = '#7BAE8A';
        ctx.font = '12px Arial, sans-serif';
        ctx.fillText('strongirl-tech.github.io/TING', 340, 870);
        var link = document.createElement('a');
        link.download = 'TING-share-card.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
      }};
      qrImg.onerror = function() {{
        ctx.fillStyle = '#2E4A35';
        ctx.font = '16px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(window.location.href, 340, 600);
        ctx.fillStyle = '#7BAE8A';
        ctx.font = '12px Arial, sans-serif';
        ctx.fillText('strongirl-tech.github.io/TING', 340, 870);
        var link = document.createElement('a');
        link.download = 'TING-share-card.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
      }};
      qrImg.src = qrSrc;
    }}
    function roundRect(ctx, x, y, w, h, r) {{
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }}
    function wrapText(ctx, text, x, y, maxWidth, lineHeight) {{
      var chars = text.split('');
      var line = '';
      var lines = [];
      for (var i = 0; i < chars.length; i++) {{
        var testLine = line + chars[i];
        var metrics = ctx.measureText(testLine);
        if (metrics.width > maxWidth && line.length > 0) {{
          lines.push(line);
          line = chars[i];
        }} else {{
          line = testLine;
        }}
      }}
      lines.push(line);
      for (var j = 0; j < lines.length; j++) {{
        ctx.fillText(lines[j], x, y + j * lineHeight);
      }}
      return lines.length;
    }}
  </script></body>
</html>
'''
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    return filename, filepath


def update_index_html(filename, note_data, date_info):
    """更新首页 index.html"""
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    excerpt = note_data.get("excerpt", "")[:120]
    if len(excerpt) > 117:
        excerpt = excerpt[:117] + "..."
    
    new_card = f'''          <article class="post-card">
            <div class="post-card-meta">
              <time datetime="{date_info['iso']}">{date_info['dot']}</time>
              <span class="post-tag">研究笔记</span>
            </div>
            <h3 class="post-card-title">
              <a href="{filename}">{html_escape(note_data["title"])}：{html_escape(note_data["subtitle"])}</a>
            </h3>
            <p class="post-card-excerpt">{html_escape(excerpt)}</p>
            <a href="{filename}" class="read-more">阅读全文 →</a>
          </article>
'''
    
    # 在 posts-grid 开头插入新卡片
    pattern = r'(<div class="posts-grid">)\n'
    replacement = r'\1\n' + new_card
    content = re.sub(pattern, replacement, content, count=1)
    
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"已更新 {INDEX_PATH}")


def update_blog_html(filename, note_data, date_info):
    """更新博客列表页 blog.html"""
    with open(BLOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    excerpt = note_data.get("excerpt", "")[:120]
    if len(excerpt) > 117:
        excerpt = excerpt[:117] + "..."
    
    new_article = f'''            <article class="post-card">
              <div class="post-card-meta">
                <time datetime="{date_info['iso']}">{date_info['dot']}</time>
                <span class="post-tag">研究笔记</span>
              </div>
              <h3 class="post-card-title">
                <a href="{filename}">{html_escape(note_data["title"])}：{html_escape(note_data["subtitle"])}</a>
              </h3>
              <p class="post-card-excerpt">{html_escape(excerpt)}</p>
              <a href="{filename}" class="read-more">阅读全文 →</a>
            </article>

'''
    
    # 在 blog-list 开头插入
    pattern = r'(<div class="blog-list">)\n'
    replacement = r'\1\n' + new_article
    content = re.sub(pattern, replacement, content, count=1)
    
    with open(BLOG_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"已更新 {BLOG_PATH}")


def main():
    print("=" * 50)
    print("TING 每日研究笔记生成器")
    print("=" * 50)
    
    # 1. 检查今日是否已更新
    if check_already_updated():
        print("跳过执行。")
        sys.exit(0)
    
    date_info = get_today_display()
    print(f"\n今日日期: {date_info['cn']}")
    
    # 2. 获取论坛内容
    print("\n[1/4] 正在连接她乡论坛...")
    topics_content = fetch_forum_content()
    
    # 3. 生成笔记
    print("\n[2/4] 生成研究笔记...")
    note_data = None
    
    if topics_content:
        print(f"基于 {len(topics_content)} 个相关主题生成笔记")
        # 预处理内容
        for t in topics_content:
            t["clean_body"] = clean_html(t.get("body", ""))
        
        # 尝试AI生成
        note_data = generate_note_with_ai(topics_content)
    
    if not note_data:
        print("未能自动生成笔记，使用后备模板（需手动补充内容）")
        note_data = generate_fallback_note()
    
    # 4. 创建HTML文件
    print("\n[3/4] 创建文章页面...")
    filename, filepath = create_post_html(note_data, date_info)
    print(f"文章已创建: {filepath}")
    
    # 5. 更新首页和博客列表
    print("\n[4/4] 更新索引页面...")
    update_index_html(filename, note_data, date_info)
    update_blog_html(filename, note_data, date_info)
    
    print("\n" + "=" * 50)
    print("完成！请检查生成的文件并提交到GitHub。")
    print("=" * 50)


if __name__ == "__main__":
    main()
