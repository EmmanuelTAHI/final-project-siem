//go:build windows

package main

import (
	"bufio"
	"fmt"
	"os"
)

func pauseBeforeExitOnWindows() {
	fmt.Fprintln(os.Stderr, "\nAppuyez sur Entrée pour fermer...")
	bufio.NewReader(os.Stdin).ReadString('\n')
}
