from datetime import datetime

from PyQt5.QtWidgets import (
    QComboBox, QDialogButtonBox, QGridLayout, QDialog, QVBoxLayout, QLabel
)


class TimeSelectorDialog(QDialog):
    def __init__(self, current_value="", title="选择时间"):
        super().__init__()
        self.setWindowTitle(title)
        self.setFixedWidth(600)

        main_layout = QVBoxLayout()
        grid = QGridLayout()

        now = datetime.now()
        if current_value:
            try:
                dt = datetime.strptime(current_value, "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = now
        else:
            dt = now

        self.year_cb = QComboBox()
        self.year_cb.addItems([str(y) for y in range(2020, 2031)])
        self.year_cb.setCurrentText(str(dt.year))

        self.month_cb = QComboBox()
        self.month_cb.addItems([f"{m:02d}" for m in range(1, 13)])
        self.month_cb.setCurrentText(f"{dt.month:02d}")

        self.day_cb = QComboBox()
        self.day_cb.addItems([f"{d:02d}" for d in range(1, 32)])
        self.day_cb.setCurrentText(f"{dt.day:02d}")

        self.hour_cb = QComboBox()
        self.hour_cb.addItems([f"{h:02d}" for h in range(0, 24)])
        self.hour_cb.setCurrentText(f"{dt.hour:02d}")

        self.minute_cb = QComboBox()
        self.minute_cb.addItems([f"{m:02d}" for m in range(0, 60)])
        self.minute_cb.setCurrentText(f"{dt.minute:02d}")

        grid.addWidget(QLabel("年"), 0, 1)
        grid.addWidget(self.year_cb, 0, 0)
        grid.addWidget(QLabel("月"), 0, 3)
        grid.addWidget(self.month_cb, 0, 2)
        grid.addWidget(QLabel("日"), 0, 5)
        grid.addWidget(self.day_cb, 0, 4)
        grid.addWidget(QLabel("时"), 0, 7)
        grid.addWidget(self.hour_cb, 0, 6)
        grid.addWidget(QLabel("分"), 0, 9)
        grid.addWidget(self.minute_cb, 0, 8)

        main_layout.addLayout(grid)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)

    def get_time(self):
        return f"{self.year_cb.currentText()}-{self.month_cb.currentText()}-{self.day_cb.currentText()} {self.hour_cb.currentText()}:{self.minute_cb.currentText()}:00"