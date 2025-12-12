"""License 校验与功能授权。

设计目标：
1. 不暴露私钥，仅内置公钥，用于离线校验授权文件。
2. 授权文件为 JSON，包含 user/features/expires_at/signature。
3. signature 使用 Ed25519 非对称签名，对除 signature 外的字段做规范化 JSON 后签名。
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


logger = logging.getLogger(__name__)

# 功能名常量（license.features 中使用）
FEATURE_PROCESS = "process"
FEATURE_ANALYZE = "analyze"
FEATURE_CONFIG = "config"
FEATURE_HISTORY = "history"
FEATURE_FEISHU = "feishu"
FEATURE_ALL = "*"


# 默认公钥（Ed25519），请在你自己发放 license 前替换为真实公钥。
# 也可以通过环境变量 DRAMA_PROCESSOR_PUBLIC_KEY 传入 PEM 公钥覆盖。
DEFAULT_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
<REPLACE_WITH_YOUR_ED25519_PUBLIC_KEY_PEM>
-----END PUBLIC KEY-----"""


class LicenseError(Exception):
    """License 相关错误。"""


@dataclass(frozen=True)
class LicenseInfo:
    """校验通过后的授权信息。"""

    user: str
    features: Set[str]
    expires_at: Optional[datetime]
    raw: Dict[str, Any]

    def allows(self, feature: str) -> bool:
        """判断是否允许某功能。"""
        return FEATURE_ALL in self.features or feature in self.features


def _find_license_path_in_argv(argv: List[str]) -> Optional[str]:
    """从命令行参数中查找 --license 指定的路径。"""
    for i, arg in enumerate(argv):
        if arg == "--license" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--license="):
            return arg.split("=", 1)[1]
    return None


def _canonical_payload_bytes(data: Dict[str, Any]) -> bytes:
    """将 license 中除 signature 外的字段做稳定序列化，作为签名原文。"""
    payload = {k: v for k, v in data.items() if k != "signature"}
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return text.encode("utf-8")


def _b64url_decode(value: str) -> bytes:
    """URL-safe base64 解码。"""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _parse_datetime(value: str) -> Optional[datetime]:
    """解析 expires_at（支持 ISO8601 或 YYYY-MM-DD）。"""
    try:
        v = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.strptime(value.strip(), "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_license_file(path: str) -> Dict[str, Any]:
    """读取 license JSON 文件。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise LicenseError("license 文件内容必须是 JSON 对象")
    return data


def verify_license_dict(
    data: Dict[str, Any], public_key_pem: Optional[str] = None
) -> LicenseInfo:
    """校验 license（Ed25519 签名 + 过期校验）。"""
    signature_b64 = data.get("signature")
    if not signature_b64 or not isinstance(signature_b64, str):
        raise LicenseError("license 缺少 signature 字段")

    payload_bytes = _canonical_payload_bytes(data)
    signature = _b64url_decode(signature_b64)

    pem = (
        public_key_pem
        or os.environ.get("DRAMA_PROCESSOR_PUBLIC_KEY")
        or DEFAULT_PUBLIC_KEY_PEM
    )
    if "<REPLACE_WITH_YOUR_ED25519_PUBLIC_KEY_PEM>" in pem:
        raise LicenseError("未配置公钥，请替换 DEFAULT_PUBLIC_KEY_PEM 或设置环境变量")

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError as e:
        raise LicenseError(
            "缺少 cryptography 依赖，无法校验 license（请安装 cryptography）"
        ) from e

    public_key = load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(public_key, Ed25519PublicKey):
        raise LicenseError("当前仅支持 Ed25519 公钥校验")

    try:
        public_key.verify(signature, payload_bytes)
    except InvalidSignature as e:
        raise LicenseError("license 签名校验失败") from e

    expires_at = None
    expires_at_raw = data.get("expires_at")
    if isinstance(expires_at_raw, str) and expires_at_raw.strip():
        expires_at = _parse_datetime(expires_at_raw)
        if expires_at is None:
            raise LicenseError("expires_at 格式不正确")
        if datetime.now(timezone.utc) > expires_at:
            raise LicenseError("license 已过期")

    features_raw = data.get("features") or []
    if not isinstance(features_raw, list):
        raise LicenseError("features 必须是字符串数组")
    features = {str(x).strip() for x in features_raw if str(x).strip()}

    user = str(data.get("user") or "").strip()
    return LicenseInfo(user=user, features=features, expires_at=expires_at, raw=data)


def load_and_verify_license(
    path: str, public_key_pem: Optional[str] = None
) -> LicenseInfo:
    """从文件读取并校验 license。"""
    data = load_license_file(path)
    return verify_license_dict(data, public_key_pem=public_key_pem)


def get_license_info_from_args_and_env(
    argv: Optional[List[str]] = None,
    *,
    logger_: Optional[logging.Logger] = None,
) -> Optional[LicenseInfo]:
    """从 --license 参数或环境变量读取并校验 license。

    校验失败时返回 None（并可选记录 warning）。
    """
    argv = argv or []
    path = _find_license_path_in_argv(argv) or os.environ.get("DRAMA_PROCESSOR_LICENSE")
    if not path:
        return None
    try:
        return load_and_verify_license(path)
    except LicenseError as e:
        (logger_ or logger).warning(f"License 无效，将以未授权模式运行：{e}")
        return None


def get_allowed_features_from_args_and_env(argv: Optional[List[str]] = None) -> Set[str]:
    """快速获取授权 feature 集合（用于 import 时决定是否注册命令）。"""
    info = get_license_info_from_args_and_env(argv)
    return info.features if info else set()

