from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QDialogButtonBox, QMessageBox

class RangeInputDialog(QDialog):
    def __init__(self, current_value: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑范围")
        self.setModal(True)

        # 创建布局
        layout = QVBoxLayout(self)

        # 创建水平布局
        h_layout = QHBoxLayout()
        min_value = current_value.split("~")[0].strip() if "~" in current_value else ""
        max_value = current_value.split("~")[1].strip() if "~" in current_value else ""
        self.min_input = QLineEdit(min_value)
        self.max_input = QLineEdit(max_value)
        h_layout.addWidget(self.min_input)
        h_layout.addWidget(QLabel("~"))
        h_layout.addWidget(self.max_input)

        # 创建按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # 将水平布局和按钮添加到主布局
        layout.addLayout(h_layout)
        layout.addWidget(button_box)

    @staticmethod
    def save(key, val):
        if "~" in val:
            parts = val.split("~")
            return key, [
                float(parts[0].strip()) if parts[0].strip() and "inf" not in parts[0] else "-inf",
                float(parts[1].strip()) if parts[1].strip() and "inf" not in parts[1] else "inf",
            ]
        else:
            return key, []

    def get_values(self):
        self.min_value = self.min_input.text()
        self.max_value = self.max_input.text()
        return f"{self.min_input.text()} ~ {self.max_input.text()}"

    def accept(self):
        self.get_values()

        # 判断输入的有效性
        if self.min_value and self.max_value:
            try:
                min_value = float(self.min_value)
                max_value = float(self.max_value)
                if min_value > max_value:
                    QMessageBox.warning(self, "输入错误", "最小值不能大于最大值。")
                    return
            except ValueError:
                QMessageBox.warning(self, "输入错误", "请输入有效的数字。")
                return

        # 更新范围值
        self.result = f"{self.min_value} ~ {self.max_value}"
        super().accept()

    def reject(self):
        self.result = None
        super().reject()