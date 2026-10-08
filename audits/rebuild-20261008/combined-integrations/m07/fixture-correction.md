# M07 HTML-heading fixture correction

Original replay of reviewed M07 1fa21207: 1 failed, 35 passed. The failing test decodes stored artifact bytes and searches for HTML text. WeasyPrint is available here and Service._pdf returns compressed PDF bytes. M19 changes do not affect M07 rendering.

Original assertion, retained unchanged:

    assert lab == {"views": "VERIFIED"} and "Verified metrics" in html

The fixture now patches only this Service instance's _pdf to return HTML bytes and text/html. All VERIFIED/PARTIAL/UNVERIFIED and report assertions remain. Product rendering is unchanged. The original failure log is preserved alongside this record. This test verifies HTML-template/metric-label behavior, not actual PDF content or visual acceptance.
