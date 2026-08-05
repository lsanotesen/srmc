APP_NAME := srmc-agent
VERSION := 1.0.0
BUILD_TIME := $(shell date -u +%Y%m%d%H%M%S)

.PHONY: all build build-linux-amd64 build-linux-arm64 build-windows-amd64 clean run test

all: build

build: build-linux-amd64 build-linux-arm64

build-linux-amd64:
	GOOS=linux GOARCH=amd64 go build -ldflags "-X main.version=$(VERSION) -X main.buildTime=$(BUILD_TIME)" -o dist/$(APP_NAME)-linux-amd64 .

build-linux-arm64:
	GOOS=linux GOARCH=arm64 go build -ldflags "-X main.version=$(VERSION) -X main.buildTime=$(BUILD_TIME)" -o dist/$(APP_NAME)-linux-arm64 .

build-windows-amd64:
	GOOS=windows GOARCH=amd64 go build -ldflags "-X main.version=$(VERSION) -X main.buildTime=$(BUILD_TIME)" -o dist/$(APP_NAME)-windows-amd64.exe .

clean:
	rm -rf dist/

run:
	go run . -config config.yaml

test:
	go test ./...