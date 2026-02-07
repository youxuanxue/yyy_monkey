import json
import os
import shutil
from pathlib import Path

def copy_model():
    # 配置路径
    home = Path.home()
    source_manifest_path = home / ".ollama/models/manifests/registry.ollama.ai/library/qwen2.5/3b"
    source_blobs_dir = home / ".ollama/models/blobs"
    
    # 目标根目录 (相对于当前脚本运行位置)
    target_root = Path("wechat_gzh/runtime/ollama_models")
    target_manifest_path = target_root / "manifests/registry.ollama.ai/library/qwen2.5/3b"
    target_blobs_dir = target_root / "blobs"
    
    print(f"源 Manifest: {source_manifest_path}")
    
    if not source_manifest_path.exists():
        print(f"错误: 找不到源 manifest 文件: {source_manifest_path}")
        return

    # 读取 manifest
    with open(source_manifest_path, 'r') as f:
        manifest = json.load(f)
        
    digests = set()
    # Config digest
    digests.add(manifest['config']['digest'])
    # Layers digests
    for layer in manifest['layers']:
        digests.add(layer['digest'])
        
    print(f"找到 {len(digests)} 个相关文件 (blobs)")
    
    # 创建目标目录
    target_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    target_blobs_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 复制 Manifest
    print(f"复制 Manifest 到 {target_manifest_path}...")
    shutil.copy2(source_manifest_path, target_manifest_path)
    
    # 2. 复制 Blobs
    for digest in digests:
        # 转换格式 sha256:xxx -> sha256-xxx
        blob_name = digest.replace(":", "-")
        source_blob = source_blobs_dir / blob_name
        target_blob = target_blobs_dir / blob_name
        
        if not source_blob.exists():
            print(f"警告: 找不到 blob 文件 {source_blob}")
            continue
            
        if target_blob.exists():
            print(f"跳过已存在: {blob_name}")
            continue
            
        print(f"正在复制: {blob_name} ({source_blob.stat().st_size / 1024 / 1024:.2f} MB)")
        shutil.copy2(source_blob, target_blob)
        
    print("="*60)
    print("模型文件复制完成！")

if __name__ == "__main__":
    copy_model()
