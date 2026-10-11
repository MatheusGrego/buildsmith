//go:build embutido

package main

import _ "embed"

// O zip do programa, copiado para cá pelo release/construir.py só na hora de montar (não vai para o repositório).
//
//go:embed programa.zip
var programaZip []byte

func init() { programa = programaZip }
