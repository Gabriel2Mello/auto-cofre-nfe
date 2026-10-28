'use strict';
const el=id=>document.getElementById(id);
const token=document.querySelector('meta[name="cofre-token"]').content;
const headers={Authorization:'Bearer '+token,'Content-Type':'application/json','X-Cofre-Pagina':crypto.randomUUID()};
let estado=null, encerrado=false, saindo=false, presenca=null, ciclo=0, timer=null, assinatura='', perguntaId='';
let enviando=false, confirmacaoPendente=true, configurandoPasta=false, abrindoPasta=false;
const desktop=document.querySelector('meta[name="cofre-desktop"]')?.content==='1';
const selecionado=id=>document.querySelector(`#${id} input:checked`).value;
el('escolher-pasta').hidden=!desktop;
el('escolher-emitentes').hidden=!desktop;
for(const id of ['abrir-emitentes','editar-emitentes'])el(id).hidden=!desktop;
el('abrir-pasta').hidden=!desktop;

const tema=window.NunesTema.iniciar({controle:el('tema'),chave:'cofre-tema',cookie:!desktop});
el('tema').addEventListener('click',()=>{document.documentElement.dataset.temaAnimado='1';});
if(desktop){
  tema.aplicar(document.querySelector('meta[name="cofre-tema"]').content);
  el('tema').addEventListener('click',async()=>{
    try{await api('/api/tema',{tema:document.documentElement.dataset.tema});}
    catch(e){el('mensagem').textContent=e.message;}
  });
}
async function api(caminho,dados){
  const r=await fetch(caminho,{method:dados===undefined?'GET':'POST',headers,body:dados===undefined?undefined:JSON.stringify(dados)});
  const retorno=await r.json();if(!r.ok)throw Error(retorno.erro||'Não foi possível concluir a ação.');return retorno;
}
function destino(){
  el('pasta').disabled=el('mesma-pasta').checked;
  el('pasta').required=!el('mesma-pasta').checked;
  if(el('mesma-pasta').checked)el('pasta').value=el('competencia').value;
}
for(const id of ['tipo','empresa','competencia','pasta','mesma-pasta'])el(id).addEventListener('change',destino);
destino();

function texto(tag,valor,classe=''){const no=document.createElement(tag);no.textContent=valor;if(classe)no.className=classe;return no;}
function renderizar(dados){
  estado=dados;
  // Controles também precisam voltar quando a leitura recuperada é igual à anterior.
  el('campos').disabled=dados.ativo||dados.encerrando||dados.configurando||configurandoPasta||enviando||confirmacaoPendente;
  el('iniciar').disabled=el('campos').disabled;
  el('limpar-notas').disabled=el('campos').disabled;
  el('escolher-pasta').disabled=el('campos').disabled||!desktop;
  el('escolher-emitentes').disabled=el('escolher-pasta').disabled;
  for(const id of ['abrir-emitentes','editar-emitentes'])el(id).disabled=el('escolher-emitentes').disabled;
  el('abrir-pasta').disabled=!desktop||dados.encerrando||dados.configurando||configurandoPasta||abrindoPasta||confirmacaoPendente;
  const chave=JSON.stringify(dados);if(chave===assinatura)return;assinatura=chave;
  el('parar').hidden=!dados.ativo;el('parar').disabled=dados.parando;
  el('fase').textContent=dados.encerrando?'Encerrando':dados.parando?'Parando':dados.pergunta?'Sua conferência':dados.ativo?'Processando':dados.resultados.length?'Finalizado':'Aguardando';
  el('status').textContent=dados.encerrando?'Encerrando. Aguarde a conclusão da operação atual…':dados.status==='Pronto para baixar os documentos.'?'Pronto':dados.status;
  const feitos=dados.resultados.filter(r=>r.situacao==='Concluído').length;
  const pendentes=dados.resultados.filter(r=>['Aguardando','Processando','Não processado'].includes(r.situacao)).length;
  const erros=dados.resultados.length-feitos-pendentes;
  el('concluidos').textContent=feitos;el('pendentes').textContent=pendentes;el('erros').textContent=erros;
  el('resumo').hidden=!dados.resultados.length;
  el('progresso').max=Math.max(1,dados.resultados.length);
  el('progresso').value=dados.resultados.filter(r=>!['Aguardando','Processando'].includes(r.situacao)).length;
  el('lote').hidden=!dados.lote;
  if(dados.lote){const l=dados.lote;el('lote').textContent=`${l.tipo==='nfe'?'NF-e':'CT-e'} · ${l.empresa==='MATRIZ'?'Matriz':'Filial'} · documentos ${l.competencia.slice(5)}/${l.competencia.slice(0,4)} · pasta ${l.pasta.slice(5)}/${l.pasta.slice(0,4)}`;}
  const fragmento=document.createDocumentFragment();
  for(const r of dados.resultados){
    const item=document.createElement('li');item.className='resultado-nota';
    const classe=r.situacao==='Concluído'?' concluido':r.situacao==='Erro'?' erro':['Conferir sinalização','Não processado'].includes(r.situacao)?' atencao':'';
    const detalhe=r.situacao==='Concluído'?(r.detalhe||'').replace(/^XML e PDF salvos · /,''):r.detalhe;
    const linha=texto('p','','detalhe-nota');
    linha.append(texto('strong',r.nota),document.createTextNode(' · '+(detalhe||'Aguardando processamento.')));
    item.append(texto('span',r.situacao,'situacao'+classe),linha);fragmento.append(item);
  }
  if(dados.resultados.length)el('linhas').replaceChildren(fragmento);else el('linhas').replaceChildren(texto('li','O resultado das notas aparecerá aqui.','vazio'));
  renderizarPergunta(dados.pergunta);
}
function renderizarPergunta(p){
  el('decisao').hidden=!p;
  if(!p){perguntaId='';return;}if(p.id===perguntaId)return;perguntaId=p.id;
  el('erro-decisao').textContent='';el('responder').disabled=false;el('opcoes').replaceChildren();
  el('campo-nome').hidden=p.tipo!=='nome';el('nome').required=p.tipo==='nome';
  el('titulo-decisao').textContent=p.tipo==='nome'?'Apelido':'Qual emitente corresponde ao documento?';
  el('titulo-decisao').className=p.tipo==='nome'?'sr-only':'';
  el('ajuda-decisao').textContent=p.tipo==='nome'?`Emitente novo: ${p.emitente}`:'Há mais de um resultado para este número e competência. Selecione o documento correto.';
  if(p.tipo==='nome'){el('nome').value=p.sugestao;el('nome').focus();}
  else{p.opcoes.forEach((opcao,i)=>{const label=document.createElement('label');label.className='escolha';const radio=document.createElement('input');radio.type='radio';radio.name='emitente';radio.value=String(i);radio.required=true;const conteudo=document.createElement('span');conteudo.append(texto('strong',opcao.nome),texto('small',`${opcao.data} · ${opcao.valor}`));label.append(radio,conteudo);el('opcoes').append(label);});el('titulo-decisao').focus();}
  el('decisao').scrollIntoView({block:'nearest'});
}
async function atualizar(){
  clearTimeout(timer);if(encerrado||saindo)return;const atual=++ciclo;
  // Ociosidade confirmada não consulta periodicamente. Uma falha conserva a
  // necessidade de confirmação, inclusive antes de observar o lote aceito.
  try{const dados=await api('/api/estado');if(atual!==ciclo||encerrado||saindo)return;confirmacaoPendente=false;el('conexao').hidden=true;renderizar(dados);if(dados.ativo||dados.configurando)timer=setTimeout(atualizar,800);}
  catch{if(atual!==ciclo||encerrado||saindo)return;confirmacaoPendente=true;assinatura='';el('fase').textContent='Reconectando';el('status').textContent='Aguardando confirmação do andamento…';el('conexao').hidden=false;el('conexao').textContent='Sem confirmação do andamento. Reconectando para conferir o lote; não reenvie os documentos.';el('campos').disabled=true;el('iniciar').disabled=true;el('escolher-pasta').disabled=true;el('escolher-emitentes').disabled=true;el('abrir-emitentes').disabled=true;el('editar-emitentes').disabled=true;el('abrir-pasta').disabled=true;timer=setTimeout(atualizar,1500);}
}
async function acao(caminho,dados={}){el('mensagem').textContent='';try{await api(caminho,dados);await atualizar();}catch(e){el('mensagem').textContent=e.message;}}
const notasPermitidas=valor=>/^[0-9,; \t\r\n]*$/.test(valor);
let ultimasNotasValidas=el('notas').value;
el('notas').addEventListener('beforeinput',e=>{
  if(notasPermitidas(el('notas').value))ultimasNotasValidas=el('notas').value;
  if(e.data&&!notasPermitidas(e.data))e.preventDefault();
});
el('notas').addEventListener('input',()=>{
  const campo=el('notas');
  if(notasPermitidas(campo.value))ultimasNotasValidas=campo.value;
  else campo.value=ultimasNotasValidas;
});
el('limpar-notas').onclick=()=>{
  if(el('campos').disabled||el('iniciar').disabled)return;
  el('notas').value='';ultimasNotasValidas='';
  el('notas').focus();
};
function atualizarDicaNotas(){
  el('dica-notas').textContent=el('enter-baixar').checked?'Separe por vírgula.':'Separe por vírgula ou linha.';
}
atualizarDicaNotas();
el('enter-baixar').addEventListener('change',async()=>{
  const controle=el('enter-baixar'), escolhido=controle.checked;
  controle.disabled=true;
  atualizarDicaNotas();
  try{await api('/api/entrada-notas',{enter_baixar:escolhido});}
  catch(e){controle.checked=!escolhido;atualizarDicaNotas();el('mensagem').textContent=e.message;}
  finally{controle.disabled=false;}
});
el('notas').addEventListener('keydown',e=>{
  if(e.key!=='Enter'||!el('enter-baixar').checked||e.shiftKey||e.ctrlKey||e.altKey||e.metaKey||e.isComposing)return;
  e.preventDefault();
  if(e.repeat||el('campos').disabled||el('iniciar').disabled||!el('notas').value.trim())return;
  el('formulario').requestSubmit(el('iniciar'));
});
el('formulario').onsubmit=async e=>{
  e.preventDefault();if(enviando||el('iniciar').disabled||estado?.ativo||estado?.encerrando)return;
  enviando=true;confirmacaoPendente=true;el('campos').disabled=true;el('iniciar').disabled=true;el('mensagem').textContent='';
  try{await api('/api/iniciar',{notas:el('notas').value,empresa:selecionado('empresa'),tipo:selecionado('tipo'),competencia:el('competencia').value,pasta:el('mesma-pasta').checked?el('competencia').value:el('pasta').value});}
  catch(e){el('mensagem').textContent=e.message;}
  finally{enviando=false;assinatura='';await atualizar();}
};
function informarPasta(mensagem){
  if(el('configuracoes').open)el('configuracao-status').textContent=mensagem;
}
el('escolher-pasta').onclick=async()=>{
  if(!desktop||el('escolher-pasta').disabled||configurandoPasta)return;
  configurandoPasta=true;el('escolher-pasta').disabled=true;el('escolher-emitentes').disabled=true;el('abrir-emitentes').disabled=true;el('editar-emitentes').disabled=true;el('abrir-pasta').disabled=true;el('campos').disabled=true;el('iniciar').disabled=true;
  informarPasta('Escolha a pasta no diálogo do Windows.');
  try{const r=await api('/api/pasta',{});if(r.alterado){el('pasta-base').textContent=r.pasta;informarPasta('Pasta salva. Será usada nas próximas execuções.');}else informarPasta('Escolha cancelada. A pasta anterior foi mantida.');}
  catch(e){informarPasta(e.message);}
  finally{configurandoPasta=false;await atualizar();}
};
el('escolher-emitentes').onclick=async()=>{
  if(!desktop||el('escolher-emitentes').disabled||configurandoPasta)return;
  configurandoPasta=true;el('escolher-pasta').disabled=true;el('escolher-emitentes').disabled=true;el('abrir-emitentes').disabled=true;el('editar-emitentes').disabled=true;el('abrir-pasta').disabled=true;el('campos').disabled=true;el('iniciar').disabled=true;
  informarPasta('Escolha o arquivo JSON de emitentes no diálogo do Windows.');
  try{const r=await api('/api/emitentes',{});if(r.alterado){el('arquivo-emitentes').textContent=r.arquivo;informarPasta('Arquivo salvo. Será usado e atualizado nas próximas execuções.');}else informarPasta('Escolha cancelada. O arquivo anterior foi mantido.');}
  catch(e){informarPasta(e.message);}
  finally{configurandoPasta=false;await atualizar();}
};
for(const acaoEmitentes of ['abrir','editar']){
  const botao=el(acaoEmitentes+'-emitentes');
  botao.onclick=async()=>{
    if(botao.disabled||!desktop)return;
    botao.disabled=true;
    try{await api('/api/emitentes/'+acaoEmitentes,{});informarPasta(acaoEmitentes==='editar'?'Arquivo aberto no Bloco de Notas. Salve as alterações antes de iniciar um lote.':'Pasta do arquivo aberta no Explorador de Arquivos.');}
    catch(e){informarPasta(e.message);}
    finally{await atualizar();}
  };
}
el('abrir-pasta').onclick=async()=>{
  if(!desktop||el('abrir-pasta').disabled||abrindoPasta)return;
  abrindoPasta=true;el('abrir-pasta').disabled=true;
  try{await api('/api/pasta/abrir',{});informarPasta('Pasta aberta no Explorador de Arquivos.');}
  catch(e){informarPasta(e.message);}
  finally{abrindoPasta=false;el('abrir-pasta').disabled=!desktop||Boolean(estado?.encerrando)||Boolean(estado?.configurando)||configurandoPasta||confirmacaoPendente;}
};
el('configuracoes').addEventListener('toggle',()=>{
  if(!el('configuracoes').open)el('configuracao-status').textContent='';
});
window.addEventListener('keydown',e=>{if(e.key==='Escape')el('configuracoes').open=false;});
function fecharConfiguracoesFora(e){
  const menu=el('configuracoes');
  if(menu.open&&!menu.contains(e.target))menu.open=false;
}
window.addEventListener('pointerdown',fecharConfiguracoesFora,true);
window.addEventListener('focusin',fecharConfiguracoesFora);
el('parar').onclick=()=>acao('/api/parar',{origem:'parar'});el('cancelar-decisao').onclick=()=>acao('/api/parar',{origem:'decisao'});
el('form-decisao').onsubmit=async e=>{e.preventDefault();if(!estado?.pergunta||el('responder').disabled)return;const p=estado.pergunta;const valor=p.tipo==='nome'?el('nome').value:document.querySelector('input[name="emitente"]:checked')?.value;if(valor===undefined)return;el('responder').disabled=true;try{await api('/api/responder',{id:p.id,valor});await atualizar();}catch(erro){el('erro-decisao').textContent=erro.message;}finally{el('responder').disabled=false;}};
el('encerrar').onclick=async()=>{if(estado?.encerrando||!confirm('Deseja realmente encerrar o Cofre NF-e? Se houver processamento, a operação em curso será concluída antes da parada.'))return;try{await api('/api/fechar',{});encerrado=true;clearTimeout(timer);presenca?.abort();document.querySelectorAll('button,input,select,textarea').forEach(no=>no.disabled=true);el('status').textContent=desktop?'Encerrando. Aguarde a operação atual; a janela fechará automaticamente.':'Encerrando a aplicação. Você pode fechar esta aba.';el('decisao').hidden=true;}catch(e){el('mensagem').textContent=e.message;}};

async function acompanhar(){
  if(encerrado||saindo)return;presenca=new AbortController();
  try{const r=await fetch('/api/presenca',{headers,signal:presenca.signal});if(!r.ok)return;const leitor=r.body.getReader();while(!encerrado&&!saindo){if((await leitor.read()).done)break;}}
  catch{}finally{if(!encerrado&&!saindo)setTimeout(acompanhar,1500);}
}
window.addEventListener('beforeunload',e=>{if(!desktop&&!encerrado){e.preventDefault();e.returnValue='';}});
window.addEventListener('pagehide',()=>{saindo=true;clearTimeout(timer);presenca?.abort();});
window.addEventListener('pageshow',e=>{if(e.persisted){saindo=false;acompanhar();atualizar();}});
acompanhar();atualizar();
