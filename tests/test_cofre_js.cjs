// Contrato do navegador: consulta única ocioso; atualização somente durante execução.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elementos = new Map();
const idsHtml=new Set([...fs.readFileSync(require('node:path').join(__dirname,'../src/cofre.html'),'utf8').matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]));
function elemento() {
  return {tagName:'BUTTON',setAttribute(){},content:'teste', value:'2026-10', checked:true, disabled:false, hidden:false,
    selectedOptions:[{textContent:'Matriz'}], dataset:{}, children:[], textContent:'',
    eventos:new Map(),addEventListener(nome,acao){this.eventos.set(nome,acao);}, append(...nos){this.children.push(...nos);},
    replaceChildren(...nos){this.children=nos;}, focus(){}, click(){},scrollIntoView(){}};
}
for(const id of ['tipo','empresa','competencia','pasta','mesma-pasta'])elementos.set(id,elemento());
elementos.get('tipo').value='nfe';
elementos.get('empresa').value='FILIAL';
const eventos = new Map(), timers = new Map(), chamadas = [], pedidos = [];
let proximoTimer=0;
let retorno={ativo:false,parando:false,status:'Pronto',resultados:[],pergunta:null,lote:null};
let iniciarPendente=null, falharEstado=false;
const contexto = vm.createContext({
  document:{documentElement:{dataset:{},setAttribute(nome,valor){this.dataset.tema=valor;}},getElementById(id){if(!idsHtml.has(id))return null;if(!elementos.has(id))elementos.set(id,elemento());return elementos.get(id);},
    querySelector(seletor){if(seletor==='#tipo input:checked')return elementos.get('tipo');if(seletor==='#empresa input:checked')return elementos.get('empresa');return elemento();},querySelectorAll(){return [];},createElement:elemento,createDocumentFragment:elemento,createTextNode(textContent){return {textContent};}},
  localStorage:{getItem(){return null;},setItem(){}},matchMedia(){return {matches:false,addEventListener(){}};},
  crypto:{randomUUID(){return 'pagina-teste';}},
  window:{addEventListener(nome,acao){const anterior=eventos.get(nome);eventos.set(nome,anterior?e=>{anterior(e);acao(e);}:acao);}},
  setTimeout(fn,tempo){const id=++proximoTimer;timers.set(id,{fn,tempo});return id;},
  clearTimeout(id){timers.delete(id);},AbortController,
  fetch:async(caminho,opcoes)=>{
    chamadas.push(caminho);
    if(opcoes?.body)pedidos.push({caminho,dados:JSON.parse(opcoes.body)});
    if(caminho==='/api/presenca')return new Promise(()=>{});
    if(caminho==='/api/iniciar')return new Promise(resolve=>{iniciarPendente=()=>resolve({ok:true,json:async()=>({ok:true})});});
    if(caminho==='/api/estado'&&falharEstado)throw Error('Conexão sintética perdida');
    return {ok:true,json:async()=>structuredClone(retorno)};
  },console,
});
async function esvaziar(){for(let i=0;i<8;i++)await Promise.resolve();}
async function agendamento(tempo){
  const entrada=[...timers.entries()].find(([,t])=>t.tempo===tempo);
  assert.ok(entrada,`O código deve agendar a próxima leitura em ${tempo} ms.`);
  timers.delete(entrada[0]);await entrada[1].fn();await esvaziar();
}
async function testar(){
  vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../src/nunes-tema.js'),'utf8'),contexto);
  vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../src/cofre.js'),'utf8'),contexto);
  await esvaziar();
  assert.equal(elementos.get('limpar-notas').disabled,false,'Limpar habilitado ao confirmar ociosidade.');
  const notas=elementos.get('notas'), atalho=elementos.get('enter-baixar');
  const antesEntrada=notas.eventos.get('beforeinput'), entradaNotas=notas.eventos.get('input');
  notas.value='123, 456';entradaNotas();
  let letrasBloqueadas=0;
  antesEntrada({data:'abc',preventDefault(){letrasBloqueadas++;}});
  assert.equal(letrasBloqueadas,1,'Letras digitadas devem ser bloqueadas.');
  notas.value='123, 456abc';entradaNotas();
  assert.equal(notas.value,'123, 456','Colagem inválida preserva os números anteriores.');
  notas.value='12a34';entradaNotas();
  assert.equal(notas.value,'123, 456','Não juntar dígitos ao remover letras.');
  notas.value='00123, 456;789\n101';entradaNotas();
  assert.equal(notas.value,'00123, 456;789\n101','Separadores e zeros iniciais preservados.');
  const teclado=notas.eventos.get('keydown');
  let enviosTeclado=0, impedidos=0;
  elementos.get('formulario').requestSubmit=botao=>{assert.equal(botao,elementos.get('iniciar'));enviosTeclado++;};
  notas.value='123, 456';atalho.checked=false;
  teclado({key:'Enter',preventDefault(){impedidos++;}});
  assert.equal(enviosTeclado,0);
  atalho.checked=true;
  await atalho.eventos.get('change')();
  assert.equal(elementos.get('dica-notas').textContent,'Separe por vírgula.');
  assert.ok(pedidos.some(p=>p.caminho==='/api/entrada-notas'&&p.dados.enter_baixar===true));
  for(const extra of [{shiftKey:true},{ctrlKey:true},{altKey:true},{metaKey:true},{isComposing:true}]){
    teclado({key:'Enter',...extra,preventDefault(){impedidos++;}});
  }
  assert.equal(impedidos,0,'Quebra de linha e composição preservadas.');
  teclado({key:'Enter',preventDefault(){impedidos++;}});
  assert.equal(enviosTeclado,1);
  teclado({key:'Enter',repeat:true,preventDefault(){}});
  elementos.get('campos').disabled=true;
  teclado({key:'Enter',preventDefault(){}});
  elementos.get('limpar-notas').onclick();
  assert.equal(notas.value,'123, 456','Limpar bloqueado durante operação.');
  elementos.get('campos').disabled=false;
  elementos.get('limpar-notas').onclick();
  assert.equal(notas.value,'');
  teclado({key:'Enter',preventDefault(){}});
  assert.equal(enviosTeclado,1,'Campo vazio, repetição e operação ativa não enviam.');
  const enviosAntes=chamadas.filter(c=>c==='/api/iniciar').length;
  await elementos.get('formulario').onsubmit({preventDefault(){}});
  assert.equal(chamadas.filter(c=>c==='/api/iniciar').length,enviosAntes,'Campo vazio não inicia lote pelo botão.');
  assert.equal(elementos.get('mensagem').textContent,'Informe ao menos uma nota.');
  assert.equal(elementos.get('iniciar').disabled,false,'Validação vazia mantém o formulário disponível.');
  await esvaziar();
  assert.equal(elementos.get('mensagem').textContent,'Informe ao menos uma nota.','Aviso permanece sem interação.');
  for(const nomeEvento of ['pointerdown','click','keydown','input','change','wheel']){
    await elementos.get('formulario').onsubmit({preventDefault(){}});
    eventos.get(nomeEvento)({key:'a',target:notas});
    assert.equal(elementos.get('mensagem').textContent,'',`${nomeEvento} devolve o espaço à dica anterior.`);
  }
  elementos.get('mensagem').textContent='Falha de conexão';
  eventos.get('keydown')({key:'a',target:notas});
  assert.equal(elementos.get('mensagem').textContent,'Falha de conexão','Interação não descarta outros erros.');
  elementos.get('mensagem').textContent='';
  atalho.checked=false;
  await atalho.eventos.get('change')();
  assert.equal(chamadas.filter(c=>c==='/api/estado').length,1);
  assert.equal(timers.size,0,'Tela ociosa não deve agendar consultas.');
  assert.equal(elementos.get('abrir-pasta').hidden,true,'Abertura da pasta fica restrita ao desktop.');
  await elementos.get('abrir-pasta').onclick();
  assert.equal(chamadas.includes('/api/pasta/abrir'),false,'Modo web não deve solicitar abertura nativa.');
  const menu=contexto.document.getElementById('configuracoes');
  const avisoPasta=contexto.document.getElementById('configuracao-status');
  const informarPasta=vm.runInContext('informarPasta',contexto);
  for(const mensagem of ['Pasta aberta no Explorador de Arquivos.','Pasta salva. Será usada nas próximas execuções.',
    'Escolha cancelada. A pasta anterior foi mantida.','Escolha a pasta no diálogo do Windows.','Falha ao acessar a pasta.']){
    menu.open=true;informarPasta(mensagem);menu.eventos.get('toggle')();
    assert.equal(avisoPasta.textContent,mensagem,'Menu aberto mantém a mensagem atual.');
    menu.open=false;menu.eventos.get('toggle')();
    assert.equal(avisoPasta.textContent,'','Fechar pelo próprio controle limpa qualquer mensagem.');
    informarPasta(mensagem);
    assert.equal(avisoPasta.textContent,'','Resposta recebida com menu fechado não restaura o aviso.');
    menu.open=true;menu.eventos.get('toggle')();
    assert.equal(avisoPasta.textContent,'','Reabrir não recupera a mensagem dispensada.');
  }
  const controleInterno=elemento(), controleExterno=elemento();
  menu.contains=alvo=>alvo===menu||alvo===controleInterno;
  for(const nome of ['pointerdown','focusin']){
    menu.open=true;
    avisoPasta.textContent='Pasta aberta no Explorador de Arquivos.';
    eventos.get(nome)({target:controleInterno});
    assert.equal(menu.open,true,`${nome} interno deve preservar o menu aberto.`);
    eventos.get(nome)({target:menu});
    assert.equal(menu.open,true,'Interagir no próprio menu deve preservá-lo.');
    eventos.get(nome)({target:controleExterno});
    assert.equal(menu.open,false,`${nome} externo deve fechar o menu.`);
    menu.eventos.get('toggle')();
    assert.equal(avisoPasta.textContent,'',`${nome} externo deve dispensar a confirmação.`);
    eventos.get(nome)({target:controleExterno});
    assert.equal(menu.open,false,'Interação externa não deve reabrir o menu.');
  }
  menu.open=true;
  avisoPasta.textContent='Pasta aberta no Explorador de Arquivos.';
  eventos.get('keydown')({key:'Escape'});
  assert.equal(menu.open,false,'Escape deve continuar fechando o menu.');
  menu.eventos.get('toggle')();
  assert.equal(avisoPasta.textContent,'','Escape também limpa a confirmação.');
  assert.equal(elementos.get('pasta').disabled,true,'Pasta vinculada permanece visível e bloqueada.');
  assert.equal(elementos.get('pasta').required,false);
  assert.equal(elementos.get('pasta').value,elementos.get('competencia').value);
  elementos.get('mesma-pasta').checked=false;
  elementos.get('pasta').value='2026-11';
  elementos.get('tipo').value='cte';elementos.get('empresa').value='MATRIZ';
  vm.runInContext('destino()',contexto);
  assert.equal(elementos.get('pasta').disabled,false);
  assert.equal(elementos.get('pasta').required,true);
  assert.equal(elementos.get('pasta').value,'2026-11','Pasta independente conserva o mês escolhido.');
  elementos.get('mesma-pasta').checked=true;
  elementos.get('tipo').value='nfe';elementos.get('empresa').value='FILIAL';
  vm.runInContext('destino()',contexto);
  let confirmado=false;
  eventos.get('beforeunload')({preventDefault(){confirmado=true;}});
  assert.equal(confirmado,true,'Fechar deve solicitar a confirmação nativa.');
  retorno={...retorno,ativo:true,resultados:[{nota:'123',situacao:'Aguardando',detalhe:''}]};
  await vm.runInContext('atualizar()',contexto);
  assert.equal(timers.size,1,'Execução ativa deve acompanhar o andamento.');
  assert.equal(elementos.get('resumo').dataset.finalizado,'false','Borda final não aparece durante a execução.');
  const agendado=[...timers.values()][0];timers.clear();
  retorno={...retorno,ativo:false,resultados:[{nota:'123',situacao:'Concluído',detalhe:'XML e PDF salvos · FORNECEDOR 123'}]};
  await agendado.fn();
  assert.equal(timers.size,0,'Finalizar deve parar as consultas periódicas.');
  assert.equal(elementos.get('resumo').dataset.finalizado,'true','Fim da execução habilita a borda neutra.');
  assert.equal(elementos.get('concluidos').textContent,1);
  const primeiraNota=elementos.get('linhas').children[0].children[0];
  assert.equal(primeiraNota.children[0].textContent,'Concluído');
  assert.equal(primeiraNota.children[1].children[0].textContent,'123');
  assert.equal(primeiraNota.children[1].children[1].textContent,' · FORNECEDOR 123');
  assert.equal(retorno.resultados[0].detalhe,'XML e PDF salvos · FORNECEDOR 123','Resumo visual não altera o detalhe exportado.');
  const linhasAntes=elementos.get('linhas').children;
  await vm.runInContext('atualizar()',contexto);
  assert.equal(elementos.get('linhas').children,linhasAntes,'Estado igual não deve reconstruir a tabela.');
  retorno={...retorno,ativo:true,pergunta:{id:'nome-1',tipo:'nome',emitente:'TESTE',sugestao:'NOME INICIAL'}};
  await vm.runInContext('atualizar()',contexto);
  elementos.get('nome').value='DECISÃO PARCIAL DO OPERADOR';
  retorno.status='Atualização de andamento';
  await vm.runInContext('atualizar()',contexto);
  assert.equal(elementos.get('nome').value,'DECISÃO PARCIAL DO OPERADOR','Atualização não apaga a decisão em edição.');
  retorno={...retorno,ativo:false,pergunta:null};
  await vm.runInContext('atualizar()',contexto);
  notas.value='123';
  const evento={preventDefault(){}};
  const primeira=elementos.get('formulario').onsubmit(evento);
  assert.equal(elementos.get('resumo').dataset.finalizado,'false','Novo envio remove a borda anterior imediatamente.');
  await elementos.get('formulario').onsubmit(evento);
  assert.equal(chamadas.filter(c=>c==='/api/iniciar').length,1,'Duplo envio não deve repetir início.');
  falharEstado=true;iniciarPendente();await primeira;
  assert.equal(elementos.get('iniciar').disabled,true,'Perda de resposta mantém início bloqueado até uma leitura válida.');
  assert.equal(elementos.get('campos').disabled,true);
  assert.equal(elementos.get('fase').textContent,'Reconectando');
  assert.equal(timers.size,1,'Estado ocioso anterior não dispensa a recuperação do início ainda sem confirmação.');
  falharEstado=false;
  retorno={...retorno,ativo:true};
  await agendamento(1500);
  assert.equal(chamadas.filter(c=>c==='/api/iniciar').length,1,'Recuperação deve usar somente leitura.');
  assert.equal(elementos.get('iniciar').disabled,true,'Lote recuperado continua em andamento.');
  retorno={...retorno,ativo:false};
  await agendamento(800);
  assert.equal(timers.size,0,'Ociosidade confirmada encerra as consultas.');
  assert.equal(elementos.get('iniciar').disabled,false);
  // A leitura pode voltar ao mesmo snapshot ocioso (POST recusado ou lote rápido).
  // Mesmo sem alteração do DOM, os controles precisam ser liberados.
  const segunda=elementos.get('formulario').onsubmit(evento);
  falharEstado=true;iniciarPendente();await segunda;
  falharEstado=false;await agendamento(1500);
  assert.equal(elementos.get('campos').disabled,false);
  assert.equal(elementos.get('iniciar').disabled,false);
  assert.equal(chamadas.filter(c=>c==='/api/iniciar').length,2,'Um POST por envio explícito, nenhum POST durante recuperação.');
  assert.equal(timers.size,0);
  assert.equal(chamadas.includes('/api/parar'),false,'Iniciar e recuperar o andamento não devem solicitar parada.');
  await elementos.get('parar').onclick();
  await elementos.get('cancelar-decisao').onclick();
  assert.deepEqual(pedidos.filter(p=>p.caminho==='/api/parar').map(p=>p.dados.origem),['parar','decisao']);
  retorno={...retorno,encerrando:true,ativo:true};
  await vm.runInContext('atualizar()',contexto);
  assert.equal(elementos.get('campos').disabled,true);
  assert.equal(elementos.get('fase').textContent,'Encerrando');
  eventos.get('pagehide')();
  const quantidadeAntes=chamadas.length;
  await vm.runInContext('atualizar()',contexto);
  assert.equal(chamadas.length,quantidadeAntes,'Aba saindo não deve iniciar novas consultas.');
  console.log('OK: recuperação automática por timers sem reenvio, ociosidade saudável, bloqueio de duplo envio, decisões e DOM preservados.');
}
testar().catch(erro=>{console.error(erro);process.exitCode=1;});
