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

# ---------------------------------------------------------------------------
# Demo: blog_demo
# ---------------------------------------------------------------------------
DEMO_SCRIPTS := tests/e2e/scripts
DEMO_DIR     := $(DEMO_SCRIPTS)/demos/blog_demo
DEMO_LOGS    := $(DEMO_DIR)/.run

.PHONY: demo-blog
demo-blog:  demo-blog-clean ## Régénère la demo blog_demo (drop DB + regen complet)
	dropdb -f --if-exists blog_demo
	cd $(DEMO_SCRIPTS) && yes | PATH="$${VIRTUAL_ENV:+$$VIRTUAL_ENV/bin:}$$PATH" bash demo_blog.sh

.PHONY: demo-blog-clean
demo-blog-clean:  demo-blog-stop ## Nettoie la demo (drop DB + suppression projet)
	cd $(DEMO_SCRIPTS) && PATH="$${VIRTUAL_ENV:+$$VIRTUAL_ENV/bin:}$$PATH" bash demo_blog.sh --cleanup

.PHONY: demo-blog-api
demo-blog-api:  ## Régénère l'API
	cd $(DEMO_DIR) && half_orm gen api --litestar

.PHONY: demo-blog-api-run
demo-blog-api-run:  ## Lance l'API Litestar en tâche de fond puis suit les logs
	@mkdir -p $(DEMO_LOGS)
	@setsid nohup bash -c 'cd $(DEMO_DIR)/ho_api && PATH="$${VIRTUAL_ENV:+$$VIRTUAL_ENV/bin:}$$PATH" exec litestar run --debug --reload' \
		> $(DEMO_LOGS)/api.log 2>&1 & echo $$! > $(DEMO_LOGS)/api.pid
	@echo "API   PID $$(cat $(DEMO_LOGS)/api.pid) — logs: $(DEMO_LOGS)/api.log"
	@tail -f $(DEMO_LOGS)/api.log & echo $$! > $(DEMO_LOGS)/api.tail.pid

.PHONY: demo-blog-angular
demo-blog-angular:  ## Régénère le front Angular
	cd $(DEMO_DIR) && half_orm gen frontend --angular

.PHONY: demo-blog-angular-run
demo-blog-angular-run:  ## Lance le front Angular en tâche de fond puis suit les logs
	@mkdir -p $(DEMO_LOGS)
	@setsid nohup bash -c 'export NVM_DIR="$$HOME/.nvm"; source "$$NVM_DIR/nvm.sh"; nvm use 22 && cd $(DEMO_DIR)/ho_frontend/angular && npm install && exec npm start' \
		> $(DEMO_LOGS)/angular.log 2>&1 & echo $$! > $(DEMO_LOGS)/angular.pid
	@echo "Angular PID $$(cat $(DEMO_LOGS)/angular.pid) — logs: $(DEMO_LOGS)/angular.log"
	@tail -f $(DEMO_LOGS)/angular.log & echo $$! > $(DEMO_LOGS)/angular.tail.pid

.PHONY: demo-blog-svelte
demo-blog-svelte:  ## Régénère le front svelte
	cd $(DEMO_DIR) && half_orm gen frontend --svelte

.PHONY: demo-blog-svelte-run
demo-blog-svelte-run:  ## Lance le front Svelte en tâche de fond puis suit les logs
	@mkdir -p $(DEMO_LOGS)
	@setsid nohup bash -c 'cd $(DEMO_DIR)/ho_frontend/svelte && npm install && exec npm run dev' \
		> $(DEMO_LOGS)/svelte.log 2>&1 & echo $$! > $(DEMO_LOGS)/svelte.pid
	@echo "Svelte PID $$(cat $(DEMO_LOGS)/svelte.pid) — logs: $(DEMO_LOGS)/svelte.log"
	@tail -f $(DEMO_LOGS)/svelte.log & echo $$! > $(DEMO_LOGS)/svelte.tail.pid

.PHONY: demo-blog-run
demo-blog-run: demo-blog-api-run demo-blog-angular-run demo-blog-svelte-run  ## Lance API + fronts en tâche de fond

.PHONY: demo-blog-stop
demo-blog-stop:  ## Arrête API + fronts + tails (via PID files)
	@for f in $(DEMO_LOGS)/*.pid; do \
		[ -f "$$f" ] || continue; \
		pid=$$(cat "$$f"); \
		case "$$f" in \
			*.tail.pid) kill $$pid 2>/dev/null ;; \
			*) kill -- -$$pid 2>/dev/null ;; \
		esac && echo "stopped $$(basename $$f .pid)"; \
		rm -f "$$f"; \
	done
	@ng_pid=$$(ps ux | grep 'ng serve' | grep -v grep | awk '{print $$2}'); \
	if [ -n "$$ng_pid" ]; then kill -9 $$ng_pid; echo "stopped angular (ng serve, orphaned)"; fi

