FROM golang:1.22-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git

RUN echo "nameserver 8.8.8.8" >> /etc/resolv.conf
RUN echo "nameserver 114.114.114.114" >> /etc/resolv.conf

ENV GOPROXY=https://goproxy.cn,direct
ENV GOSUMDB=off

COPY go.mod ./
RUN go mod download

COPY . .
RUN go mod tidy

# Build static binary with purego tag to avoid CGO dependency
# This ensures the binary works on any Linux distribution regardless of GLIBC version
RUN CGO_ENABLED=0 go build -tags "purego netgo" -ldflags="-s -w -extldflags=-static" -o srmc-agent .

FROM alpine:3.19

RUN apk add --no-cache ca-certificates docker-cli docker-cli-compose

WORKDIR /app

COPY --from=builder /app/srmc-agent /app/srmc-agent

RUN mkdir -p /etc/srmc-agent /var/log/srmc-agent

EXPOSE 8080

CMD ["/app/srmc-agent", "-config", "/etc/srmc-agent/config.yaml"]
