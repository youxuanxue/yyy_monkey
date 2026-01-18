import os
import json
import shutil
from pathlib import Path

def copy_model_files():
    # 配置路径
    home = Path.home()
    source_root = home / ".ollama" / "models"
    
    # 目标根目录 (相对于脚本运行位置)
    target_root = Path("wechat_gzh/runtime/ollama_models")
    
    # 模型信息
    model_library = "library"
    model_name = "qwen2.5"
    model_tag = "3b"
    
    # 1. 源 Manifest 路径
    src_manifest_path = source_root / "manifests" / "registry.ollama.ai" / model_library / model_name / model_tag
    
    if not src_manifest_path.exists():
        print(f"错误: 找不到模型 manifest 文件: {src_manifest_path}")
        return

    # 2. 读取 Manifest
    print(f"读取 manifest: {src_manifest_path}")
    with open(src_manifest_path, "r") as f:
        manifest = json.load(f)
    
    # 3. 收集所有需要复制的文件 digest
    digests = set()
    
    # Config
    if "config" in manifest:
        digests.add(manifest["config"]["digest"])
        
    # Layers
    if "layers" in manifest:
        for layer in manifest["layers"]:
            digests.add(layer["digest"])
            
    print(f"找到 {len(digests)} 个 blob 文件需要复制")
    
    # 4. 创建目标目录结构
    dst_manifest_dir = target_root / "manifests" / "registry.ollama.ai" / model_library / model_name
    dst_blobs_dir = target_root / "blobs"
    
    os.makedirs(dst_manifest_dir, exist_ok=True)
    os.makedirs(dst_blobs_dir, exist_ok=True)
    
    # 5. 复制 Manifest 文件
    dst_manifest_path = dst_manifest_dir / model_tag
    print(f"复制 Manifest: \n  From: {src_manifest_path}\n  To:   {dst_manifest_path}")
    shutil.copy2(src_manifest_path, dst_manifest_path)
    
    # 6. 复制 Blobs
    print("开始复制 Blobs...")
    for digest in digests:
        # 转换 digest 格式: sha256:xxx -> sha256-xxx
        blob_filename = digest.replace(":", "-")
        src_blob = source_root / "blobs" / blob_filename
        dst_blob = dst_blobs_dir / blob_filename
        
        if not src_blob.exists():
            print(f"警告: 找不到 blob 文件: {src_blob}")
            continue
            
        if dst_blob.exists():
            print(f"  跳过已存在: {blob_filename}")
            continue
            
        print(f"  复制: {blob_filename} ({src_blob.stat().st_size / 1024 / 1024:.2f} MB)")
        shutil.copy2(src_blob, dst_blob)

    print("\n复制完成!")
    print(f"模型文件已准备在: {target_root}")

if __name__ == "__main__":
    copy_model_files()
