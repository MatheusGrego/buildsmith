// Lançador do Buildsmith: um exe só para baixar.
//
// O programa (a mesma pasta do zip da release: Buildsmith.exe, python.exe, pythonw.exe, runtime\, app\, skills\...)
// vai embutido. Na primeira vez ele descompacta em %LOCALAPPDATA%\Buildsmith\<versão>\ (o servidor, os scripts e o
// plugin do Claude precisam dos arquivos numa pasta que fica); depois só roda o Buildsmith.exe de lá com os mesmos
// argumentos. Versão nova descompacta em outra pasta e apaga as antigas. Os dados do jogador ficam em
// %USERPROFILE%\.buildsmith e não são tocados.
//
// Não rode `go build` direto: `python release/construir.py` embute o programa (tag "embutido") e o ícone.
package main

import (
	"archive/zip"
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

const marca = ".completo" // gravada por último: pasta sem ela é extração pela metade

var (
	versao   = "dev" // -ldflags "-X main.versao=0.26.1"
	programa []byte  // o zip do programa (embutido.go, com a tag "embutido")
)

func pastaBase() (string, error) {
	if d := os.Getenv("LOCALAPPDATA"); d != "" {
		return filepath.Join(d, "Buildsmith"), nil
	}
	d, err := os.UserCacheDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(d, "Buildsmith"), nil
}

// extrair descompacta o zip em destino tirando a pasta de cima ("Buildsmith/"); caminho que sai de destino é erro.
func extrair(dados []byte, destino string) error {
	z, err := zip.NewReader(bytes.NewReader(dados), int64(len(dados)))
	if err != nil {
		return err
	}
	raiz, err := filepath.Abs(destino)
	if err != nil {
		return err
	}
	for _, f := range z.File {
		partes := strings.SplitN(strings.ReplaceAll(f.Name, "\\", "/"), "/", 2)
		if len(partes) < 2 || partes[1] == "" {
			continue
		}
		alvo := filepath.Join(raiz, filepath.FromSlash(partes[1]))
		if alvo != raiz && !strings.HasPrefix(alvo, raiz+string(os.PathSeparator)) {
			return fmt.Errorf("caminho fora da pasta no programa embutido: %s", f.Name)
		}
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(alvo, 0o755); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(alvo), 0o755); err != nil {
			return err
		}
		if err := copiar(f, alvo); err != nil {
			return err
		}
	}
	return nil
}

func copiar(f *zip.File, alvo string) error {
	r, err := f.Open()
	if err != nil {
		return err
	}
	defer r.Close()
	w, err := os.OpenFile(alvo, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	if _, err := io.Copy(w, r); err != nil {
		w.Close()
		return err
	}
	return w.Close()
}

func completa(pasta string) bool {
	_, err := os.Stat(filepath.Join(pasta, marca))
	return err == nil
}

// preparar devolve a pasta da versão, descompactando o programa se ela ainda não está completa.
func preparar(base, versao string, dados []byte) (string, error) {
	if len(dados) == 0 {
		return "", errors.New("este lançador não traz o programa (monte com python release/construir.py)")
	}
	pasta := filepath.Join(base, versao)
	if completa(pasta) {
		return pasta, nil
	}
	tmp := pasta + ".novo-" + strconv.Itoa(os.Getpid())
	os.RemoveAll(tmp)
	if err := extrair(dados, tmp); err != nil {
		os.RemoveAll(tmp)
		return "", err
	}
	if err := os.WriteFile(filepath.Join(tmp, marca), []byte(versao), 0o644); err != nil {
		os.RemoveAll(tmp)
		return "", err
	}
	os.RemoveAll(pasta) // resto de uma extração interrompida
	if err := os.Rename(tmp, pasta); err != nil {
		os.RemoveAll(tmp)
		if completa(pasta) { // outro lançador aberto ao mesmo tempo terminou primeiro
			return pasta, nil
		}
		return "", err
	}
	return pasta, nil
}

// limparAntigas apaga as outras versões completas. Renomeia antes: pasta em uso (servidor velho ainda de pé) não
// renomeia e fica inteira para a próxima vez, em vez de ficar pela metade.
func limparAntigas(base, atual string) {
	entradas, err := os.ReadDir(base)
	if err != nil {
		return
	}
	for _, e := range entradas {
		pasta := filepath.Join(base, e.Name())
		if !e.IsDir() || e.Name() == atual || !completa(pasta) {
			continue
		}
		lixo := pasta + ".apagar-" + strconv.Itoa(os.Getpid())
		if os.Rename(pasta, lixo) == nil {
			os.RemoveAll(lixo)
		}
	}
}

func main() {
	base, err := pastaBase()
	if err == nil {
		var pasta string
		if pasta, err = preparar(base, versao, programa); err == nil {
			self, _ := os.Executable()
			cmd := exec.Command(filepath.Join(pasta, "Buildsmith.exe"), os.Args[1:]...)
			cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
			cmd.Env = append(os.Environ(), "BUILDSMITH_LANCADOR="+self) // o atalho aponta para este exe, não para a pasta da versão
			err = cmd.Run()
			limparAntigas(base, versao)
			var saida *exec.ExitError
			if errors.As(err, &saida) {
				os.Exit(saida.ExitCode())
			}
		}
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "Buildsmith: não consegui abrir:", err)
		os.Exit(1)
	}
}
