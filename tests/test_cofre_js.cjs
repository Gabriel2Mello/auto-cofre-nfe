// Contrato do navegador: consulta única ocioso; atualização somente durante execução.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elementos = new Map();
function elemento() {
  return {tagName:'BUTTON',setAttribute(){},content:'teste', value:'2026-10', checked:true, disabled:false, hidden:false,
    selectedOptions:[{textContent:'Matriz'}], dataset:{}, children:[], textContent:'',
    addEventListener(){}, append(...nos){this.children.push(...nos);},
    replaceChildren(...nos){this.children=nos;}, focus(){}, click(){},scrollIntoView(){}};
}
for(const id of ['tipo','empresa','competencia','pasta','mesma-pasta'])elementos.set(id,elemento());
elementos.get('tipo').value='nfe';
elementos.get('empresa').value='FILIAL';
const eventos = new Map(), timers = new Map(), chamadas = [];
let proximoTimer=0;
let retorno={ativo:false,parando:false,status:'Pronto',resultados:[],pergunta:null,lote:null};
let iniciarPendente=null, falharEstado=false;
const contexto = vm.createContext({
  document:{documentElement:{dataset:{},setAttribute(nome,valor){this.dataset.tema=valor;}},getElementById(id){if(!elementos.has(id))elementos.set(id,elemento());return elementos.get(id);},
    querySelector(seletor){if(seletor==='#tipo input:checked')return elementos.get('tipo');if(seletor==='#empresa input:checked')return elementos.get('empresa');return elemento();},querySelectorAll(){return [];},createElement:elemento,createDocumentFragment:elemento},
  localStorage:{getItem(){return null;},setItem(){}},matchMedia(){return {matches:false,addEventListener(){}};},
  crypto:{randomUUID(){return 'pagina-teste';}},
  window:{addEventListener(nome,acao){eventos.set(nome,acao);}},
  setTimeout(fn,tempo){const id=++proximoTimer;timers.set(id,{fn,tempo});return id;},
  clearTimeout(id){timers.delete(id);},AbortController,
  fetch:async(caminho,opcoes)=>{
    chamadas.push(caminho);
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
  assert.equal(chamadas.filter(c=>c==='/api/estado').length,1);
  assert.equal(timers.size,0,'Tela ociosa não deve agendar consultas.');
  assert.match(elementos.get('destino').textContent,/Filial/);
  assert.equal(elementos.get('pasta').disabled,true,'Pasta vinculada permanece visível e bloqueada.');
  elementos.get('mesma-pasta').checked=false;
  elementos.get('pasta').value='2026-11';
  elementos.get('tipo').value='cte';elementos.get('empresa').value='MATRIZ';
  vm.runInContext('destino()',contexto);
  assert.equal(elementos.get('pasta').disabled,false);
  assert.match(elementos.get('destino').textContent,/CT-e.*Matriz.*11\/2026/);
  elementos.get('mesma-pasta').checked=true;
  elementos.get('tipo').value='nfe';elementos.get('empresa').value='FILIAL';
  vm.runInContext('destino()',contexto);
  let confirmado=false;
  eventos.get('beforeunload')({preventDefault(){confirmado=true;}});
  assert.equal(confirmado,true,'Fechar deve solicitar a confirmação nativa.');
  retorno={...retorno,ativo:true,resultados:[{nota:'123',situacao:'Aguardando',detalhe:''}]};
  await vm.runInContext('atualizar()',contexto);
  assert.equal(timers.size,1,'Execução ativa deve acompanhar o andamento.');
  const agendado=[...timers.values()][0];timers.clear();
  retorno={...retorno,ativo:false,resultados:[{nota:'123',situacao:'Concluído',detalhe:'Simulado'}]};
  await agendado.fn();
  assert.equal(timers.size,0,'Finalizar deve parar as consultas periódicas.');
  assert.equal(elementos.get('concluidos').textContent,1);
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
  const evento={preventDefault(){}};
  const primeira=elementos.get('formulario').onsubmit(evento);
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
