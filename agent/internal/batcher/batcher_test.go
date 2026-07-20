package batcher

import (
	"context"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	"logplus-agent/internal/model"
	"logplus-agent/internal/sender"
	"logplus-agent/internal/spool"
)

func testLogger() *log.Logger { return log.New(io.Discard, "", 0) }

func openTestSpool(t *testing.T) *spool.Spool {
	t.Helper()
	sp, err := spool.Open(filepath.Join(t.TempDir(), "spool.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { sp.Close() })
	return sp
}

func TestBatcher_FlushesAndAcksOnSuccess(t *testing.T) {
	var received int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&received, 1)
		w.WriteHeader(http.StatusCreated)
	}))
	defer srv.Close()

	sp := openTestSpool(t)
	sd, err := sender.New(srv.URL, "tok", true, testLogger())
	if err != nil {
		t.Fatal(err)
	}
	b := New(sp, sd, testLogger(), 20*time.Millisecond, 500, 1<<20)

	if err := b.Add(model.Event{Message: "hello"}); err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	go b.Run(ctx)

	deadline := time.Now().Add(1 * time.Second)
	for time.Now().Before(deadline) {
		n, _ := sp.Len()
		if n == 0 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}

	n, _ := sp.Len()
	if n != 0 {
		t.Errorf("le spool contient encore %d événement(s) non acquitté(s) après succès d'envoi", n)
	}
	if atomic.LoadInt32(&received) == 0 {
		t.Error("le serveur n'a reçu aucune requête")
	}
}

func TestBatcher_KeepsEventsInSpoolOnServerFailure(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	sp := openTestSpool(t)
	sd, err := sender.New(srv.URL, "tok", true, testLogger())
	if err != nil {
		t.Fatal(err)
	}
	b := New(sp, sd, testLogger(), 20*time.Millisecond, 500, 1<<20)

	if err := b.Add(model.Event{Message: "hello"}); err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()
	b.Run(ctx) // bloque jusqu'au timeout du contexte (flush final inclus)

	n, err := sp.Len()
	if err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("attendu 1 événement conservé dans le spool après échec serveur, obtenu %d (perte de log)", n)
	}
}
