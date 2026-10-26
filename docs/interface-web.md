# Interface local do Cofre NF-e

O desktop WebView2 apresenta o painel; a automação continua neste computador, usando
as variáveis de ambiente e a pasta de documentos da instalação. Não há hospedagem
externa. As dependências fiscais estão fixadas em `requirements.txt`, incluindo o leitor de PDF aprovado na E3. O modo console continua em `main.py`.
O guia [DESKTOP.md](../DESKTOP.md) documenta o runtime da janela, instância única,
atalhos, persistência, integração com o Hub e pacote. Esse guia substitui as
orientações antigas de abertura/empacotamento pelo navegador.

## Abrir

Abra `Abrir Cofre NFe.cmd` ou gere o atalho com:

```powershell
.\"Criar Atalho Cofre NFe.ps1"
```

O atalho usa o ícone Nunes e aponta diretamente para `Cofre NFe.exe`, quando
presente, ou para o `pythonw.exe` de `.venv` ou `..\.venv`, nessa ordem.
Nesta instalação em `Projetos/Nunes`, o ambiente fica no `.venv` local. O `.lnk` é
específico da máquina; gere novamente após mover a aplicação. O CMD também
respeita essa ordem. Um executável antigo com outro nome não é usado.

Para preparar uma instalação nova com Python 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe cofre.py
```

Configure `SENHA_COFRE`, `CNPJ_MATRIZ` e `CNPJ_FILIAL` conforme o README.
Escolha a própria pasta DOCUMENTOS DE ENTRADA em **Configurações → Escolher pasta…**.
Sem escolha salva, a interface usa `CAMINHO_DOCUMENTO_ENTRADA` como antes.
A interface não exibe nem
armazena senhas e não consulta o portal ao abrir.

## Uso

1. Informe as **Notas** separadas por vírgula ou linha. NF-e, Filial e o mês
   atual já vêm selecionados; Tipo e Empresa usam escolhas diretas, sem dropdown.
2. Para organizar em outro mês/ano, desmarque **Pasta na mesma competência**.
   Confira a prévia de destino e clique em **Baixar e organizar**.
3. Se houver mais de um emitente, selecione o resultado correto. Para emitente
   novo, confirme o nome usado nos arquivos; esse nome é salvo na base local.
4. Confira cada resultado. **Conferir sinalização** significa que XML/PDF foram
   salvos, mas a confirmação da marcação no portal falhou. Uma falha ao salvar
   pode deixar uma publicação parcial identificada pelo ID da pendência; use
   o guia de recuperação antes de repetir. Não há repetição automática de
   downloads ou sinalizações.
5. O painel mostra apenas a execução atual; iniciar outra substitui a lista.
   Não há exportação da lista pela interface, histórico persistente
   de lotes nem retomada automática após encerrar.

Desde a E3, downloads passam pela [validação de formato e identidade](../README.md#validação-dos-downloads--e3-20102026) antes do salvamento: conteúdo inválido, divergente ou sem identidade verificável resulta em **Erro**, sem gravação, métrica ou sinalização. PDF protegido, em imagem ou com identidade ambígua exige conferência manual no portal.

Desde a E4, o [catálogo de emitentes](../README.md#catálogo-de-emitentes--e4-20102026) inválido impede o início do lote, com mensagem explícita. Uma falha ao salvar esse catálogo no encerramento preserva a versão anterior e informa o temporário disponível para conferência; os documentos já salvos continuam concluídos.

O salvamento conserva as pastas e o comportamento existentes, incluindo a cópia
XML de CT-e. A E5 preserva arquivos existentes: uma colisão usa a chave fiscal
no nome da nova baixa; conjuntos válidos da mesma chave são reaproveitados.
O painel informa o nome usado. A sinalização no Cofre ocorre somente após a
conferência do conjunto completo. Consulte o [guia de recuperação](gravacao-recuperavel.md)
para listar pendências e concluir publicações interrompidas, com a ferramenta fechada.

## Parada e fechamento

**Parar processamento** impede os próximos documentos e cancela uma decisão
pendente. Uma operação de gravação já iniciada conclui o salvamento e a tentativa
de sinalização antes de parar. Requisições de rede respeitam os timeouts existentes;
parar não significa matar o processo imediatamente.

No desktop, fechar pelo X durante processamento pede confirmação e mantém a
janela até a operação segura terminar. **Encerrar** e o monitor do Hub confirmam
em suas próprias telas e solicitam a mesma parada cuidadosa, sem outro diálogo.
O servidor encerra após a execução terminar.

No modo web usado pelas prévias, uma conexão de presença detecta quando a última aba é fechada. Após a desconexão,
há uma margem de quatro segundos para recarregar ou reconectar, antes de solicitar
o encerramento. Outra aba ainda conectada mantém o programa aberto. A conexão de
presença não consulta os documentos nem altera a tela. A interface consulta o
estado uma vez ao abrir e após ações do operador; consultas periódicas e
alterações do andamento ocorrem durante uma execução ou enquanto falta confirmar
o estado após uma falha de conexão. A recuperação repete somente a leitura,
sem reenviar o início. Uma leitura válida ociosa encerra as consultas periódicas.
Estados iguais não reconstroem a tela; os controles ainda são reabilitados ao
recuperar a confirmação.
No desktop, a janela controla o ciclo de vida: queda dessa conexão não solicita saída.

O servidor aceita somente `127.0.0.1`, valida Host, token por execução e Origin
nas ações, e serve uma lista fixa de recursos. Ele não foi preparado para acesso
por rede ou publicação.

## Identidade e verificação

O layout segue o painel local de Pedidos Havan e a referência de Contas a Receber,
com temas claro/escuro e adaptação para telas menores. O ícone `#166534` veio de
`estrutura-nunes/identidade-visual/gerados/auto-cofre-nfe`, copiado para `icons`.
A assinatura g2mello segue o padrão Essencial do hub, com dois traços separados
sob os `l`, link para o GitHub e foco de teclado visível. O funcionamento da
aplicação não depende do caminho do hub.

Testes locais, sem credenciais nem integrações reais:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -v
node --check src/cofre.js
node tests/test_cofre_js.cjs
```

`python -m tests.preview_interface` abre uma prévia sintética, sem consultar
o portal nem gravar documentos. Esta prévia serve somente para testar a interface.
Os testes simulados não comprovam login, download ou sinalização no portal real.

Em 16/10/2026, passaram 16 testes Python e o teste JavaScript de ociosidade,
execução, finalização e confirmação de saída. A prévia sintética foi conferida
no navegador, com decisões de emitente e nome, temas claro/escuro e largura de
390 px sem rolagem horizontal da página. O encerramento do servidor também
foi conferido; nenhum documento real foi consultado, salvo ou sinalizado.

Para empacotar a interface desktop com seus recursos e DLLs:

```powershell
& '.\Build Desktop.ps1'
```

A pasta inteira é produzida em `dist/Cofre NFe`; não mova somente o exe.
Dados mutáveis usam pasta persistente documentada em [DESKTOP.md](../DESKTOP.md).
Nenhum executável novo é necessário para rodar a versão Python.

## Integração com o Hub Nunes

O contrato local `integracao_hub.py`, mantido no Hub Nunes, permite reconhecer
interfaces abertas pelo atalho próprio, conferir sua saúde e solicitar a parada
segura pelo monitor. Cofre pode permanecer aberto junto de uma ferramenta
Sisplan. O desktop permanece aberto quando a conexão de presença cai e pode
continuar funcionando após fechar o Hub.
Executáveis anteriores precisam ser reconstruídos para incluir a integração;
os atalhos Python usam os fontes atualizados.
