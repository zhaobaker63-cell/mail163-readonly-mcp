# 📧 Mail Read-Only MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)
[![MCP Spec](https://img.shields.io/badge/MCP-2024--11--05-orange.svg)](https://modelcontextprotocol.io/)
[![Zero External Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](pyproject.toml)

> **专为 AI 智能体设计的企业邮箱只读 MCP 服务器。**  
> 纯标准库实现，零第三方依赖；严格只读（EXAMINE + BODY.PEEK）；密码永不落盘（OS 级系统凭据保护）；精简元数据返回，强力控制 LLM 上下文消耗。  
> 完美兼容 **Codex、Accio、DeepSeek Harness、WorkBuddy、Cursor、Claude Desktop** 等一切主流 MCP 客户端。

---

## 🌟 核心特性

- **🛡️ 纯粹只读，绝对安全**：
  - 强制使用 IMAP `EXAMINE` 只读模式（服务器不返回 `READ-ONLY` 立即拒绝）。
  - 正文严格通过 `BODY.PEEK` 抓取，绝不标记邮件已读，绝不改变邮箱原始状态。
  - 命令白名单防护：底层拦截并拒绝一切 `STORE/EXPUNGE/COPY/MOVE/APPEND` 等写操作。
  - 不提供 SMTP，不具备任何邮件发送、回复、转发或草稿生成能力。
- **🧠 极低 Token 占用（防上下文爆炸）**：
  - 搜索（`mail_search`）**默认只返回元数据**（UID、主题、发件人、收件人、时间、大小），不带正文。
  - 读取正文（`mail_get_message`）具备自动截断保护（默认 8000 字符可配置）。
  - 附件（`mail_get_attachment`）**默认落盘本地临时文件返回路径**，拒绝将数 MB 的 base64 强行塞入对话上下文。
  - 线程追踪（`mail_get_thread`）基于 Message-ID/References 精准聚合。
- **⚡ 零 IT 化门槛（双击即可配置）**：
  - 提供 Windows 原生配置向导（`一键配置.bat`），交互式输入并自动完成连通性自检。
  - 密码/授权码直接加密保存在操作系统自带的凭据管理器（Windows Credential Manager / 系统钥匙串），配置文件决不保存明文密码。
  - 自动输出各大 Agent 平台的一键接入配置片段。
- **📦 零外部依赖**：
  - 纯 Python 3.10+ 标准库（`imaplib`, `email`, `ctypes`, `json` 等），无需 `pip install` 繁杂依赖。

---

## 🛠️ MCP 工具清单（5 个只读工具）

| 工具名称 | 作用 | 适用场景 |
|---|---|---|
| `mail_list_folders` | 列出已授权的只读文件夹（如 INBOX、已发送） | 初始探索邮箱目录结构 |
| `mail_search` | 搜索邮件元数据（仅返回摘要，不含正文） | 快速检索时间段或关键词的邮件清单 |
| `mail_get_message` | 提取单封邮件正文与附件元数据（截断保护） | 按需深度查看某封关键邮件的正文细节 |
| `mail_get_attachment` | 提取并下载指定附件到本地临时目录 | 需要下游 Agent 进一步分析 PDF/Excel 等附件 |
| `mail_get_thread` | 追踪特定 Message-ID 的完整往来对话链 | 还原询盘、报价、还价的往返上下文 |

> 详细参数结构与返回格式请查阅：[docs/TOOLS.md](docs/TOOLS.md)。

---

## 🚀 30 秒快速上手

### 步骤一：一键配置

1. 下载或克隆本项目到本地。
2. 双击运行 `launcher/一键配置.bat`（或在终端运行 `python -m mail163_mcp setup`）。
3. 按照提示输入：
   - 企业邮箱地址（如 `user@yourcompany.com`）
   - IMAP 主机地址（默认回车即可，通常为 `imap.qiye.163.com`）
   - 客户端授权码（在网易企业邮箱网页端「设置 → 客户端设置」中生成）
4. 程序将自动进行只读连接验证，并在成功后加密保存凭据。

### 步骤二：接入您的 AI 智能体平台

根据您使用的平台，复制下方对应的配置片段即可：

#### 1. Codex (`~/.codex/config.toml`)
```toml
[mcp_servers.mail163]
command = "python"
args = ["-m", "mail163_mcp", "serve"]
```

#### 2. Accio / Claude Desktop / Cursor (`mcp.json` / 设置)
```json
{
  "mcpServers": {
    "mail163": {
      "command": "python",
      "args": ["-m", "mail163_mcp", "serve"]
    }
  }
}
```

#### 3. WorkBuddy (阿里/钉钉智能体工作台)
- **命令 (Command)**: `python`
- **参数 (Arguments)**: `-m mail163_mcp serve`

#### 4. DeepSeek Harness (命令行或测试环境)
```bash
python -m mail163_mcp serve
```

---

## 🔒 安全性与隐私设计

1. **零硬编码**：本项目不包含任何公司专有域名、文档绝对路径或内部业务逻辑。任何企业或团队均可开箱即用。
2. **凭据安全**：邮箱授权码由操作系统底层（Win32 Advapi32 CredWriteW）以通用凭据形式加密管理，项目源码、配置文件、环境变量及日志中均无明文泄露风险。
3. **隔离理念**：本 MCP 仅作为通用**只读数据源管道**。客户画像、邮件归并、时间线还原等业务分析完全解耦，交由各企业下游专用 Agent 独立处理。

---

## 📄 开源许可证

本项目采用 [MIT 许可证](LICENSE)。
