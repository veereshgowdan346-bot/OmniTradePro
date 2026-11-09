import sys
import os
sys.path.insert(0, r'C:\Users\veere\Desktop\shiva')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

print("Step 1: creating QApplication")
from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
print("Step 2: QApp created")

from ui.main_window import MainWindow
print("Step 3: importing MainWindow")
win = MainWindow()
print("Step 4: MainWindow created OK")
print(f"Stacked count: {win.stacked_widget.count()}")
