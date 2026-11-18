"""Strict read-only IMAP reader. Bounded, safe, zero-write capability."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email import policy
from email.header import decode_header
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
import imaplib
import re
import ssl


class MailError(RuntimeError):
    pass


_ALLOWED_COMMANDS = {
    "CAPABILITY", "NOOP", "LOGOUT", "AUTHENTICATE", "LOGIN", "EXAMINE",
    "LIST", "SEARCH", "FETCH", "ID", "UID"
}

_ALLOWED_UID_SUBCOMMANDS = {"SEARCH", "FETCH"}

_SAFE_ATOM_PATTERN = re.compile(r"^[A-Za-z0-9_.\-+/=]+$")


def _is_safe_atom(val: str) -> bool:
    return bool(_SAFE_ATOM_PATTERN.match(val))


def _clean_str(val: str) -> str:
    return "".join(c for c in val if c >= " " or c in "\t\r\n")


def _decode_hdr(header_val: str | None) -> str:
    if not header_val:
        return ""
    try:
        parts = decode_header(header_val)
        res = []
        for text, enc in parts:
            if isinstance(text, bytes):
                res.append(text.decode(enc or "utf-8", errors="replace"))
            else:
                res.append(str(text))
        return " ".join(res).strip()
    except Exception:
        return str(header_val).strip()


class ReadOnlyIMAP4_SSL(imaplib.IMAP4_SSL):
    """拦截一切非白名单 IMAP 命令，严禁执行 STORE/EXPUNGE/COPY/MOVE/APPEND 等写操作。"""

    def _command(self, name, *args):
        upper_name = name.upper()
        if upper_name not in _ALLOWED_COMMANDS:
            raise MailError(f"安全违规：只读模式严禁执行写命令 '{upper_name}'")
        if upper_name == "UID" and args:
            sub = str(args[0]).upper()
            if sub not in _ALLOWED_UID_SUBCOMMANDS:
                raise MailError(f"安全违规：只读模式严禁执行 UID 写命令 '{sub}'")
        return super()._command(name, *args)


class MailReader:
    def __init__(self, config: dict, secret_loader):
        self._config = config
        self._secret_loader = secret_loader
        self._mailbox = config["mailbox"]
        self._host = config["imap_host"]
        self._port = config["imap_port"]
        self._allowed_folders = set(config["allowed_folders"])
        self._max_bytes = config["max_message_bytes"]
        self._max_body_chars = config["max_body_chars"]
        self._window_months = config["date_window_months"]

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _date_window(self) -> tuple[datetime, datetime]:
        upper = self._now()
        # 约等于 window_months * 30.5 天
        lower = upper - timedelta(days=int(self._window_months * 30.5))
        return lower, upper

    @contextmanager
    def _connection(self):
        ctx = ssl.create_default_context()
        try:
            conn = ReadOnlyIMAP4_SSL(self._host, self._port, ssl_context=ctx, timeout=30)
            conn.debug = 0
            secret = self._secret_loader()
            if not secret or len(secret) > 1024:
                raise MailError("无效的授权码")
            status, _ = conn.login(self._mailbox, secret)
            if status != "OK":
                raise MailError("企业邮箱认证失败，请检查邮箱地址或授权码")
            yield conn
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def _select_readonly(self, conn, folder: str):
        if folder not in self._allowed_folders:
            raise MailError(f"拒绝访问未授权文件夹: '{folder}'")
        # 严格使用 EXAMINE 只读模式（imaplib 中通过 select(folder, readonly=True) 发送 EXAMINE 命令）
        status, data = conn.select(folder, readonly=True)
        if status != "OK" or conn.is_readonly is not True:
            raise MailError(f"无法以只读 (EXAMINE) 模式打开文件夹: {folder}")

    def list_folders(self) -> list[dict]:
        """只列出白名单中允许的安全只读文件夹。"""
        with self._connection() as conn:
            status, data = conn.list()
            if status != "OK" or not data:
                return [{"name": f, "flags": []} for f in self._allowed_folders]

            results = []
            for item in data:
                if not isinstance(item, bytes):
                    continue
                line = item.decode("latin1", errors="replace")
                # 简单解析文件夹名称
                m = re.search(r'\((?P<flags>.*?)\)\s+"(?P<delim>.*?)"\s+(?P<name>.*)$', line)
                if m:
                    raw_name = m.group("name").strip().strip('"')
                    # 解码 utf-7 imap 常用中文
                    try:
                        import binascii
                        # 兼容处理常用网易默认文件夹
                        if raw_name in self._allowed_folders:
                            results.append({"name": raw_name, "flags": m.group("flags").split()})
                    except Exception:
                        pass
            if not results:
                # 兜底返回白名单文件夹
                for f in self._allowed_folders:
                    results.append({"name": f, "flags": []})
            return results

    def search_messages(self, folder: str, since: str | None = None, before: str | None = None,
                        query: str | None = None, limit: int = 50, cursor: int | None = None) -> dict:
        """轻量搜索：仅返回元数据分页，默认不带邮件正文，强力控制 Token 消耗。"""
        limit = min(max(1, limit), 200)
        lower_bound, upper_bound = self._date_window()

        with self._connection() as conn:
            self._select_readonly(conn, folder)

            # 构造安全 IMAP 查询
            criteria = ["CHARSET", "UTF-8"]
            # 默认带上时间窗口约束
            criteria.extend(["SINCE", lower_bound.strftime("%d-%b-%Y")])
            if query and _is_safe_atom(query):
                criteria.extend(["TEXT", f'"{query}"'])

            status, data = conn.uid("SEARCH", *criteria)
            if status != "OK" or not data or not data[0]:
                return {"folder": folder, "total_found": 0, "messages": [], "has_more": False}

            all_uids = sorted({int(u) for u in data[0].split()}, reverse=True)
            if cursor:
                all_uids = [u for u in all_uids if u < cursor]

            page_uids = all_uids[:limit]
            has_more = len(all_uids) > limit
            next_cursor = page_uids[-1] if has_more else None

            if not page_uids:
                return {"folder": folder, "total_found": len(all_uids), "messages": [], "has_more": False}

            # 批量获取轻量头部信息 (UID, RFC822.SIZE, INTERNALDATE, BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID)])
            uid_set = ",".join(str(u) for u in page_uids)
            fetch_fields = "(UID RFC822.SIZE INTERNALDATE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID IN-REPLY-TO REFERENCES)])"
            status, fetch_data = conn.uid("FETCH", uid_set, fetch_fields)
            if status != "OK":
                raise MailError("获取邮件摘要失败")

            messages = []
            for item in fetch_data:
                if isinstance(item, tuple) and len(item) == 2:
                    header_line, raw_header = item
                    hdr_str = header_line.decode("ascii", errors="replace")
                    uid_match = re.search(r"UID\s+(\d+)", hdr_str)
                    size_match = re.search(r"RFC822\.SIZE\s+(\d+)", hdr_str)
                    date_match = re.search(r'INTERNALDATE\s+"([^"]+)"', hdr_str)

                    uid = int(uid_match.group(1)) if uid_match else 0
                    size = int(size_match.group(1)) if size_match else 0
                    internal_date = date_match.group(1) if date_match else ""

                    msg_obj = BytesParser(policy=policy.default).parsebytes(raw_header)
                    messages.append({
                        "uid": uid,
                        "size": size,
                        "date": internal_date or str(msg_obj.get("Date", "")),
                        "subject": _decode_hdr(msg_obj.get("Subject", "")),
                        "from": _clean_str(str(msg_obj.get("From", ""))),
                        "to": _clean_str(str(msg_obj.get("To", ""))),
                        "message_id": _clean_str(str(msg_obj.get("Message-ID", ""))),
                    })

            # 按 UID 降序排序
            messages.sort(key=lambda m: m["uid"], reverse=True)
            return {
                "folder": folder,
                "total_matched": len(all_uids),
                "messages": messages,
                "has_more": has_more,
                "next_cursor": next_cursor,
            }

    def read_message(self, folder: str, uid: int, max_chars: int | None = None) -> dict:
        """读取单封邮件详情（含正文与截断保护，附件仅列出元数据）。"""
        limit_chars = max_chars or self._max_body_chars
        with self._connection() as conn:
            self._select_readonly(conn, folder)

            fields = f"(UID INTERNALDATE RFC822.SIZE BODY.PEEK[]<0.{self._max_bytes + 1}>)"
            status, data = conn.uid("FETCH", str(uid), fields)
            if status != "OK" or not data or not data[0]:
                raise MailError(f"未找到邮件 UID: {uid}")

            raw = None
            for item in data:
                if isinstance(item, tuple) and len(item) == 2:
                    raw = item[1]
                    break

            if not raw or not isinstance(raw, bytes):
                raise MailError("读取邮件正文失败")

            msg = BytesParser(policy=policy.default).parsebytes(raw)

            # 提取纯文本正文与附件元数据
            body_text_parts = []
            attachments = []
            part_index = 0

            for part in msg.walk():
                if part.is_multipart():
                    continue
                fn = part.get_filename()
                cd = part.get("Content-Disposition", "")
                ct = part.get_content_type()

                if fn or "attachment" in cd:
                    filename = _decode_hdr(fn or f"attachment_{part_index}")
                    payload = part.get_payload(decode=True) or b""
                    attachments.append({
                        "part": part_index,
                        "filename": filename,
                        "content_type": ct,
                        "size": len(payload),
                    })
                elif ct == "text/plain":
                    body_text_parts.append(part.get_content(errors="replace"))
                elif ct == "text/html" and not body_text_parts:
                    # 如果只有 HTML，进行简单文本剥离
                    html = part.get_content(errors="replace")
                    text = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
                    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
                    text = re.sub(r"<.*?>", "", text)
                    body_text_parts.append(text.strip())

                part_index += 1

            full_body = "\n\n".join(p.strip() for p in body_text_parts if p.strip())
            is_truncated = len(full_body) > limit_chars
            body_content = full_body[:limit_chars] if is_truncated else full_body

            return {
                "folder": folder,
                "uid": uid,
                "subject": _decode_hdr(msg.get("Subject", "")),
                "from": _clean_str(str(msg.get("From", ""))),
                "to": _clean_str(str(msg.get("To", ""))),
                "cc": _clean_str(str(msg.get("Cc", ""))),
                "date": _clean_str(str(msg.get("Date", ""))),
                "message_id": _clean_str(str(msg.get("Message-ID", ""))),
                "in_reply_to": _clean_str(str(msg.get("In-Reply-To", ""))),
                "references": _clean_str(str(msg.get("References", ""))),
                "body_text": body_content,
                "body_truncated": is_truncated,
                "total_body_chars": len(full_body),
                "attachments": attachments,
            }

    def fetch_attachment_bytes(self, folder: str, uid: int, part_id: int) -> tuple[str, str, bytes]:
        """读取附件原始字节。"""
        with self._connection() as conn:
            self._select_readonly(conn, folder)
            status, data = conn.uid("FETCH", str(uid), f"(BODY.PEEK[]<0.{self._max_bytes + 1}>)")
            if status != "OK" or not data:
                raise MailError("读取邮件失败")
            raw = None
            for item in data:
                if isinstance(item, tuple) and len(item) == 2:
                    raw = item[1]
                    break
            if not raw:
                raise MailError("邮件正文为空")

            msg = BytesParser(policy=policy.default).parsebytes(raw)
            current_index = 0
            for part in msg.walk():
                if part.is_multipart():
                    continue
                if current_index == part_id:
                    fn = _decode_hdr(part.get_filename() or f"attachment_{part_id}")
                    ct = part.get_content_type()
                    payload = part.get_payload(decode=True) or b""
                    return fn, ct, payload
                current_index += 1

            raise MailError(f"未找到指定的附件部件编号 part={part_id}")

    def get_thread_by_message_id(self, folder: str, message_id: str, max_messages: int = 30) -> list[dict]:
        """按 Message-ID / References 精确追溯上下文对话链（时间升序排列）。"""
        target_id = message_id.strip("<> \t\r\n")
        if not target_id:
            raise MailError("message_id 不能为空")

        # 搜索包含此 message_id 的邮件
        with self._connection() as conn:
            self._select_readonly(conn, folder)
            status, data = conn.uid("SEARCH", "CHARSET", "UTF-8", "HEADER", "MESSAGE-ID", f'"{target_id}"')
            matched_uids = set()
            if status == "OK" and data and data[0]:
                matched_uids.update(int(u) for u in data[0].split())

            # 搜索以此为引用回复的邮件
            status, data = conn.uid("SEARCH", "CHARSET", "UTF-8", "HEADER", "REFERENCES", f'"{target_id}"')
            if status == "OK" and data and data[0]:
                matched_uids.update(int(u) for u in data[0].split())

        thread_msgs = []
        for u in sorted(matched_uids)[:max_messages]:
            try:
                # 线程中每封邮件默认给予 4000 字符轻量截断
                thread_msgs.append(self.read_message(folder, u, max_chars=4000))
            except Exception:
                continue

        # 按 UID 升序作为时间顺序
        thread_msgs.sort(key=lambda m: m["uid"])
        return thread_msgs
