import os
import string
import sys

def get_available_drives():
    """获取系统中所有可用的本地硬盘驱动器。"""
    drives = []
    if sys.platform == 'win32':
        # Windows 系统
        available_drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
        for drive in available_drives:
            try:
                # 尝试获取驱动器信息，过滤掉光驱等非本地硬盘
                # os.statvfs 在 Windows 上不可用，使用 os.path.ismount 检查是否为挂载点
                # 并结合 os.path.exists 确保驱动器存在
                if os.path.ismount(drive + '\\'): # 检查是否为挂载点
                    drives.append(drive + '\\')
            except OSError:
                # 忽略访问被拒绝或其他错误
                pass
    else:
        # 其他系统（Linux, macOS） - 暂不详细实现，可以根据需要扩展
        # 这里可以添加对 /mnt, /media 或其他挂载点的扫描逻辑
        print("当前仅支持 Windows 系统。")
    return drives

def format_size(size_bytes):
    """将字节大小格式化为易于阅读的单位 (KB, MB, GB)。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.2f} MB"
    else:
        return f"{size_bytes/1024**3:.2f} GB"

def get_folder_size(folder_path):
    """计算文件夹的总大小（包括所有子文件和子文件夹）。"""
    total_size = 0
    try:
        for entry in os.scandir(folder_path):
            if entry.is_file():
                try:
                    total_size += entry.stat().st_size
                except OSError:
                    # 忽略无法访问的文件
                    pass
            elif entry.is_dir():
                try:
                    total_size += get_folder_size(entry.path)
                except PermissionError:
                    # GUI 将处理或记录此错误
                    pass
                except OSError:
                    # 忽略其他OS错误
                    pass
    except PermissionError:
        # GUI 将处理或记录此错误
        pass
    except OSError:
        # 忽略其他无法访问的文件夹错误
        # GUI 将处理或记录此错误
        pass
    return total_size

def analyze_directory(directory_path):
    """分析指定目录下的文件和文件夹占用空间。"""
    items = []
    try:
        for entry in os.scandir(directory_path):
            name = entry.name
            path = entry.path
            size = 0
            is_dir = entry.is_dir()
            try:
                if is_dir:
                    size = get_folder_size(path)
                else:
                    size = entry.stat().st_size
                items.append({"name": name, "size": size, "is_dir": is_dir, "path": path})
            except PermissionError:
                # print(f"警告：权限不足，无法获取 {path} 的信息。")
                items.append({"name": name, "size": 0, "is_dir": is_dir, "path": path, "error": "权限不足"})
            except OSError as e:
                # print(f"警告：无法获取 {path} 的信息。")
                items.append({"name": name, "size": 0, "is_dir": is_dir, "path": path, "error": f"OS错误: {e}"})

    except PermissionError as e:
        # print(f"错误：权限不足，无法扫描目录 {directory_path} - {e}")
        # 让调用者处理异常
        raise PermissionError(f"无法扫描目录 {directory_path}: 权限不足") from e
    except OSError as e:
        # print(f"错误：无法扫描目录 {directory_path} - {e}")
        # 让调用者处理异常
        raise OSError(f"无法扫描目录 {directory_path}: {e}") from e

    # 按大小降序排序
    items.sort(key=lambda x: x["size"], reverse=True)
    return items

# display_analysis 函数不再需要，GUI负责显示


# main 函数和 if __name__ == '__main__' 不再需要，由 GUI 启动