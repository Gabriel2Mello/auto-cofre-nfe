'use strict';
const el=id=>document.getElementById(id);
const token=document.querySelector('meta[name="cofre-token"]').content;
const headers={Authorization:'Bearer '+token,'Content-Type':'application/json','X-Cofre-Pagina':crypto.randomUUID()};
let estado=null, encerrado=false, saindo=false, presenca=null, ciclo=0, timer=null, assinatura='', perguntaId='';

function temaAtual(){return document.documentElement.dataset.tema||(matchMedia('(prefers-color-scheme:dark)').matches?'escuro':'claro');}
function rotuloTema(){el('tema').textContent=temaAtual()==='escuro'?'Tema claro':'Tema escuro';}
try{const tema=localStorage.getItem('cofre-tema');if(['claro','escuro'].includes(tema))document.documentElement.dataset.tema=tema;}catch{}
rotuloTema();
el('tema').onclick=()=>{const tema=temaAtual()==='escuro'?'claro':'escuro';document.documentElement.dataset.tema=tema;try{localStorage.setItem('cofre-tema',tema);}catch{}rotuloTema();};
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',rotuloTema);

async function api(caminho,dados){
  const r=await fetch(caminho,{method:dados===undefined?'GET':'POST',headers,body:dados===undefined?undefined:JSON.stringify(dados)});
  const retorno=await r.json();if(!r.ok)throw Error(retorno.erro||'Não foi possível concluir a ação.');return retorno;
}
function destino(){
  el('campo-pasta').hidden=el('mesma-pasta').checked;
  el('pasta').required=!el('mesma-pasta').checked;
  const mes=el('mesma-pasta').checked?el('competencia').value:el('pasta').value;
  const tipo=el('tipo').value==='nfe'?'NF-e':'CT-e';
  const data=mes?mes.slice(5)+'/'+mes.slice(0,4):'selecione a competência';
  el('destino').textContent=`PDF ${tipo} e XML - ${tipo} · ${el('empresa').selectedOptions[0].textContent} · ${data}`;
}
for(const id of ['tipo','empresa','competencia','pasta','mesma-pasta'])el(id).addEventListener('change',destino);
destino();

function texto(tag,valor,classe=''){const no=document.createElement(tag);no.textContent=valor;if(classe)no.className=classe;return no;}
function renderizar(dados){
  estado=dados;const chave=JSON.stringify(dados);if(chave===assinatura)return;assinatura=chave;
  el('campos').disabled=dados.ativo;el('iniciar').disabled=dados.ativo;
  el('parar').hidden=!dados.ativo;el('parar').disabled=dados.parando;
  el('fase').textContent=dados.parando?'Parando':dados.pergunta?'Sua conferência':dados.ativo?'Processando':dados.resultados.length?'Finalizado':'Aguardando';
  el('status').textContent=dados.status;
  const feitos=dados.resultados.filter(r=>r.situacao==='Concluído').length;
  const pendentes=dados.resultados.filter(r=>['Aguardando','Processando','Não processado'].includes(r.situacao)).length;
  const erros=dados.resultados.length-feitos-pendentes;
  el('concluidos').textContent=feitos;el('pendentes').textContent=pendentes;el('erros').textContent=erros;
  el('progresso').max=Math.max(1,dados.resultados.length);
  el('progresso').value=dados.resultados.filter(r=>!['Aguardando','Processando'].includes(r.situacao)).length;
  if(dados.lote){const l=dados.lote;el('lote').textContent=`${l.tipo==='nfe'?'NF-e':'CT-e'} · ${l.empresa==='MATRIZ'?'Matriz':'Filial'} · documentos ${l.competencia.slice(5)}/${l.competencia.slice(0,4)} · pasta ${l.pasta.slice(5)}/${l.pasta.slice(0,4)}`;}
  el('exportar').disabled=dados.ativo||!dados.resultados.length;
  const fragmento=document.createDocumentFragment();
  for(const r of dados.resultados){const tr=document.createElement('tr');const td=document.createElement('td');const classe=r.situacao==='Erro'?' erro':['Conferir sinalização','Não processado'].includes(r.situacao)?' atencao':'';td.append(texto('span',r.situacao,'situacao'+classe));tr.append(texto('td',r.nota),td,texto('td',r.detalhe||'Aguardando processamento.'));fragmento.append(tr);}
  if(dados.resultados.length)el('linhas').replaceChildren(fragmento);
  renderizarPergunta(dados.pergunta);
}
function renderizarPergunta(p){
  el('decisao').hidden=!p;
  if(!p){perguntaId='';return;}if(p.id===perguntaId)return;perguntaId=p.id;
  el('erro-decisao').textContent='';el('responder').disabled=false;el('opcoes').replaceChildren();
  el('campo-nome').hidden=p.tipo!=='nome';el('nome').required=p.tipo==='nome';
  el('titulo-decisao').textContent=p.tipo==='nome'?'Como salvar os arquivos deste emitente?':'Qual emitente corresponde ao documento?';
  el('ajuda-decisao').textContent=p.tipo==='nome'?`Emitente novo: ${p.emitente}`:'Há mais de um resultado para este número e competência. Selecione o documento correto.';
  if(p.tipo==='nome'){el('nome').value=p.sugestao;el('nome').focus();}
  else{p.opcoes.forEach((opcao,i)=>{const label=document.createElement('label');label.className='escolha';const radio=document.createElement('input');radio.type='radio';radio.name='emitente';radio.value=String(i);radio.required=true;const conteudo=document.createElement('span');conteudo.append(texto('strong',opcao.nome),texto('small',`${opcao.data} · ${opcao.valor}`));label.append(radio,conteudo);el('opcoes').append(label);});el('titulo-decisao').focus();}
}
async function atualizar(){
  clearTimeout(timer);if(encerrado||saindo)return;const atual=++ciclo;
  // Uma consulta inicial; novas consultas são agendadas somente enquanto há execução.
  try{const dados=await api('/api/estado');if(atual!==ciclo||encerrado||saindo)return;el('conexao').hidden=true;renderizar(dados);if(dados.ativo)timer=setTimeout(atualizar,800);}
  catch{if(atual!==ciclo||encerrado||saindo)return;el('conexao').hidden=false;el('conexao').textContent='A conexão com o programa foi interrompida. Confira o andamento antes de reenviar os documentos.';el('iniciar').disabled=true;if(estado?.ativo)timer=setTimeout(atualizar,1500);}
}
async function acao(caminho,dados={}){el('mensagem').textContent='';try{await api(caminho,dados);await atualizar();}catch(e){el('mensagem').textContent=e.message;}}
el('formulario').onsubmit=async e=>{e.preventDefault();el('iniciar').disabled=true;await acao('/api/iniciar',{notas:el('notas').value,empresa:el('empresa').value,tipo:el('tipo').value,competencia:el('competencia').value,pasta:el('mesma-pasta').checked?el('competencia').value:el('pasta').value});el('iniciar').disabled=Boolean(estado?.ativo)||!estado;};
el('parar').onclick=()=>acao('/api/parar');el('cancelar-decisao').onclick=()=>acao('/api/parar');
el('form-decisao').onsubmit=async e=>{e.preventDefault();if(!estado?.pergunta)return;const p=estado.pergunta;const valor=p.tipo==='nome'?el('nome').value:document.querySelector('input[name="emitente"]:checked')?.value;if(valor===undefined)return;el('responder').disabled=true;try{await api('/api/responder',{id:p.id,valor});await atualizar();}catch(erro){el('erro-decisao').textContent=erro.message;}finally{el('responder').disabled=false;}};
el('exportar').onclick=()=>{if(!estado)return;const blob=new Blob([JSON.stringify({exportado_em:new Date().toISOString(),...estado},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='resultado-cofre.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
el('encerrar').onclick=async()=>{if(!confirm('Deseja realmente encerrar o Cofre NF-e? Se houver processamento, a operação em curso será concluída antes da parada.'))return;try{await api('/api/fechar',{});encerrado=true;clearTimeout(timer);presenca?.abort();document.querySelectorAll('button,input,select,textarea').forEach(no=>no.disabled=true);el('status').textContent='Encerrando a aplicação. Você pode fechar esta aba.';el('decisao').hidden=true;}catch(e){el('mensagem').textContent=e.message;}};

async function acompanhar(){
  if(encerrado||saindo)return;presenca=new AbortController();
  try{const r=await fetch('/api/presenca',{headers,signal:presenca.signal});if(!r.ok)return;const leitor=r.body.getReader();while(!encerrado&&!saindo){if((await leitor.read()).done)break;}}
  catch{}finally{if(!encerrado&&!saindo)setTimeout(acompanhar,1500);}
}
window.addEventListener('beforeunload',e=>{if(!encerrado){e.preventDefault();e.returnValue='';}});
window.addEventListener('pagehide',()=>{saindo=true;clearTimeout(timer);presenca?.abort();});
window.addEventListener('pageshow',e=>{if(e.persisted){saindo=false;acompanhar();atualizar();}});
acompanhar();atualizar();
