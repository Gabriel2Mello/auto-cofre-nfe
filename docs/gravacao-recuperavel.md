# Gravação e recuperação dos documentos — E5

Implementada em 20/10/2026 no console e no painel. XML e PDF passam novamente
pela validação da E3 antes da preparação em disco. CT-e inclui sua cópia XML.
Métrica, sinalização no portal e conclusão da nota só acontecem depois que o
salvamento confirma o conjunto completo.

## Nomes e arquivos existentes

- Quando os destinos estão livres, mantém `EMITENTE NUMERO.pdf`, `.xml` e,
  para CT-e, `EMITENTE NUMERO copia.xml`.
- Um conjunto completo, válido e da mesma chave é reaproveitado. Uma nova
  renderização do PDF não substitui a primeira cópia válida.
- Se há arquivos de outra chave, inválidos ou incompletos nos nomes originais,
  eles são preservados. A nova baixa usa `EMITENTE NUMERO - CHAVE_FISCAL` em
  todos os arquivos, incluindo `EMITENTE NUMERO - CHAVE_FISCAL copia.xml` no CT-e.
- Destinos com chave no nome que já estejam ocupados por conteúdo divergente
  também são preservados; a baixa falha e exige conferência. Não há troca
  automática de nomes dos arquivos antigos ou sobrescrita silenciosa.

O painel e o console informam o nome usado. A identidade histórica das métricas
continua baseada em empresa, tipo e identificador do portal, conforme a E3.

## Preparação e publicação

Desde 21/10/2026, cada gravação recebe um ID e um registro na raiz do projeto:
`auto-cofre-nfe/.cofre-gravacoes/DESTINO/ID/manifesto.json`. `DESTINO` é o hash
do caminho absoluto normalizado da pasta de documentos, separando pendências
de bases distintas. A localização independe da pasta atual do terminal ou Hub.
Não é criada uma pasta `.cofre-gravacoes` na área compartilhada dos documentos.
O registro contém contexto
fiscal, chave, nomes e hashes SHA-256; não contém senha ou sessão do portal.
Inclua a pasta local `.cofre-gravacoes` no backup, além da área de documentos
com seus temporários. Ao mudar o caminho absoluto da base, o hash muda; preserve
a associação da subpasta de registros com a base original antes de recuperar.

Desde 26/10/2026, o primeiro manifesto é escrito e sincronizado em
`.cofre-gravacoes/.iniciando/DESTINO/ID-TENTATIVA`, antes de publicar o diretório
definitivo do registro. A preparação dos documentos só começa após essa
publicação. Falhar antes dela não cria uma pendência inválida na listagem nem
bloqueia uma nova baixa depois de corrigir o armazenamento. Restos dessa área
são preservados e não representam documentos publicados; não os promova
manualmente. A mesma proteção vale para a primeira atualização local de um
registro antigo, sem ocultar o registro original em caso de falha.
Registros definitivos inválidos anteriores continuam exigindo conferência;
não há reparo ou remoção automática de dados existentes.

Registros antigos em `CAMINHO_BASE/.cofre-gravacoes` continuam disponíveis para
listagem e recuperação, sem criação ou atualização de registros nesse local.
Ao concluir ou abandonar uma pendência antiga, o estado atualizado fica somente
no projeto e passa a prevalecer na listagem. Os registros antigos são preservados;
não há remoção ou movimentação automática na pasta compartilhada. Mantenha o
Cofre anterior encerrado e reabra a ferramenta para carregar esta alteração.

Os arquivos completos são preparados como `.cofre-ID-pdf.tmp`, `-xml.tmp` e
`-copia.tmp` nos próprios diretórios de destino. Escritas usam criação exclusiva,
sincronização e conferência dos bytes. Somente após preparar e conferir todos
eles começa a publicação, por arquivo, sem substituir destinos existentes.
No Windows, isso utiliza a [semântica de `os.rename`](https://docs.python.org/3.13/library/os.html#os.rename).

O conjunto é novamente conferido antes de marcar o registro como `concluido`.
Uma falha preserva os arquivos anteriores e os dados disponíveis da pendência;
não registra métrica nem sinaliza o portal. Registros e temporários remanescentes não são
descartados automaticamente. Dentro de um checkout, esses dados são ignorados pelo Git.

Como os destinos são pastas distintas, a publicação do conjunto **não é uma
transação única**. Arquivos novos podem aparecer parcialmente antes da conclusão.
Não trate um conjunto pendente como entregue; use a conferência/recuperação.

## Listar e recuperar

Feche o Cofre antes de usar o comando, que respeita a reserva da aplicação no
Hub por usuário/sessão. Nos exemplos, substitua `CAMINHO_BASE` pela pasta base
configurada para os documentos e `ID` pelo identificador da pendência.

```powershell
.\.venv\Scripts\python.exe recuperar_documentos.py --pasta "CAMINHO_BASE"
.\.venv\Scripts\python.exe recuperar_documentos.py --pasta "CAMINHO_BASE" --concluir ID
```

A listagem é somente leitura dos registros locais e antigos. `--pasta` continua
indicando a base dos documentos, não a pasta local de registros. Os estados são:

| Estado | Significado e ação |
|---|---|
| `preparando` | A preparação foi iniciada. `--concluir` verifica se todos os arquivos estão disponíveis e íntegros antes de publicar. |
| `pronto` | A preparação terminou; a publicação pode estar parcial. `--concluir` confere arquivos já publicados e promove somente os que faltam. |
| `concluido` | Houve conferência e conclusão local. Repetir `--concluir` confere o conjunto sem publicar novamente. A listagem não verifica continuamente os arquivos. |
| `abandonado` | Preparação liberada para nova baixa, preservando registro e temporários. |
| `invalido` | Registro corrompido, indisponível ou incompatível. Preserve os dados e peça conferência; não há reparo automático. |

Se faltam arquivos preparados, eles estão corrompidos ou a publicação ainda não
começou, é possível liberar uma nova baixa **somente quando nenhum destino foi
publicado**:

```powershell
.\.venv\Scripts\python.exe recuperar_documentos.py --pasta "CAMINHO_BASE" --abandonar ID
```

Esse comando aceita `preparando` ou `pronto` sem arquivos finais. Ele altera
apenas o estado, preservando o registro e os temporários para conferência.
Conjuntos com publicação iniciada não podem ser abandonados pelo comando;
use recuperação ou confira os dados com o responsável, sem apagar arquivos
para forçar a repetição. Destino conflitante, hash divergente ou registro inválido
bloqueia a recuperação e preserva a evidência. Um registro inválido também bloqueia
novas gravações até ser conferido, pois não é possível identificar sua pendência.

O comando só atua nos arquivos locais: **não baixa, não contabiliza e não sinaliza
no portal**. Depois de recuperar, uma nova baixa pelo fluxo normal valida o
download, reaproveita o conjunto íntegro e executa a métrica/sinalização usuais.
Falha somente na sinalização continua aparecendo como **Conferir sinalização**.

## Validação e limites

Na mudança de localização de 21/10/2026, passaram os **55 testes Python** do
Cofre, com presença/métricas isoladas e documentos sintéticos. As seis novas
regressões cobrem gravação na raiz do projeto a partir de outro diretório,
separação de bases, recuperação/abandono de registros antigos sem alterá-los,
falha no armazenamento local sem criar registro compartilhado e corrupção
local sem recorrer silenciosamente ao registro antigo. Nenhum registro real
foi movido ou removido.

Passaram **49 testes Python e um JavaScript**, incluindo **17 novos testes**
da E5. Cobrem colisões, falhas na preparação e antes/depois da publicação de
cada arquivo, cópia CT-e, alteração de conteúdo, corrida de destino, registro
corrompido, repetição da recuperação, reserva do Cofre e ausência de métrica/flag
em cada falha. Também foi conferida a recuperação de CT-e em outro processo.

Código de produção alterado, comando e testes novos/de download passaram na
tipagem sem erros/avisos. A análise global conserva as 11 pendências anteriores
na interface HTTP e em testes existentes. Sem novas dependências.

Os testes usam documentos fictícios, diretórios locais temporários e bloqueio
de rede externa. Nenhum documento, catálogo ou portal real foi acessado. Reabra
o programa Python para carregar a E5; executáveis antigos precisam ser reconstruídos.

A coordenação do Hub continua por usuário/sessão; não é uma trava distribuída
entre computadores. Criação concorrente de um destino é tratada como conflito,
sem substituição. Windows local foi validado; compartilhamento real, queda de
energia e execução POSIX ainda exigem homologação. As verificações da E3 não
substituem assinatura digital, XSD integral ou consulta de situação na SEFAZ.
