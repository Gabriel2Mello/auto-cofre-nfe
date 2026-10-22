# 🤖 RPA - Automação de Notas Cofre NF-e & CT-e (Painel Web ➔ Empresa Nunes)

Este é um robô de automação de processos (RPA) desenvolvido em Python para otimizar o fluxo de gerenciamento interno de documentos fiscais da Empresa Nunes. O sistema realiza a varredura e download automatizado de Notas Fiscais Eletrônicas (NF-e) e Conhecimentos de Transporte Eletrônicos (CT-e) diretamente do portal Cofre NFe, processa metadados e organiza os arquivos em uma estrutura de diretórios locais.

## Interface web local

Abra **Abrir Cofre NFe.cmd** para usar o fluxo completo no navegador, com
NF-e/CT-e, Matriz/Filial, competência dos documentos e competência da pasta.
NF-e, Matriz e o mês atual já vêm preenchidos. Escolhas de emitente, nomes de
arquivos e resultados aparecem no próprio painel, com temas claro e escuro.

Ao fechar a última aba, o programa solicita a parada e encerra após a operação
em curso. A confirmação de saída usa o aviso nativo do navegador; a tela ociosa
não faz consultas periódicas de andamento. O modo console permanece em `main.py`.
Veja [instalação, atalhos, funcionamento e validação](docs/interface-web.md).

## Estatísticas com central local

O cliente opcional `sincronizar_estatisticas.py` acompanha `cofre.py` (web) e
`main.py` (console), lendo apenas as métricas já persistidas. Sem vínculo em
`.local/central.json` e sem `NUNES_CENTRAL_CONFIG`, permanece desabilitado.
O Cofre funciona individualmente, sem Hub ou central em execução.

Um documento conta uma vez após gravar o conjunto XML/PDF; repetir a mesma
baixa não soma novamente. Falhar a sinalização posterior no portal não desfaz
a contagem. Se a central estiver indisponível, a automação continua normalmente;
o envio é retomado a cada cinco segundos enquanto estiver aberta ou na próxima
abertura. O fechamento tenta um último envio após aguardar o processamento.
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
5. **Download, Validação e Persistência:** Baixa e valida o XML e o PDF (DANFE/DACTE) antes de gravar. Respostas inválidas geram erro por documento, sem substituir os arquivos anteriores, contar entrega ou sinalizar o portal. A E5 prepara e confere o conjunto completo, preserva arquivos anteriores e registra pendências de publicação para recuperação. Somente depois de confirmar todos os arquivos registra a entrega e tenta a sinalização (seta-flag). A publicação entre pastas distintas continua sem transação única; consulte o guia de recuperação abaixo.

---

## Validação dos downloads — E3 (20/10/2026)

A validação é compartilhada pelo console e pelo painel, em `src/validacao_documentos.py`, antes do retorno de `baixar_arquivos`:

- **HTTP:** exige resposta 200 completa e não segue redirecionamentos de download, inclusive para login. Extensão e Content-Type não comprovam validade.
- **XML:** leitura sem DTD, entidades externas ou recuperação de conteúdo quebrado. Exige um documento NF-e modelo 55 ou CT-e modelo 57, namespace fiscal, número e competência solicitados, identificação coerente com emitente/modelo/série/número/data/UF e, no XML processado, chave correspondente no protocolo.
- **Empresa:** o CNPJ configurado deve participar do documento: emitente/destinatário na NF-e; emitente, remetente, expedidor, recebedor, destinatário ou tomador identificado no CT-e. Aparecer somente em `autXML` não estabelece esse vínculo.
- **PDF:** leitura estrutural estrita com [pypdf](https://pypdf.readthedocs.io/en/latest/modules/PdfReader.html), páginas legíveis, identificação DANFE/DACTE e a mesma chave fiscal de 44 dígitos do XML. Aceita chave contínua ou em grupos de quatro. Chaves de NF-e referenciadas no DACTE são permitidas; várias chaves do modelo solicitado tornam a identidade ambígua e geram erro.

PDF protegido, em imagem sem chave extraível ou com identidade ambígua exige conferência manual no portal. Não há OCR nem aceitação automática quando não é possível confirmar a identidade. A E3 confere formato e identidade, sem validar assinatura digital, XSD integral, autenticidade do PDF ou autorização/cancelamento atual na SEFAZ. Não há operação fiscal real nos testes.

O identificador de 22 caracteres usado nas URLs do Cofre é distinto da chave fiscal do XML. Ele permanece nos downloads e na identidade das métricas para preservar a compatibilidade do histórico. A chave fiscal do XML é usada para a conferência do par, sem ser publicada em mensagens de erro.

`pypdf==6.21.1` foi aprovado pelo responsável, fixado em `requirements.txt` e instalado no `.venv` desta cópia. Em outras instalações, atualize com `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` e reabra o programa. Executáveis precisam ser reconstruídos para incluir a validação e a dependência.

Validação: **21 testes Python e um JavaScript aprovados**, com 70 cenários nos três novos testes (54 rejeições e 16 sucessos), usando documentos e HTTP sintéticos, arquivos temporários e nenhuma conexão ao portal. `pip check` passou. Tipagem dos seis arquivos Python da entrega: zero erros/avisos. A análise global ainda aponta 11 pendências anteriores em `src/interface_web.py`, `tests/test_interface_web.py` e `tests/test_metricas_integracao.py`, também reproduzidas na cópia anterior à E3. O parser XML utiliza as [opções de segurança do lxml](https://lxml.de/parsing.html).

## Gravação recuperável — E5 (20/10/2026)

Nomes livres conservam o padrão atual. Conjuntos válidos da mesma chave são reaproveitados; colisões preservam os arquivos anteriores e acrescentam a chave fiscal aos nomes da nova baixa. XML, PDF e cópia CT-e são preparados e conferidos antes da publicação. Falhas deixam uma pendência identificada, sem métrica ou sinalização.

O [guia de gravação e recuperação](docs/gravacao-recuperavel.md) explica os estados e o comando `recuperar_documentos.py` para listar, concluir ou abandonar preparações sem arquivos publicados. A recuperação atua somente no disco; uma nova baixa normal reaproveita o conjunto recuperado e executa métrica/sinalização.

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

Cada documento fiscal é contado após confirmar o conjunto completo de arquivos (XML, PDF e cópia CT-e quando aplicável), antes da sinalização no portal. Pendências de publicação e ações do comando de recuperação não geram métricas. Uma falha apenas na sinalização não desfaz a baixa. Empresa, tipo e identificador do documento fornecido pelo portal identificam a entrega, com esse identificador armazenado como hash. A chave fiscal de 44 dígitos é conferida no XML/PDF, sem substituir a identidade histórica da métrica. Baixar novamente o mesmo documento não aumenta o total. Pendências não entram nas métricas.

O registro funciona na interface web e no console, mesmo com o hub fechado. O módulo `metricas_nunes.py` é distribuído a partir do Hub Nunes; seu README documenta armazenamento, recuperação, filtros e exportação. Feche e reabra esta ferramenta após atualizar. O histórico começa com esta versão e não importa operações anteriores. Falhas na estatística não repetem nem interrompem operações concluídas; uma fila local recupera gravações transitórias e falhas de persistência são registradas no log. Antes de rodar a suíte completa, use um terminal exclusivo de testes e configure NUNES_METRICAS_DADOS para uma pasta temporária; o README do Hub Nunes contém o comando de isolamento.
