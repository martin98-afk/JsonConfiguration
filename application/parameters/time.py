from PyQt5.QtWidgets import QDialog

from application.base import BaseParameter
from application.dialogs.time_selector_dialog import TimeSelectorDialog
from application.parameters import rigister_parameter


@rigister_parameter()
class Time(BaseParameter):
    parameter_name = "time"
    parameter_desc = "时间选择"

    def edit_parameter(self, item, current_value):
        dlg = TimeSelectorDialog(current_value)
        dlg.setWindowTitle(f"选择 {item.text(0)} 时间")
        if dlg.exec_() == QDialog.Accepted:
            return dlg.get_time()