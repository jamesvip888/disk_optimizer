# -*- coding: utf-8 -*-
"""
磁盘优化器 Professional
三个功能：磁盘概览、空间分析、大文件管理
"""

import sys
import os
import traceback
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal, QMutex, QMutexLocker
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QTabWidget, QGroupBox, QMessageBox, QFileDialog, QAbstractItemView
)
from PySide6.QtGui import QFont, QColor, QBrush

from disk_analyzer import DiskAnalyzer
from large_file_manager import LargeFileManager


# ============ ScanThread ============

class ScanThread(QThread):
    """后台扫描线程"""
    
    progress = Signal(int, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, task_type, params=None):
        super().__init__()
        self.task_type = task_type
        self.params = params or {}
        self.mutex = QMutex()
        self.is_cancelled = False

    def cancel(self):
        with QMutexLocker(self.mutex):
            self.is_cancelled = True

    def run(self):
        try:
            if self.is_cancelled:
                self.finished.emit({'cancelled': True})
                return

            if self.task_type == 'disks':
                analyzer = DiskAnalyzer()
                self.finished.emit({'disks': analyzer.get_all_disks()})

            elif self.task_type == 'analyze':
                path = self.params.get('path', 'C:\\')
                max_depth = self.params.get('max_depth', 3)
                analyzer = DiskAnalyzer()
                self.progress.emit(0, f'开始分析 {path}...')

                def cancel_cb():
                    with QMutexLocker(self.mutex):
                        return self.is_cancelled

                def progress_cb(pct, msg):
                    self.progress.emit(pct, msg)

                result = analyzer.analyze_directory(
                    path,
                    max_depth=max_depth,
                    cancel_callback=cancel_cb,
                    progress_callback=progress_cb
                )
                if not self.is_cancelled:
                    self.progress.emit(100, '分析完成')
                    self.finished.emit(result)

            elif self.task_type == 'large_files':
                path = self.params.get('path', 'C:\\')
                min_size = self.params.get('min_size', 100)
                manager = LargeFileManager()
                self.progress.emit(0, f'开始查找大文件（> {min_size} MB）...')

                def cancel_cb():
                    with QMutexLocker(self.mutex):
                        return self.is_cancelled

                def progress_cb(pct, msg):
                    self.progress.emit(pct, msg)

                files = manager.find_large_files(
                    path, min_size,
                    cancel_callback=cancel_cb,
                    progress_callback=progress_cb
                )

                summary = manager.get_summary()
                if self.is_cancelled:
                    self.finished.emit({
                        'files': files,
                        'summary': summary,
                        'cancelled': True
                    })
                else:
                    self.progress.emit(100, f'查找完成，找到 {len(files)} 个文件')
                    self.finished.emit({
                        'files': files,
                        'summary': summary
                    })

        except MemoryError:
            self.error.emit('内存不足，请关闭其他程序后重试')
        except PermissionError as e:
            self.error.emit(f'权限不足: {e}')
        except Exception as e:
            self.error.emit(f'{e}\n\n{traceback.format_exc()}')


# ============ 主窗口 ============

class DiskOptimizerUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('磁盘优化器 Professional')
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(900, 600)

        self.analyzer = DiskAnalyzer()
        self.file_manager = LargeFileManager()
        self.current_files = []

        self.thread = None
        self.thread_mutex = QMutex()

        self._init_ui()
        self._apply_styles()

    # ==================== UI 构建 ====================

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title = QLabel('磁盘优化器 Professional')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Microsoft YaHei', 18, QFont.Weight.Bold))
        main_layout.addWidget(title)

        # Tab 容器
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 构建 3 个 Tab
        self._build_overview_tab()
        self._build_analysis_tab()
        self._build_large_files_tab()

        # 底部状态栏
        self.status_label = QLabel('就绪')
        self.statusBar().addWidget(self.status_label, 1)

        # 状态栏进度
        self.status_progress = QProgressBar()
        self.status_progress.setMaximumWidth(300)
        self.status_progress.setMaximumHeight(16)
        self.status_progress.setTextVisible(True)
        self.statusBar().addPermanentWidget(self.status_progress)

    # ---------- Tab 1: 磁盘概览 ----------

    def _build_overview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)

        # 按钮行
        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton('  刷新磁盘信息  ')
        self.refresh_btn.clicked.connect(self._refresh_disks)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()

        self.disk_info_label = QLabel('')
        btn_row.addWidget(self.disk_info_label)
        layout.addLayout(btn_row)

        # 磁盘表格
        self.disk_table = QTableWidget()
        self.disk_table.setColumnCount(7)
        self.disk_table.setHorizontalHeaderLabels([
            '磁盘', '挂载点', '文件系统', '总容量', '已用', '可用', '使用率'
        ])
        header = self.disk_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.disk_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.disk_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.disk_table.setAlternatingRowColors(True)
        layout.addWidget(self.disk_table)

        self.tab_widget.addTab(tab, '  磁盘概览  ')

    # ---------- Tab 2: 空间分析 ----------

    def _build_analysis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)

        # 控制区
        ctrl_group = QGroupBox('分析设置')
        ctrl_layout = QVBoxLayout(ctrl_group)

        # 路径行
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel('分析路径:'))
        self.analysis_path = QComboBox()
        self.analysis_path.setEditable(True)
        self.analysis_path.setMinimumWidth(300)
        path_row.addWidget(self.analysis_path, 1)

        browse_btn = QPushButton('浏览...')
        browse_btn.clicked.connect(self._browse_analysis_path)
        path_row.addWidget(browse_btn)
        ctrl_layout.addLayout(path_row)

        # 参数行
        param_row = QHBoxLayout()
        param_row.addWidget(QLabel('扫描深度:'))
        self.analysis_depth = QSpinBox()
        self.analysis_depth.setRange(1, 10)
        self.analysis_depth.setValue(3)
        self.analysis_depth.setToolTip('控制目录递归深度，值越大扫描越深入但耗时越长')
        param_row.addWidget(self.analysis_depth)

        self.start_analysis_btn = QPushButton('  开始分析  ')
        self.start_analysis_btn.clicked.connect(self._start_analysis)
        param_row.addWidget(self.start_analysis_btn)

        self.cancel_analysis_btn = QPushButton('取消')
        self.cancel_analysis_btn.clicked.connect(self._cancel_task)
        self.cancel_analysis_btn.setEnabled(False)
        param_row.addWidget(self.cancel_analysis_btn)
        param_row.addStretch()
        ctrl_layout.addLayout(param_row)

        layout.addWidget(ctrl_group)

        # 进度条
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setVisible(False)
        layout.addWidget(self.analysis_progress)

        # 分析结果信息区
        result_row = QHBoxLayout()
        self.analysis_summary = QLabel('选择路径后点击开始分析')
        result_row.addWidget(self.analysis_summary)
        result_row.addStretch()
        layout.addLayout(result_row)

        # 结果表格
        self.analysis_table = QTableWidget()
        self.analysis_table.setColumnCount(4)
        self.analysis_table.setHorizontalHeaderLabels(['目录路径', '占用空间', '文件数', '占比'])
        header = self.analysis_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.analysis_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.analysis_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.analysis_table.setAlternatingRowColors(True)
        layout.addWidget(self.analysis_table)

        self.tab_widget.addTab(tab, '  空间分析  ')

    # ---------- Tab 3: 大文件管理 ----------

    def _build_large_files_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)

        # 控制区
        ctrl_group = QGroupBox('查找设置')
        ctrl_layout = QVBoxLayout(ctrl_group)

        # 路径行
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel('扫描路径:'))
        self.lf_path = QComboBox()
        self.lf_path.setEditable(True)
        self.lf_path.setMinimumWidth(300)
        path_row.addWidget(self.lf_path, 1)

        browse_btn = QPushButton('浏览...')
        browse_btn.clicked.connect(self._browse_lf_path)
        path_row.addWidget(browse_btn)
        ctrl_layout.addLayout(path_row)

        # 参数行
        param_row = QHBoxLayout()
        param_row.addWidget(QLabel('最小文件大小:'))
        self.lf_min_size = QSpinBox()
        self.lf_min_size.setRange(1, 10240)
        self.lf_min_size.setValue(100)
        self.lf_min_size.setSuffix(' MB')
        param_row.addWidget(self.lf_min_size)

        self.start_lf_btn = QPushButton('  查找大文件  ')
        self.start_lf_btn.clicked.connect(self._find_large_files)
        param_row.addWidget(self.start_lf_btn)

        self.cancel_lf_btn = QPushButton('取消')
        self.cancel_lf_btn.clicked.connect(self._cancel_task)
        self.cancel_lf_btn.setEnabled(False)
        param_row.addWidget(self.cancel_lf_btn)
        param_row.addStretch()
        ctrl_layout.addLayout(param_row)

        layout.addWidget(ctrl_group)

        # 进度条
        self.lf_progress = QProgressBar()
        self.lf_progress.setVisible(False)
        layout.addWidget(self.lf_progress)

        # 结果统计
        stats_row = QHBoxLayout()
        self.lf_summary = QLabel('选择路径后点击查找')
        stats_row.addWidget(self.lf_summary)
        stats_row.addStretch()

        # 操作按钮
        self.lf_delete_btn = QPushButton('删除选中')
        self.lf_delete_btn.setStyleSheet('background-color: #e53935; color: white;')
        self.lf_delete_btn.clicked.connect(self._delete_selected_files)
        self.lf_delete_btn.setEnabled(False)
        stats_row.addWidget(self.lf_delete_btn)

        self.lf_move_btn = QPushButton('移动选中')
        self.lf_move_btn.setStyleSheet('background-color: #1e88e5; color: white;')
        self.lf_move_btn.clicked.connect(self._move_selected_files)
        self.lf_move_btn.setEnabled(False)
        stats_row.addWidget(self.lf_move_btn)

        self.lf_open_btn = QPushButton('打开位置')
        self.lf_open_btn.setStyleSheet('background-color: #43a047; color: white;')
        self.lf_open_btn.clicked.connect(self._open_file_location)
        self.lf_open_btn.setEnabled(False)
        stats_row.addWidget(self.lf_open_btn)

        self.lf_refresh_btn = QPushButton('刷新')
        self.lf_refresh_btn.clicked.connect(self._find_large_files)
        self.lf_refresh_btn.setEnabled(False)
        stats_row.addWidget(self.lf_refresh_btn)

        layout.addLayout(stats_row)

        # 文件表格
        self.lf_table = QTableWidget()
        self.lf_table.setColumnCount(5)
        self.lf_table.setHorizontalHeaderLabels(['文件名', '路径', '大小', '类型', '修改时间'])
        header = self.lf_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.lf_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lf_table.setAlternatingRowColors(True)
        self.lf_table.itemSelectionChanged.connect(self._on_lf_selection_changed)
        layout.addWidget(self.lf_table)

        self.tab_widget.addTab(tab, '  大文件管理  ')

    # ==================== 磁盘概览 ====================

    def _refresh_disks(self):
        self._start_task('disks')
        self.refresh_btn.setEnabled(False)
        self.disk_info_label.setText('正在获取磁盘信息...')

    def _display_disks(self, data):
        disks = data.get('disks', [])
        self.disk_table.setRowCount(len(disks))

        for row, d in enumerate(disks):
            # 磁盘
            item_dev = QTableWidgetItem(d['device'])
            item_dev.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
            self.disk_table.setItem(row, 0, item_dev)

            # 挂载点
            self.disk_table.setItem(row, 1, QTableWidgetItem(d['mountpoint']))

            # 文件系统
            self.disk_table.setItem(row, 2, QTableWidgetItem(d.get('fstype', '未知')))

            # 总容量
            self.disk_table.setItem(row, 3, QTableWidgetItem(self.analyzer.format_size(d['total'])))

            # 已用
            used_pct = d['percent']
            used_str = f"{self.analyzer.format_size(d['used'])} ({used_pct:.1f}%)"
            item_used = QTableWidgetItem(used_str)
            # 已用超过80%标红
            if used_pct > 80:
                item_used.setForeground(QBrush(QColor('#e53935')))
            elif used_pct > 60:
                item_used.setForeground(QBrush(QColor('#ff8f00')))
            self.disk_table.setItem(row, 4, item_used)

            # 可用
            free_item = QTableWidgetItem(self.analyzer.format_size(d['free']))
            if d['free'] < 10 * 1024**3:  # 少于10GB
                free_item.setForeground(QBrush(QColor('#e53935')))
            self.disk_table.setItem(row, 5, free_item)

            # 使用率 - 自绘进度条
            bar_item = QTableWidgetItem()
            bar_item.setData(Qt.ItemDataRole.DisplayRole, f"{used_pct:.1f}%")
            bar_item.setData(Qt.ItemDataRole.UserRole, used_pct)
            self.disk_table.setItem(row, 6, bar_item)

        self.refresh_btn.setEnabled(True)
        self.disk_info_label.setText(f'共 {len(disks)} 个磁盘分区')
        self.status_label.setText(f'磁盘信息已刷新 ({datetime.now().strftime("%H:%M:%S")})')

    # ==================== 空间分析 ====================

    def _browse_analysis_path(self):
        path = QFileDialog.getExistingDirectory(self, '选择要分析的目录')
        if path:
            self.analysis_path.setCurrentText(path)

    def _start_analysis(self):
        path = self.analysis_path.currentText().strip()
        if not path:
            QMessageBox.warning(self, '提示', '请输入或选择要分析的路径')
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, '提示', f'路径不是有效目录:\n{path}')
            return

        self.analysis_table.setRowCount(0)
        self.analysis_summary.setText('正在分析...')
        self.analysis_progress.setVisible(True)
        self.analysis_progress.setValue(0)

        self._start_task('analyze', {
            'path': path,
            'max_depth': self.analysis_depth.value()
        })

    def _display_analysis(self, data):
        self.analysis_progress.setVisible(False)

        if data.get('cancelled'):
            self.analysis_summary.setText('分析已取消')
            self._reset_analysis_buttons()
            return

        if 'error' in data:
            self.analysis_summary.setText(f'分析失败: {data["error"]}')
            self._reset_analysis_buttons()
            return

        dirs = data.get('directories', [])
        total_size = data.get('total_size', 0)
        file_count = data.get('file_count', 0)
        dir_count = data.get('dir_count', 0)
        path = data.get('path', '')

        # 更新统计
        self.analysis_summary.setText(
            f'路径: {path}  |  总大小: {self.analyzer.format_size(total_size)}  |  '
            f'文件: {file_count}  |  目录: {dir_count}  |  结果: {len(dirs)} 个子目录'
        )

        # 填充表格
        self.analysis_table.setRowCount(len(dirs))
        for row, d in enumerate(dirs):
            # 目录路径 - 相对路径
            rel_path = d['path']
            if path and rel_path.startswith(path):
                rel_path = rel_path[len(path):].lstrip(os.sep)
            path_item = QTableWidgetItem(rel_path)
            path_item.setToolTip(d['path'])  # 悬停显示完整路径
            self.analysis_table.setItem(row, 0, path_item)

            # 占用空间
            size_str = self.analyzer.format_size(d['size'])
            size_item = QTableWidgetItem(size_str)
            # 大目录标色
            if total_size > 0:
                pct = d['size'] / total_size * 100
                if pct > 10:
                    size_item.setForeground(QBrush(QColor('#e53935')))
                    size_item.setFont(QFont('Microsoft YaHei', 9, QFont.Weight.Bold))
                elif pct > 5:
                    size_item.setForeground(QBrush(QColor('#ff8f00')))
            self.analysis_table.setItem(row, 1, size_item)

            # 文件数
            self.analysis_table.setItem(row, 2, QTableWidgetItem(str(d['file_count'])))

            # 占比
            if total_size > 0:
                pct = d['size'] / total_size * 100
                pct_item = QTableWidgetItem(f'{pct:.2f}%')
                if pct > 10:
                    pct_item.setForeground(QBrush(QColor('#e53935')))
                self.analysis_table.setItem(row, 3, pct_item)
            else:
                self.analysis_table.setItem(row, 3, QTableWidgetItem('0.00%'))

        self._reset_analysis_buttons()
        self.status_label.setText(
            f'空间分析完成: {self.analyzer.format_size(total_size)}, {len(dirs)} 个目录'
        )

    def _reset_analysis_buttons(self):
        self.start_analysis_btn.setEnabled(True)
        self.cancel_analysis_btn.setEnabled(False)

    # ==================== 大文件管理 ====================

    def _browse_lf_path(self):
        path = QFileDialog.getExistingDirectory(self, '选择要扫描的目录')
        if path:
            self.lf_path.setCurrentText(path)

    def _find_large_files(self):
        path = self.lf_path.currentText().strip()
        if not path:
            QMessageBox.warning(self, '提示', '请输入或选择要扫描的路径')
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, '提示', f'路径不是有效目录:\n{path}')
            return

        self.lf_table.setRowCount(0)
        self.lf_summary.setText('正在查找...')
        self.lf_progress.setVisible(True)
        self.lf_progress.setValue(0)

        self._start_task('large_files', {
            'path': path,
            'min_size': self.lf_min_size.value()
        })

    def _display_large_files(self, data):
        self.lf_progress.setVisible(False)

        if data.get('cancelled'):
            self.lf_summary.setText('查找已取消')
            self._reset_lf_buttons()
            return

        files = data.get('files', [])
        summary = data.get('summary', {})

        # 更新统计
        total_count = summary.get('total_count', 0)
        total_size = summary.get('total_size', 0)
        total_gb = summary.get('total_size_gb', 0)
        self.lf_summary.setText(
            f'找到 {total_count} 个大文件, 共 {self.analyzer.format_size(total_size)} '
            f'({total_gb:.2f} GB)'
        )

        # 填充表格
        self.lf_table.setRowCount(len(files))
        for row, f in enumerate(files):
            # 文件名
            self.lf_table.setItem(row, 0, QTableWidgetItem(f['name']))

            # 路径
            path_item = QTableWidgetItem(f['path'])
            path_item.setToolTip(f['path'])
            self.lf_table.setItem(row, 1, path_item)

            # 大小
            size_str = f"{f['size_gb']:.2f} GB" if f['size_gb'] >= 1 else f"{f['size_mb']:.2f} MB"
            size_item = QTableWidgetItem(size_str)
            size_item.setData(Qt.ItemDataRole.UserRole, f['size'])  # 存原始大小用于排序
            if f['size_gb'] >= 1:
                size_item.setFont(QFont('Microsoft YaHei', 9, QFont.Weight.Bold))
            self.lf_table.setItem(row, 2, size_item)

            # 类型
            ext = f.get('extension', '') or '(无)'
            ext_item = QTableWidgetItem(ext)
            # 按类型标色
            if LargeFileManager.is_media_file(ext):
                ext_item.setForeground(QBrush(QColor('#1e88e5')))
            elif LargeFileManager.is_archive_file(ext):
                ext_item.setForeground(QBrush(QColor('#ff8f00')))
            elif LargeFileManager.is_document_file(ext):
                ext_item.setForeground(QBrush(QColor('#43a047')))
            self.lf_table.setItem(row, 3, ext_item)

            # 修改时间
            mod = f.get('modified')
            if mod:
                if isinstance(mod, datetime):
                    time_str = mod.strftime('%Y-%m-%d %H:%M')
                else:
                    time_str = str(mod)
            else:
                time_str = ''
            self.lf_table.setItem(row, 4, QTableWidgetItem(time_str))

        self.current_files = files
        self._reset_lf_buttons()
        self.lf_refresh_btn.setEnabled(True)
        self.status_label.setText(
            f'大文件查找完成: {len(files)} 个文件, {self.analyzer.format_size(total_size)}'
        )

    def _on_lf_selection_changed(self):
        rows = self.lf_table.selectionModel().selectedRows()
        has_selection = len(rows) > 0
        self.lf_delete_btn.setEnabled(has_selection)
        self.lf_move_btn.setEnabled(has_selection)
        self.lf_open_btn.setEnabled(len(rows) == 1)

    def _get_selected_file_paths(self):
        """获取表格中选中行的文件路径"""
        paths = []
        for row_index in self.lf_table.selectionModel().selectedRows():
            row = row_index.row()
            item = self.lf_table.item(row, 1)
            if item:
                paths.append(item.text())
        return paths

    def _delete_selected_files(self):
        paths = self._get_selected_file_paths()
        if not paths:
            return

        total_size = 0
        for p in paths:
            try:
                total_size += os.path.getsize(p)
            except OSError:
                pass

        reply = QMessageBox.warning(
            self, '确认删除',
            f'确定要删除 {len(paths)} 个文件吗？\n\n'
            f'将释放约 {self.analyzer.format_size(total_size)} 空间\n'
            f'此操作不可撤销！',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, fail, freed, reasons = self.file_manager.delete_files(paths)

        msg = f'成功删除: {ok} 个文件\n释放空间: {self.analyzer.format_size(freed)}'
        if fail > 0:
            msg += f'\n失败: {fail} 个文件'
            for r in reasons[:5]:
                msg += f'\n  - {r}'
            if len(reasons) > 5:
                msg += f'\n  ... 还有 {len(reasons)-5} 个错误'

        QMessageBox.information(self, '删除结果', msg)
        # 刷新列表
        self._find_large_files()

    def _move_selected_files(self):
        paths = self._get_selected_file_paths()
        if not paths:
            return

        dest = QFileDialog.getExistingDirectory(self, '选择目标文件夹')
        if not dest:
            return

        ok, fail, reasons = self.file_manager.move_files(paths, dest)

        msg = f'成功移动: {ok} 个文件到:\n{dest}'
        if fail > 0:
            msg += f'\n失败: {fail} 个文件'
            for r in reasons[:5]:
                msg += f'\n  - {r}'

        QMessageBox.information(self, '移动结果', msg)
        self._find_large_files()

    def _open_file_location(self):
        rows = self.lf_table.selectionModel().selectedRows()
        if len(rows) != 1:
            return
        row = rows[0].row()
        item = self.lf_table.item(row, 1)
        if item:
            import subprocess
            subprocess.Popen(['explorer', '/select,', item.text()])

    def _reset_lf_buttons(self):
        self.start_lf_btn.setEnabled(True)
        self.cancel_lf_btn.setEnabled(False)

    # ==================== 线程管理 ====================

    def _start_task(self, task_type, params=None):
        with QMutexLocker(self.thread_mutex):
            # 如果有旧线程在运行，先停止
            if self.thread and self.thread.isRunning():
                self.thread.cancel()
                self.thread.quit()
                self.thread.wait(3000)

            self.thread = ScanThread(task_type, params)
            self.thread.progress.connect(self._on_progress)
            self.thread.finished.connect(self._on_task_finished)
            self.thread.error.connect(self._on_task_error)

            # 根据任务类型禁用对应按钮
            if task_type == 'analyze':
                self.start_analysis_btn.setEnabled(False)
                self.cancel_analysis_btn.setEnabled(True)
            elif task_type == 'large_files':
                self.start_lf_btn.setEnabled(False)
                self.cancel_lf_btn.setEnabled(True)

            self.thread.start()

    def _cancel_task(self):
        with QMutexLocker(self.thread_mutex):
            if self.thread and self.thread.isRunning():
                self.thread.cancel()
        self.status_label.setText('正在取消...')

    def _on_progress(self, value, message):
        # 更新状态栏进度
        self.status_progress.setValue(value)
        self.status_label.setText(message)

        # 更新对应 Tab 的进度条
        if hasattr(self, 'analysis_progress') and self.analysis_progress.isVisible():
            self.analysis_progress.setValue(value)
        if hasattr(self, 'lf_progress') and self.lf_progress.isVisible():
            self.lf_progress.setValue(value)

    def _on_task_finished(self, result):
        self.status_progress.setValue(0)

        # 根据 ScanThread 的 task_type 分发结果
        # ScanThread 已结束，通过结果数据判断是哪种任务
        if 'disks' in result:
            self._display_disks(result)
        elif 'directories' in result or 'error' in result:
            self._display_analysis(result)
        elif 'files' in result:
            self._display_large_files(result)

        # 重置所有取消按钮
        self.cancel_analysis_btn.setEnabled(False)
        self.cancel_lf_btn.setEnabled(False)

    def _on_task_error(self, msg):
        self.status_progress.setValue(0)
        self.analysis_progress.setVisible(False)
        self.lf_progress.setVisible(False)
        QMessageBox.critical(self, '错误', msg)
        self._reset_analysis_buttons()
        self._reset_lf_buttons()
        self.refresh_btn.setEnabled(True)
        self.status_label.setText('操作失败')

    def _init_disk_lists(self):
        """初始化磁盘路径列表"""
        try:
            import psutil
            drives = []
            for p in psutil.disk_partitions():
                if p.device and len(p.device) >= 2:
                    d = p.device[:2]
                    if d not in drives:
                        drives.append(d)
            if drives:
                paths = [d + '\\' for d in drives]
                # 更新分析路径
                cur_analysis = self.analysis_path.currentText()
                self.analysis_path.clear()
                self.analysis_path.addItems(paths)
                if cur_analysis in paths:
                    self.analysis_path.setCurrentText(cur_analysis)
                # 更新大文件路径
                cur_lf = self.lf_path.currentText()
                self.lf_path.clear()
                self.lf_path.addItems(paths)
                if cur_lf in paths:
                    self.lf_path.setCurrentText(cur_lf)
        except Exception:
            pass

    def closeEvent(self, event):
        with QMutexLocker(self.thread_mutex):
            if self.thread and self.thread.isRunning():
                self.thread.cancel()
                self.thread.quit()
                self.thread.wait(3000)
        event.accept()

    # ==================== 样式 ====================

    def _apply_styles(self):
        self.setStyleSheet('''
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 12px;
                color: #333;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #555;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
                color: #757575;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fafafa;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 10px 30px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 13px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #eeeeee;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f9f9f9;
                gridline-color: #e8e8e8;
                border: 1px solid #ddd;
                border-radius: 4px;
                selection-background-color: #C8E6C9;
                selection-color: #1B5E20;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 6px 8px;
                border: none;
                border-bottom: 2px solid #4CAF50;
                font-weight: bold;
                font-size: 12px;
                color: #333;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: #f0f0f0;
                height: 20px;
                font-size: 11px;
                color: #333;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QComboBox {
                padding: 6px 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:focus {
                border-color: #4CAF50;
            }
            QSpinBox {
                padding: 6px 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QStatusBar {
                background-color: #fafafa;
                border-top: 1px solid #ddd;
            }
        ''')


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    win = DiskOptimizerUI()
    win.show()

    # 初始化磁盘列表后自动刷新
    win._init_disk_lists()
    win._refresh_disks()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
