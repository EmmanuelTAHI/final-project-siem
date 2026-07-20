//go:build !windows

package main

// Sur Linux, `logplus-agent` sans argument est toujours lancé depuis un
// terminal déjà ouvert (pas d'équivalent du double-clic Explorateur) :
// rien à faire, le message d'usage reste visible normalement.
func pauseBeforeExitOnWindows() {}
