import base64
import hashlib
import hmac
import time
import sys
import logging
from pathlib import Path

# 密钥 (在生成端和验证端必须一致)
# TODO: 请在正式发布前修改此密钥，并保持 gen_license.py 中一致
SECRET_KEY = b"douyin-monkey-2025-trial-secret"

class LicenseError(Exception):
    pass

def _get_license_path() -> Path:
    """获取 license 文件路径"""
    if getattr(sys, 'frozen', False):
        # exe 模式
        base_dir = Path(sys.executable).parent
    else:
        # 开发模式
        base_dir = Path(__file__).resolve().parents[2]
    return base_dir / "license.lic"

def verify_license() -> None:
    """
    验证 License 文件。
    如果验证失败或过期，抛出 SystemExit 或 LicenseError。
    """
    lic_path = _get_license_path()
    
    if not lic_path.exists():
        logging.error(f"License file not found: {lic_path}")
        print("Error: License file (license.lic) is missing.")
        print("Please contact the administrator to obtain a valid license.")
        sys.exit(1)

    try:
        content = lic_path.read_bytes().strip()
        # 解码 Base64
        try:
            decoded = base64.b64decode(content).decode("utf-8")
        except Exception:
            raise LicenseError("Invalid license format.")

        if "|" not in decoded:
            raise LicenseError("Invalid license structure.")

        # 分割 payload 和 signature
        expire_ts_str, signature = decoded.split("|", 1)
        
        # 验证签名
        # 签名内容 = expire_ts_str
        expected_sig = hmac.new(SECRET_KEY, expire_ts_str.encode("utf-8"), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected_sig, signature):
            raise LicenseError("Invalid license signature.")

        # 验证是否过期
        expire_ts = float(expire_ts_str)
        now_ts = time.time()
        
        if now_ts > expire_ts:
            expire_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expire_ts))
            raise LicenseError(f"License expired on {expire_date}")

        # 验证通过
        remaining_days = int((expire_ts - now_ts) / 86400)
        # logging.info(f"License valid. Expires in {remaining_days} days.")
        return

    except LicenseError as e:
        logging.error(f"License check failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error during license check: {e}")
        print("Error: Failed to verify license.")
        sys.exit(1)

