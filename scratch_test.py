import sys
import os
sys.path.insert(0, r'C:\Users\veere\Desktop\shiva')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
print("Step 1: imports start")
from core.strategies import SMCLiquiditySweep
print("Step 2: core ok")
from ui.main_window import MainWindow
print("Step 3: main_window ok")
print("All imports OK")
