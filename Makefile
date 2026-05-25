.PHONY: up down run-arp run-mitm run-dns run-syn

DOCKER_COMPOSE := docker compose

up:
	@if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then \
		$(DOCKER_COMPOSE) up -d --build; \
		echo "Stack up."; \
	else \
		echo "ERROR: no docker-compose.yml found in repository. Nothing to start."; exit 1; \
	fi

down:
	@if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then \
		$(DOCKER_COMPOSE) down; \
	else \
		echo "Nothing to stop (no docker-compose.yml)."; \
	fi

run-arp:
	sudo .venv/bin/netlab run arp_spoof \
		--output http_post \
		--output-url http://127.0.0.1:8765/events \
		--auth-header "Authorization: Bearer changeme-receiver-token"

run-mitm:
	sudo .venv/bin/netlab run mitm \
		--output http_post \
		--output-url http://127.0.0.1:8765/events \
		--auth-header "Authorization: Bearer changeme-receiver-token"

run-dns:
	sudo .venv/bin/netlab run dns_poison \
		--output http_post \
		--output-url http://127.0.0.1:8765/events \
		--auth-header "Authorization: Bearer changeme-receiver-token"

run-syn:
	sudo .venv/bin/netlab run syn_flood \
		--output http_post \
		--output-url http://127.0.0.1:8765/events \
		--auth-header "Authorization: Bearer changeme-receiver-token"
