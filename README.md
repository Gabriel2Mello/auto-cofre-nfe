# 🤖 RPA - Automação de Notas Cofre NF-e & CT-e (Painel Web ➔ Empresa Nunes)

Este é um robô de automação de processos (RPA) desenvolvido em Python para otimizar o fluxo de gerenciamento interno de documentos fiscais da Empresa Nunes. O sistema realiza a varredura e download automatizado de Notas Fiscais Eletrônicas (NF-e) e Conhecimentos de Transporte Eletrônicos (CT-e) diretamente do portal Cofre NFe, processa metadados, valida competências e organiza os arquivos em uma estrutura de diretórios locais, aplicando flags de controle via requisições HTTP para marcar os documentos dentro do site como processados.

---

## ⚙️ Tecnologias e Bibliotecas Utilizadas

* **Orquestração e Core:** Python 3.12
* **Web Scraping & Bypass:** `cloudscraper` (com emulação dinâmica de Client Hints do Chrome no Windows) e `BeautifulSoup4` (LXML parsing).
* **Processamento de Dados e Datas:** `python-dateutil` (parsing de strings de data) e `validate-docbr` (máscara e validação de documentos federais).
* **Tratamento de Texto e Strings:** `unidecode` (sanitização de caracteres especiais para gravação em disco).
* **Interface de Console:** Entrada de dados iterativa e CLI tratada nativamente.

---

## 🚀 Fluxo Operacional do Robô
[Usuário insere Notas/Empresa/Data] ➔ [Login & Extração de Hrefs de Login]
                                                     │
                                        [Troca de Contexto de Empresa]
                                                     │
[Marcar Flag no Painel] ◀─ [Salvar XML & PDF em Disco] ◀─ [Download de Arquivos]

1. **Entrada de Dados:** O robô solicita o tipo de documento, a lista de notas (com suporte a múltiplas entradas separadas por vírgula), a empresa alvo (Matriz ou Filial) e o modo de competência (data atual ou inserção manual de mês/ano).
2. **Fase Web & Autenticação:** Efetua o bypass de segurança e realiza o login no Portal Cofre NFe. Analisa a página inicial, extrai dinamicamente os links de acesso baseados nos CNPJs e realiza a troca de contexto da sessão.
3. **Varredure e Filtragem:** Sincroniza a tabela de arquivos e dispara requisições POST simulando o carregamento dinâmico de dados (DataTables). Aplica filtros para ignorar Cartas de Correção ou Notas Canceladas, validando se a data de emissão condiz com a competência informada.
4. **Tratamento Dinâmico de Emitentes:** Consulta uma base de dados JSON local (`emitentes_conhecidos.json`). Caso encontre um fornecedor novo, o robô pergunta para que o usuário informe o nome tratado do parceiro em tempo de execução, garantindo a padronização das pastas.
5. **Download e Persistência:** Baixa simultaneamente os buffers binários do XML e do PDF (DANFE/DACTE) direto da API do portal. Os arquivos são salvos de forma atômica no diretório configurado, e o robô envia uma requisição de sinalização (seta-flag) para o servidor, registrando o encerramento do processo para aquela nota.

---

## 📋 Pré-requisitos de Infraestrutura

O ambiente de execução precisa das seguintes definições no Windows/Linux:

**Estrutura de Rede/Diretório:** O caminho mapeado para o armazenamento das notas deve estar acessível e possuir permissões de escrita para a criação dinâmica de diretórios por ano e mês.

---

## 🔧 Configuração do Ambiente (Variáveis de Ambiente)

O projeto adota o isolamento de credenciais e caminhos de arquivos através de variáveis de ambiente do sistema operacional:

| Variável | Tipo | Descrição | Exemplo de Valor |
| :--- | :--- | :--- | :--- |
| `SENHA_COFRE` | `String` | Senha de acesso ao painel do portal Cofre NFe. | `MinhaSenhaCofre123` |
| `CAMINHO_DOCUMENTO_ENTRADA` | `Path` | Diretório raiz onde a árvore de pastas de NF-e/CT-e será gerada. | `X:\Empresa\Faturamento\Notas` |

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

💾 emitentes_conhecidos.json: Base que vincula o nome bruto extraído do HTML do portal com o nome limpo e formalizado desejado para a criação das pastas físicas. O salvamento deste arquivo ocorre em modo seguro com escrita em buffer temporário (.tmp) para prevenir corrupção de dados.
