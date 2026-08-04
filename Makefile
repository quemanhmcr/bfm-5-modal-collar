.PHONY: audit

audit:
	python tools/audit_docs.py
	git diff --check
