package main

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func zipDe(t *testing.T, arquivos map[string]string) []byte {
	t.Helper()
	var buf bytes.Buffer
	z := zip.NewWriter(&buf)
	for nome, conteudo := range arquivos {
		w, err := z.Create(nome)
		if err != nil {
			t.Fatal(err)
		}
		w.Write([]byte(conteudo))
	}
	if err := z.Close(); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func ler(t *testing.T, caminho string) string {
	t.Helper()
	b, err := os.ReadFile(caminho)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func TestPrimeiraVezDescompactaSemAPastaDeCimaEMarcaCompleto(t *testing.T) {
	base := t.TempDir()
	dados := zipDe(t, map[string]string{"Buildsmith/Buildsmith.exe": "exe", "Buildsmith/app/abrir.py": "print(1)"})
	pasta, err := preparar(base, "0.26.1", dados)
	if err != nil {
		t.Fatal(err)
	}
	if pasta != filepath.Join(base, "0.26.1") {
		t.Fatalf("pasta = %s", pasta)
	}
	if ler(t, filepath.Join(pasta, "Buildsmith.exe")) != "exe" || ler(t, filepath.Join(pasta, "app", "abrir.py")) != "print(1)" {
		t.Fatal("arquivos errados")
	}
	if ler(t, filepath.Join(pasta, marca)) != "0.26.1" {
		t.Fatal("sem a marca de completo")
	}
}

func TestSegundaVezNaoDescompactaDeNovo(t *testing.T) {
	base := t.TempDir()
	dados := zipDe(t, map[string]string{"Buildsmith/Buildsmith.exe": "exe"})
	pasta, _ := preparar(base, "0.26.1", dados)
	os.WriteFile(filepath.Join(pasta, "Buildsmith.exe"), []byte("mexido"), 0o644)
	if _, err := preparar(base, "0.26.1", dados); err != nil {
		t.Fatal(err)
	}
	if ler(t, filepath.Join(pasta, "Buildsmith.exe")) != "mexido" {
		t.Fatal("descompactou de novo")
	}
}

func TestExtracaoInterrompidaEhRefeita(t *testing.T) {
	base := t.TempDir()
	os.MkdirAll(filepath.Join(base, "0.26.1"), 0o755) // sem a marca: ficou pela metade
	os.WriteFile(filepath.Join(base, "0.26.1", "lixo.txt"), []byte("x"), 0o644)
	pasta, err := preparar(base, "0.26.1", zipDe(t, map[string]string{"Buildsmith/Buildsmith.exe": "exe"}))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(pasta, "lixo.txt")); !os.IsNotExist(err) {
		t.Fatal("ficou o resto da extração anterior")
	}
	if ler(t, filepath.Join(pasta, "Buildsmith.exe")) != "exe" {
		t.Fatal("não descompactou")
	}
}

func TestCaminhoParaForaDaPastaEhRecusado(t *testing.T) {
	base := t.TempDir()
	dados := zipDe(t, map[string]string{"Buildsmith/../../fora.txt": "x", "Buildsmith/Buildsmith.exe": "exe"})
	if _, err := preparar(filepath.Join(base, "b"), "0.26.1", dados); err == nil {
		t.Fatal("aceitou caminho para fora da pasta")
	}
	if _, err := os.Stat(filepath.Join(base, "fora.txt")); !os.IsNotExist(err) {
		t.Fatal("gravou fora da pasta")
	}
	if _, err := os.Stat(filepath.Join(base, "b", "0.26.1")); !os.IsNotExist(err) {
		t.Fatal("deixou a pasta da versão pela metade")
	}
}

func TestLimpaSoVersoesAntigasCompletas(t *testing.T) {
	base := t.TempDir()
	for _, v := range []string{"0.25.0", "0.26.1"} {
		os.MkdirAll(filepath.Join(base, v), 0o755)
		os.WriteFile(filepath.Join(base, v, marca), []byte(v), 0o644)
	}
	os.MkdirAll(filepath.Join(base, "outra-coisa"), 0o755) // sem marca: não é do lançador
	limparAntigas(base, "0.26.1")
	if _, err := os.Stat(filepath.Join(base, "0.25.0")); !os.IsNotExist(err) {
		t.Fatal("não apagou a versão antiga")
	}
	for _, d := range []string{"0.26.1", "outra-coisa"} {
		if _, err := os.Stat(filepath.Join(base, d)); err != nil {
			t.Fatalf("apagou %s", d)
		}
	}
}

func TestSemProgramaEmbutidoEhErro(t *testing.T) {
	if _, err := preparar(t.TempDir(), "0.26.1", nil); err == nil {
		t.Fatal("aceitou lançador sem o programa")
	}
}
