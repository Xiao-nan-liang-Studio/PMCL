"""
Minecraft Downloader Library

一个高度可扩展的Minecraft版本下载器和启动器库。
提供多线程下载、版本过滤、进度跟踪等高级功能。

版本: 1.0.0
作者: Minecraft Downloader Team
"""

import requests
import json
import os
import time
import uuid
import zipfile
import platform
import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Callable, Tuple, Any


# =============================================================================
# 配置和数据类型定义
# =============================================================================

class VersionType(Enum):
    """版本类型枚举"""
    RELEASE = "release"
    SNAPSHOT = "snapshot"
    OLD_BETA = "old_beta"
    OLD_ALPHA = "old_alpha"
    ALL = "all"


@dataclass
class DownloadConfig:
    """下载配置类"""
    max_workers: int = 10
    chunk_size: int = 1024 * 1024  # 1MB chunks
    timeout: int = 30
    max_retries: int = 3
    download_dir: str = "."
    
    def __post_init__(self):
        """初始化后处理"""
        self.download_dir = os.path.abspath(self.download_dir)


@dataclass
class VersionInfo:
    """版本信息类"""
    id: str
    type: str
    url: str
    release_time: str
    sha1: str = ""
    compliance_level: int = 0


# =============================================================================
# 异常类
# =============================================================================

class MinecraftDownloaderError(Exception):
    """基础异常类"""
    pass


class VersionNotFoundError(MinecraftDownloaderError):
    """版本未找到异常"""
    pass


class DownloadError(MinecraftDownloaderError):
    """下载错误异常"""
    pass


class NetworkError(MinecraftDownloaderError):
    """网络错误异常"""
    pass


class FileVerificationError(MinecraftDownloaderError):
    """文件验证错误异常"""
    pass


class LaunchError(MinecraftDownloaderError):
    """启动错误异常"""
    pass


# =============================================================================
# 工具函数
# =============================================================================

def verify_file(file_path: str, expected_hash: str) -> bool:
    """验证文件完整性"""
    if not os.path.exists(file_path):
        return False
    
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
            actual_hash = hashlib.sha1(data).hexdigest()
            return actual_hash == expected_hash
    except:
        return False


def is_library_allowed(library: Dict) -> bool:
    """检查库是否适用于当前系统"""
    if "rules" not in library:
        return True
    
    rules = library.get("rules", [])
    allowed = False
    current_os = platform.system().lower()
    
    for rule in rules:
        if "os" in rule:
            os_name = rule["os"].get("name", "")
            if os_name == current_os:
                if rule.get("action") == "allow":
                    allowed = True
                elif rule.get("action") == "disallow":
                    allowed = False
        else:
            if rule.get("action") == "allow":
                allowed = True
            elif rule.get("action") == "disallow":
                allowed = False
    
    return allowed


def get_native_classifier() -> str:
    """获取当前系统的原生库分类器"""
    os_name = platform.system().lower()
    if os_name == "windows":
        return "natives-windows"
    elif os_name == "linux":
        return "natives-linux"
    elif os_name == "darwin":
        return "natives-osx"
    else:
        return "natives-windows"


def create_directories(*paths: str):
    """创建目录（如果不存在）"""
    for path in paths:
        os.makedirs(path, exist_ok=True)


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"


def calculate_download_speed(downloaded_bytes: int, elapsed_time: float) -> float:
    """计算下载速度（KB/s）"""
    if elapsed_time <= 0:
        return 0
    return downloaded_bytes / elapsed_time / 1024


# =============================================================================
# 核心下载器类
# =============================================================================

class DownloadProgress:
    """下载进度跟踪类"""
    def __init__(self):
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.start_time = 0
        self.current_file = ""
        self.callback: Optional[Callable] = None
    
    def update(self, bytes_count: int):
        """更新下载字节数"""
        self.downloaded_bytes += bytes_count
        
    def set_callback(self, callback: Callable):
        """设置进度回调函数"""
        self.callback = callback
    
    def emit(self, message: str, current: int = None, total: int = None):
        """触发进度回调"""
        if self.callback:
            self.callback(message, current, total)


class MinecraftDownloader:
    """
    Minecraft版本下载器核心类
    
    提供高度可定制的Minecraft版本下载功能，支持多线程下载、
    版本过滤、进度回调等高级特性。
    """
    
    def __init__(self, config: DownloadConfig = None):
        """
        初始化下载器
        
        Args:
            config: 下载配置，如果为None则使用默认配置
        """
        self.config = config or DownloadConfig()
        self.version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
        self.assets_url = "https://resources.download.minecraft.net"
        self.libraries_url = "https://libraries.minecraft.net"
        
        # 进度跟踪
        self.progress = DownloadProgress()
        
        # 初始化会话和目录
        self._init_session()
        self._init_directories()
    
    def _init_session(self):
        """初始化HTTP会话"""
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=self.config.max_retries
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def _init_directories(self):
        """初始化必要的目录结构"""
        self.versions_dir = os.path.join(self.config.download_dir, "versions")
        self.assets_dir = os.path.join(self.config.download_dir, "assets")
        self.libraries_dir = os.path.join(self.config.download_dir, "libraries")
        
        create_directories(
            self.versions_dir,
            self.assets_dir,
            os.path.join(self.assets_dir, "indexes"),
            os.path.join(self.assets_dir, "objects"),
            self.libraries_dir
        )
    
    def set_progress_callback(self, callback: Callable):
        """
        设置进度回调函数
        
        Args:
            callback: 回调函数，接收(message, current, total)参数
        """
        self.progress.set_callback(callback)
    
    def set_download_dir(self, download_dir: str):
        """
        设置下载目录
        
        Args:
            download_dir: 新的下载目录路径
        """
        self.config.download_dir = os.path.abspath(download_dir)
        self._init_directories()
    
    def get_version_list(self, version_type: VersionType = VersionType.ALL, 
                        limit: Optional[int] = None) -> List[VersionInfo]:
        """
        获取版本列表
        
        Args:
            version_type: 版本类型过滤
            limit: 返回版本数量限制
            
        Returns:
            版本信息列表
            
        Raises:
            NetworkError: 网络请求失败时抛出
        """
        try:
            response = self.session.get(self.version_manifest_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            versions = []
            for version_data in data.get("versions", []):
                version = VersionInfo(
                    id=version_data["id"],
                    type=version_data["type"],
                    url=version_data["url"],
                    release_time=version_data["releaseTime"],
                    sha1=version_data.get("sha1", ""),
                    compliance_level=version_data.get("complianceLevel", 0)
                )
                
                # 版本类型过滤
                if version_type == VersionType.ALL or version.type == version_type.value:
                    versions.append(version)
            
            # 按发布时间排序（最新的在前）
            versions.sort(key=lambda x: x.release_time, reverse=True)
            
            # 数量限制
            if limit:
                versions = versions[:limit]
                
            return versions
            
        except requests.RequestException as e:
            raise NetworkError(f"获取版本列表失败: {e}")
    
    def get_version_info(self, version_id: str) -> VersionInfo:
        """
        根据版本ID获取版本信息
        
        Args:
            version_id: 版本ID
            
        Returns:
            版本信息
            
        Raises:
            VersionNotFoundError: 版本未找到时抛出
        """
        versions = self.get_version_list(VersionType.ALL)
        for version in versions:
            if version.id == version_id:
                return version
        
        raise VersionNotFoundError(f"未找到版本: {version_id}")
    
    def get_version_details(self, version_info: VersionInfo) -> Dict:
        """
        获取版本详细信息
        
        Args:
            version_info: 版本信息
            
        Returns:
            版本详细信息字典
            
        Raises:
            NetworkError: 网络请求失败时抛出
        """
        try:
            response = self.session.get(version_info.url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise NetworkError(f"获取版本详情失败: {e}")
    
    def download_version(self, version_info: VersionInfo, 
                        download_assets: bool = True,
                        download_libraries: bool = True) -> bool:
        """
        下载指定版本
        
        Args:
            version_info: 版本信息
            download_assets: 是否下载资源文件
            download_libraries: 是否下载库文件
            
        Returns:
            下载是否成功
        """
        try:
            self.progress.emit(f"开始下载版本: {version_info.id}")
            
            # 获取版本详情
            version_details = self.get_version_details(version_info)
            
            # 创建版本目录
            version_dir = os.path.join(self.versions_dir, version_info.id)
            create_directories(version_dir)
            
            # 保存版本详情JSON
            with open(os.path.join(version_dir, f"{version_info.id}.json"), "w") as f:
                json.dump(version_details, f, indent=2)
            
            # 下载客户端JAR文件
            client_jar_url = version_details["downloads"]["client"]["url"]
            client_jar_path = os.path.join(version_dir, f"{version_info.id}.jar")
            
            self.progress.emit("下载客户端文件...")
            if not self._download_file(client_jar_url, client_jar_path):
                return False
            
            # 下载资源文件
            if download_assets:
                self.progress.emit("下载资源文件...")
                self._download_assets(version_details)
            
            # 下载库文件
            if download_libraries:
                self.progress.emit("下载库文件...")
                self._download_libraries(version_details.get("libraries", []))
            
            # 处理原生库文件
            self.progress.emit("处理原生库文件...")
            self._extract_natives(version_details, version_info.id)
            
            self.progress.emit(f"版本 {version_info.id} 下载完成!")
            return True
            
        except Exception as e:
            self.progress.emit(f"下载版本失败: {e}")
            return False
    
    def _download_file(self, url: str, file_path: str) -> bool:
        """下载文件（自动选择下载方式）"""
        file_size = self._get_file_size(url)
        
        # 小文件使用普通下载，大文件使用多线程下载
        if file_size > self.config.chunk_size * 2:
            return self._download_file_multithread(url, file_path, file_size)
        else:
            return self._download_file_normal(url, file_path)
    
    def _get_file_size(self, url: str) -> int:
        """获取文件大小"""
        try:
            response = self.session.head(url, timeout=5)
            response.raise_for_status()
            return int(response.headers.get('content-length', 0))
        except:
            return 0
    
    def _download_file_multithread(self, url: str, file_path: str, file_size: int) -> bool:
        """多线程分块下载"""
        chunks = file_size // self.config.chunk_size
        if file_size % self.config.chunk_size != 0:
            chunks += 1
        
        self.progress.current_file = os.path.basename(file_path)
        self.progress.total_bytes = file_size
        self.progress.downloaded_bytes = 0
        self.progress.start_time = time.time()
        
        # 创建临时目录
        temp_dir = os.path.join(os.path.dirname(file_path), "temp_chunks")
        create_directories(temp_dir)
        
        # 下载所有分块
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = []
            for i in range(chunks):
                start = i * self.config.chunk_size
                end = start + self.config.chunk_size - 1
                if end >= file_size:
                    end = file_size - 1
                
                chunk_file = os.path.join(temp_dir, f"chunk_{i:04d}")
                futures.append(executor.submit(self._download_chunk, url, start, end, chunk_file, i))
            
            # 等待完成
            completed = 0
            failed_chunks = []
            for future in as_completed(futures):
                chunk_idx, success = future.result()
                if success:
                    completed += 1
                else:
                    failed_chunks.append(chunk_idx)
                
                # 更新进度
                progress = (completed / chunks) * 100
                elapsed = time.time() - self.progress.start_time
                speed = calculate_download_speed(self.progress.downloaded_bytes, elapsed)
                
                self.progress.emit(
                    f"下载 {self.progress.current_file}: {progress:.1f}%", 
                    completed, chunks
                )
        
        # 重试失败的分块
        if failed_chunks:
            for chunk_idx in failed_chunks:
                start = chunk_idx * self.config.chunk_size
                end = start + self.config.chunk_size - 1
                if end >= file_size:
                    end = file_size - 1
                
                chunk_file = os.path.join(temp_dir, f"chunk_{chunk_idx:04d}")
                for retry in range(self.config.max_retries):
                    _, success = self._download_chunk(url, start, end, chunk_file, chunk_idx)
                    if success:
                        break
        
        # 合并分块
        with open(file_path, 'wb') as outfile:
            for i in range(chunks):
                chunk_file = os.path.join(temp_dir, f"chunk_{i:04d}")
                try:
                    with open(chunk_file, 'rb') as infile:
                        outfile.write(infile.read())
                    os.remove(chunk_file)
                except Exception as e:
                    self.progress.emit(f"合并分块失败: {e}")
                    return False
        
        # 清理临时目录
        try:
            os.rmdir(temp_dir)
        except:
            pass
        
        return True
    
    def _download_chunk(self, url: str, start: int, end: int, chunk_file: str, chunk_idx: int) -> Tuple[int, bool]:
        """下载文件分块"""
        headers = {'Range': f'bytes={start}-{end}'}
        try:
            response = self.session.get(url, headers=headers, stream=True, timeout=self.config.timeout)
            response.raise_for_status()
            
            with open(chunk_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        self.progress.update(len(chunk))
            
            return chunk_idx, True
        except Exception as e:
            return chunk_idx, False
    
    def _download_file_normal(self, url: str, file_path: str) -> bool:
        """普通单线程下载"""
        try:
            response = self.session.get(url, stream=True, timeout=self.config.timeout)
            response.raise_for_status()
            
            file_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            
            create_directories(os.path.dirname(file_path))
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if file_size > 0:
                            progress = (downloaded / file_size) * 100
                            elapsed = time.time() - start_time
                            speed = calculate_download_speed(downloaded, elapsed)
                            
                            self.progress.emit(
                                f"下载 {os.path.basename(file_path)}: {progress:.1f}%",
                                downloaded, file_size
                            )
            
            return True
        except Exception as e:
            self.progress.emit(f"下载失败: {e}")
            return False
    
    def _download_assets(self, version_details: Dict):
        """下载资源文件"""
        asset_index = version_details.get("assetIndex", {})
        if not asset_index:
            return
        
        asset_index_id = asset_index.get("id")
        asset_index_url = asset_index.get("url")
        if not asset_index_id or not asset_index_url:
            return
        
        # 下载资源索引
        asset_index_path = os.path.join(self.assets_dir, "indexes", f"{asset_index_id}.json")
        if not os.path.exists(asset_index_path):
            self._download_file_normal(asset_index_url, asset_index_path)
        
        # 加载资源索引
        try:
            with open(asset_index_path, 'r', encoding='utf-8') as f:
                assets_data = json.load(f)
        except Exception as e:
            self.progress.emit(f"加载资源索引失败: {e}")
            return
        
        # 下载资源对象
        objects_dir = os.path.join(self.assets_dir, "objects")
        objects = assets_data.get("objects", {})
        download_tasks = []
        
        for asset_name, asset_info in objects.items():
            hash_value = asset_info["hash"]
            hash_prefix = hash_value[:2]
            asset_url = f"{self.assets_url}/{hash_prefix}/{hash_value}"
            asset_path = os.path.join(objects_dir, hash_prefix, hash_value)
            
            if not verify_file(asset_path, hash_value):
                download_tasks.append((asset_url, asset_path))
        
        # 并发下载
        if download_tasks:
            self.progress.emit(f"下载 {len(download_tasks)} 个资源文件...")
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = [executor.submit(self._download_file_normal, url, path) 
                          for url, path in download_tasks]
                
                completed = 0
                for future in as_completed(futures):
                    try:
                        future.result()
                        completed += 1
                        self.progress.emit("下载资源文件...", completed, len(download_tasks))
                    except Exception as e:
                        self.progress.emit(f"资源文件下载失败: {e}")
    
    def _download_libraries(self, libraries: List[Dict]):
        """下载库文件"""
        download_tasks = []
        
        for library in libraries:
            if not is_library_allowed(library):
                continue
            
            downloads = library.get("downloads", {})
            artifact = downloads.get("artifact")
            if artifact:
                library_url = artifact.get("url")
                library_path = artifact.get("path")
                
                if library_url and library_path:
                    full_path = os.path.join(self.libraries_dir, library_path)
                    if not os.path.exists(full_path):
                        download_tasks.append((library_url, full_path))
        
        # 并发下载
        if download_tasks:
            self.progress.emit(f"下载 {len(download_tasks)} 个库文件...")
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = [executor.submit(self._download_file_normal, url, path) 
                          for url, path in download_tasks]
                
                completed = 0
                for future in as_completed(futures):
                    try:
                        future.result()
                        completed += 1
                        self.progress.emit("下载库文件...", completed, len(download_tasks))
                    except Exception as e:
                        self.progress.emit(f"库文件下载失败: {e}")
    
    def _extract_natives(self, version_details: Dict, version_id: str):
        """提取原生库文件"""
        libraries = version_details.get("libraries", [])
        version_natives_dir = os.path.join(self.versions_dir, version_id, "natives")
        create_directories(version_natives_dir)
        
        native_classifier = get_native_classifier()
        
        for library in libraries:
            if "natives" not in library:
                continue
            
            os_name = platform.system().lower()
            if os_name not in library.get("natives", {}):
                continue
            
            downloads = library.get("downloads", {})
            classifiers = downloads.get("classifiers", {})
            
            if native_classifier in classifiers:
                native_info = classifiers[native_classifier]
                native_url = native_info.get("url")
                native_path = native_info.get("path")
                
                if native_url and native_path:
                    full_path = os.path.join(self.libraries_dir, native_path)
                    if not os.path.exists(full_path):
                        self._download_file_normal(native_url, full_path)
                    
                    # 提取文件
                    if os.path.exists(full_path) and (full_path.endswith('.jar') or full_path.endswith('.zip')):
                        with zipfile.ZipFile(full_path, 'r') as zip_ref:
                            zip_ref.extractall(version_natives_dir)


# =============================================================================
# 启动器类
# =============================================================================

class MinecraftLauncher:
    """
    Minecraft启动器类
    
    提供Minecraft游戏启动功能，支持自定义Java路径、内存设置等。
    """
    
    def __init__(self, downloader: MinecraftDownloader):
        """
        初始化启动器
        
        Args:
            downloader: Minecraft下载器实例
        """
        self.downloader = downloader
    
    def get_installed_versions(self) -> List[str]:
        """
        获取已安装的版本列表
        
        Returns:
            已安装的版本ID列表
        """
        if not os.path.exists(self.downloader.versions_dir):
            return []
        
        versions = []
        for version_dir in os.listdir(self.downloader.versions_dir):
            version_path = os.path.join(self.downloader.versions_dir, version_dir)
            jar_path = os.path.join(version_path, f"{version_dir}.jar")
            json_path = os.path.join(version_path, f"{version_dir}.json")
            
            if (os.path.isdir(version_path) and 
                os.path.exists(jar_path) and 
                os.path.exists(json_path)):
                versions.append(version_dir)
        
        return sorted(versions, reverse=True)
    
    def is_version_installed(self, version_id: str) -> bool:
        """
        检查版本是否已安装
        
        Args:
            version_id: 版本ID
            
        Returns:
            是否已安装
        """
        version_dir = os.path.join(self.downloader.versions_dir, version_id)
        jar_path = os.path.join(version_dir, f"{version_id}.jar")
        json_path = os.path.join(version_dir, f"{version_id}.json")
        
        return (os.path.exists(version_dir) and 
                os.path.exists(jar_path) and 
                os.path.exists(json_path))
    
    def create_launch_command(self, version_id: str, username: str = "Player", 
                            java_path: str = "java", memory: str = "2G") -> List[str]:
        """
        创建启动命令
        
        Args:
            version_id: 版本ID
            username: 用户名
            java_path: Java可执行文件路径
            memory: 内存大小（如 "2G"）
            
        Returns:
            启动命令参数列表
            
        Raises:
            VersionNotFoundError: 版本未找到时抛出
            LaunchError: 启动配置错误时抛出
        """
        if not self.is_version_installed(version_id):
            raise VersionNotFoundError(f"版本未安装: {version_id}")
        
        # 读取版本详情
        version_dir = os.path.join(self.downloader.versions_dir, version_id)
        version_json_path = os.path.join(version_dir, f"{version_id}.json")
        
        try:
            with open(version_json_path, 'r', encoding='utf-8') as f:
                version_details = json.load(f)
        except Exception as e:
            raise LaunchError(f"读取版本信息失败: {e}")
        
        # 构建类路径
        classpath_parts = []
        
        # 主JAR文件
        jar_path = os.path.join(version_dir, f"{version_id}.jar")
        classpath_parts.append(jar_path)
        
        # 库文件
        libraries = version_details.get("libraries", [])
        for library in libraries:
            if not is_library_allowed(library):
                continue
            
            downloads = library.get("downloads", {})
            artifact = downloads.get("artifact")
            if artifact:
                library_path = artifact.get("path")
                if library_path:
                    full_path = os.path.join(self.downloader.libraries_dir, library_path)
                    if os.path.exists(full_path):
                        classpath_parts.append(full_path)
        
        classpath = os.pathsep.join(classpath_parts)
        
        # 获取其他参数
        natives_dir = os.path.join(version_dir, "natives")
        asset_index_id = version_details.get("assetIndex", {}).get("id", "")
        version_type = version_details.get("type", "release")
        
        # 生成认证信息
        access_token = str(uuid.uuid4())
        player_uuid = str(uuid.uuid4())
        
        # 构建命令
        java_cmd = [
            java_path,
            f"-Xmx{memory}",
            f"-Djava.library.path={natives_dir}",
            "-cp",
            classpath,
            "net.minecraft.client.main.Main",
            "--username", username,
            "--version", version_id,
            "--gameDir", self.downloader.config.download_dir,
            "--assetsDir", self.downloader.assets_dir,
            "--assetIndex", asset_index_id,
            "--accessToken", access_token,
            "--uuid", player_uuid,
            "--userType", "mojang",
            "--versionType", version_type
        ]
        
        return java_cmd
    
    def launch_game(self, version_id: str, username: str = "Player", 
                   java_path: str = "java", memory: str = "2G", 
                   show_output: bool = True) -> bool:
        """
        启动游戏
        
        Args:
            version_id: 版本ID
            username: 用户名
            java_path: Java可执行文件路径
            memory: 内存大小
            show_output: 是否显示游戏输出
            
        Returns:
            启动是否成功
        """
        try:
            java_cmd = self.create_launch_command(version_id, username, java_path, memory)
            
            print(f"启动游戏: {version_id}")
            print(f"用户名: {username}")
            print(f"Java命令: {' '.join(java_cmd)}")
            
            # 设置进程参数
            kwargs = {
                'cwd': self.downloader.config.download_dir,
            }
            
            if show_output:
                kwargs.update({
                    'stdout': subprocess.PIPE,
                    'stderr': subprocess.STDOUT,
                    'universal_newlines': True
                })
            
            process = subprocess.Popen(java_cmd, **kwargs)
            
            # 实时输出游戏日志
            if show_output and process.stdout:
                for line in process.stdout:
                    print(line, end='')
            
            process.wait()
            print("游戏已退出")
            return True
            
        except Exception as e:
            print(f"启动游戏失败: {e}")
            return False
    
    def generate_launch_script(self, version_id: str, username: str = "Player",
                             java_path: str = "java", memory: str = "2G",
                             script_path: Optional[str] = None) -> str:
        """
        生成启动脚本
        
        Args:
            version_id: 版本ID
            username: 用户名
            java_path: Java可执行文件路径
            memory: 内存大小
            script_path: 脚本保存路径，如果为None则自动生成
            
        Returns:
            生成的脚本路径
        """
        java_cmd = self.create_launch_command(version_id, username, java_path, memory)
        
        if script_path is None:
            script_path = os.path.join(
                self.downloader.config.download_dir, 
                f"launch_{version_id}.bat"
            )
        
        # 生成批处理脚本
        script_content = f"""@echo off
echo Minecraft 启动脚本 - 版本 {version_id}
echo.

set GAME_DIR={self.downloader.config.download_dir}
set JAVA_HOME=%JAVA_HOME%
set JAVA_EXE={java_path}

if not "%JAVA_HOME%"=="" set JAVA_EXE="%JAVA_HOME%\\bin\\java.exe"

if not exist "%JAVA_EXE%" set JAVA_EXE=java.exe

echo 使用Java: %JAVA_EXE%
echo.

%JAVA_EXE% -Xmx{memory} -Djava.library.path="{os.path.join(self.downloader.versions_dir, version_id, "natives")}" ^
-cp "{os.pathsep.join(java_cmd[4].split(os.pathsep))}" {" ".join(java_cmd[5:])}

pause
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        
        print(f"启动脚本已创建: {script_path}")
        return script_path


# =============================================================================
# 使用示例
# =============================================================================

def main():
    """使用示例"""
    
    def progress_callback(message: str, current: int = None, total: int = None):
        """进度回调函数示例"""
        if current is not None and total is not None:
            print(f"\r{message} ({current}/{total})", end='', flush=True)
        else:
            print(message)
    
    # 创建配置
    config = DownloadConfig(
        max_workers=10,
        download_dir=os.path.join(os.getcwd(), "minecraft")
    )
    
    # 创建下载器和启动器
    downloader = MinecraftDownloader(config)
    downloader.set_progress_callback(progress_callback)
    
    launcher = MinecraftLauncher(downloader)
    
    # 获取版本列表
    print("获取版本列表...")
    versions = downloader.get_version_list(
        version_type=VersionType.RELEASE,
        limit=5
    )
    
    print("\n最新的5个正式版:")
    for i, version in enumerate(versions):
        print(f"{i+1}. {version.id} ({version.release_time[:10]})")
    
    # 下载版本示例
    if versions:
        version_to_download = versions[0]
        print(f"\n下载版本: {version_to_download.id}")
        
        success = downloader.download_version(version_to_download)
        if success:
            print("下载成功!")
        else:
            print("下载失败!")
    
    # 查看已安装版本
    installed = launcher.get_installed_versions()
    if installed:
        print(f"\n已安装的版本: {', '.join(installed)}")
    else:
        print("\n没有安装任何版本")


if __name__ == "__main__":
    main()