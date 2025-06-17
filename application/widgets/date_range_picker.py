import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel

from qfluentwidgets import CalendarPicker, MessageBox


class DateRangeSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("日期范围选择器 (Fluent UI)")
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # 创建 Fluent CalendarPicker 控件
        self.calendar_picker = CalendarPicker()
        self.calendar_picker.setMultiSelection(True)  # 启用多选模式（用于选择范围）
        layout.addWidget(self.calendar_picker)

        # 显示结果的标签
        self.label_result = QLabel("请选择日期范围")
        layout.addWidget(self.label_result)

        # 获取日期按钮
        self.btn_get_dates = QPushButton("获取日期范围")
        self.btn_get_dates.clicked.connect(self.show_selected_range)
        layout.addWidget(self.btn_get_dates)

    def show_selected_range(self):
        selected_dates = self.calendar_picker.selectedDates()

        if len(selected_dates) < 2:
            w = MessageBox("提示", "请至少选择两个日期以形成一个范围。", self)
            w.exec_()
            return

        start_date = min(selected_dates)
        end_date = max(selected_dates)

        result_text = f"开始日期: {start_date.toString('yyyy-MM-dd')}\n结束日期: {end_date.toString('yyyy-MM-dd')}"
        self.label_result.setText(result_text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DateRangeSelector()
    window.show()
    sys.exit(app.exec_())
