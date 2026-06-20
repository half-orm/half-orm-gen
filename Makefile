# Check that we're on the main branch
.PHONY: check-main-branch
check-main-branch:
	@CURRENT_BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
	if [ "$$CURRENT_BRANCH" != "main" ]; then \
		echo "Error: Not on main branch (currently on $$CURRENT_BRANCH)"; \
		echo "Please switch to main branch: git checkout main"; \
		exit 1; \
	fi

# Check that the repository is clean (no uncommitted changes)
.PHONY: check-repo-clean
check-repo-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Repository has uncommitted changes:"; \
		git status --short; \
		echo ""; \
		echo "Please commit or stash your changes before building/deploying."; \
		exit 1; \
	fi

.PHONY: clean_build
clean_build:
	rm -rf dist

.PHONY: build
build: check-main-branch check-repo-clean clean_build
	@echo "✓ On main branch"
	@echo "✓ Repository is clean"
	@echo "Building package..."
	python -m build

.PHONY: publish
publish: build
	@echo "Publishing to PyPI..."
	twine upload -r half-orm-gen dist/*
