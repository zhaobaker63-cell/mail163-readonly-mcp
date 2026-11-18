# 📖 完整配置与使用指南

本文档提供面向非技术用户的“傻瓜式”部署教程。

---

## 准备工作

1. **获取网易企业邮箱客户端授权密码**：
   - 浏览器登录你的网易企业邮箱网页端。
   - 点击右上角「设置」→「客户端设置」/「安全设置」。
   - 找到「客户端授权密码」或「应用密码」，点击「生成新授权码」，保存好那串英文字符。

---

## 极简部署流程（推荐 Windows 用户）

1. 下载本项目并解压到你喜欢的目录。
2. 双击打开 `launcher/一键配置.bat`。
3. 按照命令行提示依次敲入：
   - 你的企业邮箱地址（例如 `yourname@company.com`）
   - 服务器地址（默认直接按回车，通常为 `imap.qiye.163.com`）
   - 客户端授权密码（在控制台输入时屏幕不会显示字符，属于正常安全机制，敲完直接按回车）
4. 程序将自动进行只读握手测试。当看到 `✅ 连接成功` 时，配置已自动完成！

---

## 自检验证

双击打开 `launcher/一键测试连接.bat`。如果输出类似以下信息：
```text
✅ 连接验证成功！
• 邮箱: yourname@company.com
• 主机: imap.qiye.163.com:993
• 可读文件夹: ['INBOX', '已发送']
```
说明一切准备就绪！

---

## 接入各大 AI 平台

### 1. Codex
编辑你的 `~/.codex/config.toml` 文件，在最底部添加：
```toml
[mcp_servers.mail163]
command = "python"
args = ["-m", "mail163_mcp", "serve"]
```

### 2. Accio 桌面工作台
在智能体工作台设置中，添加自定义 MCP 服务：
- 命令: `python`
- 参数: `-m mail163_mcp serve`

### 3. WorkBuddy (阿里/钉钉)
在工作空间「插件/MCP 管理」中添加：
- Transport: `stdio`
- Command: `python`
- Arguments: `-m mail163_mcp serve`

### 4. DeepSeek Harness
直接在运行命令或 harness 配置文件中挂载：
```bash
python -m mail163_mcp serve
```
