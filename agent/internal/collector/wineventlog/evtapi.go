//go:build windows

// Package wineventlog lit le journal d'événements Windows nativement via
// l'API wevtapi.dll (EvtSubscribe en mode callback/push), sans passer par
// un outil tiers (NXLog...). Bindings syscall purs — CGO_ENABLED=0, aucune
// dépendance externe au-delà de golang.org/x/sys/windows.
//
// Le mode "pull" (EvtNext avec SignalEvent/Timeout) s'est avéré peu fiable
// en test réel sur cette machine (erreur Win32 4317 "The operation
// identifier is not valid", cause exacte non identifiée avec certitude
// malgré plusieurs pistes explorées) ; le mode callback, recommandé par
// Microsoft et utilisé par les outils de référence du domaine (winlogbeat),
// fonctionne de façon fiable et est retenu ici.
package wineventlog

import (
	"fmt"
	"sync"
	"sync/atomic"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

var (
	modWevtapi = windows.NewLazySystemDLL("wevtapi.dll")

	procEvtSubscribe      = modWevtapi.NewProc("EvtSubscribe")
	procEvtRender         = modWevtapi.NewProc("EvtRender")
	procEvtClose          = modWevtapi.NewProc("EvtClose")
	procEvtCreateBookmark = modWevtapi.NewProc("EvtCreateBookmark")
	procEvtUpdateBookmark = modWevtapi.NewProc("EvtUpdateBookmark")
)

const (
	evtSubscribeToFutureEvents     = 1
	evtSubscribeStartAfterBookmark = 3

	evtSubscribeActionDeliver = 1

	evtRenderEventXml = 1
	evtRenderBookmark = 2
)

type evtHandle uintptr

// --- Dispatch du callback EvtSubscribe (modèle push) ---
//
// Le handle d'événement fourni au callback n'est valide QUE pendant
// l'appel : tout traitement (rendu XML, mise à jour du bookmark) doit se
// faire de façon synchrone à l'intérieur, jamais après (voir MSDN).

var (
	callbackHandlers sync.Map // map[uintptr]func(evtHandle)
	nextCallbackID    uint64
	evtSubscribeCB    = syscall.NewCallback(evtSubscribeCallbackDispatch)
)

func evtSubscribeCallbackDispatch(action, userContext, eventHandle uintptr) uintptr {
	if action == evtSubscribeActionDeliver {
		if v, ok := callbackHandlers.Load(userContext); ok {
			v.(func(evtHandle))(evtHandle(eventHandle))
		}
	}
	return 0
}

// registerCallback enregistre un gestionnaire pour une souscription et
// renvoie l'identifiant à passer en Context à EvtSubscribe, ainsi qu'une
// fonction de nettoyage à appeler après EvtClose de la souscription.
func registerCallback(fn func(evtHandle)) (contextID uintptr, unregister func()) {
	id := atomic.AddUint64(&nextCallbackID, 1)
	contextID = uintptr(id)
	callbackHandlers.Store(contextID, fn)
	return contextID, func() { callbackHandlers.Delete(contextID) }
}

// evtSubscribe s'abonne en mode callback (push) : onEvent est appelé de
// façon synchrone pour chaque évènement livré, jusqu'à evtClose() de la
// souscription renvoyée.
func evtSubscribe(channel string, bookmark evtHandle, flags uint32, onEvent func(evtHandle)) (evtHandle, func(), error) {
	channelPtr, err := syscall.UTF16PtrFromString(channel)
	if err != nil {
		return 0, nil, err
	}
	queryPtr, err := syscall.UTF16PtrFromString("*")
	if err != nil {
		return 0, nil, err
	}

	contextID, unregister := registerCallback(onEvent)

	r1, _, e1 := procEvtSubscribe.Call(
		0,                                    // Session (local)
		0,                                    // SignalEvent (inutilisé en mode callback)
		uintptr(unsafe.Pointer(channelPtr)),  // ChannelPath
		uintptr(unsafe.Pointer(queryPtr)),    // Query
		uintptr(bookmark),                    // Bookmark
		contextID,                            // Context (transmis au callback)
		evtSubscribeCB,                       // Callback
		uintptr(flags),
	)
	if r1 == 0 {
		unregister()
		return 0, nil, fmt.Errorf("EvtSubscribe(%s): %w", channel, e1)
	}
	return evtHandle(r1), unregister, nil
}

// evtRenderXML rend un événement en XML complet (EvtRenderEventXml).
func evtRenderXML(event evtHandle) (string, error) {
	return evtRender(uintptr(event), evtRenderEventXml)
}

// evtRenderBookmarkXML rend un bookmark en XML (pour persistance).
func evtRenderBookmarkXML(bookmark evtHandle) (string, error) {
	return evtRender(uintptr(bookmark), evtRenderBookmark)
}

func evtRender(handle uintptr, flags uint32) (string, error) {
	var used, propCount uint32
	// Premier appel pour connaître la taille du buffer nécessaire.
	procEvtRender.Call(0, handle, uintptr(flags), 0, 0, uintptr(unsafe.Pointer(&used)), uintptr(unsafe.Pointer(&propCount)))

	if used == 0 {
		return "", fmt.Errorf("EvtRender: taille de buffer nulle")
	}
	buf := make([]uint16, used/2+1)
	r1, _, e1 := procEvtRender.Call(
		0, handle, uintptr(flags),
		uintptr(len(buf)*2),
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(unsafe.Pointer(&used)),
		uintptr(unsafe.Pointer(&propCount)),
	)
	if r1 == 0 {
		return "", fmt.Errorf("EvtRender: %w", e1)
	}
	return syscall.UTF16ToString(buf), nil
}

func evtCreateBookmark(bookmarkXML string) (evtHandle, error) {
	if bookmarkXML == "" {
		r1, _, e1 := procEvtCreateBookmark.Call(0)
		if r1 == 0 {
			return 0, fmt.Errorf("EvtCreateBookmark(vide): %w", e1)
		}
		return evtHandle(r1), nil
	}
	ptr, err := syscall.UTF16PtrFromString(bookmarkXML)
	if err != nil {
		return 0, err
	}
	r1, _, e1 := procEvtCreateBookmark.Call(uintptr(unsafe.Pointer(ptr)))
	if r1 == 0 {
		return 0, fmt.Errorf("EvtCreateBookmark: %w", e1)
	}
	return evtHandle(r1), nil
}

func evtUpdateBookmark(bookmark, event evtHandle) error {
	r1, _, e1 := procEvtUpdateBookmark.Call(uintptr(bookmark), uintptr(event))
	if r1 == 0 {
		return fmt.Errorf("EvtUpdateBookmark: %w", e1)
	}
	return nil
}

func evtClose(h evtHandle) {
	if h != 0 {
		procEvtClose.Call(uintptr(h))
	}
}
