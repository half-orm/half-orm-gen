# ---------------------------------------------------------------------------
# Demo: blog_demo
# ---------------------------------------------------------------------------
# Always this project's own venv, never whatever $VIRTUAL_ENV the calling
# shell happens to have active (or doesn't) — a demo run from a shell without
# .venv activated silently fell back to a global `litestar`/`half_orm`
# install, missing local editable-install patches (e.g. with_half_orm_meta).
VENV_BIN := $(abspath .venv/bin)

DEMO_SCRIPTS := $$PWD
DEMO_DIR     := $(DEMO_SCRIPTS)/demos/blog_demo
DEMO_LOGS    := $(DEMO_DIR)/.run

.PHONY: demo-blog
demo-blog:  demo-blog-clean ## Régénère la demo blog_demo (drop DB + regen complet)
	dropdb -f --if-exists blog_demo
	cd $(DEMO_SCRIPTS) && yes | PATH="$(VENV_BIN):$$PATH" bash demo_blog.sh

.PHONY: demo-blog-clean
demo-blog-clean:  demo-blog-stop ## Nettoie la demo (drop DB + suppression projet)
	cd $(DEMO_SCRIPTS) && PATH="$(VENV_BIN):$$PATH" bash demo_blog.sh --cleanup

.PHONY: demo-blog-api
demo-blog-api:  ## Régénère l'API
	cd $(DEMO_DIR) && half_orm gen api --litestar

.PHONY: demo-blog-api-run
demo-blog-api-run:  ## Lance l'API Litestar en tâche de fond puis suit les logs
	@mkdir -p $(DEMO_LOGS)
	@setsid nohup bash -c 'cd $(DEMO_DIR)/ho_api && PATH="$(VENV_BIN):$$PATH" exec litestar run --debug' \
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

.PHONY: demo-pages-access-save
demo-pages-access-save:  ## Sauvegarde la config d'accès admin (CRUD_ACCESS/fk_auto/searchable/labels/filtres actifs) dans fixtures/
	@# role, route, field et filter sont auto-peuplées par l'app au démarrage (system
	@# roles, discover_and_register, scan des CRUD_ACCESS/@ho_api_filter) — jamais dumpées.
	@# filter.id en particulier change de valeur à chaque redémarrage (gen_random_uuid()
	@# côté insert auto) : access_filter est donc résolu par clé naturelle du filtre
	@# (schema_name, table_name, name), pas par son id, pour rester rejouable après rebuild.
	pg_dump pages_demo --data-only --inserts \
	  -t '"half_orm_meta.api".access' \
	  -t '"half_orm_meta.api".field_access_in' \
	  -t '"half_orm_meta.api".field_access_out' \
	  -t '"half_orm_meta.api".field_access_fk_auto' \
	  -t '"half_orm_meta.api".field_access_searchable' \
	  -t '"half_orm_meta.api".user_role' \
	  | sed -E '/^INSERT INTO/ s/\);$$/) ON CONFLICT DO NOTHING;/' \
	  > fixtures/pages_demo_access.sql
	psql pages_demo -Atc "SELECT 'INSERT INTO \"half_orm_meta.api\".access_filter (access_id, filter_id) SELECT ''' || af.access_id || '''::uuid, f.id FROM \"half_orm_meta.api\".filter f WHERE f.schema_name=''' || f.schema_name || ''' AND f.table_name=''' || f.table_name || ''' AND f.name=''' || f.name || ''' ON CONFLICT DO NOTHING;' FROM \"half_orm_meta.api\".access_filter af JOIN \"half_orm_meta.api\".filter f ON f.id = af.filter_id" \
	  >> fixtures/pages_demo_access.sql
	psql pages_demo -Atc "SELECT 'UPDATE \"half_orm_meta.api\".field SET label_order = ' || label_order || ' WHERE schema_name = ''' || schema_name || ''' AND table_name = ''' || table_name || ''' AND column_name = ''' || column_name || ''';' FROM \"half_orm_meta.api\".field WHERE label_order IS NOT NULL" \
	  >> fixtures/pages_demo_access.sql
	@echo "Saved fixtures/pages_demo_access.sql"

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

.PHONY: demo-pages-access-load
demo-pages-access-load:  ## Recharge la config d'accès admin sauvegardée puis signale l'API (SIGHUP) pour qu'elle relise sa config sans redémarrer
	@# ON CONFLICT DO NOTHING rend chaque tentative idempotente : ce qui a déjà
	@# été inséré lors d'un essai précédent est simplement ignoré au suivant.
	@ok=0; \
	for i in 1 2 3 4 5; do \
		if psql pages_demo -v ON_ERROR_STOP=1 -f fixtures/pages_demo_access.sql > /tmp/demo-pages-access-load.log 2>&1; then \
			echo "Loaded fixtures/pages_demo_access.sql"; ok=1; break; \
		fi; \
		echo "Attempt $$i/5 failed (a dynamic role may not be registered yet) — retrying in 2s..."; \
		sleep 2; \
	done; \
	if [ "$$ok" != "1" ]; then \
		echo "FAILED after 5 attempts — is the API running (make demo-pages-api-run)?"; \
		cat /tmp/demo-pages-access-load.log; exit 1; \
	fi
	@# crud_access_by_res / access_map_holder are read from the DB once at API
	@# startup — a psql-loaded config is invisible to an already-running process
	@# unless it's told to reload. SIGHUP is registered in build_crud_app's
	@# on_startup hook for exactly this (see runtime.py: _reload_all_access).
	@# Sent by pattern, not via api.pid: `litestar run` always spawns uvicorn as
	@# a *child* subprocess (subprocess.run, not exec) regardless of --reload,
	@# and that child is where the asyncio signal handler actually lives —
	@# signalling the wrapper PID would not reach it. (`--reload` specifically
	@# is avoided in demo-pages-api-run: it adds its own supervisor/worker split
	@# with a churning worker PID, on top of the same wrapper-vs-child gap —
	@# and it only watches ho_api/, not the installed half_orm_gen package.)
	@# `pgrep -f`/`pkill -f` match the *full command line* of every process —
	@# including this very shell's own, since the recipe text it was launched
	@# with ("sh -c '... uvicorn.*demos/pages_demo/ho_api ...'") contains that
	@# same pattern as a literal substring. Exclude our own PID ($$$$) or this
	@# recipe would SIGHUP itself instead of (or as well as) the API.
	@pids=$$(pgrep -f litestar); \
	if [ -n "$$pids" ]; then \
		echo "$$pids" | xargs -r kill -HUP; \
		echo "Sent SIGHUP to $$pids — API reloading CRUD_ACCESS/roles from DB (see api.log)"; \
	else \
		echo "No running API matched 'uvicorn.*demos/pages_demo/ho_api' — start it with make demo-pages-api-run"; \
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

# ---------------------------------------------------------------------------
# Demo: pages_demo — a separate domain (wiki), used to prove out identity
# federation (planning/identite_federee.md). Different ports so it can run
# alongside blog_demo. See `make demo-federate` to register the two as
# trusted peers of each other.
# ---------------------------------------------------------------------------
PAGES_DEMO_DIR  := $(DEMO_SCRIPTS)/demos/pages_demo
PAGES_DEMO_LOGS := $(PAGES_DEMO_DIR)/.run

.PHONY: demo-pages
demo-pages:  demo-pages-clean ## Régénère la demo pages_demo (drop DB + regen complet)
	dropdb -f --if-exists pages_demo
	cd $(DEMO_SCRIPTS) && yes | PATH="$(VENV_BIN):$$PATH" bash demo_pages.sh

.PHONY: demo-pages-clean
demo-pages-clean:  demo-pages-stop ## Nettoie la demo (drop DB + suppression projet)
	cd $(DEMO_SCRIPTS) && PATH="$(VENV_BIN):$$PATH" bash demo_pages.sh --cleanup

.PHONY: demo-pages-api-run
demo-pages-api-run:  ## Lance l'API Litestar (port 8001) en tâche de fond puis suit les logs
	@mkdir -p $(PAGES_DEMO_LOGS)
	@setsid nohup bash -c 'cd $(PAGES_DEMO_DIR)/ho_api && PATH="$(VENV_BIN):$$PATH" exec litestar run --debug --port 8001' \
		> $(PAGES_DEMO_LOGS)/api.log 2>&1 & echo $$! > $(PAGES_DEMO_LOGS)/api.pid
	@echo "API   PID $$(cat $(PAGES_DEMO_LOGS)/api.pid) — logs: $(PAGES_DEMO_LOGS)/api.log"
	@tail -f $(PAGES_DEMO_LOGS)/api.log & echo $$! > $(PAGES_DEMO_LOGS)/api.tail.pid

.PHONY: demo-pages-angular-run
demo-pages-angular-run:  ## Lance le front Angular (port 4300) en tâche de fond puis suit les logs
	@mkdir -p $(PAGES_DEMO_LOGS)
	@setsid nohup bash -c 'export NVM_DIR="$$HOME/.nvm"; source "$$NVM_DIR/nvm.sh"; nvm use 22 && cd $(PAGES_DEMO_DIR)/ho_frontend/angular && npm install && exec npm start' \
		> $(PAGES_DEMO_LOGS)/angular.log 2>&1 & echo $$! > $(PAGES_DEMO_LOGS)/angular.pid
	@echo "Angular PID $$(cat $(PAGES_DEMO_LOGS)/angular.pid) — logs: $(PAGES_DEMO_LOGS)/angular.log"
	@tail -f $(PAGES_DEMO_LOGS)/angular.log & echo $$! > $(PAGES_DEMO_LOGS)/angular.tail.pid

.PHONY: demo-pages-svelte-run
demo-pages-svelte-run:  ## Lance le front Svelte (port 5300) en tâche de fond puis suit les logs
	@mkdir -p $(PAGES_DEMO_LOGS)
	@setsid nohup bash -c 'cd $(PAGES_DEMO_DIR)/ho_frontend/svelte && npm install && exec npm run dev' \
		> $(PAGES_DEMO_LOGS)/svelte.log 2>&1 & echo $$! > $(PAGES_DEMO_LOGS)/svelte.pid
	@echo "Svelte PID $$(cat $(PAGES_DEMO_LOGS)/svelte.pid) — logs: $(PAGES_DEMO_LOGS)/svelte.log"
	@tail -f $(PAGES_DEMO_LOGS)/svelte.log & echo $$! > $(PAGES_DEMO_LOGS)/svelte.tail.pid

.PHONY: demo-pages-run
demo-pages-run: demo-pages-api-run demo-pages-angular-run demo-pages-svelte-run  ## Lance API + fronts en tâche de fond

.PHONY: demo-pages-stop
demo-pages-stop:  ## Arrête API + fronts + tails (via PID files)
	@for f in $(PAGES_DEMO_LOGS)/*.pid; do \
		[ -f "$$f" ] || continue; \
		pid=$$(cat "$$f"); \
		case "$$f" in \
			*.tail.pid) kill $$pid 2>/dev/null ;; \
			*) kill -- -$$pid 2>/dev/null ;; \
		esac && echo "stopped $$(basename $$f .pid)"; \
		rm -f "$$f"; \
	done

# ---------------------------------------------------------------------------
# Federation: register blog_demo and pages_demo as trusted peers of each
# other (bilateral, planning/identite_federee.md) — reads each project's
# REAL, freshly (re)generated RS256 public key, so this must run after both
# `make demo-blog` and `make demo-pages`. Idempotent (safe to re-run).
# ---------------------------------------------------------------------------
.PHONY: demo
demo: demo-blog demo-pages demo-federate ## Régénère blog_demo + pages_demo et les fédère (entrée principale)

.PHONY: demo-clean
demo-clean: demo-blog-clean demo-pages-clean  ## Nettoie les deux demos (drop DB + suppression projet)

.PHONY: demo-run
demo-run: demo-blog-run demo-pages-run  ## Lance API + fronts des deux demos en tâche de fond

.PHONY: demo-stop
demo-stop: demo-blog-stop demo-pages-stop  ## Arrête les deux demos (API + fronts + tails)

.PHONY: demo-federate
demo-federate:  ## Enregistre blog_demo et pages_demo comme peers de confiance mutuels
	@# psql only performs :'var' substitution on statements it *reads* (stdin/-f) —
	@# not on a -c argument (that's fed straight to the server, unparsed) — so the
	@# SQL is piped in via stdin rather than passed with -c.
	@# id/name/url/frontend_url come straight from each project's own .env —
	@# never hardcoded — since peer.id has no DEFAULT: it must be the OTHER
	@# project's own HO_PEER_ID, not a locally generated uuid, and name is
	@# self-declared (HO_PEER_NAME), not chosen here (identite_federee.md §4bis).
	@BLOG_ID=$$(grep '^HO_PEER_ID=' $(DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	BLOG_NAME=$$(grep '^HO_PEER_NAME=' $(DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	BLOG_URL=$$(grep '^HO_PEER_URL=' $(DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	BLOG_FRONTEND_URL=$$(grep '^HO_FRONTEND_URL=' $(DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	BLOG_KEY=$$(cat $(DEMO_DIR)/ho_api/public_key.pem); \
	printf '%s\n' "INSERT INTO \"half_orm_meta.identity\".peer (id, name, url, frontend_url, jwt_public_key) VALUES (:'blog_id', :'blog_name', :'blog_url', :'blog_frontend_url', :'blog_key') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, url = EXCLUDED.url, frontend_url = EXCLUDED.frontend_url, jwt_public_key = EXCLUDED.jwt_public_key;" \
	  | psql pages_demo -v blog_id="$$BLOG_ID" -v blog_name="$$BLOG_NAME" -v blog_url="$$BLOG_URL" -v blog_frontend_url="$$BLOG_FRONTEND_URL" -v blog_key="$$BLOG_KEY"
	@PAGES_ID=$$(grep '^HO_PEER_ID=' $(PAGES_DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	PAGES_NAME=$$(grep '^HO_PEER_NAME=' $(PAGES_DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	PAGES_URL=$$(grep '^HO_PEER_URL=' $(PAGES_DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	PAGES_FRONTEND_URL=$$(grep '^HO_FRONTEND_URL=' $(PAGES_DEMO_DIR)/ho_api/.env | cut -d= -f2-); \
	PAGES_KEY=$$(cat $(PAGES_DEMO_DIR)/ho_api/public_key.pem); \
	printf '%s\n' "INSERT INTO \"half_orm_meta.identity\".peer (id, name, url, frontend_url, jwt_public_key) VALUES (:'pages_id', :'pages_name', :'pages_url', :'pages_frontend_url', :'pages_key') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, url = EXCLUDED.url, frontend_url = EXCLUDED.frontend_url, jwt_public_key = EXCLUDED.jwt_public_key;" \
	  | psql blog_demo -v pages_id="$$PAGES_ID" -v pages_name="$$PAGES_NAME" -v pages_url="$$PAGES_URL" -v pages_frontend_url="$$PAGES_FRONTEND_URL" -v pages_key="$$PAGES_KEY"
	@echo "Registered blog_demo <-> pages_demo as trusted peers"
	psql pages_demo -f fixtures/pages_demo_data.sql
	@echo "Loaded fixtures/pages_demo_data.sql (pre-seeded identities + wiki pages)"

.PHONY: demo-access-load
demo-acess-load: demo-blog-access-load demo-pages-access-load

