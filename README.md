# 🤖 RPA - Automação de Notas Cofre NF-e & CT-e (Painel Web ➔ Empresa Nunes)

Este é um robô de automação de processos (RPA) desenvolvido em Python para otimizar o fluxo de gerenciamento interno de documentos fiscais da Empresa Nunes. O sistema realiza a varredura e download automatizado de Notas Fiscais Eletrônicas (NF-e) e Conhecimentos de Transporte Eletrônicos (CT-e) diretamente do portal Cofre NFe, processa metadados e organiza os arquivos em uma estrutura de diretórios locais.

## Interface desktop local

Abra **Abrir Cofre NFe.cmd** para usar o fluxo completo em janela própria, com
NF-e/CT-e, Matriz/Filial, competência dos documentos e competência da pasta.
NF-e, Filial e o mês atual já vêm preenchidos. Escolhas de emitente, nomes de
arquivos e resultados aparecem no próprio painel, com temas claro e escuro.
Notas ficam no topo e os resultados ao lado dos parâmetros. Em
**Configurações → Escolher pasta…**, selecione DOCUMENTOS DE ENTRADA;
a escolha é preservada nas próximas aberturas, sem alterar o ambiente do console.

Uma segunda abertura restaura a mesma janela, preservando campos, resultados
e decisões. X durante processamento confirma e aguarda a operação em curso;
queda de presença não encerra o desktop. O Hub também abre/restaura a janela.
O modo console permanece em `main.py`. Veja [desktop, instalação, dados,
empacotamento e validação](DESKTOP.md) e o [fluxo operacional](docs/interface-web.md).

## Testar com dados sintéticos

Para experimentar situações raras sem exemplos reais, abra **Testar Cofre NFe.cmd**.
A janela separada oferece 17 cenários sintéticos, incluindo perguntas de emitente,
falhas, HTTP 503 em três etapas, parada, reconexão e lote extenso. Ela não acessa
o portal nem grava documentos fiscais ou estatísticas reais.
Veja [como testar e os limites da simulação](docs/simulacao.md).

## Diagnóstico do acesso ao portal

Desktop e console registram login, troca e confirmação da empresa em
`%LOCALAPPDATA%\Nunes\Cofre\logs\cofre-portal.jsonl`. Com `NUNES_COFRE_DADOS`,
o arquivo fica em `logs/cofre-portal.jsonl` dentro dessa pasta de isolamento.
Feche e reabra a aplicação para ativar; executáveis precisam ser reconstruídos.

Cada tentativa de acesso tem um identificador `execucao` próprio. O JSON por
linha contém horário UTC com fuso explícito, Matriz/Filial, etapas e durações,
status HTTP, categorias das páginas e redirecionamentos, tipo/tamanho da
resposta e indicadores de formulário de login ou desafio de acesso. Esses
indicadores são indícios, não confirmação de sessão expirada ou bloqueio.
O campo `codigo` identifica por hash os arquivos-fonte de acesso na primeira
tentativa do processo; sem fontes disponíveis, informa `indisponivel`.
`formato` versiona o esquema do log.

Se a seleção terminar em outra página do portal, o cliente
confere a empresa com uma leitura do painel `/nfe/empresa`, sem seguir novos
redirecionamentos. Essa leitura aparece como etapa `confirmacao_empresa`.
Ela só libera o lote com o CNPJ solicitado confirmado; não repete a seleção
nem altera a gravação ou o catálogo de emitentes.

`confirmacao_empresa.motivo` distingue `cabecalho_ausente`,
`cabecalho_ambiguo`, `cnpj_ausente`, `cnpj_ambiguo`, `cnpj_divergente`,
`configuracao_invalida`, `vinculo_ausente`, `origem_invalida`,
`resposta_invalida` e `confirmado`. As contagens de cabeçalhos, spans diretos
e CNPJs ajudam a explicar a recusa sem gravar os valores encontrados.
Campos nulos indicam que a página/configuração ainda não foi inspecionada.

O registro cobre somente a preparação de acesso: `acesso_encerrado` com
`confirmado` não significa que o lote foi baixado. Não gera novas requisições,
repetições automáticas, métricas ou operações no portal, nem muda a checagem
da empresa. Não grava HTML, documentos, notas, CNPJ, nomes, senha, cookies,
tokens, URLs completas ou mensagens brutas de exceção. Falhas de comunicação
são classificadas como `timeout`, `http` ou `comunicacao`.

Rotação em aproximadamente 1 MiB por arquivo, com três cópias anteriores
(`.jsonl.1` a `.jsonl.3`). O diagnóstico é local, não é enviado à central e
não registra cada documento. Falhas de criação, escrita ou rotação não
interrompem a baixa. Para investigar uma ocorrência, confira as linhas do
horário correspondente e agrupe pelo mesmo `execucao`.

No desktop, a solicitação de parada também gera `parada_solicitada`, com
o mesmo `execucao` do acesso. `origem` distingue `parar` (botão de processamento),
`decisao` (botão da pergunta) e `encerramento` (encerramento da aplicação).
`pergunta` indica somente `nome`, `emitente` ou nulo; nenhum conteúdo da decisão
é registrado. Uma parada já solicitada não gera registros repetidos.
Esse evento identifica a origem do comando, não comprova que o usuário clicou
fisicamente no botão. Vírgula seguida de quebra de linha é uma entrada válida
e não solicita parada.

## Diagnóstico de abertura

Quando o pedido de início falha, o painel mostra `403 · Início não confirmado.`
(com o código HTTP recebido) ou `Início não confirmado.` (sem resposta).
O aviso desaparece na próxima interação ou quando uma consulta de estado
confirma a reconexão após falhas de leitura; o acompanhamento continua consultando
o estado sem reenviar o lote. Após uma consulta bem-sucedida, o painel solicita
o diagnóstico local: tipo conhecido da falha no navegador e código HTTP,
registrados na etapa `inicio_<tipo>_http_<codigo>` ou `inicio_<tipo>_sem_resposta`.
Mensagens brutas, notas, tokens, corpos de resposta e pilhas do navegador não
são enviados ao diagnóstico.

Para HTTP 503, o aviso temporário é `Confira o portal e a conexão.`, tanto
na falha do início local quanto em erros HTTP do portal durante o lote.
Cada ocorrência chega em `aviso_portal` com identificador próprio, tipo de
orientação e status 503 quando disponível; a interface não restaura um aviso
já dispensado em novas leituras.
Ele desaparece por interação ou reconexão, sem apagar os resultados do lote.
Quando HTTP 503 encerra o lote, o status é `Erro 503: Falha na comunicação com o Cofre.`.
Os demais avisos seguem o mesmo comportamento:

| Falha | Orientação temporária | Detalhe preservado em Resultados |
| --- | --- | --- |
| Prazo de resposta | Confira o portal e a conexão. | O Cofre não respondeu dentro do prazo. |
| Comunicação sem HTTP | Confira o portal e a conexão. | Falha na comunicação com o Cofre. |
| Destino indisponível | Confira a pasta de destino. | Não foi possível acessar a pasta DOCUMENTOS DE ENTRADA. |
| Gravação | Confira o acesso à pasta. | Não foi possível gravar os arquivos do documento. |
| Catálogo de emitentes | Arquivo emitentes indisponível. | O arquivo de emitentes está indisponível. |
| Sinalização após salvar | Confira a sinalização no Cofre. | XML e PDF salvos; não foi possível confirmar a sinalização no Cofre. |

As falhas por documento ficam na respectiva nota; falhas antes de processar
ficam no status da execução. A simulação inclui cenários de prazo excedido,
falha de conexão sem HTTP, pasta de destino e catálogo indisponíveis, além
dos cenários de gravação e sinalização. Nenhum deles executa operações fiscais.

O relatório usa o padrão Nunes, com contexto do runtime e gravação atômica de
`cofre-diagnostico.txt`: ao lado do executável, com fallback para `logs/` na
pasta de preferências e depois TEMP. Somente o último relatório é mantido.
O caminho completo fica na descrição ao passar o mouse sobre o aviso.
Sem conexão/autorização, o diagnóstico permanece pendente na página; falhas de
gravação permitem nova tentativa na próxima consulta bem-sucedida. Fechar ou
recarregar a página antes da gravação perde esse registro pendente. A gravação
não bloqueia o acompanhamento nem muda o encerramento da aplicação.

A abertura registra importações internas, identidade no Windows, estado,
servidor, sincronizador e publicação em `logs/cofre-nfe-abertura.log`, na
pasta de presença da sessão Nunes. Reabra a aplicação para carregar a mudança.
Resultados, localização e limites: [Tempos por etapa](../nunes-hub/TEMPOS_ABERTURA.md).

O painel carrega as bibliotecas de download e validação somente ao iniciar
a primeira operação. Isso reduz o tempo para mostrar a interface e transfere
parte da espera para esse primeiro lote. As dependências de `requirements.txt`
continuam necessárias para operar; sua ausência interrompe antes do download.
O executor web fica em `src/execucao_web.py`, chamado pelo controlador quando
um lote é iniciado. Feche e reabra para carregar a mudança; executáveis antigos
precisam ser reconstruídos.

## Estatísticas com central local

O cliente opcional `sincronizar_estatisticas.py` acompanha `cofre.py` (web) e
`main.py` (console), lendo apenas as métricas já persistidas. Sem vínculo em
`.local/central.json` e sem `NUNES_CENTRAL_CONFIG`, permanece desabilitado.
O Cofre funciona individualmente, sem Hub ou central em execução.

Um documento conta uma vez após gravar o conjunto XML/PDF; repetir a mesma
baixa não soma novamente. Falhar a sinalização posterior no portal não desfaz
a contagem. Se a central estiver indisponível, a automação continua normalmente;
o envio é retomado enquanto estiver aberta ou na próxima abertura. A espera
entre ciclos é de cinco segundos, subindo gradualmente até 30 segundos somente
sem atividade nem pendências; atividade ou falha retomam cinco segundos.
O fechamento tenta um último envio após aguardar o processamento.
Não repita downloads para recuperar estatísticas.

O vínculo é criado pela central com `central.py vincular --automacao '..\auto-cofre-nfe'`.
Atualize/reinicie primeiro a central e reabra o Cofre para carregar o cliente.
Consulte [preparo, consulta e recuperação](../nunes-estatisticas/README.md).
O envio inclui histórico anterior ao vínculo, sem ler os documentos fiscais.
Os eventos locais são preservados; confirmações ficam em
`sincronizacao-cofre-nfe.sqlite3` junto à pasta de métricas existente.
O Hub mostra totais de NF-e/CT-e e pendências em seção própria de Resultados.

Para consultar ou enviar manualmente, nesta pasta:

```powershell
.\.venv\Scripts\python.exe sincronizar_estatisticas.py --aplicacao cofre-nfe --resumo
.\.venv\Scripts\python.exe sincronizar_estatisticas.py --aplicacao cofre-nfe
```

O cliente tem fonte no Busca e Move; `contrato_estatisticas.py` tem fonte na
central. As cópias distribuídas no Cofre, Busca e Move e Hub devem ser iguais.
Não há imports de repositórios irmãos na execução, novas dependências, serviço
Windows ou implantação no TS01 nesta etapa.

---

## ⚙️ Tecnologias e Bibliotecas Utilizadas

* **Orquestração e Core:** Python 3.13
* **Web Scraping & Bypass:** `cloudscraper` e `BeautifulSoup4` (LXML parsing).
* **Processamento de Dados e Datas:** `python-dateutil` (parsing de strings de data) e `validate-docbr` (máscara e validação de documentos federais).
* **Tratamento de Texto e Strings:** `unidecode` (sanitização de caracteres especiais para gravação em disco).
* **Interface de Console:** Entrada de dados iterativa e CLI tratada nativamente.

---

## 🚀 Fluxo Operacional do Robô
```
[Usuário insere Notas/Empresa/Data] ➔ [Login & Extração de Hrefs de Login]
                                                     │
                                        [Troca de Contexto de Empresa]
                                                     │
[Marcar Flag no Painel] ◀─ [Salvar XML & PDF em Disco] ◀─ [Download de Arquivos]
```
1. **Entrada de Dados:** O robô solicita o tipo de documento, a lista de notas (com suporte a múltiplas entradas separadas por vírgula), a empresa alvo (Matriz ou Filial) e o modo de competência (data atual ou inserção manual de mês/ano).
2. **Fase Web & Autenticação:** Efetua o bypass de segurança e realiza o login no Portal Cofre NFe. Analisa a página inicial, extrai dinamicamente os links de acesso baseados nos CNPJs e realiza a troca de contexto da sessão.
3. **Varredure e Filtragem:** Sincroniza a tabela de arquivos e dispara requisições POST simulando o carregamento dinâmico de dados (DataTables). Aplica filtros para ignorar Cartas de Correção ou Notas Canceladas, validando se a data de emissão condiz com a competência informada.
4. **Tratamento Dinâmico de Emitentes:** Consulta uma base de dados JSON local (`emitentes_conhecidos.json`). Caso encontre um fornecedor novo, o robô pergunta o nome tratado em tempo de execução, garantindo a padronização das pastas.
5. **Download e Organização:** Baixa XML e PDF e confere sua integridade básica antes de organizar nas pastas escolhidas. A seleção de nota, empresa e competência ocorre na consulta ao portal; incongruências fiscais ficam para o operador. Respostas inválidas geram erro por documento, sem substituir os arquivos anteriores, contar entrega ou sinalizar o portal. A E5 prepara e confere o conjunto completo, preserva arquivos anteriores e registra pendências de publicação para recuperação. Somente depois de confirmar todos os arquivos registra a entrega e tenta a sinalização (seta-flag). A publicação entre pastas distintas continua sem transação única; consulte o guia de recuperação abaixo.

## Correções da revisão técnica — 26/10/2026

A troca de empresa agora exige o CNPJ correto no cabeçalho ativo do portal.
A consulta percorre as páginas antes de selecionar o documento e recusa respostas
incompletas ou inconsistentes. Depois de solicitar a flag uma única vez, o cliente
relê seu estado; HTTP 200 sozinho não produz confirmação. Arquivos e métricas
permanecem preservados quando essa confirmação falha.

A primeira gravação do manifesto usa uma área inicial separada, para que falhas
antes de publicar o registro não bloqueiem novas baixas. No console, Ctrl+C/EOF
na pergunta do emitente interrompe o lote; nomes já aprovados são salvos no
encerramento, sem continuar o documento cancelado.

Veja o [contrato observado e as amostras sanitizadas](docs/contrato-portal.md)
e o [procedimento de gravação e recuperação](docs/gravacao-recuperavel.md).
Reabra o programa Python para carregar as mudanças; executáveis precisam ser
reconstruídos. A operação completa no portal real não foi homologada nesta etapa.

---

## Validação dos downloads — E3 (20/10/2026)

A validação é compartilhada pelo console e pelo painel, em `src/validacao_documentos.py`, antes do retorno de `baixar_arquivos`:

- **HTTP:** exige resposta 200 completa e não segue redirecionamentos de download, inclusive para login. Extensão e Content-Type não comprovam validade.
- **XML:** leitura sem DTD, entidades externas ou recuperação de conteúdo quebrado. Exige um único documento do tipo solicitado (NF-e/CT-e), com identificação de 44 dígitos para distinguir arquivos, preservar destinos existentes e recuperar gravações. Não compara os dados fiscais internos, CPF/CNPJ, série, data ou protocolo com a chave; não exige correspondência desses dados com os parâmetros da consulta ao portal.
- **PDF:** leitura estrutural com [pypdf](https://pypdf.readthedocs.io/en/latest/modules/PdfReader.html), arquivo completo, sem proteção e com páginas. Não exige texto extraível, rótulo DANFE/DACTE nem correspondência de chaves com o XML. PDFs em imagem e com notas referenciadas são aceitos.
- **Conferência operacional:** nota, empresa, competência e emitente são selecionados no portal e usados na organização. A conferência fiscal dos arquivos baixados cabe ao operador. CPF, nota avulsa e CNPJ da SEFAZ não recebem validação fiscal especial.

Arquivos vazios, truncados, HTML de login, XML inseguro e PDF protegido ou sem páginas continuam gerando erro. A automação se concentra em baixar e organizar, sem validar assinatura digital, XSD integral, autenticidade do PDF ou autorização/cancelamento atual na SEFAZ. Não há operação fiscal real nos testes.

O identificador de 22 caracteres usado nas URLs do Cofre é distinto da chave fiscal do XML. Ele permanece nos downloads e na identidade das métricas para preservar a compatibilidade do histórico. A chave do XML identifica os arquivos na gravação e na recuperação, sem ser comparada ao conteúdo do PDF nem publicada em mensagens de erro.

`pypdf==6.21.1` foi aprovado pelo responsável, fixado em `requirements.txt` e instalado no `.venv` desta cópia. Em outras instalações, atualize com `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` e reabra o programa. Executáveis precisam ser reconstruídos para incluir a validação e a dependência.

Validação: **21 testes Python e um JavaScript aprovados**, com 70 cenários nos três novos testes (54 rejeições e 16 sucessos), usando documentos e HTTP sintéticos, arquivos temporários e nenhuma conexão ao portal. `pip check` passou. Tipagem dos seis arquivos Python da entrega: zero erros/avisos. A análise global ainda aponta 11 pendências anteriores em `src/interface_web.py`, `tests/test_interface_web.py` e `tests/test_metricas_integracao.py`, também reproduzidas na cópia anterior à E3. O parser XML utiliza as [opções de segurança do lxml](https://lxml.de/parsing.html).

## Gravação recuperável — E5 (20/10/2026)

Nomes livres conservam o padrão atual. Conjuntos válidos da mesma chave são reaproveitados; colisões preservam os arquivos anteriores e acrescentam a chave fiscal aos nomes da nova baixa. XML, PDF e cópia CT-e são preparados e conferidos antes da publicação. Falhas deixam uma pendência identificada, sem métrica ou sinalização.

O [guia de gravação e recuperação](docs/gravacao-recuperavel.md) explica os estados e o comando `recuperar_documentos.py` para listar, concluir ou abandonar preparações sem arquivos publicados. A recuperação atua somente no disco; uma nova baixa normal reaproveita o conjunto recuperado e executa métrica/sinalização.

Desde 21/10/2026, os registros ficam em `.cofre-gravacoes` na raiz deste projeto,
separados por destino fiscal, sem criar essa pasta no OneDrive/área compartilhada.
Pendências antigas continuam legíveis; sua recuperação grava o novo estado somente
no projeto e preserva o registro antigo. Os temporários `.cofre-*.tmp` continuam
nos diretórios dos documentos para publicação segura. Inclua registros locais e
documentos no backup e reabra o Cofre para carregar a mudança.

**49 testes Python e um JavaScript aprovados**, incluindo 17 novos testes da E5 e recuperação CT-e em outro processo. Código alterado e testes novos/download passaram na tipagem; permanecem 11 pendências globais anteriores. Sem novos pacotes e sem acesso a documentos, catálogo ou portal reais. Reabra a ferramenta Python para carregar a E5; executáveis precisam ser reconstruídos.

## 📋 Pré-requisitos de Infraestrutura

O ambiente de execução precisa das seguintes definições no Windows/Linux:

**Estrutura de Rede/Diretório:** O caminho mapeado para o armazenamento das notas deve estar acessível e possuir permissões de escrita para a criação dinâmica de diretórios por ano e mês.

---

## 🔧 Configuração do Ambiente (Variáveis de Ambiente)

O projeto adota o isolamento de credenciais e caminhos de arquivos através de variáveis de ambiente do sistema operacional:

| Campo | Tipo | Descrição | Exemplo |
| :--- | :--- | :--- | :--- |
| `SENHA_COFRE` | `String` | Senha de autenticação. | `MinhaSenhaCofre123` |
| `CAMINHO_DOCUMENTO_ENTRADA` | `Path (Diretório)` | Caminho na máquina/rede para as pastas. | `X:\Empresa\Faturamento\Notas` |
| `CNPJ_FILIAL` | `String` | CNPJ da filial correspondente. | `00000000000100` |
| `CNPJ_MATRIZ` | `String` | CNPJ da matriz da empresa. | `00000000000100` |

---

## 💾 Organização de Arquivos e Saídas (Estrutura em Disco)

Ao processar os documentos com sucesso, o robô gera automaticamente a seguinte árvore de pastas estruturada sob o caminho parametrizado em `CAMINHO_DOCUMENTO_ENTRADA`:
```
📁 [Caminho Base Configurado]
├── 📁 PDF NF-e (ou PDF CT-e)
│   └── 📁 [ANO_PASTA]
│       └── 📁 [MATRIZ / FILIAL]
│           └── 📁 [MÊS_PASTA (Ex: JANEIRO)]
│               └── 📄 [NOME_EMITENTE] [NUMERO_NOTA].pdf
└── 📁 XML - NF-e (ou XML - CT-e)
    └── 📁 [ANO_PASTA]
        └── 📁 [MATRIZ / FILIAL]
            └── 📁 [MÊS_PASTA (Ex: JANEIRO)]
                └── 📄 [NOME_EMITENTE] [NUMERO_NOTA].xml
```
## Catálogo de emitentes — E4 (20/10/2026)

`emitentes_conhecidos.json` vincula o nome do emitente no portal ao nome aprovado para os arquivos. Somente um arquivo ausente inicia uma base vazia. JSON quebrado, codificação diferente de UTF-8, raiz diferente de objeto ou mapeamentos com chaves/nomes não textuais ou vazios geram erro explícito, preservando o arquivo para correção ou restauração pelo responsável.

Ao salvar alterações, o programa valida e serializa o catálogo, grava em um temporário exclusivo no mesmo diretório, executa `flush`/`fsync`, fecha o arquivo e o promove com `Path.replace`. O catálogo anterior permanece até a substituição, sem remoção prévia. Sem alterações, fechar não grava novamente. Uma falha mantém as alterações em memória enquanto a instância existir.

Em caso de falha, a mensagem identifica o catálogo e, quando disponível, o temporário `.emitentes_conhecidos-*.tmp`. Esse arquivo é preservado e ignorado pelo Git; uma falha de escrita pode deixá-lo incompleto. Não há promoção ou restauração automática. Para recuperação, encerre a ferramenta, valide o JSON temporário e compare seus mapeamentos com o catálogo anterior antes de decidir o que restaurar. Temporários de outras tentativas não são sobrescritos. O catálogo real não foi lido nem modificado na implementação/testes da E4.

Passaram **32 testes Python e um JavaScript**, incluindo **11 novos testes** de catálogo: falhas de criação/escrita/sincronização/promoção, nova tentativa, temporário anterior, JSON inválido/tipos inadequados, UTF-8 e fechamento sem alterações. Os dois arquivos Python da E4 passaram na tipagem sem erros/avisos; as 11 pendências globais anteriores permanecem. Os testes utilizam arquivos temporários e rede externa bloqueada. Comportamento em compartilhamentos de rede e queda de energia não foi homologado; a substituição não faz mesclagem de edições concorrentes.

Reabra o programa Python para carregar a E4; executáveis precisam ser reconstruídos. A E5 seguinte foi entregue; o guia de gravação e recuperação registra a política de colisões e seus limites.

Criado por Gabriel Mello · [g2mello](https://github.com/Gabriel2Mello)


## Estatísticas no Hub Nunes

No console, o resumo separa notas sem falha e notas com falha. Qualquer falha
no lote retorna código 1, inclusive falha de sinalização após salvar os
arquivos; estes permanecem concluídos e sua métrica é preservada. Código 0
indica lote sem falhas, e interrupção/EOF tratado retorna 130. Confira a
mensagem da nota antes de decidir uma nova tentativa; o código de saída não
desfaz arquivos nem repete o processamento automaticamente.

Cada documento fiscal é contado após confirmar o conjunto completo de arquivos (XML, PDF e cópia CT-e quando aplicável), antes da sinalização no portal. Pendências de publicação e ações do comando de recuperação não geram métricas. Uma falha apenas na sinalização não desfaz a baixa. Empresa, tipo e identificador do documento fornecido pelo portal identificam a entrega, com esse identificador armazenado como hash. A chave fiscal de 44 dígitos é conferida no XML/PDF, sem substituir a identidade histórica da métrica. Baixar novamente o mesmo documento não aumenta o total. Pendências não entram nas métricas.

O registro funciona na interface web e no console, mesmo com o hub fechado. O módulo `metricas_nunes.py` é distribuído a partir do Hub Nunes; seu README documenta armazenamento, recuperação, filtros e exportação. Feche e reabra esta ferramenta após atualizar. O histórico começa com esta versão e não importa operações anteriores. Falhas na estatística não repetem nem interrompem operações concluídas; uma fila local recupera gravações transitórias e falhas de persistência são registradas no log. Antes de rodar a suíte completa, use um terminal exclusivo de testes e configure NUNES_METRICAS_DADOS para uma pasta temporária; o README do Hub Nunes contém o comando de isolamento.
