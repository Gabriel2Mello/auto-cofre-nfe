"""Publicação sem sobrescrita e recuperação local do conjunto fiscal."""

from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from src.config import Config
from src.enums import Empresa, TipoDocumento
from src.validacao_documentos import DocumentoInvalido, validar_pdf, validar_xml


from src.caminhos import pasta_dados

RAIZ_PROJETO = pasta_dados()


@dataclass(frozen=True)
class ContextoGravacao:
  emitente: str
  nota: str
  empresa: Empresa
  mes: int
  ano: str
  tipo: TipoDocumento
  cnpj_empresa: str
  mes_nota: int
  ano_nota: int

  def __post_init__(self):
    if (not isinstance(self.emitente, str) or not self.emitente.strip()
        or any(c in self.emitente for c in '\\/*?:"<>|\x00')
        or self.emitente in ('.', '..') or self.emitente.endswith(('.', ' '))):
      raise ValueError('Nome de emitente inadequado para gravar arquivos.')
    if (not isinstance(self.nota, str) or not self.nota.isascii()
        or not self.nota.isdigit() or len(self.nota) > 9 or int(self.nota) == 0):
      raise ValueError('Número de documento inválido.')
    if not isinstance(self.ano, str) or len(self.ano) != 4 or not self.ano.isascii() or not self.ano.isdigit():
      raise ValueError('Ano da pasta inválido.')
    if not isinstance(self.empresa, Empresa) or not isinstance(self.tipo, TipoDocumento):
      raise ValueError('Empresa ou tipo inválido.')
    if any(type(n) is not int for n in (self.mes, self.mes_nota, self.ano_nota)) or not isinstance(self.cnpj_empresa, str):
      raise ValueError('Contexto fiscal inválido.')
    date(int(self.ano), self.mes, 1)
    date(self.ano_nota, self.mes_nota, 1)


class GravacaoPendente(RuntimeError):
  def __init__(self, identificador: str):
    self.identificador = identificador
    super().__init__(f'Gravação pendente: {identificador}. Preserve os arquivos e confira a recuperação antes de repetir a baixa.')


def _base(caminho: str | Path) -> Path:
  base = Path(caminho).resolve()
  if not base.is_dir():
    raise ValueError('A pasta de documentos está indisponível.')
  return base


def _seguro(base: Path, caminho: Path) -> Path:
  resolvido = caminho.resolve()
  if not resolvido.is_relative_to(base):
    raise ValueError('Caminho de gravação fora da pasta permitida.')
  return resolvido


def _destinos(base: Path, contexto: ContextoGravacao, nome: str) -> dict[str, Path]:
  tipo = 'NF-e' if contexto.tipo == TipoDocumento.NFE else 'CT-e'
  xml = base / f'XML - {tipo}' / contexto.ano / contexto.empresa / Config.MONTHS[contexto.mes]
  pdf = base / f'PDF {tipo}' / contexto.ano / contexto.empresa / Config.MONTHS[contexto.mes]
  destinos = {'pdf': pdf / f'{nome}.pdf', 'xml': xml / f'{nome}.xml'}
  if contexto.tipo == TipoDocumento.CTE:
    destinos['copia'] = xml / f'{nome} copia.xml'
  return {papel: _seguro(base, caminho) for papel, caminho in destinos.items()}


def _temporarios(destinos: dict[str, Path], identificador: str) -> dict[str, Path]:
  return {papel: caminho.with_name(f'.cofre-{identificador}-{papel}.tmp') for papel, caminho in destinos.items()}


def _validar_par(xml: bytes, pdf: bytes, contexto: ContextoGravacao) -> str:
  chave = validar_xml(xml, contexto.tipo)
  validar_pdf(pdf)
  return chave


def _gravar_bytes(caminho: Path, conteudo: bytes) -> None:
  with caminho.open('xb') as arquivo:
    arquivo.write(conteudo)
    arquivo.flush()
    os.fsync(arquivo.fileno())
  if caminho.read_bytes() != conteudo:
    raise OSError('A conferência do arquivo preparado falhou.')


def _salvar_registro(pasta: Path, registro: dict) -> None:
  if not pasta.exists():
    _iniciar_registro(pasta, registro)
    return
  temporario = pasta / f'manifesto-{uuid4().hex}.tmp'
  _gravar_bytes(temporario, json.dumps(registro, ensure_ascii=False, indent=2).encode('utf-8'))
  temporario.replace(pasta / 'manifesto.json')


def _iniciar_registro(pasta: Path, registro: dict) -> None:
  # A listagem só vê registros publicados. Uma interrupção nesta área nunca
  # pode ter publicado documentos, pois a preparação fiscal começa depois.
  preparacao = _seguro(RAIZ_PROJETO.resolve(),
    pasta.parent.parent / '.iniciando' / pasta.parent.name / f'{pasta.name}-{uuid4().hex}')
  preparacao.mkdir(parents=True)
  _salvar_registro(preparacao, registro)
  pasta.parent.mkdir(parents=True, exist_ok=True)
  preparacao.rename(pasta)


def _id(identificador: str) -> None:
  if len(identificador) != 32 or any(c not in '0123456789abcdef' for c in identificador):
    raise ValueError('Identificador de gravação inválido.')


def _pasta_registros(base: Path) -> Path:
  # Separa destinos fiscais sem depender da pasta de trabalho do iniciador.
  raiz = RAIZ_PROJETO.resolve()
  destino = sha256(os.path.normcase(str(base)).encode('utf-8')).hexdigest()
  return _seguro(raiz, raiz / '.cofre-gravacoes' / destino)


def _pasta_registro(base: Path, identificador: str) -> Path:
  _id(identificador)
  pasta = _pasta_registros(base)
  return _seguro(pasta, pasta / identificador)


def _carregar(base: Path, identificador: str, *, registros: Path | None = None) -> tuple[dict, ContextoGravacao]:
  if registros is None:
    pasta = _pasta_registro(base, identificador)
  else:
    _id(identificador)
    pasta = _seguro(registros, registros / identificador)
  try:
    if not pasta.exists():
      # Compatibilidade somente de leitura com registros anteriores no OneDrive.
      pasta = _seguro(base, base / '.cofre-gravacoes' / identificador)
    registro = json.loads(_seguro(pasta, pasta / 'manifesto.json').read_text(encoding='utf-8'))
    if (not isinstance(registro, dict) or registro.get('versao') != 1 or registro.get('id') != identificador
        or registro.get('estado') not in ('preparando', 'pronto', 'concluido', 'abandonado')
        or not isinstance(registro.get('contexto'), dict)):
      raise ValueError('Estrutura inválida.')
    dados = dict(registro['contexto'])
    dados['empresa'], dados['tipo'] = Empresa(dados['empresa']), TipoDocumento(dados['tipo'])
    contexto = ContextoGravacao(**dados)
    chave = registro['chave']
    if not isinstance(chave, str) or len(chave) != 44 or not chave.isascii() or not chave.isdigit():
      raise ValueError('Chave inválida.')
    nome_base = f'{contexto.emitente} {contexto.nota}'
    if registro['nome'] not in (nome_base, f'{nome_base} - {chave}'):
      raise ValueError('Nome de destino inválido.')
    destinos = _destinos(base, contexto, registro['nome'])
    hashes = registro['sha256']
    if (not isinstance(hashes, dict) or set(hashes) != set(destinos)
        or any(not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h) for h in hashes.values())):
      raise ValueError('Hashes inválidos.')
    return registro, contexto
  except (OSError, ValueError, TypeError, KeyError) as erro:
    raise ValueError(f'Registro de gravação inválido ou indisponível: {identificador}. Preserve-o para conferência.') from erro


def listar_gravacoes(caminho: str | Path) -> list[dict]:
  base = _base(caminho)
  pastas = (_pasta_registros(base), _seguro(base, base / '.cofre-gravacoes'))
  identificadores = set()
  for pasta in pastas:
    if pasta.exists():
      identificadores.update(entrada.name for entrada in pasta.iterdir() if entrada.is_dir())
  resultados = []
  for identificador in sorted(identificadores):
    try:
      # A raiz é a mesma nesta consulta. Cada registro e seus destinos continuam
      # sendo resolvidos e validados; nenhuma leitura persiste entre consultas.
      registro, contexto = _carregar(base, identificador, registros=pastas[0])
      resultados.append({'id': identificador, 'estado': registro['estado'], 'nome': registro['nome'],
                         'empresa': str(contexto.empresa), 'tipo': str(contexto.tipo)})
    except ValueError as erro:
      resultados.append({'id': identificador, 'estado': 'invalido', 'detalhe': str(erro)})
  return resultados


def _promover(temporario: Path, destino: Path) -> None:
  # rename não substitui destinos no Windows; link é exclusivo no POSIX.
  if os.name == 'nt':
    os.rename(temporario, destino)
  else:
    os.link(temporario, destino)
    temporario.unlink()


def _concluir(base: Path, registro: dict, contexto: ContextoGravacao) -> str:
  identificador = registro['id']
  if registro['estado'] == 'abandonado':
    raise ValueError('Esta preparação foi abandonada e não pode ser promovida.')
  destinos = _destinos(base, contexto, registro['nome'])
  temporarios = _temporarios(destinos, identificador)
  conteudos = {}
  for papel, destino in destinos.items():
    origem = destino if destino.exists() else temporarios[papel]
    conteudo = origem.read_bytes()
    if sha256(conteudo).hexdigest() != registro['sha256'][papel]:
      raise ValueError('Arquivo incompleto, alterado ou destino ocupado por outro conteúdo. Nenhum arquivo será substituído.')
    conteudos[papel] = conteudo
  if _validar_par(conteudos['xml'], conteudos['pdf'], contexto) != registro['chave']:
    raise ValueError('Identidade fiscal da pendência diverge do registro.')
  if 'copia' in conteudos and conteudos['copia'] != conteudos['xml']:
    raise ValueError('A cópia XML de CT-e diverge do original.')
  pasta = _pasta_registro(base, identificador)
  if registro['estado'] == 'preparando':
    registro['estado'] = 'pronto'
    _salvar_registro(pasta, registro)
  for papel, destino in destinos.items():
    if not destino.exists():
      try:
        _promover(temporarios[papel], destino)
      except FileExistsError:
        # Outro escritor pode ter publicado entre a verificação e o rename/link.
        if sha256(destino.read_bytes()).hexdigest() != registro['sha256'][papel]:
          raise ValueError('Destino criado por outra gravação. Conteúdo preservado.')
    if sha256(destino.read_bytes()).hexdigest() != registro['sha256'][papel]:
      raise ValueError('O arquivo publicado não corresponde ao preparado.')
  if any(sha256(destino.read_bytes()).hexdigest() != registro['sha256'][papel]
         for papel, destino in destinos.items()):
    raise ValueError('O conjunto publicado foi alterado durante a conferência final.')
  if registro['estado'] != 'concluido':
    registro['estado'] = 'concluido'
    _salvar_registro(pasta, registro)
  return registro['nome']


def recuperar_gravacao(caminho: str | Path, identificador: str) -> str:
  base = _base(caminho)
  registro, contexto = _carregar(base, identificador)
  try:
    return _concluir(base, registro, contexto)
  except (OSError, ValueError) as erro:
    raise GravacaoPendente(identificador) from erro


def abandonar_preparacao(caminho: str | Path, identificador: str) -> None:
  base = _base(caminho)
  registro, contexto = _carregar(base, identificador)
  if registro['estado'] not in ('preparando', 'pronto') or any(p.exists() for p in _destinos(base, contexto, registro['nome']).values()):
    raise ValueError('Só é possível abandonar uma preparação sem arquivos publicados. Use recuperação para conjuntos parciais.')
  registro['estado'] = 'abandonado'
  _salvar_registro(_pasta_registro(base, identificador), registro)


def _existente_valido(destinos: dict[str, Path], contexto: ContextoGravacao, chave: str) -> bool:
  if not all(p.is_file() for p in destinos.values()):
    return False
  try:
    xml = destinos['xml'].read_bytes()
    if _validar_par(xml, destinos['pdf'].read_bytes(), contexto) != chave:
      return False
    return 'copia' not in destinos or destinos['copia'].read_bytes() == xml
  except DocumentoInvalido:
    return False


def gravar_conjunto(xml: bytes, pdf: bytes, contexto: ContextoGravacao, caminho: str | Path) -> str:
  chave = _validar_par(xml, pdf, contexto)
  base = _base(caminho)
  for resumo in listar_gravacoes(base):
    if resumo['estado'] == 'invalido':
      raise ValueError(resumo['detalhe'])
    if resumo['estado'] not in ('concluido', 'abandonado'):
      pendencia, anterior = _carregar(base, resumo['id'])
      if (pendencia['chave'], anterior.empresa, anterior.tipo, anterior.ano, anterior.mes) == (chave, contexto.empresa, contexto.tipo, contexto.ano, contexto.mes):
        raise GravacaoPendente(resumo['id'])
  nome = f'{contexto.emitente} {contexto.nota}'
  destinos = _destinos(base, contexto, nome)
  if any(p.exists() for p in destinos.values()):
    if _existente_valido(destinos, contexto, chave):
      return nome
    nome += f' - {chave}'
    destinos = _destinos(base, contexto, nome)
    if any(p.exists() for p in destinos.values()):
      if _existente_valido(destinos, contexto, chave):
        return nome
      raise ValueError('Já existe destino com a chave fiscal, mas o conjunto está incompleto ou divergente. Confira a recuperação; os arquivos não foram substituídos.')
  identificador = uuid4().hex
  conteudos = {'pdf': pdf, 'xml': xml}
  if contexto.tipo == TipoDocumento.CTE:
    conteudos['copia'] = xml
  registro = {'versao': 1, 'id': identificador, 'contexto': asdict(contexto), 'chave': chave, 'nome': nome,
              'estado': 'preparando', 'sha256': {papel: sha256(conteudo).hexdigest() for papel, conteudo in conteudos.items()}}
  try:
    _iniciar_registro(_pasta_registro(base, identificador), registro)
  except (OSError, ValueError) as erro:
    raise RuntimeError('Não foi possível iniciar o registro de gravação. Nenhum documento foi publicado. '
                       'Confira o armazenamento local antes de tentar novamente; '
                       f'preparação {identificador} preservada quando disponível.') from erro
  try:
    for papel, temporario in _temporarios(destinos, identificador).items():
      temporario.parent.mkdir(parents=True, exist_ok=True)
      _gravar_bytes(temporario, conteudos[papel])
    return _concluir(base, registro, contexto)
  except (OSError, ValueError) as erro:
    raise GravacaoPendente(identificador) from erro
