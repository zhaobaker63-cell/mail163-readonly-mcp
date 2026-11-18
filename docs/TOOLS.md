# 🛠️ MCP 工具规范与协议文档

本项目严格遵循 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 规范，通过标准 `stdio` 传输（输入输出均为标准 JSON-RPC 2.0），设计原则为**“只读数据源，极低Token消耗，正文按需提取”**。

---

## 工具清单一览

| 工具名称 | 作用 | 默认返回体积 | Token控制策略 |
|---|---|---|---|
| `mail_list_folders` | 列出已授权的只读文件夹 | 极小 (<100 tokens) | 只返回白名单文件夹与标记 |
| `mail_search` | 按条件搜索邮件 | 小 (~200 tokens/10封) | **仅返回元数据列表，不带正文** |
| `mail_get_message` | 获取单封邮件完整详情 | 可控 (可截断) | 纯文本格式，正文超长截断保护 |
| `mail_get_attachment` | 提取下载单部件附件 | 极小 (<50 tokens) | **默认落盘临时路径，不塞 base64** |
| `mail_get_thread` | 按 Message-ID 追踪整条对话链 | 中等 | 精确引用串联，按时间升序 |

---

## 1. `mail_list_folders`

获取当前邮箱可读取的文件夹列表。

### 输入参数
无。

### 返回示例
```json
{
  "folders": [
    {
      "name": "INBOX",
      "flags": []
    },
    {
      "name": "已发送",
      "flags": ["\\sent"]
    }
  ]
}
```

---

## 2. `mail_search`

在指定文件夹下根据条件检索邮件。**强烈建议下游 Agent 先用此工具检索元数据，再按需挑选关键邮件调用 `mail_get_message`，避免上下文溢出。**

### 输入参数
| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `folder` | string | 是 | - | 文件夹名称，如 `"INBOX"` 或 `"已发送"` |
| `query` | string | 否 | `null` | 搜索关键词（支持主题/正文模糊匹配） |
| `limit` | integer | 否 | `30` | 返回条数限制，最大 200 |
| `cursor` | integer | 否 | `null` | 分页游标（上一页返回的 `next_cursor`） |

### 返回示例
```json
{
  "folder": "INBOX",
  "total_matched": 483,
  "has_more": true,
  "next_cursor": 1647970050,
  "messages": [
    {
      "uid": 1647970093,
      "size": 1500225,
      "date": "Tue, 17 Nov 2026 18:20:17 +0800",
      "subject": "Re: Inquiry for Electric Toothbrush Heads",
      "from": "John Doe <john@client-company.com>",
      "to": "user@example-company.com",
      "message_id": "<d8a2...3b1@client-company.com>"
    }
  ]
}
```

---

## 3. `mail_get_message`

获取某一封邮件的完整正文与附件信息。

### 输入参数
| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `folder` | string | 是 | - | 文件夹名称 |
| `uid` | integer | 是 | - | 邮件的 IMAP UID |
| `max_chars` | integer | 否 | `8000` | 正文最大返回字符数，超过部分自动截断 |

### 返回示例
```json
{
  "folder": "INBOX",
  "uid": 1647970093,
  "subject": "Re: Inquiry for Electric Toothbrush Heads",
  "from": "John Doe <john@client-company.com>",
  "to": "user@example-company.com",
  "cc": "",
  "date": "Tue, 17 Nov 2026 18:20:17 +0800",
  "message_id": "<d8a2...3b1@client-company.com>",
  "in_reply_to": "<f1b9...0a2@example-company.com>",
  "references": "<f1b9...0a2@example-company.com>",
  "body_text": "Hi Sales Team,\n\nThanks for your quotation. Could you please send samples for the soft bristle model?\n\nBest regards,\nJohn",
  "body_truncated": false,
  "total_body_chars": 128,
  "attachments": [
    {
      "part": 1,
      "filename": "spec_sheet.pdf",
      "content_type": "application/pdf",
      "size": 245100
    }
  ]
}
```

---

## 4. `mail_get_attachment`

提取并下载附件。

### 输入参数
| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `folder` | string | 是 | - | 文件夹名称 |
| `uid` | integer | 是 | - | 邮件 UID |
| `part` | integer | 是 | - | 附件部件编号（对应 `mail_get_message` 中的 `part`） |
| `as_base64` | boolean | 否 | `false` | 若为 `false` 则落盘本地返回临时路径；若为 `true` 则返回 base64 字符串 |

### 返回示例（默认 `as_base64: false`，推荐，防上下文过载）
```json
{
  "filename": "spec_sheet.pdf",
  "content_type": "application/pdf",
  "size_bytes": 245100,
  "temp_path": "<system_temp_dir>/mail163_mcp_attachments/1647970093_1_spec_sheet.pdf"
}
```

---

## 5. `mail_get_thread`

追踪该邮件所在整条业务线程对话链。

### 输入参数
| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `folder` | string | 是 | - | 文件夹名称 |
| `message_id` | string | 是 | - | 目标邮件的 Message-ID |
| `max_messages` | integer | 否 | `20` | 最大聚合邮件数量 |

### 返回示例
```json
{
  "message_id": "<d8a2...3b1@client-company.com>",
  "thread_length": 3,
  "messages": [
    {
      "uid": 1647970010,
      "subject": "Inquiry for Electric Toothbrush Heads",
      "from": "John Doe <john@client-company.com>",
      "date": "Mon, 16 Nov 2026 10:00:00 +0800",
      "body_text": "..."
    },
    {
      "uid": 1647970045,
      "subject": "Re: Inquiry for Electric Toothbrush Heads",
      "from": "user@example-company.com",
      "date": "Mon, 16 Nov 2026 15:30:00 +0800",
      "body_text": "..."
    },
    {
      "uid": 1647970093,
      "subject": "Re: Inquiry for Electric Toothbrush Heads",
      "from": "John Doe <john@client-company.com>",
      "date": "Tue, 17 Nov 2026 18:20:17 +0800",
      "body_text": "..."
    }
  ]
}
```
