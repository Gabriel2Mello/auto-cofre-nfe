// Compilado para CLR 4 do Windows 10/11; nao exige .NET 4.8 para iniciar.
using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;
using Microsoft.Win32;

internal class EstadoRequisitos
{
    internal bool DotNet48, WebView2;
}

internal class PreparadorCofre
{
    internal static object Registro(RegistryHive hive, string caminho, string nome)
    {
        using (RegistryKey raiz = RegistryKey.OpenBaseKey(hive, RegistryView.Registry32))
        using (RegistryKey chave = raiz.OpenSubKey(caminho))
            return chave == null ? null : chave.GetValue(nome);
    }

    internal static bool VersaoWebViewValida(object valor)
    {
        Version versao;
        return Version.TryParse(Convert.ToString(valor), out versao) && versao > new Version(0, 0, 0, 0);
    }

    internal static EstadoRequisitos Detectar()
    {
        const string caminho = @"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
        return new EstadoRequisitos {
            DotNet48 = Convert.ToInt64(Registro(RegistryHive.LocalMachine, @"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full", "Release")) >= 528040,
            WebView2 = VersaoWebViewValida(Registro(RegistryHive.LocalMachine, caminho, "pv")) ||
                       VersaoWebViewValida(Registro(RegistryHive.CurrentUser, caminho, "pv"))
        };
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ArquivoTrust
    {
        internal uint Tamanho;
        [MarshalAs(UnmanagedType.LPWStr)] internal string Caminho;
        internal IntPtr Arquivo, Assunto;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct DadosTrust
    {
        internal uint Tamanho;
        internal IntPtr Politica, Sip;
        internal uint Interface, Revogacao, Escolha;
        internal IntPtr Arquivo;
        internal uint Acao;
        internal IntPtr Estado, Url;
        internal uint Flags, Contexto;
        internal IntPtr ConfiguracaoAssinatura;
    }

    [DllImport("wintrust.dll", ExactSpelling = true)]
    private static extern int WinVerifyTrust(IntPtr janela, ref Guid acao, ref DadosTrust dados);

    internal static void ValidarAssinatura(string caminho)
    {
        // Authenticode do Windows: somente retorno zero indica confianca.
        Guid acao = new Guid("00AAC56B-CD44-11D0-8CC2-00C04FC295EE");
        ArquivoTrust arquivo = new ArquivoTrust {
            Tamanho = (uint)Marshal.SizeOf(typeof(ArquivoTrust)), Caminho = Path.GetFullPath(caminho)
        };
        IntPtr memoria = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(ArquivoTrust)));
        Marshal.StructureToPtr(arquivo, memoria, false);
        DadosTrust dados = new DadosTrust {
            Tamanho = (uint)Marshal.SizeOf(typeof(DadosTrust)), Interface = 2,
            Revogacao = 1, Escolha = 1, Arquivo = memoria, Acao = 1, Flags = 0x80
        };
        try {
            int codigo = WinVerifyTrust(new IntPtr(-1), ref acao, ref dados);
            if (codigo != 0)
                throw new InvalidOperationException("Assinatura invalida ou nao verificavel: 0x" + codigo.ToString("X8"));
            using (X509Certificate certificado = X509Certificate.CreateFromSignedFile(caminho))
            using (X509Certificate2 editor = new X509Certificate2(certificado)) {
                if (editor.GetNameInfo(X509NameType.SimpleName, false) != "Microsoft Corporation")
                    throw new InvalidOperationException("O instalador nao foi assinado pela Microsoft Corporation.");
            }
        } finally {
            dados.Acao = 2; // WTD_STATEACTION_CLOSE
            WinVerifyTrust(new IntPtr(-1), ref acao, ref dados);
            Marshal.DestroyStructure(memoria, typeof(ArquivoTrust));
            Marshal.FreeHGlobal(memoria);
        }
    }

    internal static string Baixar(string url, string nome)
    {
        string pasta = Path.Combine(Path.GetTempPath(), "cofre-pre-requisitos-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(pasta);
        string arquivo = Path.Combine(pasta, nome);
        ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
        Console.WriteLine("Baixando " + nome + " da Microsoft...");
        using (WebClient cliente = new WebClient()) cliente.DownloadFile(url, arquivo);
        ValidarAssinatura(arquivo);
        return arquivo;
    }

    internal static int Executar(string arquivo, string argumentos, bool administrador)
    {
        ProcessStartInfo opcoes = new ProcessStartInfo(arquivo, argumentos) {
            UseShellExecute = true, WindowStyle = ProcessWindowStyle.Hidden
        };
        if (administrador) opcoes.Verb = "runas";
        using (Process processo = Process.Start(opcoes)) {
            processo.WaitForExit();
            return processo.ExitCode;
        }
    }

    internal static int Instalar(Func<EstadoRequisitos> detectar, Func<string, string, string> baixar,
                                Func<string, string, bool, int> executar)
    {
        EstadoRequisitos estado = detectar();
        if (!estado.DotNet48) {
            Console.WriteLine(".NET Framework 4.8 ausente. Autorize o administrador quando solicitado.");
            string arquivo = baixar("https://go.microsoft.com/fwlink/?LinkId=2085155", "ndp48-web.exe");
            int codigo = executar(arquivo, "/q /norestart", true);
            if (codigo == 3010 || codigo == 1641) {
                Console.WriteLine("Reinicie o Windows quando puder e execute este preparador novamente.");
                return 3010;
            }
            if (codigo != 0) throw new InvalidOperationException("Instalacao do .NET falhou (codigo " + codigo + ").");
            if (!detectar().DotNet48) throw new InvalidOperationException(".NET 4.8 ainda nao detectado. Consulte a TI.");
        }
        if (!estado.WebView2) {
            Console.WriteLine("WebView2 ausente. Instalando para o usuario atual...");
            string arquivo = baixar("https://go.microsoft.com/fwlink/p/?LinkId=2124703", "MicrosoftEdgeWebview2Setup.exe");
            int codigo = executar(arquivo, "/silent /install", false);
            if (codigo != 0) throw new InvalidOperationException("Instalacao do WebView2 falhou (codigo " + codigo + ").");
        }
        EstadoRequisitos final = detectar();
        if (!final.DotNet48 || !final.WebView2) throw new InvalidOperationException("Pre-requisitos ainda nao detectados. Consulte a TI.");
        Console.WriteLine("Pre-requisitos prontos. Abra Cofre NFe.exe na pasta extraida.");
        return 0;
    }

    internal static int Main(string[] args)
    {
        bool verificar = args.Length == 1 && args[0] == "--verificar";
        int codigo = 1;
        try {
            if (args.Length != 0 && !verificar) throw new ArgumentException("Opcao disponivel: --verificar");
            if (verificar) {
                EstadoRequisitos estado = Detectar();
                Console.WriteLine("DotNet48=" + estado.DotNet48 + "; WebView2=" + estado.WebView2);
                return 0;
            }
            codigo = Instalar(Detectar, Baixar, Executar);
        } catch (Exception erro) {
            Console.WriteLine("Nao foi possivel preparar o Cofre: " + erro.Message);
            Console.WriteLine("Confira internet, permissoes e politicas da empresa com a TI.");
        }
        if (!Console.IsInputRedirected) {
            Console.WriteLine("Pressione uma tecla para fechar.");
            Console.ReadKey(true);
        }
        return codigo;
    }
}
