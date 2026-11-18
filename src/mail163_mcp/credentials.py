"""System credential manager bindings (Zero-dependency, uses Win32 Advapi32 on Windows)."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes


class SecurityError(RuntimeError):
    pass


# Windows Credential Manager constants
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


if os.name == "nt":
    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", wintypes.LPVOID),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    PCREDENTIALW = ctypes.POINTER(CREDENTIALW)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    _CredWriteW = advapi32.CredWriteW
    _CredWriteW.argtypes = [PCREDENTIALW, wintypes.DWORD]
    _CredWriteW.restype = wintypes.BOOL

    _CredReadW = advapi32.CredReadW
    _CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(PCREDENTIALW)]
    _CredReadW.restype = wintypes.BOOL

    _CredFree = advapi32.CredFree
    _CredFree.argtypes = [wintypes.LPVOID]
    _CredFree.restype = None

    _CredDeleteW = advapi32.CredDeleteW
    _CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    _CredDeleteW.restype = wintypes.BOOL


def write_credential(target_name: str, secret: str, user_name: str = "") -> None:
    """写入当前用户的 Windows 凭据管理器（通用凭据）。"""
    if os.name != "nt":
        # 非 Windows 环境回退到环境检查
        os.environ[f"MAIL163_SECRET_{target_name}"] = secret
        return

    if not target_name or not isinstance(secret, str) or not secret:
        raise SecurityError("凭证目标名和授权码不能为空")

    raw_bytes = secret.encode("utf-16le")
    blob_len = len(raw_bytes)
    byte_array = (ctypes.c_byte * blob_len)(*raw_bytes)

    cred = CREDENTIALW()
    cred.Flags = 0
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = target_name
    cred.Comment = "163 Mail Read-Only MCP Authorization Code"
    cred.CredentialBlobSize = blob_len
    cred.CredentialBlob = ctypes.cast(byte_array, ctypes.POINTER(ctypes.c_byte))
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = user_name or os.environ.get("USERNAME", "")

    if not _CredWriteW(ctypes.byref(cred), 0):
        code = ctypes.get_last_error()
        raise SecurityError(f"写入凭证管理器失败: win32 error {code}")


def read_credential(target_name: str) -> str:
    """从系统钥匙串/凭证管理器读取当前用户的邮箱授权码。"""
    if os.name != "nt":
        val = os.environ.get(f"MAIL163_SECRET_{target_name}") or os.environ.get("MAIL163_AUTH_CODE")
        if val:
            return val
        raise SecurityError(f"非 Windows 环境未设置环境变量 MAIL163_SECRET_{target_name} 或 MAIL163_AUTH_CODE")

    pcred = PCREDENTIALW()
    if not _CredReadW(target_name, CRED_TYPE_GENERIC, 0, ctypes.byref(pcred)):
        code = ctypes.get_last_error()
        if code == ERROR_NOT_FOUND:
            raise SecurityError(f"未找到凭证: '{target_name}'，请先运行配置向导录入授权码")
        raise SecurityError(f"读取凭证管理器失败: win32 error {code}")

    try:
        cred = pcred.contents
        if not cred.CredentialBlob or cred.CredentialBlobSize == 0:
            raise SecurityError("凭证内容为空")
        buf = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        return buf.decode("utf-16le")
    finally:
        _CredFree(pcred)


def delete_credential(target_name: str) -> None:
    if os.name != "nt":
        os.environ.pop(f"MAIL163_SECRET_{target_name}", None)
        return
    _CredDeleteW(target_name, CRED_TYPE_GENERIC, 0)
