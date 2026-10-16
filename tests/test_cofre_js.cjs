// Contrato do navegador: consulta única ocioso; atualização somente durante execução.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elementos = new Map();
function elemento() {
  return {content:'teste', value:'2026-10', checked:true, disabled:false, hidden:false,
    selectedOptions:[{textContent:'Matriz'}], dataset:{}, children:[], textContent:'',
    addEventListener(){}, append(...nos){this.children.push(...nos);},
    replaceChildren(...nos){this.children=nos;}, focus(){}, click(){}};
}
for(const id of ['tipo','empresa','competencia','pasta','mesma-pasta'])elementos.set(id,elemento());
elementos.get('tipo').value='nfe';
const eventos = new Map(), timers = new Map(), chamadas = [];
let proximoTimer=0;
let retorno={ativo:false,parando:false,status:'Pronto',resultados:[],pergunta:null,lote:null};
const contexto = vm.createContext({
  document:{documentElement:{dataset:{}},getElementById(id){if(!elementos.has(id))elementos.set(id,elemento());return elementos.get(id);},
    querySelector(){return elemento();},querySelectorAll(){return [];},createElement:elemento,createDocumentFragment:elemento},
  localStorage:{getItem(){return null;},setItem(){}},matchMedia(){return {matches:false,addEventListener(){}};},
  crypto:{randomUUID(){return 'pagina-teste';}},
  window:{addEventListener(nome,acao){eventos.set(nome,acao);}},
  setTimeout(fn,tempo){const id=++proximoTimer;timers.set(id,{fn,tempo});return id;},
  clearTimeout(id){timers.delete(id);},AbortController,
  fetch:async(caminho,opcoes)=>{
    chamadas.push(caminho);
    if(caminho==='/api/presenca')return new Promise(()=>{});
    return {ok:true,json:async()=>structuredClone(retorno)};
  },console,
});
async function esvaziar(){for(let i=0;i<8;i++)await Promise.resolve();}
async function testar(){
  vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../src/cofre.js'),'utf8'),contexto);
  await esvaziar();
  assert.equal(chamadas.filter(c=>c==='/api/estado').length,1);
  assert.equal(timers.size,0,'Tela ociosa não deve agendar consultas.');
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
  eventos.get('pagehide')();
  const quantidadeAntes=chamadas.length;
  await vm.runInContext('atualizar()',contexto);
  assert.equal(chamadas.length,quantidadeAntes,'Aba saindo não deve iniciar novas consultas.');
  console.log('OK: ociosidade, execução, finalização, confirmação de saída e preservação do DOM.');
}
testar().catch(erro=>{console.error(erro);process.exitCode=1;});
