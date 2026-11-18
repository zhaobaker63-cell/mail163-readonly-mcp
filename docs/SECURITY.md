# 🛡️ 安全模型与边界说明

本项目设计以**“只读、隔离、防泄漏”**为最高准则。

---

## 1. 严格只读模型

- **只读协议级约束**：
  IMAP 客户端强制调用 `EXAMINE` 而非 `SELECT`。如果网易服务器未返回 `READ-ONLY` 状态，连接将立即异常终止，绝不降级到可写模式。
- **底层命令拦截**：
  在 `imaplib` 的协议底层，通过重载 `_command` 实施严格的命令白名单（仅允许 `CAPABILITY`, `NOOP`, `LOGOUT`, `AUTHENTICATE`, `LOGIN`, `EXAMINE`, `LIST`, `SEARCH`, `FETCH`, `ID`）。
  任何 `STORE`（修改邮件标签/已读标记）、`EXPUNGE`（彻底删除）、`COPY`/`MOVE`（移动邮件）、`APPEND`（保存草稿）等写操作将在发送到网络之前直接被本地拦截并抛出安全异常。
- **无发信能力**：
  代码中完全没有引入任何 SMTP 模块或发信工具，物理上不具备发送、回复或转发邮件的能力。

---

## 2. 凭据存储安全

- **禁止写入文件**：
  用户的邮箱授权码绝不会被写入任何本地 JSON、TOML、文本或日志文件中。
- **系统级加密凭据管理器**：
  Windows 下采用系统底层的 Windows Credential Manager（通过 `advapi32.dll` 的 `CredWriteW` / `CredReadW`）持久化存储。
- **安全边界客观说明**：
  Windows 凭据管理器是针对“防止明文存储与防跨账户窥探”的保护措施，不代表对当前登录用户自身所有本地进程实现了绝对的沙箱隔离。请妥善保管个人计算机的登录环境。

---

## 3. 防 LLM 上下文爆炸机制

- `mail_search` 绝不携带邮件正文返回，仅返回必要元数据，防止单次搜索打爆数百 K 的上下文。
- `mail_get_message` 设置正文长度硬上限（默认 8000 字符），超长正文自动截断并标记 `body_truncated: true`。
- `mail_get_attachment` 默认将附件以文件流写入系统本地临时目录并返回 `temp_path`，只有显式指定 `as_base64: true` 时才输出 base64，从根本上防止大附件把 AI 上下文占满。
