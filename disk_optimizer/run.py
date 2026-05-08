#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
磁盘优化器 Professional - 主程序入口
改进版：添加错误处理和用户体验优化
"""

import sys
import os
import traceback

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """检查必要的依赖"""
    missing = []
    optional_missing = []
    
    # 必需依赖
    try:
        import psutil
    except ImportError:
        missing.append("psutil")
    
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        missing.append("PySide6")
    
    # 可选依赖（警告但不阻止运行）
    try:
        import win32api
    except ImportError:
        optional_missing.append("pywin32")
    
    return missing, optional_missing

if __name__ == '__main__':
    print("=" * 50)
    print("磁盘优化器 Professional - 启动中...")
    print("=" * 50)
    print()
    
    # 检查依赖
    missing_deps, optional_missing = check_dependencies()
    
    # 处理可选依赖警告
    if optional_missing:
        print(f"[提示] 缺少可选依赖: {', '.join(optional_missing)}")
        print("程序可以正常运行，但某些功能可能受限")
        print(f"如需完整功能，请运行：pip install {' '.join(optional_missing)}")
        print()
    
    # 处理必需依赖
    if missing_deps:
        print("=" * 50)
        print("[错误] 缺少必要的依赖库")
        print("=" * 50)
        print(f"缺少的库：{', '.join(missing_deps)}")
        print()
        print("请运行以下命令安装依赖：")
        print(f"pip install {' '.join(missing_deps)}")
        print()
        
        # 尝试启动GUI显示错误（如果PySide6可用）
        if 'PySide6' not in missing_deps:
            try:
                from PySide6.QtWidgets import QApplication, QMessageBox
                from PySide6.QtCore import Qt
                app = QApplication(sys.argv)
                QMessageBox.critical(
                    None,
                    "缺少依赖",
                    f"程序缺少必要的依赖库：\n\n{', '.join(missing_deps)}\n\n"
                    f"请运行以下命令安装：\n"
                    f"pip install {' '.join(missing_deps)}"
                )
            except Exception as e:
                print(f"[警告] 无法显示错误对话框: {e}")
        
        print("按任意键退出...")
        input()
        sys.exit(1)
    
    try:
        # 导入主模块
        print("[信息] 正在加载主模块...")
        from ui_main import main
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        
        print("[信息] 设置高DPI支持...")
        # 设置高DPI支持
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        print("[信息] 启动主窗口...")
        # 运行主程序
        main()
        
    except ImportError as e:
        print("=" * 50)
        print("[错误] 无法导入主模块")
        print("=" * 50)
        print(f"详细信息：{e}")
        print()
        import traceback
        traceback.print_exc()
        print()
        print("按任意键退出...")
        input()
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("[信息] 程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print("=" * 50)
        print("[错误] 程序运行出错")
        print("=" * 50)
        print(f"错误信息：{e}")
        print()
        print("详细错误信息：")
        traceback.print_exc()
        print()
        
        # 如果GUI已启动，显示错误对话框
        if 'app' in locals():
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    None,
                    "程序错误",
                    f"程序运行出错：\n\n{str(e)}\n\n"
                    f"详细错误信息已输出到控制台。"
                )
            except:
                pass
        
        print("按任意键退出...")
        input()
        sys.exit(1)