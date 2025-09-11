"""AI模型下载和管理工具"""

import os
import hashlib
from pathlib import Path
from typing import Dict, Optional
import requests
from urllib.parse import urlparse

class ModelDownloader:
    """AI模型下载和缓存管理"""
    
    # 预定义的模型配置
    MODEL_CONFIGS = {
        # 轻量级场景检测模型
        "scene_classifier": {
            "url": "https://github.com/opencv/opencv_zoo/raw/main/models/image_classification_mobilenet/image_classification_mobilenetv1_224x224.onnx",
            "filename": "mobilenet_scene_classifier.onnx",
            "sha256": "placeholder_hash",  # 实际使用时需要真实hash
            "description": "MobileNet场景分类模型"
        },
        
        # 内容安全检测模型
        "content_safety": {
            "url": "https://huggingface.co/martin-ha/toxic-comment-model/resolve/main/pytorch_model.bin",
            "filename": "content_safety_model.bin",
            "sha256": "placeholder_hash",
            "description": "内容安全检测模型"
        },
        
        # 轻量级目标检测模型（检测人物、物体等）
        "object_detection": {
            "url": "https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx",
            "filename": "yolox_nano.onnx", 
            "sha256": "placeholder_hash",
            "description": "YOLOX轻量级目标检测模型"
        }
    }
    
    def __init__(self, cache_dir: Optional[str] = None):
        """初始化模型下载器
        
        Args:
            cache_dir: 模型缓存目录，默认为 ~/.drama_processor/models
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.drama_processor/models")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def download_model(self, model_name: str, force_download: bool = False) -> Path:
        """下载指定模型
        
        Args:
            model_name: 模型名称
            force_download: 是否强制重新下载
            
        Returns:
            模型文件路径
            
        Raises:
            ValueError: 未知模型名称
            RuntimeError: 下载失败
        """
        if model_name not in self.MODEL_CONFIGS:
            raise ValueError(f"未知模型: {model_name}。可用模型: {list(self.MODEL_CONFIGS.keys())}")
        
        config = self.MODEL_CONFIGS[model_name]
        model_path = self.cache_dir / config["filename"]
        
        # 检查是否已存在且有效
        if model_path.exists() and not force_download:
            if self._verify_file_integrity(model_path, config.get("sha256")):
                print(f"✅ 模型已存在: {model_path}")
                return model_path
            else:
                print(f"⚠️ 模型文件损坏，重新下载: {model_path}")
        
        # 下载模型
        print(f"📥 下载模型: {config['description']}")
        print(f"   URL: {config['url']}")
        print(f"   保存到: {model_path}")
        
        try:
            self._download_file(config["url"], model_path)
            
            # 验证下载的文件
            if config.get("sha256") and not self._verify_file_integrity(model_path, config["sha256"]):
                model_path.unlink()  # 删除损坏的文件
                raise RuntimeError(f"下载的模型文件校验失败: {model_name}")
            
            print(f"✅ 模型下载完成: {model_path}")
            return model_path
            
        except Exception as e:
            if model_path.exists():
                model_path.unlink()  # 清理失败的下载
            raise RuntimeError(f"模型下载失败 {model_name}: {e}")
    
    def _download_file(self, url: str, output_path: Path) -> None:
        """下载文件到指定路径"""
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # 简单的进度显示
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        print(f"\r   进度: {progress:.1f}%", end='', flush=True)
        
        print()  # 换行
    
    def _verify_file_integrity(self, file_path: Path, expected_hash: Optional[str]) -> bool:
        """验证文件完整性"""
        if not expected_hash or expected_hash == "placeholder_hash":
            return True  # 跳过占位符hash的验证
        
        if not file_path.exists():
            return False
        
        # 计算文件SHA256
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest() == expected_hash
    
    def list_available_models(self) -> Dict[str, str]:
        """列出所有可用模型"""
        return {name: config["description"] for name, config in self.MODEL_CONFIGS.items()}
    
    def get_model_path(self, model_name: str) -> Optional[Path]:
        """获取模型路径（如果已下载）"""
        if model_name not in self.MODEL_CONFIGS:
            return None
        
        model_path = self.cache_dir / self.MODEL_CONFIGS[model_name]["filename"]
        return model_path if model_path.exists() else None


def main():
    """命令行工具：下载模型"""
    import argparse
    
    parser = argparse.ArgumentParser(description="下载AI模型")
    parser.add_argument("model_name", help="模型名称")
    parser.add_argument("--force", action="store_true", help="强制重新下载")
    parser.add_argument("--list", action="store_true", help="列出可用模型")
    
    args = parser.parse_args()
    
    downloader = ModelDownloader()
    
    if args.list:
        print("可用模型:")
        for name, desc in downloader.list_available_models().items():
            print(f"  {name}: {desc}")
        return
    
    try:
        model_path = downloader.download_model(args.model_name, args.force)
        print(f"模型已准备就绪: {model_path}")
    except Exception as e:
        print(f"错误: {e}")
        exit(1)


if __name__ == "__main__":
    main()
