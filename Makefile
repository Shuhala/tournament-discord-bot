
.PHONY: build
build:
	@docker build -t discord_bot .

.PHONY: run
run: build
	@docker run \
		-v $$(pwd):/opt/app \
		--name errbot \
		--rm \
		discord_bot \
			poetry run errbot

.PHONY: run-prod
run-prod: build
	@docker run \
		-v $$(pwd):/opt/app \
		--name errbot \
		--rm \
		-d \
		discord_bot \
			poetry run errbot

.PHONY: docker-kill
docker-kill:
	@docker kill errbot || true

.PHONY: clean
clean: docker-kill
	rm -rf data/*.db
	docker rmi -f discord_bot

.PHONY: lint
lint: build
	@docker run --rm -v $$(pwd):/opt/app \
		discord_bot black .
	@docker run --rm -v $$(pwd):/opt/app \
		discord_bot flake8
