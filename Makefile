DC = docker compose

up:
	$(DC) up -d

down:
	$(DC) down

build:
	$(DC) build

rebuild:
	$(DC) build --no-cache

logs:
	$(DC) logs -f app postgres

ps:
	$(DC) ps

migrate:
	$(DC) run --rm app migrate

bot:
	$(DC) run --rm app bot

notifications:
	$(DC) run --rm app notifications

test:
	$(DC) run --rm app test
