# TING

一个关于研究、旅行与成长的思考空间。记录海外华人女性的身份协商、自我重构与跨国探索。

## 每日研究笔记自动化

本项目已配置 GitHub Actions 工作流，每天北京时间上午9点自动从她乡论坛抓取最新讨论，生成研究笔记并更新博客。

### 配置步骤

#### 1. 配置论坛认证（必需）

她乡论坛需要登录才能访问内容。请在 GitHub 仓库设置中添加以下 Secrets：

- `FORUM_USERNAME` — 她乡论坛用户名/邮箱
- `FORUM_PASSWORD` — 她乡论坛密码
- `FORUM_API_KEY` — （可选）Discourse API Key，比密码登录更稳定

> 获取 API Key 的方法：登录她乡论坛 → 点击头像 → 偏好设置 → 账户 → API 密钥

#### 2. 配置 AI 生成（可选）

如需使用 AI 自动生成笔记内容，请添加：

- `OPENAI_API_KEY` — OpenAI API Key

若不配置，脚本将生成模板文件，需手动补充内容。

#### 3. 手动触发

进入 Actions → Daily Research Note → Run workflow，可手动执行或强制更新。

### 脚本说明

- `scripts/generate_note.py` — 主脚本：抓取、筛选、生成、更新
- `.github/workflows/daily-note.yml` — GitHub Actions 定时触发配置

### 本地测试

```bash
pip install requests beautifulsoup4 lxml
export FORUM_USERNAME="你的用户名"
export FORUM_PASSWORD="你的密码"
python scripts/generate_note.py
```

### 注意事项

- 若当天已更新过，脚本会自动跳过（可通过 `FORCE_UPDATE` 强制更新）
- 论坛内容抓取依赖认证，未配置认证时脚本会生成占位模板
