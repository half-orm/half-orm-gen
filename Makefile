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
	@setsid nohup bash -c 'cd $(DEMO_DIR)/ho_api && PATH="$${VIRTUAL_ENV:+$$VIRTUAL_ENV/bin:}$$PATH" exec litestar run --debug' \
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

.PHONY: demo-blog-access-save
demo-blog-access-save:  ## Sauvegarde la config d'accès admin (CRUD_ACCESS/fk_auto/searchable/labels/filtres actifs) dans fixtures/
	@# role, route, field et filter sont auto-peuplées par l'app au démarrage (system
	@# roles, discover_and_register, scan des CRUD_ACCESS/@ho_api_filter) — jamais dumpées.
	@# filter.id en particulier change de valeur à chaque redémarrage (gen_random_uuid()
	@# côté insert auto) : access_filter est donc résolu par clé naturelle du filtre
	@# (schema_name, table_name, name), pas par son id, pour rester rejouable après rebuild.
	pg_dump blog_demo --data-only --inserts \
	  -t '"half_orm_meta.api".access' \
	  -t '"half_orm_meta.api".field_access_in' \
	  -t '"half_orm_meta.api".field_access_out' \
	  -t '"half_orm_meta.api".field_access_fk_auto' \
	  -t '"half_orm_meta.api".field_access_searchable' \
	  -t '"half_orm_meta.api".user_role' \
	  | sed -E '/^INSERT INTO/ s/\);$$/) ON CONFLICT DO NOTHING;/' \
	  > fixtures/blog_demo_access.sql
	psql blog_demo -Atc "SELECT 'INSERT INTO \"half_orm_meta.api\".access_filter (access_id, filter_id) SELECT ''' || af.access_id || '''::uuid, f.id FROM \"half_orm_meta.api\".filter f WHERE f.schema_name=''' || f.schema_name || ''' AND f.table_name=''' || f.table_name || ''' AND f.name=''' || f.name || ''' ON CONFLICT DO NOTHING;' FROM \"half_orm_meta.api\".access_filter af JOIN \"half_orm_meta.api\".filter f ON f.id = af.filter_id" \
	  >> fixtures/blog_demo_access.sql
	psql blog_demo -Atc "SELECT 'UPDATE \"half_orm_meta.api\".field SET label_order = ' || label_order || ' WHERE schema_name = ''' || schema_name || ''' AND table_name = ''' || table_name || ''' AND column_name = ''' || column_name || ''';' FROM \"half_orm_meta.api\".field WHERE label_order IS NOT NULL" \
	  >> fixtures/blog_demo_access.sql
	@echo "Saved fixtures/blog_demo_access.sql"

.PHONY: demo-blog-access-load
demo-blog-access-load:  ## Recharge la config d'accès admin sauvegardée puis signale l'API (SIGHUP) pour qu'elle relise sa config sans redémarrer
	@# ON CONFLICT DO NOTHING rend chaque tentative idempotente : ce qui a déjà
	@# été inséré lors d'un essai précédent est simplement ignoré au suivant.
	@ok=0; \
	for i in 1 2 3 4 5; do \
		if psql blog_demo -v ON_ERROR_STOP=1 -f fixtures/blog_demo_access.sql > /tmp/demo-blog-access-load.log 2>&1; then \
			echo "Loaded fixtures/blog_demo_access.sql"; ok=1; break; \
		fi; \
		echo "Attempt $$i/5 failed (a dynamic role may not be registered yet) — retrying in 2s..."; \
		sleep 2; \
	done; \
	if [ "$$ok" != "1" ]; then \
		echo "FAILED after 5 attempts — is the API running (make demo-blog-api-run)?"; \
		cat /tmp/demo-blog-access-load.log; exit 1; \
	fi
	@# crud_access_by_res / access_map_holder are read from the DB once at API
	@# startup — a psql-loaded config is invisible to an already-running process
	@# unless it's told to reload. SIGHUP is registered in build_crud_app's
	@# on_startup hook for exactly this (see runtime.py: _reload_all_access).
	@# Sent by pattern, not via api.pid: `litestar run` always spawns uvicorn as
	@# a *child* subprocess (subprocess.run, not exec) regardless of --reload,
	@# and that child is where the asyncio signal handler actually lives —
	@# signalling the wrapper PID would not reach it. (`--reload` specifically
	@# is avoided in demo-blog-api-run: it adds its own supervisor/worker split
	@# with a churning worker PID, on top of the same wrapper-vs-child gap —
	@# and it only watches ho_api/, not the installed half_orm_gen package.)
	@# `pgrep -f`/`pkill -f` match the *full command line* of every process —
	@# including this very shell's own, since the recipe text it was launched
	@# with ("sh -c '... uvicorn.*demos/blog_demo/ho_api ...'") contains that
	@# same pattern as a literal substring. Exclude our own PID ($$$$) or this
	@# recipe would SIGHUP itself instead of (or as well as) the API.
	@pids=$$(pgrep -f litestar); \
	if [ -n "$$pids" ]; then \
		echo "$$pids" | xargs -r kill -HUP; \
		echo "Sent SIGHUP to $$pids — API reloading CRUD_ACCESS/roles from DB (see api.log)"; \
	else \
		echo "No running API matched 'uvicorn.*demos/blog_demo/ho_api' — start it with make demo-blog-api-run"; \
	fi

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

