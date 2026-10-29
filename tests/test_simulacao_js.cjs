const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const eventos = new Map(), pedidos = [];
const opcao = {textContent:'Perda de resposta / reconexão',dataset:{notas:'1001',ajuda:'Recuperar sem reenviar.'}};
let bloqueado = false, autorizado = true, entradas = 0;
const notas = {value:'',matches(){return bloqueado;},dispatchEvent(){entradas++;},focus(){}};
const elementos = {
  cenario:{selectedOptions:[opcao],addEventListener(nome,acao){eventos.set('cenario:'+nome,acao);}},
  'preparar-cenario':{addEventListener(nome,acao){eventos.set('preparar:'+nome,acao);}},
  'ajuda-cenario':{textContent:''},notas,
};
const contexto = vm.createContext({
  document:{getElementById(id){return elementos[id];}},
  window:{fetch:async(url,opcoes)=>{pedidos.push({url,opcoes});return {ok:autorizado};}},
  Event:class{},TypeError,
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'simulacao.js'),'utf8'),contexto);

(async()=>{
  eventos.get('preparar:click')();
  assert.equal(notas.value,'1001');
  assert.equal(entradas,1);
  await assert.rejects(contexto.window.fetch('/api/iniciar',{method:'POST'}),/Resposta de início perdida/);
  await assert.rejects(contexto.window.fetch('/api/estado'),/Leitura temporariamente indisponível/);
  await assert.rejects(contexto.window.fetch('/api/estado'),/Leitura temporariamente indisponível/);
  assert.equal((await contexto.window.fetch('/api/estado')).ok,true);
  assert.deepEqual(pedidos.map(p=>p.url),['/api/iniciar','/api/estado']);
  assert.equal(pedidos.filter(p=>p.url==='/api/iniciar').length,1,'Perder a resposta não pode reenviar o início.');

  bloqueado = true;
  opcao.dataset.notas = '1004';
  eventos.get('preparar:click')();
  assert.equal(notas.value,'1001','Preparar outro cenário não pode alterar um lote ativo.');
  assert.match(elementos['ajuda-cenario'].textContent,/Conclua ou pare/);

  bloqueado = false;
  eventos.get('preparar:click')();
  autorizado = false;
  assert.equal((await contexto.window.fetch('/api/iniciar',{method:'POST'})).ok,false,'Uma recusa real deve ser preservada.');
  assert.equal((await contexto.window.fetch('/api/estado')).ok,false,'Uma recusa não deve armar falhas de leitura.');
  console.log('OK: preparação preserva lote ativo e reconexão perde respostas sem duplicar o início.');
})().catch(erro=>{console.error(erro);process.exitCode=1;});
