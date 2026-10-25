# Cofre NF-e desktop

Entrada `cofre.py`: pywebview 6.2.1 + WebView2/WinForms, backend e janela no
mesmo processo; HTTP em thread própria e executor fiscal na thread existente.
Python local conferido: 3.13.13 x64. `main.py` conserva o modo console.
Windows com .NET Framework 4.8 e WebView2 Evergreen são requisitos do destino;
o pacote não instala esses runtimes. Não há fallback para Internet Explorer.

## Preparar e abrir

```powershell
Set-Location 'C:\Users\ADM07\Projetos\Nunes\auto-cofre-nfe'
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
& .\.venv\Scripts\python.exe cofre.py
# Ou Abrir Cofre NFe.cmd
& '.\Criar Atalho Cofre NFe.ps1'
```

O iniciador restaura a instância saudável da mesma sessão, inclusive minimizada,
sem navegação, novo formulário ou repetição de lote/decisão. Aguarda inicialização
e saída em curso por até 15 segundos e volta a disputar a trava quando liberada.
Um processo sem resposta continua sendo dono da trava; não é terminado à força.
Uma versão web antiga deve ser encerrada normalmente antes de usar o desktop.

`AppUserModelID=Nunes.Cofre.Desktop.1` identifica processo, janela e atalho;
comando de relançamento, nome e ícone pertencem à Cofre. Gere novamente atalhos
após mover a instalação. A fixação na barra é uma ação manual do usuário.
O Windows pode negar foco e sinalizar o botão na barra; não se simula teclado.

## Encerrar e trabalhar com o Hub

X ocioso solicita saída. X em processamento confirma uma vez, solicita a mesma
parada cooperativa existente e mantém a janela com indicação de encerramento
até a fronteira segura. Cancelar a confirmação mantém a operação. **Encerrar**
confirma pela aplicação; o Hub confirma no seu próprio monitor. Não há segunda
confirmação na Cofre para um pedido já confirmado nessas telas.
Não são interrompidas gravação, validação nem sinalização em curso. A saída
aguarda o worker antes de fechar o sincronizador e liberar a exclusividade.

No desktop, presença continua contando conexões reais; sua queda isolada não
encerra a aplicação. A janela passa a controlar sua vida. O Hub inicia ou
restaura a Cofre sem abrir navegador e pode ser encerrado sem fechar a Cofre.
Ferramentas web continuam usando o navegador. Reinicie um Hub antigo para
carregar essa integração. Não há imports de repositórios irmãos em execução.

`POST /desktop/ativar` exige Host exato, token da integração, ausência de Origin,
JSON e corpo fixo `{}`. A resposta confirma protocolo, aplicação, instância, PID
e desktop 1. Não recebe caminhos nem comandos livres. O iniciador não segue
redirecionamentos nem usa proxy para controle local. As rotas da página continuam
usando o token da interface e a validação de Origin. Nenhum objeto Python é
exposto ao JavaScript.

## Dados e pacote

```powershell
& '.\Build Desktop.ps1'
& '.\dist\Cofre NFe\Cofre NFe.exe'
& '.\dist\Cofre NFe\Cofre NFe.exe' --criar-atalho "$PWD\Cofre Desktop.lnk"
```

Distribua a pasta inteira `dist\Cofre NFe`, incluindo `_internal`. Não basta o
exe. Credenciais, catálogo real, métricas e documentos não entram no build.
O pacote usa `%LOCALAPPDATA%\Nunes\Cofre` para `emitentes_conhecidos.json`,
`.cofre-gravacoes`, `desktop-tema.json` e `desktop-janela.json`. Tema claro é
o padrão; escolha manual e geometria sobrevivem à troca de porta e reinício.
Geometria inválida usa o padrão; monitor removido ajusta o retângulo à área útil.
Fechar minimizada não faz o próximo início ficar oculto.

No desenvolvimento, catálogo e `.cofre-gravacoes` conservam a raiz do projeto;
preferências visuais usam o perfil. `NUNES_COFRE_DADOS` substitui explicitamente
ambos para ensaios ou uma instalação com dados em outra pasta persistente.
Métricas e presença mantêm seus próprios contratos e overrides independentes.
O vínculo opcional da central no pacote fica em `central.json` nessa pasta
persistente. `NUNES_CENTRAL_CONFIG` mantém precedência. No desenvolvimento,
continua em `.local/central.json`. Sem vínculo, a sincronização permanece desativada.

**Migração para pacote:** com a ferramenta fechada e backup, o responsável deve
copiar o catálogo e a pasta completa `.cofre-gravacoes` da instalação anterior
para a pasta de dados escolhida, antes da primeira operação. Não há migração,
mesclagem nem leitura automática de dados de produção. Mantenha a mesma pasta
nas atualizações e no console de recuperação. Para o script de recuperação
de uma instalação empacotada, use Python com `requirements.txt` e configure
`NUNES_COFRE_DADOS` para essa pasta antes de executar `recuperar_documentos.py`.
Os registros legados no destino fiscal continuam legíveis segundo a política E5.
O pacote windowed não substitui a ferramenta de recuperação de console.
Se havia sincronização central, copie também o vínculo `.local/central.json`
para `central.json` na pasta persistente ou mantenha o override explícito.

O Hub pode usar `pasta` apontando à pasta distribuída, `entrada: "Cofre NFe.exe"`
e `ambientes: []`. No desenvolvimento, o catálogo mantém `cofre.py` e `.venv`.
Catálogos do Hub empacotado precisam ser ajustados à localização da instalação.

## Interface e manutenção

Layout **Lista ao lado**: notas, parâmetros e ação compõem uma única coluna à
esquerda, abaixo de Baixar documentos. Resultados por nota ficam à direita,
alinhados ao início do campo de notas. Tipo usa NF-e/CT-e
e Empresa usa Filial/Matriz, com NF-e e Filial selecionadas inicialmente.
Competência dos documentos e competência da pasta permanecem alinhadas e
visíveis; a pasta fica bloqueada e acompanha os documentos enquanto a opção
Pasta na mesma competência estiver marcada. O resumo do destino mantém tipo,
empresa e mês fáceis de conferir. Arquivos anteriores continuam preservados pela E5.
Andamento e contagens são discretos na lista, sem mostrador grande. Na janela
compacta, os resultados passam para baixo dos parâmetros. Há somente a rolagem
da página. Listas extensas não afastam a ação dos campos. Erros e conferências
usam texto além de cor.
O neon orientativo do campo de notas só acende vazio e sem foco; com conteúdo,
mantém a borda normal. O botão de pasta usa **Alterar**, conforme o
[padrão compartilhado](../estrutura-nunes/identidade-visual/interfaces/README.md).
Em 25/10/2026, o ensaio `tests.verificar_janela_desktop` passou com 80 resultados
sintéticos, ação visível, ausência de rolagem interna e adaptação compacta.
O CSS do pacote foi atualizado e conferido por SHA-256; não houve operação fiscal.
Envio duplicado é bloqueado enquanto o pedido está pendente; perder a resposta
mantém o início bloqueado até uma leitura válida, sem reenvio automático.
Falha na leitura agenda nova consulta mesmo quando o último estado observado
era ocioso: o lote iniciado ainda precisa de confirmação. Após recuperar um
estado ocioso válido, cessam as consultas periódicas. A faixa informa a reconexão.
Atualizações conservam a decisão em edição quando a pergunta não mudou.
No desktop, **Salvar resultado** usa Salvar como nativo, com gravação atômica do
snapshot concluído. A rota exige token/Origin e não aceita caminho nem conteúdo
fornecido pela página. Cancelar preserva os resultados na janela. No modo web,
o mecanismo Blob/download permanece disponível.

Reutilizados: componente de tema distribuído sem alteração e suporte Windows
de `nunes-hub/desktop_windows.py`, com parâmetros opcionais para identidade,
nome, entrada e descrição; a cópia local tem hash conferido no manifesto
`nunes-hub/manutencao.json`. Defaults do Hub foram preservados. Esse pequeno
reaproveitamento evita duplicar correções de foco, identidade e geometria.
O ciclo cooperativo e a tela são específicos da Cofre. Não foi criado um
framework. A interface usa superfícies neutras como o Hub e fontes monoespaçadas
disponíveis no Windows (Cascadia Code/Consolas), sem importar recursos do Hub em
execução. Ícones aprovados existentes foram preservados. A referência das APIs
é a [documentação do pywebview](https://pywebview.flowrl.com/api/).

### Pasta de documentos

Em **Configurações → Alterar**, escolha a própria pasta DOCUMENTOS DE
ENTRADA no diálogo nativo do Windows. O caminho completo fica recolhido nesse
menu. Cancelar mantém a escolha anterior; escolher uma nova pasta não move
arquivos ou catálogos já existentes. A alteração é permitida somente ociosa;
enquanto o diálogo está aberto, o backend também recusa início de lote.

A escolha é gravada atomicamente em `desktop-configuracao.json`, na pasta de
preferências já definida acima. Sobrevive à reabertura do processo e tem
precedência sobre `CAMINHO_DOCUMENTO_ENTRADA` para o executor da interface.
Sem preferência salva, essa variável mantém o comportamento anterior. Uma
preferência inválida exige nova escolha; não redireciona silenciosamente o lote.
`main.py` conserva seu contrato de variáveis de ambiente, sem usar essa preferência.
`NUNES_COFRE_DADOS` isola também essa configuração nos ensaios.

A rota de escolha exige token e Origin, não recebe caminhos da página e usa
somente a resposta do diálogo nativo. A pasta deve existir. A gravação E5,
reconciliação, sinalização e fronteiras de parada não foram alteradas.

## Conferência sintética e manual

```powershell
$env:NUNES_COFRE_DADOS = "$env:TEMP\cofre-ensaio\dados"
$env:NUNES_HUB_DADOS = "$env:TEMP\cofre-ensaio\presenca"
$env:NUNES_METRICAS_DADOS = "$env:TEMP\cofre-ensaio\metricas"
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_cofre_js.cjs
& .\.venv\Scripts\python.exe -m tests.verificar_janela_desktop
& .\.venv\Scripts\python.exe -m tests.verificar_pacote_desktop
# Usar --cofre e --hub para conferir pacotes específicos; --hub-desktop abre ambos.
# Janela com executor sintético e rede externa bloqueada:
& .\.venv\Scripts\python.exe -m tests.ensaio_desktop "$env:TEMP\cofre-visual"
```

No ensaio visual, informar números e iniciar produz decisões sintéticas de
emitente e nome, sem acesso ao portal nem gravação fiscal. Sua instrumentação
fica exclusivamente em `tests/` e não é distribuída no pacote.

Conferir manualmente: abrir direto/pelo Hub; editar campos e uma decisão;
minimizar/reabrir; alternar tema; exportar JSON; mover/redimensionar e reabrir;
fechar o Hub mantendo a Cofre; cancelar X durante processamento, depois confirmar
e aguardar saída. Conferir tabela extensa, erros e decisões em claro/escuro e
tamanho compacto. Não testar operação fiscal real com a sonda.
O relatório da entrega distingue testes automatizados, observação visual e
homologação humana ainda pendente.
