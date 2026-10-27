// Testes sinteticos; nunca instala runtimes. Compilar junto de src/PrepararCofre.cs.
using System;
using System.IO;

internal class TestPrepararCofre
{
    private static void Exigir(bool condicao, string mensagem)
    {
        if (!condicao) throw new Exception(mensagem);
    }

    internal static int Main(string[] args)
    {
        try {
            Exigir(!PreparadorCofre.VersaoWebViewValida(null), "Versao ausente");
            Exigir(!PreparadorCofre.VersaoWebViewValida("invalida"), "Versao invalida");
            Exigir(!PreparadorCofre.VersaoWebViewValida("0.0.0.0"), "Versao zero");
            Exigir(PreparadorCofre.VersaoWebViewValida("140.0.3485.0"), "Versao valida");
            foreach (string cenario in new[] { "existentes", "ausentes", "reiniciar", "cancelado", "nao-confirmado", "webview-falhou" }) {
                EstadoRequisitos estado = new EstadoRequisitos { DotNet48 = cenario == "existentes", WebView2 = cenario == "existentes" };
                int downloads = 0, instalacoes = 0, codigo = -1;
                bool falhou = false;
                try {
                    codigo = PreparadorCofre.Instalar(() => estado, (url, nome) => {
                        Exigir(url.StartsWith("https://go.microsoft.com/"), "URL oficial");
                        downloads++;
                        return nome;
                    }, (arquivo, argumentos, admin) => {
                        instalacoes++;
                        if (arquivo == "ndp48-web.exe") {
                            Exigir(admin && argumentos == "/q /norestart", ".NET deve elevar e impedir reinicio automatico");
                            if (cenario == "reiniciar") return 3010;
                            if (cenario == "cancelado") return 1602;
                            if (cenario != "nao-confirmado") estado.DotNet48 = true;
                        } else {
                            Exigir(!admin && argumentos == "/silent /install", "WebView2 deve usar o usuario atual");
                            if (cenario == "webview-falhou") return 1603;
                            estado.WebView2 = true;
                        }
                        return 0;
                    });
                } catch (InvalidOperationException) { falhou = true; }
                if (cenario == "existentes") Exigir(codigo == 0 && downloads == 0 && instalacoes == 0, "Nao reinstalar existentes");
                else if (cenario == "ausentes") Exigir(codigo == 0 && instalacoes == 2, "Instalar ausentes");
                else if (cenario == "reiniciar") Exigir(codigo == 3010 && instalacoes == 1, "Parar para reinicio");
                else Exigir(falhou, "Falha deve ser propagada: " + cenario);
            }
            string semAssinatura = Path.GetTempFileName();
            File.WriteAllText(semAssinatura, "sintetico");
            bool rejeitado = false;
            try { PreparadorCofre.ValidarAssinatura(semAssinatura); }
            catch (InvalidOperationException) { rejeitado = true; }
            Exigir(rejeitado, "Arquivo sem assinatura deve ser rejeitado");
            // URLs oficiais opcionais, somente download e assinatura; sem executar instaladores.
            if (args.Length == 1 && args[0] == "--downloads") {
                PreparadorCofre.Baixar("https://go.microsoft.com/fwlink/?LinkId=2085155", "ndp48-web.exe");
                PreparadorCofre.Baixar("https://go.microsoft.com/fwlink/p/?LinkId=2124703", "MicrosoftEdgeWebview2Setup.exe");
            }
            Console.WriteLine("OK: deteccao, instalacao condicional, UAC, reinicio, falhas e Authenticode.");
            return 0;
        } catch (Exception erro) {
            Console.Error.WriteLine(erro);
            return 1;
        }
    }
}
