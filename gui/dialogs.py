"""
对话框模块
"""

from PyQt6.QtWidgets import QDialog

class BaseDialog(QDialog):
    def __init__(self):
        super().__init__() 