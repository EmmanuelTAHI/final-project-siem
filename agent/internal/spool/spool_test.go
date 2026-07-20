package spool

import (
	"path/filepath"
	"testing"

	"logplus-agent/internal/model"
)

func openTestSpool(t *testing.T) *Spool {
	t.Helper()
	dir := t.TempDir()
	sp, err := Open(filepath.Join(dir, "spool.db"))
	if err != nil {
		t.Fatalf("ouverture spool: %v", err)
	}
	t.Cleanup(func() { sp.Close() })
	return sp
}

func TestPushPop_PreservesOrder(t *testing.T) {
	sp := openTestSpool(t)
	for i := 0; i < 5; i++ {
		if err := sp.Push(model.Event{Message: string(rune('a' + i))}); err != nil {
			t.Fatal(err)
		}
	}
	_, events, err := sp.PopBatch(10)
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 5 {
		t.Fatalf("attendu 5 événements, obtenu %d", len(events))
	}
	for i, e := range events {
		want := string(rune('a' + i))
		if e.Message != want {
			t.Errorf("index %d: message = %q, attendu %q (ordre non préservé)", i, e.Message, want)
		}
	}
}

func TestPopBatch_DoesNotRemoveUntilAck(t *testing.T) {
	sp := openTestSpool(t)
	_ = sp.Push(model.Event{Message: "x"})

	_, events, _ := sp.PopBatch(10)
	if len(events) != 1 {
		t.Fatalf("attendu 1 événement, obtenu %d", len(events))
	}

	// Un deuxième PopBatch sans Ack doit revoir le même événement : c'est ce
	// qui garantit qu'un crash entre lecture et envoi ne perd rien.
	_, events2, _ := sp.PopBatch(10)
	if len(events2) != 1 {
		t.Fatalf("l'événement non-acquitté a disparu du spool (perte de log potentielle)")
	}
}

func TestAck_RemovesEvent(t *testing.T) {
	sp := openTestSpool(t)
	_ = sp.Push(model.Event{Message: "x"})

	ids, _, _ := sp.PopBatch(10)
	if err := sp.Ack(ids); err != nil {
		t.Fatal(err)
	}

	n, err := sp.Len()
	if err != nil {
		t.Fatal(err)
	}
	if n != 0 {
		t.Errorf("Len() = %d après Ack, attendu 0", n)
	}
}

func TestMeta_RoundTrip(t *testing.T) {
	sp := openTestSpool(t)
	if err := sp.SetMeta("bookmark:Security", []byte("xml-bookmark-data")); err != nil {
		t.Fatal(err)
	}
	got, err := sp.GetMeta("bookmark:Security")
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "xml-bookmark-data" {
		t.Errorf("GetMeta = %q, attendu 'xml-bookmark-data'", got)
	}
}

func TestGetMeta_UnknownKeyReturnsNil(t *testing.T) {
	sp := openTestSpool(t)
	got, err := sp.GetMeta("does-not-exist")
	if err != nil {
		t.Fatal(err)
	}
	if got != nil {
		t.Errorf("attendu nil pour une clé absente, obtenu %v", got)
	}
}

func TestPersistsAcrossReopen(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "spool.db")

	sp1, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	_ = sp1.Push(model.Event{Message: "survives restart"})
	sp1.Close()

	sp2, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer sp2.Close()

	_, events, err := sp2.PopBatch(10)
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 1 || events[0].Message != "survives restart" {
		t.Fatalf("l'événement n'a pas survécu à la réouverture du spool: %+v", events)
	}
}
