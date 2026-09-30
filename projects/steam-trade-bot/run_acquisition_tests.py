#!/usr/bin/env python3
"""Test runner for acquisition integration tests without pytest."""

import sys
sys.path.insert(0, '.')

import sqlite3
from decimal import Decimal
from datetime import date, datetime, timezone
from unittest.mock import Mock

# Import from test module
from tests.test_acquisition_integration import (
    create_full_schema,
    insert_snapshot,
    Repository,
    AcquisitionDetector,
)

# Also import the test functions
from tests.test_acquisition_integration import (
    test_initial_snapshot_creates_unknown,
    test_new_item_on_subsequent_snapshot,
    test_quantity_increase_detected,
    test_quantity_decrease_no_acquisition,
    test_no_inventory_change_no_acquisition,
    test_market_history_exact_match_creates_tracked,
    test_market_history_partial_match_creates_tracked,
    test_no_market_history_match_creates_unknown,
    test_repeated_polling_no_duplicate_tracked,
    test_repeated_unknown_remain_distinct,
    test_verified_acquisition_cost_in_ledger,
    test_market_price_never_used_as_cost,
    test_phase1_invariants_preserved,
    test_existing_transactions_not_duplicated,
    test_sell_allocation_unchanged,
    test_market_valuation_not_acquisition_cost,
    test_rerun_same_cycle_no_duplicate,
    test_different_bots_independent,
    test_record_acquisition_tracked_requires_provenance,
    test_record_acquisition_unknown_requires_no_cost,
    test_record_acquisition_idempotent,
    test_unknown_external_ref_distinct,
)

def run_test(test_func, name):
    """Run a single test function with fresh DB."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    create_full_schema(conn)
    repo = Repository(conn)
    detector = AcquisitionDetector(repo, 'Rixqor')
    mock_session = Mock()
    
    try:
        test_func(repo, detector, mock_session)
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def run_test_with_conn(test_func, name):
    """Run a test that creates its own connection."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    create_full_schema(conn)
    repo = Repository(conn)
    mock_session = Mock()
    
    try:
        test_func(repo, AcquisitionDetector(repo, 'Rixqor'), mock_session)
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# Test list
tests = [
    (test_initial_snapshot_creates_unknown, "Initial snapshot creates UNKNOWN"),
    (test_new_item_on_subsequent_snapshot, "New item on subsequent snapshot"),
    (test_quantity_increase_detected, "Quantity increase detected"),
    (test_quantity_decrease_no_acquisition, "Quantity decrease no acquisition"),
    (test_no_inventory_change_no_acquisition, "No inventory change no acquisition"),
    (test_market_history_exact_match_creates_tracked, "Market History exact match creates TRACKED"),
    (test_market_history_partial_match_creates_tracked, "Market History partial match creates TRACKED"),
    (test_no_market_history_match_creates_unknown, "No Market History match creates UNKNOWN"),
    (test_repeated_polling_no_duplicate_tracked, "Repeated polling no duplicate TRACKED"),
    (test_repeated_unknown_remain_distinct, "Repeated UNKNOWN remain distinct"),
    (test_verified_acquisition_cost_in_ledger, "Verified acquisition cost in ledger"),
    (test_market_price_never_used_as_cost, "Market price never used as cost"),
    (test_phase1_invariants_preserved, "Phase 1 invariants preserved"),
    (test_existing_transactions_not_duplicated, "Existing transactions not duplicated"),
    (test_sell_allocation_unchanged, "Sell allocation unchanged"),
    (test_market_valuation_not_acquisition_cost, "Market valuation not acquisition cost"),
    (test_rerun_same_cycle_no_duplicate, "Rerun same cycle no duplicate"),
    (test_different_bots_independent, "Different bots independent"),
]

# Tests that need their own connection pattern
special_tests = [
    (test_record_acquisition_tracked_requires_provenance, "record_acquisition TRACKED requires provenance"),
    (test_record_acquisition_unknown_requires_no_cost, "record_acquisition UNKNOWN requires no cost"),
    (test_record_acquisition_idempotent, "record_acquisition idempotent"),
    (test_unknown_external_ref_distinct, "Unknown external_ref distinct"),
]

print("=" * 60)
print("RUNNING ACQUISITION INTEGRATION TESTS")
print("=" * 60)

passed = 0
failed = 0

for test_func, name in tests:
    print(f"\n{name}...", end=" ")
    success, error = run_test(test_func, name)
    if success:
        print("PASS")
        passed += 1
    else:
        print(f"FAIL: {error}")
        failed += 1

print("\n" + "=" * 60)
print("RUNNING SPECIAL TESTS (record_acquisition)")
print("=" * 60)

for test_func, name in special_tests:
    print(f"\n{name}...", end=" ")
    success, error = run_test_with_conn(test_func, name)
    if success:
        print("PASS")
        passed += 1
    else:
        print(f"FAIL: {error}")
        failed += 1

print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)