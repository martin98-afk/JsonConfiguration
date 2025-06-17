from PyQt5.QtWidgets import QApplication, QComboBox, QCalendarWidget, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import QDate, pyqtSignal


class DateRangeSelector(QFrame):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("日期范围选择器")
        self.setMinimumWidth(400)

        # 界面布局
        layout = QVBoxLayout(self)

        # 标签显示选定的日期范围
        self.label = QLabel("请选择日期范围：", self)
        layout.addWidget(self.label)

        # 自定义日期范围选择器
        self.date_range_combo = DateRangeComboBox(self)
        self.date_range_combo.rangeSelected.connect(self.display_selected_range)
        layout.addWidget(self.date_range_combo)

    def display_selected_range(self, start_date, end_date):
        """更新选择后的日期范围显示到标签"""
        self.label.setText(f"选定范围：从 {start_date} 到 {end_date}")


class DateRangeComboBox(QComboBox):
    # 信号传递选定的开始和结束日期
    rangeSelected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)  # 允许显示选定值
        self.lineEdit().setReadOnly(True)  # 禁止直接手动输入
        self.setInsertPolicy(QComboBox.NoInsert)  # 禁止插入新项

        # 创建日历组件
        self.calendar_widget = QCalendarWidget(self)
        self.calendar_widget.setGridVisible(True)  # 网格线显示更直观
        self.calendar_widget.clicked.connect(self.on_date_clicked)

        # 动态显示的日历作为下拉菜单项
        self.setModel(None)  # 清空默认模型
        self.setView(self.calendar_widget)  # 设置为自定义的日历视图

        # 变量保存选择的开始和结束日期
        self.start_date = None
        self.end_date = None

    def showPopup(self):
        """显示下拉菜单时重置状态"""
        super().showPopup()
        self.start_date = None
        self.end_date = None
        self.setEditText("请选择开始日期")

    def on_date_clicked(self, date: QDate):
        """处理用户点击日历上的日期"""
        if not self.start_date:  # 点击第一次，记录开始日期
            self.start_date = date
            self.setEditText(f"已选择开始日期：{date.toString('yyyy-MM-dd')}")
        else:  # 点击第二次，记录结束日期并关闭下拉框
            self.end_date = date
            if self.end_date < self.start_date:  # 日期顺序检查
                self.setEditText("结束日期不能早于开始日期，请重新选择")
                self.start_date = None
                self.end_date = None
                return

            self.setEditText(f"范围：{self.start_date.toString('yyyy-MM-dd')} - {self.end_date.toString('yyyy-MM-dd')}")
            self.hidePopup()  # 关闭下拉框
            # 发出选定范围信号
            self.rangeSelected.emit(self.start_date.toString("yyyy-MM-dd"), self.end_date.toString("yyyy-MM-dd"))


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = DateRangeSelector()
    window.show()
    sys.exit(app.exec_())