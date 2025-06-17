from PyQt5.QtWidgets import QDialog, QComboBox

from application.base import BaseParameter
from application.dialogs.time_selector_dialog import TimeSelectorDialog
from application.parameters import rigister_parameter


@rigister_parameter()
class Time(BaseParameter):
    parameter_name = "time"
    parameter_desc = "时间选择"

    def edit_parameter(self, item, current_value, **kwargs):
        # 初始化编辑器组件
        combo = QComboBox()
        options = self.parent.config.params_options[kwargs.get("full_path")]
        combo.addItems(options)

        # 设置当前值
        current_index = combo.findText(current_value)
        if current_index >= 0:
            combo.setCurrentIndex(current_index)

        def on_combo_activated():
            new_value = combo.currentText()
            if new_value != current_value:
                item.setText(1, new_value)
                item.setForeground(1, QColor("#1890ff"))
                QTimer.singleShot(2000, lambda: item.setForeground(1, QColor("black")))
            # 移除控件
            self.tree.removeItemWidget(item, column)
            # 恢复背景
            restore_background()

        combo.activated.connect(on_combo_activated)
