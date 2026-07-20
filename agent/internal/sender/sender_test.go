package sender

import (
	"compress/gzip"
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"testing"

	"logplus-agent/internal/model"
)

func gzipReader(r *http.Request) (io.Reader, error) {
	return gzip.NewReader(r.Body)
}

func decodeFirstNDJSONEvent(t *testing.T, r io.Reader, out *model.Event) {
	t.Helper()
	if err := json.NewDecoder(r).Decode(out); err != nil {
		t.Fatalf("décodage NDJSON échoué: %v", err)
	}
}

func testLogger() *log.Logger { return log.New(io.Discard, "", 0) }

func TestNew_RejectsPlainHTTPWithoutInsecure(t *testing.T) {
	_, err := New("http://example.com", "tok", false, testLogger())
	if err == nil {
		t.Fatal("attendu une erreur pour une URL http:// sans --insecure, obtenu nil")
	}
}

func TestNew_AllowsPlainHTTPWithInsecure(t *testing.T) {
	_, err := New("http://example.com", "tok", true, testLogger())
	if err != nil {
		t.Fatalf("http:// avec insecure=true devrait être accepté, erreur: %v", err)
	}
}

func TestNew_AllowsHTTPS(t *testing.T) {
	_, err := New("https://example.com", "tok", false, testLogger())
	if err != nil {
		t.Fatalf("https:// devrait toujours être accepté, erreur: %v", err)
	}
}

func TestSend_SetsBearerTokenAndGzip(t *testing.T) {
	var gotAuth, gotEncoding string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotEncoding = r.Header.Get("Content-Encoding")
		w.WriteHeader(http.StatusCreated)
	}))
	defer srv.Close()

	sd, err := New(srv.URL, "logplus_agt_secret", true, testLogger())
	if err != nil {
		t.Fatal(err)
	}
	if err := sd.Send(context.Background(), []model.Event{{Message: "hello", Source: "test"}}); err != nil {
		t.Fatalf("Send a échoué: %v", err)
	}
	if gotAuth != "Bearer logplus_agt_secret" {
		t.Errorf("Authorization = %q, attendu 'Bearer logplus_agt_secret'", gotAuth)
	}
	if gotEncoding != "gzip" {
		t.Errorf("Content-Encoding = %q, attendu 'gzip'", gotEncoding)
	}
}

func TestSend_UnauthorizedReturnsAuthError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"message":"invalid token"}`))
	}))
	defer srv.Close()

	sd, err := New(srv.URL, "bad-token", true, testLogger())
	if err != nil {
		t.Fatal(err)
	}
	err = sd.Send(context.Background(), []model.Event{{Message: "hello"}})
	if err == nil {
		t.Fatal("attendu une AuthError, obtenu nil")
	}
	if _, ok := err.(*AuthError); !ok {
		t.Fatalf("attendu *AuthError, obtenu %T: %v", err, err)
	}
}

func TestSend_EmptyBatchIsNoop(t *testing.T) {
	called := false
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
	}))
	defer srv.Close()

	sd, err := New(srv.URL, "tok", true, testLogger())
	if err != nil {
		t.Fatal(err)
	}
	if err := sd.Send(context.Background(), nil); err != nil {
		t.Fatalf("un batch vide ne doit jamais échouer: %v", err)
	}
	if called {
		t.Error("aucune requête ne devrait être envoyée pour un batch vide")
	}
}

func TestTestConnection_SendsIdentifiableSelfTestEvent(t *testing.T) {
	var received model.Event
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gz, err := gzipReader(r)
		if err != nil {
			t.Errorf("décompression échouée: %v", err)
		} else {
			decodeFirstNDJSONEvent(t, gz, &received)
		}
		w.WriteHeader(http.StatusCreated)
	}))
	defer srv.Close()

	sd, err := New(srv.URL, "tok", true, testLogger())
	if err != nil {
		t.Fatal(err)
	}
	if err := sd.TestConnection(context.Background(), "test-host"); err != nil {
		t.Fatalf("TestConnection a échoué: %v", err)
	}
	if received.Source != "agent_selftest" {
		t.Errorf("Source = %q, attendu 'agent_selftest' (pour ne pas être confondu avec un vrai log)", received.Source)
	}
	if received.Hostname != "test-host" {
		t.Errorf("Hostname = %q, attendu 'test-host'", received.Hostname)
	}
}
