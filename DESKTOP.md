# Cofre NF-e desktop

Piloto de atualização sob demanda: [instalação, pacote assinado, atalho estável,
recuperação e limites](../nunes-hub/ATUALIZACAO-COFRE.md). O laboratório usa dados
isolados e bloqueia operações fiscais; a instalação habitual continua separada.

Entrada `cofre.py`: pywebview 6.2.1 + WebView2/WinForms, backend e janela no
mesmo processo; HTTP em thread própria e executor fiscal na thread existente.
Python local conferido: 3.13.13 x64. `main.py` conserva o modo console.
Windows com .NET Framework 4.8 ou superior e WebView2 Evergreen são requisitos do destino.
Depois de usar **Extrair Tudo** no ZIP, execute **Preparar Cofre NFe.exe** no usuário do operador:
o preparador detecta os runtimes existentes e baixa/instala somente os ausentes,
com internet e verificação da assinatura digital da Microsoft. O .NET solicita
elevação pelo Windows; o WebView2 usa a instalação do usuário atual. Se o .NET
exigir reinicialização, o preparador retorna 3010, pede reinício manual e deve ser
executado novamente depois. Não reinicia o computador nem altera políticas de
execução. É um executável CLR 4, disponível no Windows 10/11, sem depender do
.NET 4.8 para iniciar nem executar scripts PowerShell. Bloqueios corporativos de
executáveis precisam ser tratados pela TI. A preparação não
configura credenciais, pasta fiscal nem vínculo da central, e não abre a automação.
`Preparar Cofre NFe.exe --verificar` somente consulta os runtimes, sem baixar ou
instalar. Não há fallback para Internet Explorer.

Referências dos instaladores e detecção: [WebView2](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)
e [.NET Framework](https://learn.microsoft.com/dotnet/framework/deployment/deployment-guide-for-developers).

Falhas na abertura do painel exibem a etapa e o caminho de `cofre-diagnostico.txt`.
O módulo `diagnostico_nunes.py` tem fonte no Hub e cópias independentes declaradas
no manifesto; a adaptação Cofre fica em `src/diagnostico_abertura.py`. Veja o
[padrão Nunes de diagnóstico](../estrutura-nunes/area-nunes/diagnosticos.md).
No pacote, o arquivo fica ao lado do exe quando há permissão; os fallbacks são
a pasta de preferências `logs/` e TEMP. O relatório registra tipos e locais da
cadeia de exceções, códigos numéricos e presença/marca de download de recursos.
Não inclui mensagens brutas, credenciais, documentos ou valores livres do ambiente.

Se o diagnóstico indicar falha em `clr_loader/netfx.py` ao carregar
`Python.Runtime.dll`, com `marca_download: true`, confira a marca de origem da
distribuição. O Windows pode propagar a marca do ZIP para as bibliotecas extraídas,
e o .NET recusa carregá-las. Confirmado em cópia sintética: adicionar ZoneId=3
reproduziu `RuntimeError`; desbloquear somente a biblioteca de teste fez o
autoteste do mesmo pacote passar, sem reinstalar runtimes.

Para o ZIP conhecido do Cofre: **Propriedades → Desbloquear → Aplicar**, antes de
**Extrair Tudo** em uma pasta nova. Isso se limita ao arquivo escolhido, sem mudar
ExecutionPolicy, políticas de anexos ou a configuração global do .NET. Se a opção
for bloqueada pela empresa, encaminhe à TI. Veja a
[orientação da Microsoft para assemblies de origem remota](https://learn.microsoft.com/dotnet/framework/configure-apps/file-schema/runtime/loadfromremotesources-element).

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
o padrão; escolha manual e posição sobrevivem à troca de porta e reinício.
A janela tem tamanho fixo de 1009 × 618 unidades lógicas. A largura foi ampliada
para acomodar o espaço de 12 px antes da barra de rolagem, preservando a largura
anterior do conteúdo dos resultados e do formulário; a altura segue a referência.
Não permite redimensionar ou maximizar. Tamanhos e maximizações salvos por versões
anteriores são ignorados. Monitor removido ajusta a posição à área útil.
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

Layout **Lista ao lado**: parâmetros, notas e ação compõem uma única coluna à
esquerda. Resultados por nota ficam à direita,
alinhados ao início dos parâmetros. Tipo usa NF-e/CT-e
e Empresa usa Filial/Matriz, com NF-e e Filial selecionadas inicialmente.
Competência dos documentos e competência da pasta permanecem alinhadas e
visíveis; a pasta fica bloqueada e acompanha os documentos enquanto a opção
Pasta na mesma competência estiver marcada. O checkbox e seu texto formam a área
clicável, sem estender a seleção pelo restante da linha. Em Notas, apenas o campo
de digitação recebe foco ao clicar; o título conserva o nome acessível do campo,
sem ativá-lo. Notas ficam abaixo dos parâmetros, com a dica e o botão **Baixar**
logo abaixo do campo; o botão fica à direita,
com altura compacta de 28 px (30% menor que a altura anterior de 40 px).
Arquivos anteriores continuam preservados pela E5.
Andamento é discreto na lista. O resumo mostra três indicadores compactos de
concluídas, pendentes e erros (incluindo itens para conferir), acima dos dados
do lote. A lista usa uma linha acima de cada nota, incluindo a primeira,
sem linha abaixo da última. Resultados
têm rolagem vertical própria, incluindo andamento e decisões; o título
permanece visível. Cada nota mostra a situação em uma etiqueta com fundo suave acima do
número e do detalhe, com separadores entre os itens. Listas extensas mantêm
o formulário e o rodapé visíveis, sem aumentar a página nem a janela.
Erros e conferências usam texto além de cor, com etiquetas verdes para conclusão,
amarelas para atenção, rosadas para erro e neutras para espera/processamento.
Rótulos e mensagens usam Segoe UI; o campo de notas e seus números na lista
mantêm Cascadia Code/Consolas para facilitar a leitura dos identificadores.
No modo web com largura inferior
a 760 px, os resultados passam para baixo e a página volta a ter rolagem.
Apelidos são exibidos em maiúsculas durante a digitação; a normalização na
confirmação permanece no backend. Consultas sem notas elegíveis exibem somente
**Nenhuma nota encontrada**; falhas de gravação e sinalização conservam seus avisos.
O neon orientativo do campo de notas só acende vazio e sem foco; com conteúdo,
mantém a borda normal. O botão de pasta usa **Alterar**, conforme o
[padrão compartilhado](../estrutura-nunes/identidade-visual/interfaces/README.md).
Envio duplicado é bloqueado enquanto o pedido está pendente; perder a resposta
mantém o início bloqueado até uma leitura válida, sem reenvio automático.
Falha na leitura agenda nova consulta mesmo quando o último estado observado
era ocioso: o lote iniciado ainda precisa de confirmação. Após recuperar um
estado ocioso válido, cessam as consultas periódicas. A faixa informa a reconexão.
Atualizações conservam a decisão em edição quando a pergunta não mudou.
O painel mostra os resultados da execução atual, sem opção de exportar a lista.

Reutilizados: componente de tema distribuído sem alteração e suporte Windows
de `nunes-hub/desktop_windows.py`, com parâmetros opcionais para identidade,
nome, entrada e descrição; a cópia local tem hash conferido no manifesto
`nunes-hub/manutencao.json`. Defaults do Hub foram preservados. Esse pequeno
reaproveitamento evita duplicar correções de foco, identidade e geometria.
O ciclo cooperativo e a tela são específicos da Cofre. Não foi criado um
framework. A interface usa superfícies neutras como o Hub e fontes disponíveis
no Windows (Segoe UI e Cascadia Code/Consolas), sem importar recursos do Hub em
execução. Ícones aprovados existentes foram preservados. A referência das APIs
é a [documentação do pywebview](https://pywebview.flowrl.com/api/).

### Pasta de documentos

O cabeçalho usa apenas o ícone de controles do Hub para abrir Configurações.
Ao lado, um botão independente alterna o tema: lua no modo claro e lua com
círculo e raios no modo escuro. Ambos mantêm nomes acessíveis e dicas ao passar
o mouse. O menu de configurações fica dedicado à pasta de documentos.

Em **Configurações → Alterar**, escolha a própria pasta DOCUMENTOS DE
ENTRADA no diálogo nativo do Windows. O caminho completo fica recolhido nesse
menu. Cancelar mantém a escolha anterior; escolher uma nova pasta não move
arquivos ou catálogos já existentes. A alteração é permitida somente ociosa;
enquanto o diálogo está aberto, o backend também recusa início de lote.

À direita de **Alterar**, **Abrir** abre a pasta configurada no Explorador de
Arquivos, inclusive durante um lote. Usa somente a configuração local, sem
receber caminhos da página. Pasta indisponível exibe um erro no próprio menu.
A ação exige token e Origin no desktop e fica bloqueada durante escolha de
pasta, reconexão ou encerramento.
As mensagens abaixo de Alterar e Abrir são limpas ao fechar o menu, inclusive
confirmações, cancelamentos e erros; respostas recebidas com ele fechado não
deixam avisos para a próxima abertura.

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
minimizar/reabrir; alternar tema; mover e reabrir no tamanho fixo;
fechar o Hub mantendo a Cofre; cancelar X durante processamento, depois confirmar
e aguardar saída. Conferir tabela extensa, erros e decisões em claro/escuro e
tamanho fixo. Não testar operação fiscal real com a sonda.
O relatório da entrega distingue testes automatizados, observação visual e
homologação humana ainda pendente.
