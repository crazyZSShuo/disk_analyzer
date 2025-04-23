#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTreeView, QLabel, QLineEdit, QMessageBox,
    QStatusBar, QHeaderView, QSizePolicy, QStyleFactory
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QMetaObject, Q_ARG, QSortFilterProxyModel

# 假设 disk_analyzer.py 在同一目录下
from disk_analyzer import get_available_drives, analyze_directory, format_size

# --- Custom Sort Filter Proxy Model ---
class SizeSortFilterProxyModel(QSortFilterProxyModel):
    def lessThan(self, left, right):
        # Sort by size (column 1)
        if left.column() == 1 and right.column() == 1:
            left_data = self.sourceModel().data(left, Qt.ItemDataRole.UserRole)
            right_data = self.sourceModel().data(right, Qt.ItemDataRole.UserRole)

            # Handle potential None or non-numeric data gracefully
            if isinstance(left_data, (int, float)) and isinstance(right_data, (int, float)):
                return left_data < right_data
            elif isinstance(left_data, (int, float)): # Place numbers before non-numbers (like N/A)
                return True
            elif isinstance(right_data, (int, float)):
                return False
            else: # If both are non-numeric, use default string comparison
                return super().lessThan(left, right)

        # Default comparison for other columns
        return super().lessThan(left, right)

# --- Analysis Worker (No changes needed here) ---
class AnalysisWorker(QObject):
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str, str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            items = analyze_directory(self.path)
            self.finished.emit(items, self.path)
        except PermissionError as e:
            self.error.emit(f"权限错误: {e}", self.path)
        except Exception as e:
            self.error.emit(f"分析时出错: {e}", self.path)

# --- Main Application Window ---
class DiskAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("磁盘空间分析器 (PyQt6)")
        self.setGeometry(100, 100, 900, 650) # Slightly larger window

        self.current_path = ""
        self.path_history = []

        # --- Central Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10) # Add margins
        main_layout.setSpacing(10) # Add spacing between widgets

        # --- Top Frame: Drive selection and navigation ---
        top_frame = QWidget()
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(top_frame)

        top_layout.addWidget(QLabel("驱动器:"))
        self.drive_combobox = QComboBox()
        self.drive_combobox.setFixedWidth(120)
        self.drive_combobox.currentIndexChanged.connect(self.on_drive_selected)
        top_layout.addWidget(self.drive_combobox)

        self.up_button = QPushButton("向上")
        self.up_button.setIcon(QIcon.fromTheme("go-up", QIcon("icons/go-up.png"))) # Placeholder icon
        self.up_button.setEnabled(False)
        self.up_button.setToolTip("返回上一级目录")
        self.up_button.clicked.connect(self.go_up)
        top_layout.addWidget(self.up_button)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh", QIcon("icons/view-refresh.png"))) # Placeholder icon
        self.refresh_button.setEnabled(False)
        self.refresh_button.setToolTip("重新分析当前目录")
        self.refresh_button.clicked.connect(self.refresh_view)
        top_layout.addWidget(self.refresh_button)

        top_layout.addStretch(1)

        # --- Current Path Display ---
        path_frame = QWidget()
        path_layout = QHBoxLayout(path_frame)
        path_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(path_frame)
        path_layout.addWidget(QLabel("当前路径:"))
        self.path_lineedit = QLineEdit()
        self.path_lineedit.setReadOnly(True)
        self.path_lineedit.setStyleSheet("background-color: #f0f0f0;") # Slightly different background
        path_layout.addWidget(self.path_lineedit)

        # --- Treeview for directory contents ---
        self.tree_view = QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.doubleClicked.connect(self.on_item_double_click)
        self.tree_view.setUniformRowHeights(True) # Optimization
        main_layout.addWidget(self.tree_view)

        self.source_model = QStandardItemModel()
        self.source_model.setHorizontalHeaderLabels(['名称', '大小', '类型', '路径']) # Keep original headers

        # Use the custom proxy model for sorting
        self.proxy_model = SizeSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.proxy_model.setSortRole(Qt.ItemDataRole.UserRole) # Tell proxy to use UserRole for sorting column 1

        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setColumnHidden(3, True) # Hide the full path column (in proxy model)

        # Adjust column widths (apply to the view, which uses the proxy model)
        header = self.tree_view.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tree_view.setColumnWidth(1, 150)
        self.tree_view.setColumnWidth(2, 100)

        # Set initial sort on the view (which controls the proxy model)
        self.tree_view.sortByColumn(1, Qt.SortOrder.DescendingOrder) # Sort by size descending initially

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # --- Initialization ---
        self.populate_drives()
        self.set_status("请选择一个驱动器开始分析。")
        self._apply_styles()

    def _apply_styles(self):
        # Apply a modern style if available
        available_styles = QStyleFactory.keys()
        if 'Fusion' in available_styles:
            QApplication.setStyle(QStyleFactory.create('Fusion'))
        elif 'WindowsVista' in available_styles:
             QApplication.setStyle(QStyleFactory.create('WindowsVista'))

        # Basic Stylesheet (can be expanded)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f8f8; /* Light background */
            }
            QTreeView {
                border: 1px solid #cccccc;
                font-size: 10pt; /* Slightly larger font */
            }
            QTreeView::item:selected {
                background-color: #cde8ff; /* Light blue selection */
                color: black;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #b0b0b0;
                border-radius: 3px;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #f0f0f0, stop:1 #e0e0e0);
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #e8f0f8, stop:1 #d8e8f8);
                border-color: #80a0c0;
            }
            QPushButton:pressed {
                background-color: #d0e0f0;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #a0a0a0;
            }
            QComboBox {
                padding: 3px 5px;
            }
            QLineEdit {
                padding: 3px 5px;
                border: 1px solid #cccccc;
                border-radius: 2px;
            }
            QLabel {
                padding: 2px;
            }
            QStatusBar {
                font-size: 9pt;
            }
        """)

    def set_status(self, message):
        self.status_bar.showMessage(message)

    def populate_drives(self):
        try:
            drives = get_available_drives()
            self.drive_combobox.clear()
            self.drive_combobox.addItem("请选择驱动器…")
            if drives:
                self.drive_combobox.addItems(drives)
            else:
                self.set_status("错误：未找到可用驱动器。")
                QMessageBox.critical(self, "错误", "未找到可用的本地驱动器。")
        except Exception as e:
            self.set_status(f"获取驱动器列表时出错: {e}")
            QMessageBox.critical(self, "错误", f"获取驱动器列表时出错:\n{e}")

    def on_drive_selected(self, index):
        selected_drive = self.drive_combobox.itemText(index)
        if index == 0 or selected_drive == "请选择驱动器…":
            self.current_path = ""
            self.path_history = []
            self.path_lineedit.setText("")
            self.source_model.removeRows(0, self.source_model.rowCount())
            self.set_status("欢迎使用磁盘空间分析器！\n\n本软件可帮助您快速分析各个磁盘或文件夹的空间占用情况。\n请选择上方的驱动器后开始分析。\n\n功能简介：\n- 直观展示各文件夹/文件大小\n- 支持排序、刷新、导航\n- 友好的操作体验\n\n感谢您的使用！")
            return
        if selected_drive:
            self.path_history = [selected_drive] # Reset history
            self.navigate_to(selected_drive)

    def navigate_to(self, path):
        path = os.path.normpath(path)

        if not os.path.isdir(path):
            QMessageBox.critical(self, "错误", f"路径无效或不是目录：\n{path}")
            if self.path_history:
                self.path_lineedit.setText(self.path_history[-1])
            else:
                self.path_lineedit.setText("")
            return

        self.current_path = path
        self.path_lineedit.setText(path)
        self.set_status(f"正在分析 {path} ... 请稍候。")
        self.source_model.removeRows(0, self.source_model.rowCount()) # Clear source model
        self.set_controls_enabled(False)

        # Run analysis in a separate thread
        self.analysis_thread = QThread()
        self.worker = AnalysisWorker(path)
        self.worker.moveToThread(self.analysis_thread)

        self.worker.finished.connect(self.update_treeview)
        self.worker.error.connect(self.show_error)
        self.analysis_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.analysis_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.analysis_thread.quit)
        self.worker.error.connect(self.worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)
        self.analysis_thread.finished.connect(lambda: self.set_controls_enabled(True))

        self.analysis_thread.start()

    def set_controls_enabled(self, enabled):
        self.drive_combobox.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        is_root = len(self.path_history) <= 1
        self.up_button.setEnabled(enabled and not is_root)

    def update_treeview(self, items, path):
        if path != self.current_path:
            return

        self.source_model.removeRows(0, self.source_model.rowCount()) # Clear source model

        if not items:
            self.set_status(f"目录 {path} 为空或无法访问。")
            return

        # No need to sort items here, proxy model handles it

        for item in items:
            name = item.get('name', '未知')
            size = item.get('size', 0)
            is_dir = item.get('is_dir', False)
            item_path = item.get('path', '')
            has_error = item.get('error', False)

            item_type = "文件夹" if is_dir else "文件"
            formatted_size = format_size(size) if not has_error else "N/A"
            display_name = f"{name} {'(无法访问)' if has_error else ''}"

            # Create items for the row
            name_item = QStandardItem(display_name)
            name_item.setEditable(False)
            icon = QIcon.fromTheme("folder", QIcon("icons/folder.png")) if is_dir else QIcon.fromTheme("text-x-generic", QIcon("icons/file.png"))
            name_item.setIcon(icon)

            size_item = QStandardItem(formatted_size)
            # Store raw size in UserRole for sorting by the proxy model
            size_item.setData(size if not has_error else -1, Qt.ItemDataRole.UserRole) # Use -1 for errors to sort them differently if needed
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size_item.setEditable(False)

            type_item = QStandardItem(item_type)
            type_item.setEditable(False)

            path_item = QStandardItem(item_path)
            path_item.setEditable(False)

            # Add row to source model
            self.source_model.appendRow([name_item, size_item, type_item, path_item])

        self.set_status(f"分析完成: {path}")
        # No need to manually sort here, the view/proxy handles it
        # sort_column = self.tree_view.header().sortIndicatorSection()
        # sort_order = self.tree_view.header().sortIndicatorOrder()
        # self.proxy_model.sort(sort_column, sort_order) # Sorting is handled by enabling it on the view

    def show_error(self, error_message, path):
         if path == self.current_path:
            self.set_status(f"错误: {error_message}")
            QMessageBox.critical(self, "分析错误", f"无法分析目录 '{path}':\n{error_message}")
            self.set_controls_enabled(True)

    def on_item_double_click(self, index):
        if not index.isValid():
            return

        # Map proxy index to source index before getting data from source model
        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid():
            return

        # Get data from the source model using the source index
        path_item = self.source_model.item(source_index.row(), 3)
        item_path = path_item.text() if path_item else ""

        type_item = self.source_model.item(source_index.row(), 2)
        item_type = type_item.text() if type_item else ""

        name_item = self.source_model.item(source_index.row(), 0)
        item_text = name_item.text() if name_item else ""

        if item_type == "文件夹":
            if "(无法访问)" in item_text:
                 QMessageBox.warning(self, "无法访问", f"无法访问文件夹:\n{item_path}")
                 return
            if item_path and os.path.isdir(item_path):
                self.path_history.append(item_path)
                self.navigate_to(item_path)
            else:
                QMessageBox.warning(self, "导航错误", f"无法导航到文件夹:\n{item_path}")

    def go_up(self):
        if len(self.path_history) > 1:
            self.path_history.pop()
            parent_path = self.path_history[-1]
            self.navigate_to(parent_path)
        self.up_button.setEnabled(len(self.path_history) > 1)

    def refresh_view(self):
        if self.current_path:
            self.navigate_to(self.current_path)

# --- Main Execution ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Ensure icons directory exists or handle gracefully
    icon_dir = os.path.join(os.path.dirname(__file__), 'icons')
    if not os.path.isdir(icon_dir):
        print(f"Warning: Icon directory not found at {icon_dir}", file=sys.stderr)
        # Consider creating it or disabling custom icons

    # Set fallback icon search paths if needed
    # QIcon.setThemeSearchPaths(QIcon.themeSearchPaths() + [icon_dir])
    # QIcon.setThemeName("default") # Or your theme name

    window = DiskAnalyzerApp()
    window.show()
    sys.exit(app.exec())