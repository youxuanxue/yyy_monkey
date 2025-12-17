import base64
import hashlib
import hmac
import time
import argparse
from pathlib import Path

# 密钥 (必须与 src/douyin_auto_like/license.py 中一致)
SECRET_KEY = b"douyin-monkey-2025-trial-secret"

def generate_license(days: int, output_path: Path):
    now = time.time()
    expire_ts = now + (days * 86400)
    
    # 构造 payload
    expire_ts_str = f"{expire_ts:.0f}"
    
    # 生成签名
    signature = hmac.new(SECRET_KEY, expire_ts_str.encode("utf-8"), hashlib.sha256).hexdigest()
    
    # 组合: timestamp|signature
    raw_content = f"{expire_ts_str}|{signature}"
    
    # Base64 编码
    b64_content = base64.b64encode(raw_content.encode("utf-8"))
    
    # 写入文件
    output_path.write_bytes(b64_content)
    
    expire_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expire_ts))
    print(f"License generated successfully!")
    print(f"Expire Date: {expire_date}")
    print(f"File Path:   {output_path.resolve()}")

def main():
    parser = argparse.ArgumentParser(description="Generate License for Douyin Auto Like")
    parser.add_argument("--days", type=int, required=True, help="Valid days (e.g. 3)")
    parser.add_argument("--output", type=str, default="license.lic", help="Output filename")
    
    args = parser.parse_args()
    
    # 默认输出到 douyin/ 根目录（如果是开发环境）
    # 或者当前目录
    out_path = Path(args.output)
    if not out_path.is_absolute():
        # 尝试定位到项目根目录
        base_dir = Path(__file__).resolve().parent.parent
        out_path = base_dir / args.output

    generate_license(args.days, out_path)

if __name__ == "__main__":
    main()

