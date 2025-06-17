from PyQt5.QtWidgets import QDialog

from application.base import BaseParameter
from application.dialogs.time_range_dialog import TimeRangeDialog
from application.dialogs.time_selector_dialog import TimeSelectorDialog
from application.parameters import rigister_parameter


@rigister_parameter()
class Time(BaseParameter):
    parameter_name = "time"
    parameter_desc = "时间选择"

    def edit_parameter(self, item, current_value):
        self.message_status(("正在加载时间范围选择器..."))
        # 创建并显示时间范围选择对话框，优化标题和UI
        curve_viewer = TimeRangeDialog(
            self.parent.config.get_tools_by_type("trenddb-fetcher")[0],
            current_text=current_value,
            parent=self.parent,
        )
        curve_viewer.setWindowTitle(f"时间范围选择 - {item.text(0)}")

        if curve_viewer.exec_() == QDialog.Accepted:
            # 获取用户选择的时间范围
            return curve_viewer.get_selected_time_ranges()
