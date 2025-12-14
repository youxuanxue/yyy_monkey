import base64
import os
from pathlib import Path
from itertools import cycle

KEY = "douyin-monkey-2025-secret"

def xor_cipher(data: bytes, key: str) -> bytes:
    key_bytes = key.encode("utf-8")
    return bytes(a ^ b for a, b in zip(data, cycle(key_bytes)))

def encrypt_file(input_path: Path, output_path: Path):
    if not input_path.exists():
        print(f"Skipping {input_path} (not found)")
        return
    
    print(f"Encrypting {input_path} -> {output_path}")
    # 读取原始文本
    text = input_path.read_text(encoding="utf-8")
    # 转 bytes
    raw_bytes = text.encode("utf-8")
    # XOR 加密
    encrypted_bytes = xor_cipher(raw_bytes, KEY)
    # Base64 编码方便存储
    b64_bytes = base64.b64encode(encrypted_bytes)
    
    output_path.write_bytes(b64_bytes)
    print("Done.")

def main():
    base_dir = Path(__file__).resolve().parent.parent / "data"
    
    comments_txt = base_dir / "comments.txt"
    comments_enc = base_dir / "comments.enc"
    encrypt_file(comments_txt, comments_enc)
    
    danmaku_txt = base_dir / "danmaku.txt"
    danmaku_enc = base_dir / "danmaku.enc"
    encrypt_file(danmaku_txt, danmaku_enc)

if __name__ == "__main__":
    main()

