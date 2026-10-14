"""Optional visual/browser smoke test.

Requirements: a built or Vite-served React frontend plus Python playwright/browser binaries.
Run: FAIR_UI_URL=http://127.0.0.1:5173 python tests/ui_playwright_demo.py
This script is not part of `unittest discover` because the frontend needs npm install.
"""
from __future__ import annotations

import os
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = os.environ.get('FAIR_UI_URL', 'http://127.0.0.1:5173')
OUT = Path(os.environ.get('FAIR_SCREENSHOT', 'ui-v2-captured.png')).resolve()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1672, 'height': 941}, device_scale_factor=1)
    page.goto(URL, wait_until='networkidle', timeout=30000)
    page.get_by_text('Target HDF5 Design').wait_for()
    page.get_by_text('Pressure Sensor', exact=True).first.wait_for()
    page.screenshot(path=str(OUT), full_page=True)
    print('Screenshot saved:', OUT)

    # Add and select another pressure sensor, including profile-related fields.
    palette_item = page.locator('.palette-item').filter(has_text='Pressure sensor').first
    palette_item.hover()
    page.get_by_role('button', name='Add Pressure sensor').click()
    page.get_by_text('Node Configuration').wait_for()
    page.get_by_label('New metadata field').fill('calibration_certificate')
    page.get_by_role('button', name='Add field').click()
    page.get_by_text('calibration certificate', exact=False).first.wait_for()

    # A new mandatory attribute without a value must cause a validation issue.
    page.get_by_role('button', name='Validate', exact=True).last.click()
    page.get_by_text('Validation report', exact=True).wait_for()
    page.get_by_text('Conformance issues found').wait_for()
    page.get_by_role('button', name='Close', exact=True).last.click()

    # Confirm a real HDF5 payload can be downloaded.
    with page.expect_download() as transfer:
        page.get_by_role('button', name='Export HDF5 Template').click()
    download = transfer.value
    assert download.suggested_filename.endswith('.h5')
    browser.close()
    print('Browser integration checks passed.')
