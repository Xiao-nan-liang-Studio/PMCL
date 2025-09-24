#PythonMinecraftLauncher_ai

一个高速、多线程的Minecraft游戏下载器和启动器库。

功能特性
🚀 多线程高速下载Minecraft游戏文件

📦 自动下载资源文件、库文件和原生库

🔍 支持版本列表获取和选择

🎮 自动创建启动脚本和直接启动游戏

📊 完整的进度跟踪和错误处理

🖥️ 跨平台支持（Windows、Linux、macOS）

安装
bash
pip install superfast-mc-downloader
或直接下载源代码：

bash
git clone https://github.com/yourusername/superfast-mc-downloader.git
cd superfast-mc-downloader
快速开始
基本使用
python
from superfast_mc_downloader import SuperFastMCDownloader

# 创建下载器实例
downloader = SuperFastMCDownloader(max_workers=10)

# 获取版本列表
version_data = downloader.get_version_list()
releases = downloader.get_release_versions(version_data, limit=5)

# 下载最新版本
if releases:
    latest_version = releases[0]
    downloader.download_version(latest_version)
    
    # 创建启动脚本
    downloader.create_launch_script(latest_version['id'])
    
    # 启动游戏
    downloader.launch_game(latest_version['id'], "MyPlayer")
高级使用（带回调函数）
python
def on_progress(filename, progress, speed):
    print(f"{filename}: {progress:.1f}% ({speed:.2f} KB/s)")

def on_status(message):
    print(f"状态: {message}")

def on_error(message, exception):
    print(f"错误: {message}")

downloader = SuperFastMCDownloader()
downloader.set_callbacks(on_progress, on_status, on_error)

# 批量下载多个版本
versions_to_download = ["1.20.1", "1.19.4", "1.18.2"]
for version_id in versions_to_download:
    # 查找版本信息并下载
    version_data = downloader.get_version_list()
    for version in version_data.get("versions", []):
        if version["id"] == version_id:
            downloader.download_version(version)
            break
API 参考
SuperFastMCDownloader 类
初始化参数
working_dir: 工作目录（默认当前目录）

max_workers: 最大下载线程数（默认10）

session: 自定义requests会话

主要方法
get_version_list(): 获取Minecraft版本列表

get_release_versions(limit=None): 获取发布版本

download_version(version_info): 下载指定版本

launch_game(version_id, username="Player"): 启动游戏

create_launch_script(version_id): 创建启动脚本

get_downloaded_versions(): 获取已下载版本列表

回调函数设置
python
downloader.set_callbacks(
    progress_callback,  # (filename, progress, speed)
    status_callback,    # (message)
    error_callback      # (message, exception)
)
