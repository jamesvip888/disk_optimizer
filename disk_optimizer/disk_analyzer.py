import os
import psutil
from typing import Dict, List, Tuple, Optional, Callable
from collections import defaultdict


class DiskScanner:
    """
    磁盘扫描器类
    职责:
    1. 扫描系统中所有的磁盘设备
    2. 收集磁盘使用情况和分区信息
    3. 提供统一的磁盘信息接口
    """
    
    def __init__(self):
        self.cached_disks = None
        self.cache_time = None
    
    def get_all_disks(self, use_cache: bool = True, cache_duration: int = 60) -> List[Dict]:
        """
        获取所有磁盘信息（支持缓存）
        
        Args:
            use_cache: 是否使用缓存
            cache_duration: 缓存有效期（秒）
        
        Returns:
            List[Dict]: 磁盘信息列表
        """
        import time
        
        # 检查缓存
        if use_cache and self.cached_disks and self.cache_time:
            if time.time() - self.cache_time < cache_duration:
                return self.cached_disks
        
        # 重新扫描
        disks = []
        partitions = psutil.disk_partitions(all=True)
        
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info = {
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                }
                disks.append(disk_info)
            except PermissionError:
                continue
            except Exception as e:
                print(f"扫描磁盘时出错: {e}")
                continue
        
        # 更新缓存
        self.cached_disks = disks
        self.cache_time = time.time()
        
        return disks
    
    def get_disk_by_mountpoint(self, mountpoint: str) -> Optional[Dict]:
        """
        根据挂载点获取磁盘信息
        
        Args:
            mountpoint: 挂载点路径
        
        Returns:
            Optional[Dict]: 磁盘信息，未找到返回 None
        """
        disks = self.get_all_disks()
        for disk in disks:
            if disk['mountpoint'].lower() == mountpoint.lower():
                return disk
        return None
    
    def format_bytes(self, bytes_value: int) -> str:
        """
        格式化字节数为人类可读格式
        
        Args:
            bytes_value: 字节数
        
        Returns:
            str: 格式化后的字符串
        """
        if bytes_value == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(bytes_value)
        
        while size >= 1024 and i < len(size_names) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.2f} {size_names[i]}"


class DiskAnalyzer:
    """
    磁盘空间分析模块（整合版）
    职责:
    1. 分析指定目录的磁盘使用情况
    2. 识别大文件和占用空间的目录
    3. 与磁盘扫描器协同工作
    """
    
    def __init__(self):
        self.scanner = DiskScanner()  # 使用磁盘扫描器
        self.disk_info = {}
    
    def get_all_disks(self) -> List[Dict]:
        """获取所有磁盘信息（使用磁盘扫描器）"""
        return self.scanner.get_all_disks()
    
    def get_disk_for_path(self, path: str) -> Optional[Dict]:
        """
        获取指定路径所在的磁盘信息
        
        Args:
            path: 文件或目录路径
        
        Returns:
            Optional[Dict]: 磁盘信息
        """
        path = os.path.abspath(path)
        
        # 查找匹配的磁盘
        disks = self.get_all_disks()
        best_match = None
        
        for disk in disks:
            mountpoint = disk['mountpoint']
            if path.startswith(mountpoint):
                # 找到更长的匹配（更具体的挂载点）
                if best_match is None or len(mountpoint) > len(best_match['mountpoint']):
                    best_match = disk
        
        return best_match
    
    def analyze_directory(self, path: str, max_depth: int = 3, cancel_callback=None, progress_callback=None, max_files: int = 10000) -> Dict:
        """分析指定目录的磁盘使用情况（改进版）
        
        Args:
            path: 要分析的路径
            max_depth: 最大扫描深度
            cancel_callback: 取消回调函数，返回 True 表示应该取消
            progress_callback: 进度回调函数，参数为 (percent, message)
            max_files: 最大扫描文件数限制
        """
        if not os.path.exists(path):
            return {'error': '路径不存在', 'path': path}
        
        if not os.path.isdir(path):
            return {'error': '路径不是目录', 'path': path}
        
        result = {
            'path': path,
            'total_size': 0,
            'file_count': 0,
            'dir_count': 0,
            'directories': [],
            'cancelled': False
        }
        
        file_counter = 0  # 用于定期检查取消状态
        cancel_check_interval = 50  # 每处理50个文件检查一次
        progress_check_interval = 100  # 每处理100个文件更新一次进度
        
        # 发送初始进度
        if progress_callback:
            progress_callback(0, "开始分析...")
        
        try:
            for root, dirs, files in os.walk(path):
                # 检查是否应该取消
                if cancel_callback and cancel_callback():
                    result['cancelled'] = True
                    result['directories'].sort(key=lambda x: x['size'], reverse=True)
                    return result
                
                depth = root[len(path):].count(os.sep)
                if depth > max_depth:
                    dirs[:] = []  # 不继续深入子目录
                    continue
                
                # 跳过系统目录
                system_dirs = [
                    'system volume information', 
                    '$recycle.bin',
                    'program files',
                    'program files (x86)',
                    'programdata',
                    'windows',
                    '$windows',
                    '$winreagent',
                    'boot',
                    'recovery'
                ]
                dirs[:] = [d for d in dirs if not d.startswith('$') and d.lower() not in system_dirs]
                
                dir_size = 0
                file_count = 0
                
                for file in files:
                    # 检查文件数量限制
                    if file_counter >= max_files:
                        if progress_callback:
                            progress_callback(95, f"已达到最大文件数限制: {max_files}")
                        break
                    
                    # 定期检查取消状态和更新进度
                    file_counter += 1
                    if file_counter % cancel_check_interval == 0 and cancel_callback and cancel_callback():
                        result['cancelled'] = True
                        result['directories'].sort(key=lambda x: x['size'], reverse=True)
                        return result
                    
                    # 定期更新进度
                    if file_counter % progress_check_interval == 0 and progress_callback:
                        # 估算进度：假设最多扫描 max_files 个文件
                        progress = min(20 + int(file_counter / max_files * 70), 90)
                        progress_callback(progress, f"正在扫描... 已处理 {file_counter} 个文件")
                    
                    try:
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        dir_size += file_size
                        file_count += 1
                        result['total_size'] += file_size
                        result['file_count'] += 1
                    except (PermissionError, OSError):
                        continue
                
                if depth > 0:  # 不包含根目录
                    result['directories'].append({
                        'path': root,
                        'size': dir_size,
                        'file_count': file_count
                    })
                
                result['dir_count'] += 1
        
        except PermissionError:
            result['error'] = '权限不足，无法访问某些目录'
        except OSError as e:
            result['error'] = f'系统错误: {str(e)}'
        except Exception as e:
            result['error'] = f'未知错误: {str(e)}'
        
        # 按大小排序
        result['directories'].sort(key=lambda x: x['size'], reverse=True)
        
        # 添加磁盘信息（与磁盘扫描器协同）
        disk_info = self.get_disk_for_path(path)
        if disk_info:
            result['disk'] = {
                'device': disk_info['device'],
                'mountpoint': disk_info['mountpoint'],
                'fstype': disk_info['fstype'],
                'total': disk_info['total'],
                'used': disk_info['used'],
                'free': disk_info['free'],
                'percent': disk_info['percent']
            }
            
            # 计算分析目录占磁盘的百分比
            if disk_info['total'] > 0:
                result['disk_usage_percent'] = round((result['total_size'] / disk_info['total']) * 100, 2)
            else:
                result['disk_usage_percent'] = 0
        else:
            result['disk'] = None
            result['disk_usage_percent'] = None
        
        return result
    
    def find_large_files(self, path: str, min_size_mb: int = 100) -> List[Dict]:
        """查找大文件"""
        large_files = []
        min_size_bytes = min_size_mb * 1024 * 1024
        
        if not os.path.exists(path):
            return large_files
        
        try:
            for root, _, files in os.walk(path):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        
                        if file_size >= min_size_bytes:
                            large_files.append({
                                'path': file_path,
                                'size': file_size,
                                'size_mb': file_size / (1024 * 1024),
                                'modified': os.path.getmtime(file_path)
                            })
                    except (PermissionError, OSError):
                        continue
        
        except PermissionError:
            pass
        
        # 按大小排序
        large_files.sort(key=lambda x: x['size'], reverse=True)
        
        return large_files
    
    def get_file_type_distribution(self, path: str) -> Dict[str, int]:
        """获取文件类型分布"""
        type_sizes = defaultdict(int)
        
        if not os.path.exists(path):
            return dict(type_sizes)
        
        try:
            for root, _, files in os.walk(path):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        ext = os.path.splitext(file)[1].lower() or '无扩展名'
                        type_sizes[ext] += file_size
                    except (PermissionError, OSError):
                        continue
        
        except PermissionError:
            pass
        
        # 按大小排序
        sorted_types = dict(sorted(type_sizes.items(), key=lambda x: x[1], reverse=True))
        return sorted_types
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"