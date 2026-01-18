import os
import shutil
import json
from pathlib import Path

def copy_model():
    # 源和目标路径
    home = Path.home()
    src_models_root = home / ".ollama" / "models"
    dst_runtime_root = Path("wechat_gzh/runtime/ollama_models")
    
    # Manifest 路径
    manifest_rel_path = "manifests/registry.ollama.ai/library/qwen2.5/3b"
    src_manifest = src_models_root / manifest_rel_path
    dst_manifest = dst_runtime_root / manifest_rel_path
    
    print(f"源 manifest: {src_manifest}")
    
    if not src_manifest.exists():
        print(f"错误: 未找到 Manifest 文件: {src_manifest}")
        return

    # 创建目标 Manifest 目录
    dst_manifest.parent.mkdir(parents=True, exist_ok=True)
    
    # 复制 Manifest
    print(f"复制 Manifest 到: {dst_manifest}")
    shutil.copy2(src_manifest, dst_manifest)
    
    # 解析 Manifest
    with open(src_manifest, "r") as f:
        data = json.load(f)
    
    # 收集需要复制的 digest
    digests = set()
    
    # Config digest
    if "config" in data and "digest" in data["config"]:
        digests.add(data["config"]["digest"])
        
    # Layers digests
    if "layers" in data:
        for layer in data["layers"]:
            if "digest" in layer:
                digests.add(layer["digest"])
                
    print(f"需要复制 {len(digests)} 个 blobs")
    
    # 创建目标 blobs 目录
    dst_blobs_dir = dst_runtime_root / "blobs"
    dst_blobs_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制 blobs
    for digest in digests:
        # 转换 digest 格式: sha256:xxx -> sha256-xxx
        blob_filename = digest.replace(":", "-")
        src_blob = src_models_root / "blobs" / blob_filename
        dst_blob = dst_blobs_dir / blob_filename
        
        if not src_blob.exists():
            print(f"警告: 未找到 blob 文件: {src_blob}")
            continue
            
        if dst_blob.exists():
            print(f"跳过已存在: {blob_filename}")
            continue
            
        print(f"正在复制: {blob_filename} ({src_blob.stat().st_size / 1024 / 1024:.2f} MB)")
        shutil.copy2(src_blob, dst_blob)

    print("复制完成！")

if __name__ == "__main__":
    copy_model()
