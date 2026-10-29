# Testar o Cofre com dados sintéticos

Abra **Testar Cofre NFe.cmd**, na pasta do projeto. O atalho usa o Python do
ambiente local e abre uma janela separada, identificada como **SIMULAÇÃO**.
Pode ficar aberta junto do Cofre de uso normal. Não é necessário ter notas,
credenciais ou exemplos reais.

1. Escolha um **Cenário de teste**.
2. Clique em **Preparar cenário** para preencher as notas fictícias.
3. Confira NF-e/CT-e, Matriz/Filial e as competências, se quiser variá-los.
4. Clique em **Baixar** e responda às perguntas normalmente.
5. Confira os resultados. Para repetir, prepare o mesmo cenário e clique em Baixar.

Preparar um cenário não inicia a execução. Durante um lote, conclua ou pare o
processamento antes de preparar outro. Fechar uma pergunta com **Parar execução**
ou usar **Parar processamento** interrompe somente a simulação.

| Cenário | Notas preenchidas | O que observar |
| --- | --- | --- |
| Sucesso | 1001 | Conclusão e contador |
| Nenhuma nota encontrada | 1002 | Mensagem de ausência na competência |
| Escolher entre emitentes | 1003 | Seleção obrigatória entre duas opções |
| Emitente novo / apelido | 1004 | Nome sugerido, edição e rejeição de nomes inválidos |
| XML inválido | 1005 | Erro de validação, sem conclusão |
| PDF inválido | 1006 | Erro de validação, sem conclusão |
| Falha ao gravar | 1007 | Mensagem de acesso/permissão |
| Conferir sinalização | 1008 | Atenção e orientação antes de repetir |
| Arquivos já existentes | 1009 | Mensagem de reaproveitamento |
| Parar durante o processamento | 1010, 1001 | Primeira nota aguarda 12 segundos; use Parar processamento |
| Nomes e mensagens longos | 1011 | Quebras de linha e acesso aos controles |
| Lote misto | 1001 a 1009 | Sucessos, perguntas, erros e atenção na mesma execução |
| Lote com 80 notas | 2000 a 2079 | Contagens, rolagem e estabilidade do formulário |
| Perda de resposta / reconexão | 1001 | Aviso de reconexão e recuperação sem reenviar o lote |
| HTTP 503 ao acessar o Cofre | 1012, 1001 | Lote encerrado antes do processamento; ambas as notas não processadas |
| HTTP 503 na consulta / baixa | 1013, 1001 | Erro no primeiro documento; o seguinte continua |
| HTTP 503 na sinalização | 1014, 1001 | Primeiro documento pede conferência da sinalização; o seguinte continua |

Também é possível digitar esses números diretamente. Outros números válidos
produzem sucesso fictício. Para simular a perda de resposta, use o seletor e
**Preparar cenário**, pois esse caso também prepara a falha temporária no cliente.

Os casos de HTTP 503 criam uma resposta fictícia e usam a mesma classificação
de erro da aplicação. No acesso e na consulta/baixa, a mensagem informa **Falha de
comunicação com o Cofre NF-e. Confira o portal e a conexão.**, sem exibir o código HTTP no resultado.
No acesso inicial, a indisponibilidade interrompe o lote inteiro; por documento,
a execução continua conforme o fluxo real. A falha após a gravação fictícia usa
**Conferir sinalização**, com a mensagem **XML e PDF salvos; não foi possível
confirmar a sinalização no Cofre NF-e. Confira o portal e a conexão.**
Nenhum desses casos faz requisições externas ou grava
documentos. A API local permanece disponível para consultar os resultados.

O aviso de simulação permanece visível, e os resultados usam texto fictício.
A interface e as validações de entrada, decisões e parada são as mesmas da
aplicação. O executor é separado: não importa o executor fiscal, não consulta
o portal, não baixa nem grava XML/PDF, não salva apelidos no catálogo real e não
registra ou sincroniza estatísticas reais. Conexões Python fora do loopback
são bloqueadas. Preferências e diagnósticos ficam em uma pasta temporária própria.
O menu de arquivos/pastas fica indisponível nesse modo.

Esses cenários reproduzem o comportamento da interface diante dos resultados.
Não validam os arquivos XML/PDF, o acesso ao portal, a gravação recuperável ou
a sinalização reais; os testes específicos dessas funções continuam separados.

A janela de simulação permite redimensionar e maximizar para conferir o layout.
O Cofre normal conserva sua política de janela fixa. O atalho de teste pertence
ao projeto com Python; ele não é adicionado ao executável de produção.

Para abrir pelo terminal:

```powershell
.\.venv\Scripts\python.exe -m tests.preview_interface --desktop
```

Sem `--desktop`, o comando imprime uma URL local para abrir no navegador.
Fechar a última aba encerra essa prévia após a margem de presença existente.

Verificações automatizadas dos cenários e do isolamento:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_simulacao -v
node --check tests/simulacao.js
node tests/test_simulacao_js.cjs
```
