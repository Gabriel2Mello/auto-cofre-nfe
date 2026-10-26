# Contrato observado do portal Cofre

Observação feita em 26/10/2026 na aba do Edge disponibilizada pelo responsável.
Este documento descreve os sinais usados pelo cliente; não é documentação
oficial da API nem garantia de estabilidade do HTML do fornecedor.

## Empresa ativa

Depois da seleção de vínculo, a página `/nfe/empresa` identifica a empresa em
`#mws-header-container > span`. Dentro desse elemento, o nome aparece em um
span com o CNPJ formatado entre parênteses. O cabeçalho também contém o nome da
contabilidade. A lista de vínculos da página de login não identifica a empresa
ativa e não deve ser usada como confirmação da troca.

`trocar_empresa` exige HTTP 200 no próprio portal e um único CNPJ nesse
cabeçalho, igual ao CNPJ solicitado. Cabeçalho ausente, ambíguo ou divergente
interrompe o lote antes de consultar, baixar, publicar, contabilizar ou sinalizar.
Os erros não reproduzem CNPJ, HTML, vínculos ou identificadores de sessão.

## Sinalização

Na tabela `#tabelaNavegaArquivos`, o estado corrente de cada documento aparece
em `div#flagArqID`, com classe `flagN`. A marcação usada pelo Cofre é `flag10`.
A paleta `#balaoEscolheFlagID` contém opções com classes semelhantes e ações
como `setaFlag(10,'ID')`; essas opções não comprovam o estado corrente.

O cliente envia uma única solicitação para `/nfe/seta-flag/ID/10`, sem seguir
redirecionamentos. Após HTTP 200, faz uma nova consulta de documentos e exige
exatamente um indicador `div#flagArqID` com a classe `flag10`. O corpo da escrita,
inclusive um corpo vazio ou uma indicação genérica de sucesso, não comprova a
marcação. Falha na releitura deixa **Conferir sinalização**, preservando os
arquivos e a métrica já confirmados. A confirmação não repete a escrita.

O responsável autorizou repetir somente a marcação correta já existente.
A paleta não pôde ser acionada de forma confiável pela automação do navegador;
nenhuma reaplicação real foi confirmada nesta entrega. Não foram baixados XML/PDF,
alteradas marcações diferentes, executadas manifestações ou consultada a SEFAZ.
O corpo HTTP real da escrita não foi capturado. O cliente confirma o estado
pela estrutura observada na consulta, em vez de presumir um formato desse corpo.

## Consulta e paginação

O código de inicialização da tabela observado usa DataTables com processamento
no servidor, POST, página de 25 registros e endpoint
`/nfe/empresa/ver-arquivos-nfe/load`. O formulário e seu código de envio expõem
`nro_nota_de` e `nro_nota_ate`; o cliente preenche os dois com a nota solicitada,
evitando percorrer documentos de outros números. Avança `iDisplayStart` até
consumir `iTotalDisplayRecords`. Sem esse total,
continua até receber uma página com menos de 25 registros. A seleção ocorre
somente depois de reunir as páginas.

Página repetida, total divergente, término antes do total, estrutura inválida,
redirecionamento ou página de login interrompem a consulta. A paginação não
garante um snapshot transacional do portal: mudanças concorrentes que mantenham
o mesmo total ainda dependem das garantias de ordenação do fornecedor.
As respostas HTTP usadas nos testes são sintéticas; não foram arquivadas respostas
JSON de documentos reais.

## Amostras e regressões

- `tests/amostras_portal/empresa_ativa.html`: estrutura mínima do cabeçalho.
- `tests/amostras_portal/marcacao.html`: indicador corrente e opções da paleta.
- `tests/test_contrato_portal.py`: respostas HTTP falsas, paginação, contexto e
  confirmação de marcação, incluindo recusas antes dos efeitos de negócio.

As amostras são recortes mínimos reconstruídos da estrutura observada, com
textos e identificadores fictícios. Não contêm documentos fiscais, nomes reais,
CNPJ real, cookies, tokens, credenciais, chaves de software ou identificadores
reais de vínculo/arquivo. Não são capturas integrais do portal.

Ao atualizar o contrato, observe somente os elementos necessários e sanitize
antes de gravar qualquer amostra. Não use captura integral de HTML, HAR, tela,
logs ou respostas fiscais como fixture. Não execute a escrita de flag em teste
automatizado de produção; use HTTP falso e documentos sintéticos.

Reabra a aplicação Python para carregar as mudanças. Executáveis distribuídos
precisam ser reconstruídos. Login, download e sinalização completos no ambiente
operacional ainda exigem homologação controlada pelo responsável.
