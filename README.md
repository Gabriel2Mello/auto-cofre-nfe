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
5. **Download e Persistência:** Baixa os buffers binários do XML e do PDF (DANFE/DACTE) direto da API do portal. Após salvar os arquivos no diretório configurado, o robô envia uma requisição de sinalização (seta-flag) para o servidor. Falhas ao salvar podem deixar arquivos parciais; a gravação do par XML/PDF não é transacional.

---

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
💾 `emitentes_conhecidos.json`: Base que vincula o nome bruto extraído do HTML do portal com o nome limpo e formalizado desejado para a criação das pastas físicas. O salvamento deste arquivo ocorre em modo seguro com escrita em buffer temporário (.tmp) para prevenir corrupção de dados.

Criado por Gabriel Mello · [g2mello](https://github.com/Gabriel2Mello)
