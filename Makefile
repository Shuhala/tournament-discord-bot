
.PHONY: build
build:
	@docker build -t discord_bot .

.PHONY: run
run:
	@docker run \
		-v $$(pwd):/opt/app \
		discord_bot \
			poetry run errbot

.PHONY: clean
clean:
	rm -rf data/*.db
	docker rmi -f discord_bot

.PHONY: lint
lint: build
	docker run --rm \
		-v $$(pwd):/opt/app \
		discord_bot \
			black . && \
			flake8
