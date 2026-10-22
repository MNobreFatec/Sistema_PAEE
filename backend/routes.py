"""API local do PAEE. Usa arquivo JSON persistente, sem dados pré-carregados.
Para os testes locais, as rotas não exigem autenticação; não exponha este modo à internet.
"""
from pathlib import Path
from datetime import datetime, date
from json import JSONDecodeError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from backend import armazenamento_json as db
from backend.paee_service import validar_transicao_status, validar_designacao, validar_assinatura, validar_secao
from backend.seguranca import gerar_hash, verificar_senha

app = FastAPI(title='Sistema PAEE', version='1.1.0-json-local', description='Modo local com persistência JSON para testes')
now = lambda: datetime.now().isoformat(timespec='seconds')

def required(payload, *fields):
    missing=[f for f in fields if payload.get(f) is None or str(payload.get(f)).strip()=='']
    if missing: raise HTTPException(422, 'Preencha os campos obrigatórios: '+', '.join(missing))

def as_int(value, label):
    try:
        n=int(value)
        if n <= 0: raise ValueError()
        return n
    except (TypeError,ValueError): raise HTTPException(422, f'{label} deve ser um número positivo')

@app.get('/health')
def health(): return {'status':'ok','servico':'PAEE',**db.health()}
@app.get('/api/status')
def api_status(): return {'modo':'json-local','mensagem':'Dados persistidos em arquivo JSON; nenhuma informação demonstrativa é pré-carregada.','arquivo':db.health()['file']}
@app.get('/', include_in_schema=False)
def inicio(): return RedirectResponse('/frontend/paginas/login/tela_login.html')
@app.get('/favicon.ico', include_in_schema=False)
def favicon(): return RedirectResponse('/frontend/img/logo_fate.png')

def usuario_publico(usuario):
    return {k:v for k,v in usuario.items() if k not in {'senha','senha_hash'}}

@app.post('/usuario', status_code=201)
def criar_usuario(payload: dict):
    required(payload,'email','senha','nome','nivel_usuario')
    email=str(payload['email']).strip().lower()
    senha=str(payload['senha'])
    if len(senha) < 8 or len(senha.encode('utf-8')) > 72:
        raise HTTPException(422,'A senha deve ter entre 8 e 72 bytes')
    nivel=str(payload['nivel_usuario']).strip().upper()
    if nivel not in {'ALUNO','PROFESSOR','ASSISTENTE','COORDENADOR'}:
        raise HTTPException(422,'Perfil de usuário inválido')
    if db.get('usuarios','email',email): raise HTTPException(409,'Já existe um usuário com esse e-mail')
    row=db.create('usuarios',{'email':email,'senha_hash':gerar_hash(senha),'nome':str(payload['nome']).strip(),'nivel_usuario':nivel,'ativo':True,'criado_em':now()},'id_usuario')
    return usuario_publico(row)

@app.post('/login')
async def login(request: Request):
    content_type=request.headers.get('content-type','')
    if 'application/json' in content_type:
        try: payload=await request.json()
        except JSONDecodeError: raise HTTPException(400,'Corpo JSON inválido')
    elif 'application/x-www-form-urlencoded' in content_type or 'multipart/form-data' in content_type:
        payload=dict(await request.form())
    else:
        raise HTTPException(415,'Envie as credenciais como formulário ou JSON')
    if not isinstance(payload,dict): raise HTTPException(422,'Credenciais inválidas')
    email=str(payload.get('username') or payload.get('email') or '').strip().lower()
    senha=payload.get('password',payload.get('senha'))
    required({'email':email,'senha':senha},'email','senha')
    if not isinstance(senha,str) or len(senha.encode('utf-8')) > 72:
        raise HTTPException(401,'E-mail ou senha inválidos')
    user=db.get('usuarios','email',email)
    senha_valida=False
    if user and user.get('senha_hash'):
        senha_valida=verificar_senha(str(senha),user['senha_hash'])
    elif user and isinstance(user.get('senha'),str):
        senha_valida=user['senha']==senha
        if senha_valida:
            def atualizar_senha(data):
                for registro in data['usuarios']:
                    if registro.get('id_usuario')==user['id_usuario']:
                        registro['senha_hash']=gerar_hash(str(senha))
                        registro.pop('senha',None)
                        return registro
                return None
            user=db.mutate(atualizar_senha)
    if not user or not senha_valida: raise HTTPException(401,'E-mail ou senha inválidos')
    if not user.get('ativo',True): raise HTTPException(403,'Usuário inativo')
    return {'access_token':f'local-demo-{user["id_usuario"]}','token_type':'bearer','usuario':usuario_publico(user)}

@app.get('/api/alunos')
def listar_alunos(): return [usuario_publico(u) for u in db.all_rows('usuarios') if u.get('nivel_usuario')=='ALUNO']
@app.get('/api/professores')
def listar_professores(): return [usuario_publico(u) for u in db.all_rows('usuarios') if u.get('nivel_usuario')=='PROFESSOR']
@app.get('/api/assistentes')
def listar_assistentes(): return [usuario_publico(u) for u in db.all_rows('usuarios') if u.get('nivel_usuario')=='ASSISTENTE']
@app.get('/api/coordenadores')
def listar_coordenadores(): return [usuario_publico(u) for u in db.all_rows('usuarios') if u.get('nivel_usuario')=='COORDENADOR']

@app.post('/api/solicitacoes', status_code=201)
def criar_solicitacao(payload:dict):
    required(payload,'matricula','motivo'); matricula=as_int(payload['matricula'],'Matrícula')
    criado_em=now()
    row,form=db.create_many([
        ('solicitacoes',{'matricula':matricula,'motivo':str(payload['motivo']).strip(),'status':'ABERTA','criado_em':criado_em,'atualizado_em':criado_em},'id_solicitacao'),
        ('formularios',lambda created:{'id_solicitacao':created[0]['id_solicitacao'],'status':'RASCUNHO','secoes':{},'criado_em':criado_em,'assinaturas':[]},'id_formulario'),
    ])
    row['id_formulario']=form['id_formulario']; return row
@app.get('/api/solicitacoes')
def listar_solicitacoes(): return sorted(db.all_rows('solicitacoes'),key=lambda x:x['id_solicitacao'],reverse=True)
@app.get('/api/solicitacoes/{id_solicitacao}')
def obter_solicitacao(id_solicitacao:int):
    row=db.get('solicitacoes','id_solicitacao',id_solicitacao)
    if not row: raise HTTPException(404,'Solicitação não encontrada')
    form=next((f for f in db.all_rows('formularios') if f['id_solicitacao']==id_solicitacao),None)
    return {**row,'formulario':form}
@app.patch('/api/solicitacoes/{id_solicitacao}/status')
def atualizar_status(id_solicitacao:int,payload:dict):
    row=db.get('solicitacoes','id_solicitacao',id_solicitacao)
    if not row: raise HTTPException(404,'Solicitação não encontrada')
    novo=str(payload.get('status','')).upper()
    try: validar_transicao_status(row['status'],novo)
    except ValueError as e: raise HTTPException(422,str(e))
    return db.update('solicitacoes','id_solicitacao',id_solicitacao,{'status':novo,'atualizado_em':now()})
@app.get('/api/historico/{matricula}')
def historico(matricula:int): return sorted([r for r in db.all_rows('solicitacoes') if r['matricula']==matricula],key=lambda x:x['id_solicitacao'],reverse=True)

@app.get('/api/formularios')
def listar_formularios(): return sorted(db.all_rows('formularios'),key=lambda x:x['id_formulario'],reverse=True)
@app.get('/api/formularios/{id_formulario}')
def obter_formulario(id_formulario:int):
    f=db.get('formularios','id_formulario',id_formulario)
    if not f: raise HTTPException(404,'Formulário não encontrado')
    return f
@app.get('/api/formularios/{id_formulario}/secoes')
def listar_secoes(id_formulario:int):
    f=db.get('formularios','id_formulario',id_formulario)
    if not f: raise HTTPException(404,'Formulário não encontrado')
    return [{'nome_secao':k,'conteudo':v} for k,v in f.get('secoes',{}).items()]
@app.put('/api/formularios/{id_formulario}/secoes/{secao}')
def salvar_secao(id_formulario:int,secao:str,payload:dict):
    try: validar_secao(secao,payload.get('conteudo'))
    except ValueError as e: raise HTTPException(422,str(e))
    f=db.get('formularios','id_formulario',id_formulario)
    if not f: raise HTTPException(404,'Formulário não encontrado')
    if f['status']=='APROVADO': raise HTTPException(409,'Formulário aprovado não pode ser alterado')
    secoes={**f.get('secoes',{}),secao:payload['conteudo']}
    return db.update('formularios','id_formulario',id_formulario,{'secoes':secoes,'status':'EM_PREENCHIMENTO','atualizado_em':now()})
@app.post('/api/formularios/{id_formulario}/assinar',status_code=201)
def assinar(id_formulario:int,payload:dict):
    f=db.get('formularios','id_formulario',id_formulario)
    if not f: raise HTTPException(404,'Formulário não encontrado')
    if f['status']=='APROVADO': raise HTTPException(409,'Formulário já aprovado; não pode ser alterado')
    papel=str(payload.get('papel','')).upper()
    try: validar_assinatura(papel)
    except ValueError as e: raise HTTPException(422,str(e))
    def registrar_assinatura(data):
        f=next((row for row in data['formularios'] if row['id_formulario']==id_formulario),None)
        if f is None:
            raise HTTPException(404,'Formulário não encontrado')
        if f['status']=='APROVADO':
            raise HTTPException(409,'Formulário já aprovado; não pode ser alterado')
        if any(a['id_formulario']==id_formulario and a['papel']==papel for a in data['assinaturas']):
            raise HTTPException(409,f'{papel} já assinou este formulário')
        assinatura=db.append_record(data,'assinaturas',{'id_formulario':id_formulario,'papel':papel,'assinado_em':now()},'id_assinatura')
        f['assinaturas']=[a for a in data['assinaturas'] if a['id_formulario']==id_formulario]
        f.update({'status':'AGUARDANDO_ASSINATURAS','atualizado_em':now()})
        return assinatura
    assinatura=db.mutate(registrar_assinatura)
    return assinatura
@app.get('/api/formularios/{id_formulario}/assinaturas')
def listar_assinaturas(id_formulario:int): return [a for a in db.all_rows('assinaturas') if a['id_formulario']==id_formulario]
@app.post('/api/formularios/{id_formulario}/aprovar')
def aprovar(id_formulario:int):
    def aprovar_formulario(data):
        formulario=next((row for row in data['formularios'] if row['id_formulario']==id_formulario),None)
        if not formulario: raise HTTPException(404,'Formulário não encontrado')
        if formulario['status']=='APROVADO': raise HTTPException(409,'Formulário já aprovado')
        roles={a['papel'] for a in data['assinaturas'] if a['id_formulario']==id_formulario}
        faltam={'ALUNO','PROFESSOR','COORDENADOR'}-roles
        if faltam: raise HTTPException(409,'Faltam assinaturas obrigatórias: '+', '.join(sorted(faltam)))
        aprovado_em=now()
        formulario.update({'status':'APROVADO','aprovado_em':aprovado_em,'atualizado_em':aprovado_em})
        return formulario
    return db.mutate(aprovar_formulario)

@app.post('/api/designacoes',status_code=201)
def criar_designacao(payload:dict):
    required(payload,'matricula','id_assistente','data_inicio')
    try: validar_designacao(payload['data_inicio'],payload.get('data_fim'))
    except (ValueError,TypeError) as e: raise HTTPException(422,str(e))
    matricula=as_int(payload['matricula'],'Matrícula'); assistente=as_int(payload['id_assistente'],'ID do assistente')
    if not any(u.get('id_usuario')==assistente and u.get('nivel_usuario')=='ASSISTENTE' for u in db.all_rows('usuarios')):
        raise HTTPException(422,'Cadastre um usuário com perfil de assistente antes de designá-lo')
    for r in db.all_rows('designacoes'):
        if r['matricula']==matricula and (not r.get('data_fim') or r['data_fim']>=payload['data_inicio']) and (not payload.get('data_fim') or r['data_inicio']<=payload['data_fim']): raise HTTPException(409,'Já existe designação conflitante para esta matrícula')
    return db.create('designacoes',{'matricula':matricula,'id_assistente':assistente,'data_inicio':payload['data_inicio'],'data_fim':payload.get('data_fim') or None,'criado_em':now()},'id_designacao')
@app.get('/api/designacoes')
def listar_designacoes(): return sorted(db.all_rows('designacoes'),key=lambda x:x['id_designacao'],reverse=True)

@app.post('/relatorio',status_code=201)
@app.post('/api/relatorios',status_code=201)
def criar_relatorio(payload:dict):
    required(payload,'id_aluno','data_relatorio','descricao')
    try: date.fromisoformat(str(payload['data_relatorio']))
    except ValueError: raise HTTPException(422,'Data do relatório inválida')
    return db.create('relatorios',{**payload,'id_aluno':as_int(payload['id_aluno'],'Matrícula'),'criado_em':now()},'id_relatorio')
@app.get('/api/relatorios')
def listar_relatorios(): return sorted(db.all_rows('relatorios'),key=lambda x:x['id_relatorio'],reverse=True)
@app.get('/api/relatorios/resumo')
def resumo():
    rows=db.all_rows('solicitacoes'); counts={}
    for row in rows: counts[row['status']]=counts.get(row['status'],0)+1
    return [{'status':k,'quantidade':v} for k,v in sorted(counts.items())]
@app.post('/api/feedback',status_code=201)
def feedback(payload:dict):
    required(payload,'nome','email','assunto','avaliacao','comentario')
    try: rating=int(str(payload['avaliacao']).split(' ')[0])
    except ValueError: raise HTTPException(422,'A avaliação deve ser de 1 a 5')
    if rating not in range(1,6): raise HTTPException(422,'A avaliação deve ser de 1 a 5')
    return db.create('feedbacks',{'nome':str(payload['nome']).strip(),'email':str(payload['email']).strip().lower(),'assunto':payload['assunto'],'avaliacao':rating,'comentario':str(payload['comentario']).strip(),'criado_em':now()},'id_feedback')
@app.get('/api/feedback')
def listar_feedback(): return sorted(db.all_rows('feedbacks'),key=lambda x:x['id_feedback'],reverse=True)

FRONTEND_DIR=Path(__file__).resolve().parent.parent/'frontend'
if FRONTEND_DIR.exists(): app.mount('/frontend',StaticFiles(directory=str(FRONTEND_DIR),html=True),name='frontend')
