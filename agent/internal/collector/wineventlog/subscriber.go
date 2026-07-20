//go:build windows

package wineventlog

import (
	"context"
	"encoding/xml"
	"fmt"
	"log"
	"sync"
	"time"

	"logplus-agent/internal/model"
	"logplus-agent/internal/spool"
)

// Start abonne un poste Windows aux canaux donnés (ex: Security, System) en
// temps réel (EvtSubscribe en mode callback) et bloque jusqu'à annulation
// du contexte. Reprend après le dernier événement traité via un bookmark
// persisté par canal dans le spool.
func Start(ctx context.Context, channels []string, sp *spool.Spool, logger *log.Logger, emit func(model.Event)) {
	var wg sync.WaitGroup
	for _, ch := range channels {
		wg.Add(1)
		go func(channel string) {
			defer wg.Done()
			runChannel(ctx, channel, sp, logger, emit)
		}(ch)
	}
	wg.Wait()
}

func runChannel(ctx context.Context, channel string, sp *spool.Spool, logger *log.Logger, emit func(model.Event)) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}
		if err := subscribeOnce(ctx, channel, sp, logger, emit); err != nil {
			logger.Printf("wineventlog[%s] interrompu, nouvelle tentative dans 5s: %v", channel, err)
			select {
			case <-ctx.Done():
				return
			case <-time.After(5 * time.Second):
			}
		}
	}
}

func bookmarkMetaKey(channel string) string { return "wineventlog:bookmark:" + channel }

func subscribeOnce(ctx context.Context, channel string, sp *spool.Spool, logger *log.Logger, emit func(model.Event)) error {
	savedBookmarkXML, _ := sp.GetMeta(bookmarkMetaKey(channel))

	// bookmark sert à suivre la position de reprise (mis à jour après
	// chaque événement traité, voir onEvent). subscribeBookmark est ce qui
	// est réellement passé à EvtSubscribe : l'API Win32 EXIGE qu'il soit
	// NULL avec EvtSubscribeToFutureEvents (sinon "The parameter is
	// incorrect") — seul EvtSubscribeStartAfterBookmark accepte un bookmark
	// non-null en entrée.
	var bookmark, subscribeBookmark evtHandle
	var flags uint32
	var err error
	if len(savedBookmarkXML) > 0 {
		bookmark, err = evtCreateBookmark(string(savedBookmarkXML))
		if err != nil {
			logger.Printf("wineventlog[%s] bookmark sauvegardé invalide, reprise depuis maintenant: %v", channel, err)
			bookmark, _ = evtCreateBookmark("")
			flags = evtSubscribeToFutureEvents
		} else {
			flags = evtSubscribeStartAfterBookmark
			subscribeBookmark = bookmark
		}
	} else {
		// Premier démarrage sur ce canal : pas de backfill, seulement les
		// événements à partir de maintenant (cohérent avec le tail Linux).
		bookmark, _ = evtCreateBookmark("")
		flags = evtSubscribeToFutureEvents
	}
	defer evtClose(bookmark)

	onEvent := func(ev evtHandle) {
		processEvent(ev, channel, sp, bookmark, emit)
	}

	sub, unregister, err := evtSubscribe(channel, subscribeBookmark, flags, onEvent)
	if err != nil {
		return err
	}
	defer func() {
		evtClose(sub)
		unregister()
	}()

	logger.Printf("wineventlog[%s] abonné", channel)

	<-ctx.Done()
	return nil
}

// processEvent est appelé de façon SYNCHRONE par le callback EvtSubscribe :
// le handle ev n'est valide que pendant cet appel (voir MSDN), tout
// traitement doit donc se faire ici, jamais après.
func processEvent(ev evtHandle, channel string, sp *spool.Spool, bookmark evtHandle, emit func(model.Event)) {
	xmlStr, err := evtRenderXML(ev)
	if err == nil {
		if e, ok := parseEventXML(xmlStr, channel); ok {
			emit(e)
		}
	}

	if err := evtUpdateBookmark(bookmark, ev); err == nil {
		if bxml, err := evtRenderBookmarkXML(bookmark); err == nil {
			_ = sp.SetMeta(bookmarkMetaKey(channel), []byte(bxml))
		}
	}
}

// --- Parsing XML EvtRenderEventXml ---

type xmlEvent struct {
	System struct {
		Provider struct {
			Name string `xml:"Name,attr"`
		} `xml:"Provider"`
		EventID     int    `xml:"EventID"`
		Level       int    `xml:"Level"`
		Channel     string `xml:"Channel"`
		Computer    string `xml:"Computer"`
		TimeCreated struct {
			SystemTime string `xml:"SystemTime,attr"`
		} `xml:"TimeCreated"`
	} `xml:"System"`
	EventData struct {
		Data []struct {
			Name  string `xml:"Name,attr"`
			Value string `xml:",chardata"`
		} `xml:"Data"`
	} `xml:"EventData"`
}

func parseEventXML(raw, channel string) (model.Event, bool) {
	var xe xmlEvent
	if err := xml.Unmarshal([]byte(raw), &xe); err != nil {
		return model.Event{}, false
	}

	fields := make(map[string]interface{}, len(xe.EventData.Data))
	for _, d := range xe.EventData.Data {
		if d.Name != "" {
			fields[d.Name] = d.Value
		}
	}

	var timeCreated *time.Time
	if parsed, err := time.Parse(time.RFC3339Nano, xe.System.TimeCreated.SystemTime); err == nil {
		timeCreated = &parsed
	}

	e := model.Event{
		Message:     fmt.Sprintf("%s: EventID=%d Channel=%s", xe.System.Provider.Name, xe.System.EventID, channel),
		Hostname:    xe.System.Computer,
		Severity:    mapWindowsLevel(xe.System.Level),
		Source:      "wineventlog",
		EventID:     xe.System.EventID,
		Provider:    xe.System.Provider.Name,
		Channel:     channel,
		Computer:    xe.System.Computer,
		TimeCreated: timeCreated,
		RawFields:   fields,
	}
	return e, true
}

// mapWindowsLevel convertit le niveau Windows Event Log (0=LogAlways,
// 1=Critical, 2=Error, 3=Warning, 4=Information, 5=Verbose) vers les choix
// de sévérité NormalizedLog côté backend.
func mapWindowsLevel(level int) string {
	switch level {
	case 1:
		return "critical"
	case 2:
		return "high"
	case 3:
		return "medium"
	case 4, 0:
		return "info"
	default:
		return "low"
	}
}
