'use strict';
(() => {
  const cenario = document.getElementById('cenario');
  const preparar = document.getElementById('preparar-cenario');
  const ajuda = document.getElementById('ajuda-cenario');
  const notas = document.getElementById('notas');
  let simularReconexao = false, falhasLeitura = 0;
  const original = window.fetch.bind(window);
  window.fetch = async (url, opcoes) => {
    if (simularReconexao && url === '/api/iniciar') {
      simularReconexao = false;
      const resposta = await original(url, opcoes);
      if (!resposta.ok) return resposta;
      falhasLeitura = 2;
      throw new TypeError('SIMULAÇÃO · Resposta de início perdida.');
    }
    if (url === '/api/estado' && falhasLeitura > 0) {
      falhasLeitura--;
      throw new TypeError('SIMULAÇÃO · Leitura temporariamente indisponível.');
    }
    return original(url, opcoes);
  };
  function descrever() { ajuda.textContent = cenario.selectedOptions[0].dataset.ajuda; }
  cenario.addEventListener('change', descrever);
  preparar.addEventListener('click', () => {
    if (notas.matches(':disabled')) {
      ajuda.textContent = 'Conclua ou pare a execução atual antes de preparar outro cenário.';
      return;
    }
    notas.value = cenario.selectedOptions[0].dataset.notas;
    notas.dispatchEvent(new Event('input', {bubbles:true}));
    simularReconexao = cenario.selectedOptions[0].textContent === 'Perda de resposta / reconexão';
    falhasLeitura = 0;
    descrever();
    notas.focus();
  });
  descrever();
})();
