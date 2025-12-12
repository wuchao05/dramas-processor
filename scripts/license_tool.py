#!/usr/bin/env python3
"""
License 工具：生成 Ed25519 密钥对、签发 license、校验 license。

依赖：
  - cryptography（项目已作为依赖）

使用示例：
  1) 生成密钥对（默认输出到 license_keys/）：
     python scripts/license_tool.py gen-keys

  2) 签发 license：
     python scripts/license_tool.py sign \
       --private-key license_keys/ed25519_private.pem \
       --user friend-a \
       --features process,analyze,config,history,feishu \
       --expires-at 2026-01-01T00:00:00Z \
       --out license.json

  3) 校验 license（可选）：
     python scripts/license_tool.py verify \
       --public-key license_keys/ed25519_public.pem \
       --license license.json
"""

import argparse
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def canonical_payload_bytes(data: Dict[str, Any]) -> bytes:
    """将 license 中除 signature 外字段做稳定序列化，作为签名原文。"""
    payload = {k: v for k, v in data.items() if k != "signature"}
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return text.encode("utf-8")


def b64url_encode(raw: bytes) -> str:
    """URL-safe base64 编码（去掉 = padding）。"""
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def b64url_decode(value: str) -> bytes:
    """URL-safe base64 解码。"""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def parse_expires_at(value: str) -> str:
    """简单校验 expires_at 格式，并标准化输出。"""
    v = value.strip()
    if not v:
        raise ValueError("expires_at 不能为空")
    # ISO8601 或 YYYY-MM-DD
    try:
        vv = v.replace("Z", "+00:00")
        dt = datetime.fromisoformat(vv)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    try:
        dt = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception as e:
        raise ValueError("expires_at 格式不正确，示例：2026-01-01 或 2026-01-01T00:00:00Z") from e


def cmd_gen_keys(args: argparse.Namespace) -> None:
    """生成 Ed25519 密钥对。"""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            BestAvailableEncryption,
            Encoding,
            NoEncryption,
            PrivateFormat,
            PublicFormat,
        )
    except ImportError as e:
        raise SystemExit("缺少 cryptography 依赖，请先安装：pip install cryptography") from e

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    if args.password:
        encryption = BestAvailableEncryption(args.password.encode("utf-8"))
    else:
        encryption = NoEncryption()

    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    public_pem = public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = out_dir / "ed25519_private.pem"
    public_path = out_dir / "ed25519_public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    print(f"[OK] 已生成私钥：{private_path}")
    print(f"[OK] 已生成公钥：{public_path}")
    print("请将公钥 PEM 内容复制到 src/drama_processor/utils/license.py 的 DEFAULT_PUBLIC_KEY_PEM 中后重新打 Pro 包。")


def cmd_sign(args: argparse.Namespace) -> None:
    """签发 license.json。"""
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
    except ImportError as e:
        raise SystemExit("缺少 cryptography 依赖，请先安装：pip install cryptography") from e

    private_key_pem = Path(args.private_key).expanduser().read_bytes()
    private_key = load_pem_private_key(
        private_key_pem,
        password=(args.password.encode("utf-8") if args.password else None),
    )

    user = args.user.strip()
    if not user:
        raise SystemExit("--user 不能为空")

    features = [x.strip() for x in args.features.split(",") if x.strip()]
    if not features:
        raise SystemExit("--features 不能为空")

    license_data: Dict[str, Any] = {
        "user": user,
        "features": features,
    }

    if args.expires_at:
        license_data["expires_at"] = parse_expires_at(args.expires_at)

    payload_bytes = canonical_payload_bytes(license_data)
    signature = private_key.sign(payload_bytes)
    license_data["signature"] = b64url_encode(signature)

    out_path = Path(args.out).expanduser().resolve()
    out_path.write_text(
        json.dumps(license_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] License 已生成：{out_path}")


def cmd_verify(args: argparse.Namespace) -> None:
    """校验 license.json（可选）。"""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError as e:
        raise SystemExit("缺少 cryptography 依赖，请先安装：pip install cryptography") from e

    public_key_pem = Path(args.public_key).expanduser().read_bytes()
    public_key = load_pem_public_key(public_key_pem)
    if not isinstance(public_key, Ed25519PublicKey):
        raise SystemExit("公钥类型不正确（仅支持 Ed25519）")

    lic_path = Path(args.license).expanduser()
    data = json.loads(lic_path.read_text(encoding="utf-8"))

    sig_b64 = data.get("signature")
    if not sig_b64:
        raise SystemExit("license 缺少 signature")

    payload_bytes = canonical_payload_bytes(data)
    signature = b64url_decode(sig_b64)

    try:
        public_key.verify(signature, payload_bytes)
    except InvalidSignature:
        raise SystemExit("[FAIL] 签名校验失败")

    expires_at = data.get("expires_at")
    if expires_at:
        try:
            vv = str(expires_at).replace("Z", "+00:00")
            dt = datetime.fromisoformat(vv)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > dt.astimezone(timezone.utc):
                raise SystemExit("[FAIL] license 已过期")
        except SystemExit:
            raise
        except Exception:
            print("[WARN] expires_at 无法解析，已跳过过期校验")

    print("[OK] license 校验通过")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drama Processor License 工具（Ed25519）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_keys = sub.add_parser("gen-keys", help="生成 Ed25519 密钥对")
    p_keys.add_argument("--out-dir", default="license_keys", help="输出目录（默认 license_keys/）")
    p_keys.add_argument("--password", default=None, help="可选：为私钥设置密码")
    p_keys.set_defaults(func=cmd_gen_keys)

    p_sign = sub.add_parser("sign", help="签发 license.json")
    p_sign.add_argument("--private-key", required=True, help="私钥 PEM 路径")
    p_sign.add_argument("--password", default=None, help="可选：私钥密码")
    p_sign.add_argument("--user", required=True, help="授权用户标识")
    p_sign.add_argument(
        "--features",
        required=True,
        help="功能列表，逗号分隔，如 process,analyze,config,history,feishu 或 *",
    )
    p_sign.add_argument("--expires-at", default=None, help="可选：过期时间（ISO8601 或 YYYY-MM-DD）")
    p_sign.add_argument("--out", default="license.json", help="输出 license 路径（默认 license.json）")
    p_sign.set_defaults(func=cmd_sign)

    p_verify = sub.add_parser("verify", help="校验 license.json")
    p_verify.add_argument("--public-key", required=True, help="公钥 PEM 路径")
    p_verify.add_argument("--license", required=True, help="license.json 路径")
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

