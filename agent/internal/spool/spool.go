// Package spool est la file d'attente persistante sur disque de l'agent :
// tout événement collecté y est écrit AVANT tentative d'envoi, et n'en est
// retiré qu'une fois l'envoi confirmé par le serveur. Ainsi, une coupure
// réseau ou un redémarrage du service ne perd aucun log — c'est le
// mécanisme central de fiabilité demandé pour l'agent.
//
// Implémentation : bbolt (B+tree embarqué, pur Go, aucune dépendance
// externe, aucun serveur à faire tourner).
package spool

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"time"

	bolt "go.etcd.io/bbolt"

	"logplus-agent/internal/model"
)

var (
	eventsBucket = []byte("events")
	metaBucket   = []byte("meta")
)

type Spool struct {
	db *bolt.DB
}

// Open ouvre (ou crée) le fichier de spool à path.
func Open(path string) (*Spool, error) {
	db, err := bolt.Open(path, 0o600, &bolt.Options{Timeout: 5 * time.Second})
	if err != nil {
		return nil, fmt.Errorf("ouverture spool %s: %w", path, err)
	}
	err = db.Update(func(tx *bolt.Tx) error {
		if _, err := tx.CreateBucketIfNotExists(eventsBucket); err != nil {
			return err
		}
		_, err := tx.CreateBucketIfNotExists(metaBucket)
		return err
	})
	if err != nil {
		db.Close()
		return nil, err
	}
	return &Spool{db: db}, nil
}

func (s *Spool) Close() error { return s.db.Close() }

// Push ajoute un événement à la file, sous une clé auto-incrémentée
// (préserve l'ordre d'arrivée, nécessaire pour ne pas envoyer les logs
// dans le désordre après une coupure).
func (s *Spool) Push(e model.Event) error {
	raw, err := json.Marshal(e)
	if err != nil {
		return fmt.Errorf("sérialisation événement: %w", err)
	}
	return s.db.Update(func(tx *bolt.Tx) error {
		b := tx.Bucket(eventsBucket)
		id, err := b.NextSequence()
		if err != nil {
			return err
		}
		return b.Put(itob(id), raw)
	})
}

// PopBatch lit jusqu'à max événements les plus anciens, SANS les
// supprimer (voir Ack) — pour ne perdre aucun log en cas d'échec d'envoi
// entre la lecture et la confirmation.
func (s *Spool) PopBatch(max int) (ids [][]byte, events []model.Event, err error) {
	err = s.db.View(func(tx *bolt.Tx) error {
		c := tx.Bucket(eventsBucket).Cursor()
		for k, v := c.First(); k != nil && len(ids) < max; k, v = c.Next() {
			var e model.Event
			if unmarshalErr := json.Unmarshal(v, &e); unmarshalErr != nil {
				// Entrée corrompue : on la retire silencieusement du flux
				// normal en la comptant quand même comme "traitée" (Ack)
				// pour ne pas bloquer indéfiniment la file dessus.
				idCopy := append([]byte(nil), k...)
				ids = append(ids, idCopy)
				continue
			}
			idCopy := append([]byte(nil), k...)
			ids = append(ids, idCopy)
			events = append(events, e)
		}
		return nil
	})
	return ids, events, err
}

// Ack supprime définitivement les entrées confirmées comme envoyées.
func (s *Spool) Ack(ids [][]byte) error {
	if len(ids) == 0 {
		return nil
	}
	return s.db.Update(func(tx *bolt.Tx) error {
		b := tx.Bucket(eventsBucket)
		for _, id := range ids {
			if err := b.Delete(id); err != nil {
				return err
			}
		}
		return nil
	})
}

// Len renvoie le nombre d'événements en attente (utile pour `status`).
func (s *Spool) Len() (int, error) {
	n := 0
	err := s.db.View(func(tx *bolt.Tx) error {
		n = tx.Bucket(eventsBucket).Stats().KeyN
		return nil
	})
	return n, err
}

// --- Métadonnées (bookmarks de reprise : offset de fichier, cursor
// journald, bookmark EvtSubscribe Windows...) ---

func (s *Spool) GetMeta(key string) ([]byte, error) {
	var val []byte
	err := s.db.View(func(tx *bolt.Tx) error {
		v := tx.Bucket(metaBucket).Get([]byte(key))
		if v != nil {
			val = append([]byte(nil), v...)
		}
		return nil
	})
	return val, err
}

func (s *Spool) SetMeta(key string, value []byte) error {
	return s.db.Update(func(tx *bolt.Tx) error {
		return tx.Bucket(metaBucket).Put([]byte(key), value)
	})
}

func itob(v uint64) []byte {
	b := make([]byte, 8)
	binary.BigEndian.PutUint64(b, v)
	return b
}
