# Interface local do Cofre NF-e

O navegador apresenta o painel; a automação continua neste computador, usando
as variáveis de ambiente e a pasta de documentos da instalação. Não há hospedagem
externa. As dependências estão fixadas em `requirements.txt`, incluindo o leitor de PDF aprovado na E3. O modo console continua em `main.py`.

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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe cofre.py
```

Configure `SENHA_COFRE`, `CNPJ_MATRIZ`, `CNPJ_FILIAL` e
`CAMINHO_DOCUMENTO_ENTRADA` conforme o README. A interface não exibe nem
armazena senhas e não consulta o portal ao abrir.

## Uso

1. Informe os documentos separados por vírgula ou linha. NF-e, Matriz e o mês
   atual já vêm selecionados; CT-e, Filial e outras competências estão disponíveis.
2. Para organizar em outro mês/ano, desmarque **Salvar na mesma competência**.
   Confira a prévia de destino e clique em **Baixar e organizar**.
3. Se houver mais de um emitente, selecione o resultado correto. Para emitente
   novo, confirme o nome usado nos arquivos; esse nome é salvo na base local.
4. Confira cada resultado. **Conferir sinalização** significa que XML/PDF foram
   salvos, mas a confirmação da marcação no portal falhou. Uma falha ao salvar
   pode deixar uma publicação parcial identificada pelo ID da pendência; use
   o guia de recuperação antes de repetir. Não há repetição automática de
   downloads ou sinalizações.
5. **Baixar resultado** exporta o lote para JSON. O painel mostra apenas a
   execução atual; iniciar outra substitui a lista. Não há histórico persistente
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

Fechar ou sair da aba solicita a confirmação nativa do navegador. O navegador
controla o texto e pode dispensar esse aviso se ainda não houve interação do
usuário. **Encerrar** apresenta a pergunta explícita da aplicação e solicita a
mesma parada cuidadosa. O servidor encerra após a execução terminar.

Uma conexão de presença detecta quando a última aba é fechada. Após a desconexão,
há uma margem de quatro segundos para recarregar ou reconectar, antes de solicitar
o encerramento. Outra aba ainda conectada mantém o programa aberto. A conexão de
presença não consulta os documentos nem altera a tela. A interface consulta o
estado uma vez ao abrir e após ações do operador; consultas periódicas e
alterações do andamento ocorrem somente durante uma execução. Estados iguais
não reconstroem a tela.

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

Para empacotar a interface, use `cofre.py` como entrada e inclua os recursos:

```powershell
..\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name "Cofre NFe" --icon icons/icone.ico --add-data "src/cofre.html;src" --add-data "src/cofre.css;src" --add-data "src/cofre.js;src" --add-data "icons;icons" cofre.py
```

O executável é produzido em `dist`; para os atalhos acima, coloque-o na pasta da
aplicação. Nenhum executável novo é necessário para rodar a versão Python.

## Integração com o Hub Nunes

O contrato local `integracao_hub.py`, mantido no Hub Nunes, permite reconhecer
interfaces abertas pelo atalho próprio, conferir sua saúde e solicitar a parada
segura pelo monitor. Cofre pode permanecer aberto junto de uma ferramenta
Sisplan. Fechar a última aba continua seguindo a parada segura da aplicação.
Executáveis anteriores precisam ser reconstruídos para incluir a integração;
os atalhos Python usam os fontes atualizados.
