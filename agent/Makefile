BINARY := logplus-agent
DIST := dist

.PHONY: all linux windows checksums clean

all: linux windows checksums

linux:
	mkdir -p $(DIST)
	GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o $(DIST)/$(BINARY)-linux-amd64 ./cmd/$(BINARY)
	GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o $(DIST)/$(BINARY)-linux-arm64 ./cmd/$(BINARY)

windows:
	mkdir -p $(DIST)
	GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o $(DIST)/$(BINARY)-windows-amd64.exe ./cmd/$(BINARY)

checksums:
	cd $(DIST) && for f in $(BINARY)-linux-amd64 $(BINARY)-linux-arm64 $(BINARY)-windows-amd64.exe; do sha256sum "$$f" > "$$f.sha256"; done

clean:
	rm -rf $(DIST)
