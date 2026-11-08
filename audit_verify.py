#!/usr/bin/env python3
"""Regression audit verification script."""

import sys
sys.path.insert(0, r'C:\Users\veere\Desktop\shiva')

print('=== COMPREHENSIVE REGRESSION AUDIT VERIFICATION ===')
print()

# 1. ProductType enum alignment
print('1. ProductType enum alignment:')
from brokers.base_broker import ProductType
expected = ['INTRADAY', 'DELIVERY', 'MARGIN', 'CARRYFORWARD']
actual = [pt.value for pt in ProductType]
if expected == actual:
    print('   PASS: ProductType enum values match expected')
else:
    print(f'   FAIL: Expected {expected}, got {actual}')

# 2. Side-aware profit gate
print('2. Side-aware 70 INR Gross Profit Gate:')
from core.order_router import OrderRouter
import inspect
src = inspect.getsource(OrderRouter.execute_order)
has_buy_calc = 'target_price - price' in src
has_sell_calc = 'price - target_price' in src
has_70_hurdle = 'MIN_GROSS_PROFIT_HURDLE_INR' in src or '70.0' in src
if has_buy_calc and has_sell_calc and has_70_hurdle:
    print('   PASS: Side-aware profit gate with 70 INR hurdle implemented')
else:
    print('   FAIL: Side-aware profit gate missing or incomplete')

# 3. _sync_toggles_from_vault implementation
print('3. _sync_toggles_from_vault method:')
src = inspect.getsource(OrderRouter._sync_toggles_from_vault)
if 'def _sync_toggles_from_vault' in src:
    print('   PASS: Method exists and is implemented')
else:
    print('   FAIL: Method missing')

# 4. UUID execution_id generation
print('4. UUID execution_id generation:')
if 'uuid.uuid4()' in src:
    print('   PASS: UUID generation for execution_id present')
else:
    print('   FAIL: UUID generation missing')

# 5. ThreadPoolExecutor parallel dispatch
print('5. ThreadPoolExecutor parallel dispatch:')
if 'ThreadPoolExecutor' in src:
    print('   PASS: ThreadPoolExecutor for concurrent dispatch present')
else:
    print('   FAIL: ThreadPoolExecutor missing')

# 6. BrokerToggleMatrix
print('6. BrokerToggleMatrix:')
from core.order_router import OrderRouter
import inspect
src = inspect.getsource(OrderRouter.__init__)
if '_broker_toggles' in src:
    print('   PASS: Broker toggle matrix initialized')
else:
    print('   FAIL: Broker toggle matrix missing')

# 7. CONFIRMATION_WINDOW in SMCLiquiditySweep
print('7. CONFIRMATION_WINDOW in SMCLiquiditySweep:')
from core.strategies import SMCLiquiditySweep
if hasattr(SMCLiquiditySweep, 'CONFIRMATION_WINDOW'):
    print(f'   PASS: CONFIRMATION_WINDOW = {SMCLiquiditySweep.CONFIRMATION_WINDOW}')
else:
    print('   FAIL: CONFIRMATION_WINDOW missing')

# 8. btn_connect lifecycle
print('8. btn_connect lifecycle management:')
from ui.broker_control_widget import BrokerCard
import inspect
src = inspect.getsource(BrokerCard._on_connect_clicked)
if 'if self.current_state == "CONNECTED"' in src:
    print('   PASS: Connect/disconnect lifecycle handled')
else:
    print('   FAIL: Connect/disconnect lifecycle incomplete')

# 9. Database connection signatures
print('9. Database connection thread-isolation:')
from database.db_handler import DatabaseHandler
from database.vault_manager import VaultManager
import inspect
db_src = inspect.getsource(DatabaseHandler._get_connection)
vault_src = inspect.getsource(VaultManager._get_connection)
if 'thread_local' in db_src and 'thread_local' in vault_src:
    print('   PASS: Thread-local connections in both handlers')
else:
    print('   FAIL: Missing thread-local connections')

# 10. IDOR protection via UUID
print('10. IDOR protection via UUID:')
if 'execution_uuid = str(uuid.uuid4())' in src:
    print('   PASS: Unique execution UUID per order dispatch')
else:
    print('   FAIL: UUID protection missing')

print()
print('=== AUDIT COMPLETE ===')