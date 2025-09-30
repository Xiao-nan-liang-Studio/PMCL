
# PythonMinecraftLauncher_ai

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/your-username/PythonMinecraftLauncher_ai.svg)](https://github.com/your-username/PythonMinecraftLauncher_ai/stargazers)

## ✨ 项目简介

**PythonMinecraftLauncher_ai** 是一个基于 Python 开发的高度可扩展 Minecraft 版本下载器和启动器库。提供多线程下载、版本过滤、进度跟踪等高级功能，让 Minecraft 游戏管理变得更加简单高效。

## 🚀 主要特性

- 🚀 **多线程下载** - 支持多线程并发下载，大幅提升下载速度
- 📦 **完整版本管理** - 支持下载客户端、资源文件、库文件等完整组件
- 🔍 **智能版本过滤** - 按版本类型（正式版、快照版、历史版本）筛选
- 📊 **实时进度跟踪** - 详细的下载进度和速度显示
- 🛡️ **文件完整性验证** - 自动验证文件 SHA1 校验和
- 🎮 **内置启动器** - 支持生成启动命令和启动脚本
- 🖥️ **跨平台支持** - 支持 Windows、Linux、macOS 系统
- ⚡ **高度可配置** - 灵活的下载配置和自定义选项

## 📥 安装指南

### 前提条件

- **Python 3.7** 或更高版本
- 稳定的网络连接

### 安装步骤

1. **克隆仓库或下载源代码**
```bash
git clone https://github.com/lijiayuapp/PythonMinecraftLauncher_ai.git
cd PythonMinecraftLauncher_ai
```

2. **安装依赖**
```bash
pip install requests
```

## 🎯 快速开始

### 基本用法

```python
from minecraft_downloader import MinecraftDownloader, MinecraftLauncher, DownloadConfig, VersionType

# 创建配置
config = DownloadConfig(
    max_workers=10,
    download_dir="./minecraft"
)

# 创建下载器
downloader = MinecraftDownloader(config)

# 设置进度回调
def progress_callback(message, current=None, total=None):
    if current and total:
        print(f"\r{message} ({current}/{total})", end="", flush=True)
    else:
        print(message)

downloader.set_progress_callback(progress_callback)

# 获取版本列表
versions = downloader.get_version_list(
    version_type=VersionType.RELEASE,
    limit=5
)

# 下载最新版本
if versions:
    latest_version = versions[0]
    success = downloader.download_version(latest_version)
    
    if success:
        # 创建启动器
        launcher = MinecraftLauncher(downloader)
        
        # 启动游戏
        launcher.launch_game(
            version_id=latest_version.id,
            username="YourUsername",
            memory="4G"
        )
```

### 高级用法

#### 批量下载多个版本

```python
# 下载多个版本
versions_to_download = ["1.20.1", "1.19.4", "1.18.2"]

for version_id in versions_to_download:
    try:
        version_info = downloader.get_version_info(version_id)
        print(f"开始下载 {version_id}...")
        success = downloader.download_version(version_info)
        
        if success:
            print(f"版本 {version_id} 下载完成！")
        else:
            print(f"版本 {version_id} 下载失败！")
    except Exception as e:
        print(f"下载 {version_id} 时出错: {e}")
```

#### 自定义下载组件

```python
# 仅下载客户端文件，不下载资源和库文件
version_info = downloader.get_version_info("1.20.1")
success = downloader.download_version(
    version_info,
    download_assets=False,      # 不下载资源文件
    download_libraries=False    # 不下载库文件
)
```

#### 生成启动脚本

```python
launcher = MinecraftLauncher(downloader)

# 生成 Windows 启动脚本
script_path = launcher.generate_launch_script(
    version_id="1.20.1",
    username="Steve",
    java_path="java",
    memory="4G"
)
```

## 📚 API 参考

### 主要类

#### `MinecraftDownloader`

核心下载器类，负责版本管理和文件下载。

**主要方法：**
- `get_version_list()` - 获取版本列表
- `get_version_info()` - 获取特定版本信息
- `download_version()` - 下载指定版本
- `set_progress_callback()` - 设置进度回调

#### `MinecraftLauncher`

游戏启动器类，负责生成启动命令和启动游戏。

**主要方法：**
- `get_installed_versions()` - 获取已安装版本
- `create_launch_command()` - 创建启动命令
- `launch_game()` - 启动游戏
- `generate_launch_script()` - 生成启动脚本

#### `DownloadConfig`

下载配置类，用于自定义下载行为。

**配置选项：**
- `max_workers` - 最大线程数（默认：10）
- `chunk_size` - 分块大小（默认：1MB）
- `timeout` - 请求超时时间（默认：30秒）
- `max_retries` - 最大重试次数（默认：3）
- `download_dir` - 下载目录（默认：当前目录）

### 枚举类型

#### `VersionType`

版本类型枚举：
- `RELEASE` - 正式版
- `SNAPSHOT` - 快照版
- `OLD_BETA` - 历史测试版
- `OLD_ALPHA` - 历史Alpha版
- `ALL` - 所有版本

## 🛠️ 配置说明

### 下载目录结构

```
minecraft/
├── versions/           # 版本文件
│   └── [version-id]/
│       ├── [version-id].jar
│       ├── [version-id].json
│       └── natives/    # 原生库文件
├── assets/            # 资源文件
│   ├── indexes/       # 资源索引
│   └── objects/       # 资源对象
└── libraries/         # 库文件
```

### 内存配置建议

| 游戏版本 | 推荐内存 | 最小内存 |
|---------|----------|----------|
| 1.17+   | 4-8GB    | 2GB      |
| 1.13-1.16 | 3-6GB  | 2GB      |
| 1.8-1.12 | 2-4GB    | 1GB      |
| 旧版本   | 1-2GB    | 512MB    |

## 🔧 故障排除

### 常见问题

**Q: 下载速度很慢怎么办？**
A: 尝试增加 `max_workers` 参数，或检查网络连接。

**Q: 下载过程中出现网络错误？**
A: 库会自动重试，你也可以增加 `max_retries` 参数。

**Q: 启动游戏时出现 Java 错误？**
A: 确保已安装正确版本的 Java，并检查内存设置是否合理。

**Q: 文件验证失败？**
A: 这通常是由于网络问题导致的文件损坏，库会自动重新下载损坏的文件。

### 错误代码

| 错误类型 | 描述 | 解决方法 |
|---------|------|----------|
| `VersionNotFoundError` | 版本未找到 | 检查版本ID是否正确 |
| `NetworkError` | 网络连接错误 | 检查网络连接和代理设置 |
| `DownloadError` | 下载过程错误 | 检查磁盘空间和文件权限 |
| `FileVerificationError` | 文件验证失败 | 文件将被自动重新下载 |
| `LaunchError` | 启动过程错误 | 检查Java安装和内存设置 |

## 🤝 贡献指南

我们欢迎各种形式的贡献！包括但不限于：

- 🐛 **报告 Bug**
- 💡 **提出新功能建议**
- 📝 **改进文档**
- 🔧 **提交代码修复**


## 📄 许可证

本项目采用 **MIT 许可证** - 查看 [LICENSE](LICENSE) 文件了解详情。

## ⚠️ 免责声明

本项目与 **Mojang Studios** 无关，**Minecraft** 是 Mojang Studios 的商标。使用本库下载和运行 Minecraft 需要遵守 Minecraft 的最终用户许可协议（EULA）。

## 📞 联系方式

- **项目主页**: https://github.com/lijiayuapp/PythonMinecraftLauncher_ai/
- **邮箱**: lijiayuappman@outlook.com

---

**如果这个项目对你有帮助，请给个 ⭐️ 支持一下！**

