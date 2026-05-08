import os
import shutil
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class LargeFileManager:
    """大文件管理模块"""
    
    def __init__(self):
        self.large_files = []
    
    def find_large_files(self, path: str, min_size_mb: int = 100, 
                         max_results: int = 1000, cancel_callback=None, progress_callback=None) -> List[Dict]:
        """查找大文件
        
        Args:
            path: 要扫描的路径
            min_size_mb: 最小文件大小（MB）
            max_results: 最大结果数
            cancel_callback: 取消回调函数，返回 True 表示应该取消
            progress_callback: 进度回调函数，参数为 (percent, message)
        """
        large_files = []
        min_size_bytes = min_size_mb * 1024 * 1024
        file_counter = 0
        total_files_scanned = 0
        progress_check_interval = 50
        max_scan_files = 50000  # 增加最大扫描文件数限制
        
        if not os.path.exists(path):
            if progress_callback:
                progress_callback(100, "路径不存在")
            return large_files
        
        if progress_callback:
            progress_callback(0, f"开始扫描大文件（> {min_size_mb} MB）...")
        
        try:
            for root, dirs, files in os.walk(path):
                # 检查取消
                if cancel_callback and cancel_callback():
                    return large_files
                
                # 跳过系统目录和隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith('$') 
                          and not d.startswith('.') 
                          and d.lower() not in ['system volume information', '$recycle.bin', 
                                                  'program files', 'program files (x86)', 'windows']]
                
                for file in files:
                    # 检查取消
                    if cancel_callback and cancel_callback():
                        return large_files
                    
                    # 定期更新进度
                    file_counter += 1
                    total_files_scanned += 1
                    
                    if file_counter % progress_check_interval == 0 and progress_callback:
                        # 进度从10%开始，到95%结束，根据文件数动态调整
                        progress = min(10 + int(total_files_scanned / max_scan_files * 85), 95)
                        progress_callback(progress, f"正在扫描... 已检查 {total_files_scanned} 个文件，找到 {len(large_files)} 个大文件")
                    
                    try:
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        
                        if file_size >= min_size_bytes:
                            file_info = {
                                'path': file_path,
                                'name': file,
                                'size': file_size,
                                'size_mb': file_size / (1024 * 1024),
                                'size_gb': file_size / (1024 * 1024 * 1024),
                                'extension': os.path.splitext(file)[1].lower(),
                                'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
                                'created': datetime.fromtimestamp(os.path.getctime(file_path))
                            }
                            large_files.append(file_info)
                            
                            # 限制结果数量
                            if len(large_files) >= max_results:
                                return large_files
                    except (PermissionError, OSError):
                        continue
        except PermissionError as e:
            if progress_callback:
                progress_callback(100, f"扫描完成（部分文件因权限限制无法访问），找到 {len(large_files)} 个大文件")
        except Exception as e:
            if progress_callback:
                progress_callback(100, f"扫描完成（遇到错误），找到 {len(large_files)} 个大文件")
        
        # 按大小排序
        large_files.sort(key=lambda x: x['size'], reverse=True)
        self.large_files = large_files
        
        if progress_callback:
            if len(large_files) > 0:
                progress_callback(100, f"扫描完成！共检查 {total_files_scanned} 个文件，找到 {len(large_files)} 个大文件（> {min_size_mb} MB）")
            else:
                progress_callback(100, f"扫描完成。共检查 {total_files_scanned} 个文件，未找到大于 {min_size_mb} MB 的文件")
        
        return large_files
    
    def filter_by_extension(self, extensions: List[str]) -> List[Dict]:
        """按文件扩展名过滤"""
        extensions_lower = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
                           for ext in extensions]
        return [f for f in self.large_files if f['extension'] in extensions_lower]
    
    def filter_by_age(self, days: int) -> List[Dict]:
        """按文件年龄过滤（超过指定天数的文件）"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        return [f for f in self.large_files if f['modified'] < cutoff_date]
    
    def get_size_distribution(self) -> Dict[str, Dict]:
        """获取大文件按扩展名的大小分布"""
        distribution = {}
        
        for file_info in self.large_files:
            ext = file_info['extension'] or '无扩展名'
            
            if ext not in distribution:
                distribution[ext] = {
                    'count': 0,
                    'total_size': 0,
                    'total_size_mb': 0,
                    'files': []
                }
            
            distribution[ext]['count'] += 1
            distribution[ext]['total_size'] += file_info['size']
            distribution[ext]['total_size_mb'] += file_info['size_mb']
            distribution[ext]['files'].append(file_info['path'])
        
        # 按总大小排序
        sorted_distribution = dict(
            sorted(distribution.items(), key=lambda x: x[1]['total_size'], reverse=True)
        )
        
        return sorted_distribution
    
    def get_top_files(self, limit: int = 20) -> List[Dict]:
        """获取最大的N个文件"""
        return self.large_files[:limit]
    
    def rename_file(self, file_path: str, new_name: str) -> Tuple[bool, str]:
        """重命名文件
        
        Args:
            file_path: 原文件路径
            new_name: 新文件名（仅文件名，不包含路径）
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        # 获取文件所在目录
        dir_path = os.path.dirname(file_path)
        
        # 构建新路径
        new_path = os.path.join(dir_path, new_name)
        
        # 检查新文件名是否已存在
        if os.path.exists(new_path):
            return False, f"文件名 '{new_name}' 已存在"
        
        try:
            os.rename(file_path, new_path)
            return True, "重命名成功"
        except PermissionError:
            return False, "权限不足，无法重命名文件"
        except Exception as e:
            return False, f"重命名失败: {str(e)}"
    
    def delete_files(self, file_paths: List[str]) -> Tuple[int, int, int, List[str]]:
        """删除指定的文件
        
        Returns:
            Tuple[int, int, int, List[str]]: (成功数量, 失败数量, 释放空间(字节), 失败原因列表)
        """
        deleted_count = 0
        failed_count = 0
        freed_space = 0
        failed_reasons = []
        
        for file_path in file_paths:
            try:
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                deleted_count += 1
                freed_space += file_size
            except PermissionError:
                failed_count += 1
                failed_reasons.append(f"{file_path}: 权限不足")
            except FileNotFoundError:
                failed_count += 1
                failed_reasons.append(f"{file_path}: 文件不存在")
            except Exception as e:
                failed_count += 1
                failed_reasons.append(f"{file_path}: {str(e)}")
        
        return deleted_count, failed_count, freed_space, failed_reasons
    
    def move_files(self, file_paths: List[str], dest_dir: str) -> Tuple[int, int, List[str]]:
        """移动文件到指定目录
        
        Returns:
            Tuple[int, int, List[str]]: (成功数量, 失败数量, 失败原因列表)
        """
        moved_count = 0
        failed_count = 0
        failed_reasons = []
        
        if not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir)
            except Exception as e:
                failed_count = len(file_paths)
                failed_reasons.append(f"无法创建目标目录 {dest_dir}: {str(e)}")
                return moved_count, failed_count, failed_reasons
        
        for file_path in file_paths:
            try:
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(dest_dir, file_name)
                
                # 如果目标文件已存在，添加序号
                counter = 1
                while os.path.exists(dest_path):
                    name, ext = os.path.splitext(file_name)
                    dest_path = os.path.join(dest_dir, f"{name}_{counter}{ext}")
                    counter += 1
                
                shutil.move(file_path, dest_path)
                moved_count += 1
            except PermissionError:
                failed_count += 1
                failed_reasons.append(f"{file_path}: 权限不足")
            except FileNotFoundError:
                failed_count += 1
                failed_reasons.append(f"{file_path}: 源文件不存在")
            except Exception as e:
                failed_count += 1
                failed_reasons.append(f"{file_path}: {str(e)}")
        
        return moved_count, failed_count, failed_reasons
    
    def get_summary(self) -> Dict:
        """获取大文件摘要"""
        if not self.large_files:
            return {
                'total_count': 0,
                'total_size': 0,
                'total_size_mb': 0,
                'average_size': 0,
                'largest_file': None,
                'smallest_file': None
            }
        
        total_size = sum(f['size'] for f in self.large_files)
        
        return {
            'total_count': len(self.large_files),
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'total_size_gb': total_size / (1024 * 1024 * 1024),
            'average_size': total_size / len(self.large_files),
            'largest_file': self.large_files[0] if self.large_files else None,
            'smallest_file': self.large_files[-1] if self.large_files else None
        }
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    @staticmethod
    def is_media_file(extension: str) -> bool:
        """判断是否为媒体文件"""
        media_extensions = {
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',  # 视频
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',  # 音频
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'  # 图片
        }
        return extension.lower() in media_extensions
    
    @staticmethod
    def is_archive_file(extension: str) -> bool:
        """判断是否为压缩文件"""
        archive_extensions = {
            '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'
        }
        return extension.lower() in archive_extensions
    
    @staticmethod
    def is_document_file(extension: str) -> bool:
        """判断是否为文档文件"""
        document_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.rtf', '.odt', '.ods', '.odp'
        }
        return extension.lower() in document_extensions