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

.PHONY: clean
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf dist build *.egg-info .coverage htmlcov

.PHONY: clean_build
clean_build:
	rm -rf dist

# Unit and integration tests. The end-to-end demos are not pytest — they are
# the shell scripts under tests/e2e/scripts, driven by their own Makefile
# (make -C tests/e2e/scripts demo).
.PHONY: test
test:
	@echo "Running tests..."
	pytest -x
	@echo "✓ All tests passed"

# Check that published half-orm / half-orm-dev releases satisfy the
# constraints in pyproject.toml — half-orm-gen generates code against both,
# so shipping it ahead of either one produces an uninstallable release.
.PHONY: check-half-orm-release
check-half-orm-release:
	@echo "Checking half-orm PyPI release compatibility..."
	@python scripts/check_half_orm_release.py

.PHONY: build
build: check-main-branch check-half-orm-release check-repo-clean test clean_build
	@echo "✓ On main branch"
	@echo "✓ Repository is clean"
	@echo "Building package..."
	python -m build

.PHONY: publish
publish: build
	@echo "Publishing to PyPI..."
	twine upload -r half-orm-gen dist/*

# Bump the version, point the constraints at the minimum half-orm /
# half-orm-dev releases this version needs, check those releases are actually
# published, then commit and tag. Nothing is committed if the check fails:
# version.txt and the constraints are rolled back first.
.PHONY: release
release: check-main-branch check-repo-clean
	@CURRENT=$$(cat half_orm_gen/version.txt | tr -d '[:space:]'); \
	echo "Current half-orm-gen version: $$CURRENT"; \
	CURRENT_HO=$$(grep -oP '(?<="half-orm>=)[^,"<]+' pyproject.toml); \
	CURRENT_HOD=$$(grep -oP '(?<="half-orm-dev>=)[^,"<]+' pyproject.toml); \
	printf "Minimum half-orm version required [$$CURRENT_HO]: "; \
	read MIN_HO; \
	if [ -z "$$MIN_HO" ]; then MIN_HO="$$CURRENT_HO"; fi; \
	printf "Minimum half-orm-dev version required [$$CURRENT_HOD]: "; \
	read MIN_HOD; \
	if [ -z "$$MIN_HOD" ]; then MIN_HOD="$$CURRENT_HOD"; fi; \
	if [ -z "$$MIN_HO" ] || [ -z "$$MIN_HOD" ]; then echo "Aborted."; exit 1; fi; \
	printf "New half-orm-gen version: "; \
	read NEW_VERSION; \
	if [ -z "$$NEW_VERSION" ]; then echo "Aborted."; exit 1; fi; \
	GEN_XY=$$(echo "$$NEW_VERSION" | sed 's/^\([0-9]*\.[0-9]*\).*/\1/'); \
	HO_XY=$$(echo "$$MIN_HO" | sed 's/^\([0-9]*\.[0-9]*\).*/\1/'); \
	HOD_XY=$$(echo "$$MIN_HOD" | sed 's/^\([0-9]*\.[0-9]*\).*/\1/'); \
	if [ "$$HO_XY" != "$$GEN_XY" ] || [ "$$HOD_XY" != "$$GEN_XY" ]; then \
		echo "ERROR: version mismatch — half-orm $$MIN_HO ($$HO_XY), half-orm-dev $$MIN_HOD ($$HOD_XY) and half-orm-gen $$NEW_VERSION ($$GEN_XY) must share the same X.Y"; \
		exit 1; \
	fi; \
	echo "$$NEW_VERSION" > half_orm_gen/version.txt; \
	echo "Checking half-orm PyPI release compatibility..."; \
	if ! python scripts/check_half_orm_release.py --min-half-orm "$$MIN_HO" --min-half-orm-dev "$$MIN_HOD"; then \
		echo "$$CURRENT" > half_orm_gen/version.txt; \
		git checkout pyproject.toml requirements.txt; \
		echo "Reverted to $$CURRENT"; \
		exit 1; \
	fi; \
	git add half_orm_gen/version.txt pyproject.toml requirements.txt; \
	git commit -m "[release] $$NEW_VERSION"; \
	git tag "$$NEW_VERSION"; \
	echo "✓ Committed and tagged $$NEW_VERSION"
