"""API local do PAEE com autenticação e autorização por perfil.

Os dados do fluxo continuam no armazenamento JSON local. A interface estática
não é um limite de segurança: cada operação de dados valida o token e o papel
no servidor. Para uso institucional, aplique as propostas SQL e migre o storage.
"""
from datetime import date, datetime
from hashlib import sha256
import hmac
from json import JSONDecodeError
import os
from pathlib import Path
import re
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import ConfigurationError
from backend import armazenamento_json as db
from backend.core.security import (
    JWTError,
    criar_access_token,
    decodificar_access_token,
    gerar_hash,
    verificar_senha,
)
from backend.paee_service import validar_designacao, validar_secao, validar_transicao_status
from backend.api.router import api_router

app = FastAPI(
    title="Sistema PAEE",
    version="2.0.0-json-local",
    description="Modo local com persistência JSON e RBAC.",
)
app.include_router(api_router, prefix="/api/v1")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
now = lambda: datetime.now().astimezone().isoformat(timespec="seconds")


@app.middleware("http")
async def disable_frontend_cache(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/frontend/"):
        response.headers["Cache-Control"] = "no-store"
    return response


ROLES = {"ALUNO", "COORDENADOR", "ASSISTENTE", "PROFESSOR"}
ROLE_TYPE_IDS = {
    "ALUNO": 1,
    "PROFESSOR": 2,
    "ASSISTENTE": 3,
    "COORDENADOR": 4,
}
DISABILITY_CATEGORIES = {"CEGO", "SURDO", "INTELECTUAL", "AUTISMO"}
REPORT_FIELDS = {
    "AUTISMO": {
        "socializacao": "Socialização",
        "integracao_ambiente": "Integração ao ambiente",
    },
    "CEGO": {
        "adaptacao_ambiente": "Adaptação ao ambiente",
        "ferramentas_auxilio": "Ferramentas de auxílio",
    },
    "SURDO": {
        "adaptacao_ambiente": "Adaptação ao ambiente",
        "ferramentas_auxilio": "Ferramentas de auxílio",
    },
    "INTELECTUAL": {
        "compreensao_conteudo": "Compreensão do conteúdo",
        "comportamento_sala": "Comportamento em sala",
    },
}
MAX_PDF_BYTES = 10 * 1024 * 1024
PRIVATE_STORAGE = Path(
    os.getenv(
        "PAEE_PRIVATE_STORAGE",
        str(Path(__file__).resolve().parent / "private_uploads"),
    )
).resolve()


def monthly_report_statistics(reports):
    grouped = {}
    for report in reports:
        evaluations = report.get("avaliacoes") or {}
        scores = {
            key: int(value["nota"])
            for key, value in evaluations.items()
            if isinstance(value, dict)
            and isinstance(value.get("nota"), int)
            and not isinstance(value.get("nota"), bool)
            and 1 <= value["nota"] <= 5
        }
        if not scores:
            continue
        raw_date = report.get("data_relatorio") or report.get("criado_em", "")
        try:
            month = date.fromisoformat(str(raw_date)[:10]).strftime("%Y-%m")
        except ValueError:
            continue
        bucket = grouped.setdefault(month, {"scores": [], "aspects": {}, "reports": set()})
        bucket["scores"].extend(scores.values())
        bucket["reports"].add(str(report.get("id_relatorio")))
        for key, score in scores.items():
            bucket["aspects"].setdefault(key, []).append(score)

    return [
        {
            "mes": month,
            "quantidade_relatorios": len(values["reports"]),
            "media": round(sum(values["scores"]) / len(values["scores"]), 2),
            "medias_aspectos": {
                key: round(sum(scores) / len(scores), 2)
                for key, scores in sorted(values["aspects"].items())
            },
        }
        for month, values in sorted(grouped.items())
    ]


def required(payload, *fields):
    missing = [
        field for field in fields
        if payload.get(field) is None or str(payload.get(field)).strip() == ""
    ]
    if missing:
        raise HTTPException(422, "Preencha os campos obrigatórios: " + ", ".join(missing))


def as_int(value, label):
    try:
        number = int(value)
        if number <= 0:
            raise ValueError()
        return number
    except (TypeError, ValueError):
        raise HTTPException(422, f"{label} deve ser um número positivo")


def usuario_publico(usuario):
    return {
        key: value for key, value in usuario.items()
        if key not in {"senha", "senha_hash", "password", "password_hash"}
    }


def usuario_por_email(email):
    normalized = str(email).strip().lower()
    return next(
        (
            row for row in db.all_rows("usuarios")
            if str(row.get("email", "")).strip().lower() == normalized
        ),
        None,
    )


def registrar_auditoria(ator, acao, alvo_id=None, entidade="usuario"):
    # A trilha não armazena e-mail, credencial, token nem texto de atendimento.
    return db.create(
        "auditoria",
        {
            "ator_id_usuario": ator["id_usuario"],
            "ator_papel": ator["nivel_usuario"],
            "acao": acao,
            "entidade": entidade,
            "alvo_id": alvo_id,
            "ocorrido_em": now(),
        },
        "id_auditoria",
    )


def obter_usuario_atual(request: Request):
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decodificar_access_token(token.strip())
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ConfigurationError:
        raise HTTPException(503, "Autenticação indisponível.")
    user = db.get("usuarios", "id_usuario", user_id)
    if not user or not user.get("ativo", True):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sessão inválida ou usuário inativo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def exigir_papel(usuario, *papeis):
    if str(usuario.get("nivel_usuario", "")).upper() not in papeis:
        raise HTTPException(403, "Seu perfil não tem permissão para esta operação.")
    return usuario


def coordenador(usuario=Depends(obter_usuario_atual)):
    return exigir_papel(usuario, "COORDENADOR")


def autenticar_papel(*papeis):
    def dependency(usuario=Depends(obter_usuario_atual)):
        return exigir_papel(usuario, *papeis)
    return dependency


def encontrar_solicitacao(id_solicitacao):
    row = db.get("solicitacoes", "id_solicitacao", id_solicitacao)
    if not row:
        raise HTTPException(404, "Solicitação não encontrada")
    return row


def designacao_ativa(matricula, id_assistente, quando=None):
    dia = quando or date.today()
    for row in db.all_rows("designacoes"):
        if str(row.get("matricula")) != str(matricula):
            continue
        if str(row.get("id_assistente")) != str(id_assistente):
            continue
        try:
            inicio = date.fromisoformat(str(row["data_inicio"]))
            fim = date.fromisoformat(str(row["data_fim"])) if row.get("data_fim") else None
        except (KeyError, ValueError, TypeError):
            continue
        if inicio <= dia and (fim is None or dia <= fim):
            return row
    return None


def autorizar_solicitacao(solicitacao, usuario):
    papel = usuario.get("nivel_usuario")
    if papel == "COORDENADOR":
        return
    if papel == "ALUNO":
        if str(solicitacao.get("criado_por")) != str(usuario.get("id_usuario")):
            raise HTTPException(404, "Solicitação não encontrada")
        return
    if papel == "ASSISTENTE" and designacao_ativa(
        solicitacao.get("matricula"), usuario["id_usuario"]
    ):
        return
    if papel == "ASSISTENTE":
        raise HTTPException(404, "Solicitação não encontrada")
    raise HTTPException(403, "Acesso não permitido a esta solicitação.")


def encontrar_formulario(id_formulario):
    form = db.get("formularios", "id_formulario", id_formulario)
    if not form:
        raise HTTPException(404, "Formulário não encontrado")
    solicitacao = encontrar_solicitacao(form["id_solicitacao"])
    return form, solicitacao


def autorizar_formulario(form, solicitacao, usuario):
    if usuario["nivel_usuario"] == "COORDENADOR":
        return
    autorizar_solicitacao(solicitacao, usuario)
    if usuario["nivel_usuario"] == "ASSISTENTE":
        autor = form.get("id_assistente_autor")
        if autor is not None and str(autor) != str(usuario["id_usuario"]):
            raise HTTPException(403, "Somente o assistente autor pode acessar este formulário.")


def formulario_publico(form):
    return {key: value for key, value in form.items() if key != "storage_key"}


def criar_usuario(payload, ator):
    required(payload, "email", "senha", "nome", "nivel_usuario")
    email = str(payload["email"]).strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "E-mail inválido.")
    senha = str(payload["senha"])
    if len(senha) < 12 or len(senha.encode("utf-8")) > 72:
        raise HTTPException(422, "A senha deve ter entre 12 e 72 bytes.")
    papel = str(payload["nivel_usuario"]).strip().upper()
    if papel not in ROLES:
        raise HTTPException(422, "Perfil de usuário inválido.")
    if papel == "ALUNO" and not str(payload.get("matricula", "")).strip():
        raise HTTPException(422, "A matrícula é obrigatória para o perfil de aluno.")
    category = str(payload.get("categoria_deficiencia", "")).strip().upper()
    if papel == "ALUNO" and category not in DISABILITY_CATEGORIES:
        raise HTTPException(422, "Selecione a deficiência do aluno no cadastro.")
    if papel == "ALUNO":
        matricula = str(payload["matricula"]).strip()
        if any(
            row.get("nivel_usuario") == "ALUNO"
            and str(row.get("matricula", "")).strip() == matricula
            for row in db.all_rows("usuarios")
        ):
            raise HTTPException(409, "Já existe um aluno cadastrado com essa matrícula.")
    if usuario_por_email(email):
        raise HTTPException(409, "Já existe um usuário com esse e-mail.")
    row = {
        "email": email,
        "senha_hash": gerar_hash(senha),
        "nome": str(payload["nome"]).strip(),
        "nivel_usuario": papel,
        "id_tipo_usuario": ROLE_TYPE_IDS[papel],
        "categoria_deficiencia": category if papel == "ALUNO" else None,
        "ativo": True,
        "criado_em": now(),
    }
    for field in ("matricula", "curso", "periodo"):
        if payload.get(field) not in (None, ""):
            row[field] = str(payload[field]).strip()
    tel_num = payload.get("tel_num", payload.get("telefone"))
    if tel_num not in (None, ""):
        row["tel_num"] = str(tel_num).strip()
    created = db.create("usuarios", row, "id_usuario")
    if ator:
        registrar_auditoria(ator, "USUARIO_CRIADO", created["id_usuario"])
    return usuario_publico(created)


@app.get("/health")
def health():
    return {"status": "ok", "servico": "PAEE", "storage": "json-local"}


@app.get("/api/status")
def api_status():
    return {
        "modo": "json-local",
        "mensagem": "Armazenamento local de desenvolvimento; não use dados reais.",
    }


@app.get("/api/demo-users")
def listar_usuarios_demo():
    if os.getenv("PAEE_ENVIRONMENT", "").lower() not in {"development", "local", "test"}:
        raise HTTPException(404, "Demonstração local indisponível.")
    users = db.all_rows("usuarios")
    if not users or any(not user.get("somente_teste") for user in users):
        raise HTTPException(404, "Demonstração local indisponível.")
    return {
        "senha_compartilhada": "LocalTestOnly-Placeholder-2026!",
        "usuarios": [
            {
                "nome": user.get("nome", ""),
                "email": user.get("email", ""),
                "perfil": user.get("nivel_usuario", ""),
            }
            for user in users if user.get("ativo", True)
        ],
    }


@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse("/frontend/paginas/login/tela_login.html")


@app.get("/menu", include_in_schema=False)
def entrada_menu():
    return RedirectResponse("/frontend/paginas/tela_inicial.html")


@app.get("/login", include_in_schema=False)
def entrada_login():
    return RedirectResponse("/frontend/paginas/login/tela_login.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    logo = Path(__file__).resolve().parent.parent / "frontend" / "img" / "logo_fate.png"
    if logo.exists():
        return FileResponse(logo, media_type="image/png")
    raise HTTPException(404, "Favicon não disponível.")


@app.post("/login")
async def login(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except JSONDecodeError:
            raise HTTPException(400, "Corpo JSON inválido")
    elif (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        payload = dict(await request.form())
    else:
        raise HTTPException(415, "Envie as credenciais como formulário ou JSON")
    if not isinstance(payload, dict):
        raise HTTPException(422, "Credenciais inválidas")
    email = str(payload.get("username") or payload.get("email") or "").strip().lower()
    senha = payload.get("password", payload.get("senha"))
    if not email or not isinstance(senha, str) or len(senha.encode("utf-8")) > 72:
        raise HTTPException(401, "E-mail ou senha inválidos")
    user = usuario_por_email(email)
    if user and user.get("somente_teste") and os.getenv("PAEE_ENVIRONMENT", "").lower() not in {
        "development", "local", "test"
    }:
        raise HTTPException(401, "E-mail ou senha inválidos")
    valid_password = False
    if user and user.get("senha_hash"):
        valid_password = verificar_senha(senha, user["senha_hash"])
    elif user and isinstance(user.get("senha"), str):
        valid_password = hmac.compare_digest(user["senha"], senha)
        if valid_password:
            user_id = user["id_usuario"]

            def migrar_senha_legada(data):
                record = next(
                    (row for row in data["usuarios"]
                     if str(row.get("id_usuario")) == str(user_id)),
                    None,
                )
                if record:
                    if not record.get("senha_hash"):
                        record["senha_hash"] = gerar_hash(senha)
                    record.pop("senha", None)
                return record

            user = db.mutate(migrar_senha_legada)
    if not user or not user.get("ativo", True) or not valid_password:
        raise HTTPException(401, "E-mail ou senha inválidos")
    try:
        token = criar_access_token(str(user["id_usuario"]))
    except ConfigurationError:
        raise HTTPException(
            503, "Autenticação indisponível; configure SECRET_KEY no ambiente local."
        )
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": usuario_publico(user),
    }


@app.get("/api/me")
def me(usuario=Depends(obter_usuario_atual)):
    return usuario_publico(usuario)


@app.post("/usuario", status_code=201)
def criar_usuario_compat(payload: dict, usuario=Depends(coordenador)):
    return criar_usuario(payload, usuario)


@app.get("/api/usuarios")
def listar_usuarios(usuario=Depends(coordenador)):
    return [usuario_publico(row) for row in db.all_rows("usuarios")]


@app.post("/api/usuarios", status_code=201)
def criar_usuario_coordenador(payload: dict, usuario=Depends(coordenador)):
    return criar_usuario(payload, usuario)


@app.patch("/api/usuarios/{id_usuario}")
def editar_usuario(id_usuario: int, payload: dict, ator=Depends(coordenador)):
    alvo = db.get("usuarios", "id_usuario", id_usuario)
    if not alvo:
        raise HTTPException(404, "Usuário não encontrado.")
    changes = {}
    allowed = {
        "nome", "email", "nivel_usuario", "matricula", "curso", "periodo",
        "telefone", "tel_num", "categoria_deficiencia",
    }
    unknown = set(payload) - allowed - {"senha"}
    if unknown:
        raise HTTPException(422, "Campo não permitido.")
    if "nome" in payload:
        required(payload, "nome")
        changes["nome"] = str(payload["nome"]).strip()
    if "email" in payload:
        email = str(payload["email"]).strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise HTTPException(422, "E-mail inválido.")
        collision = usuario_por_email(email)
        if collision and str(collision["id_usuario"]) != str(id_usuario):
            raise HTTPException(409, "Já existe um usuário com esse e-mail.")
        changes["email"] = email
    if "nivel_usuario" in payload:
        papel = str(payload["nivel_usuario"]).strip().upper()
        if papel not in ROLES:
            raise HTTPException(422, "Perfil de usuário inválido.")
        changes["nivel_usuario"] = papel
        changes["id_tipo_usuario"] = ROLE_TYPE_IDS[papel]
    for field in ("matricula", "curso", "periodo"):
        if field in payload:
            changes[field] = str(payload[field]).strip()
    resulting_role = changes.get("nivel_usuario", alvo.get("nivel_usuario"))
    resulting_matricula = changes.get("matricula", alvo.get("matricula"))
    resulting_category = str(
        payload.get("categoria_deficiencia", alvo.get("categoria_deficiencia", ""))
    ).strip().upper()
    if resulting_role == "ALUNO":
        if not str(resulting_matricula or "").strip():
            raise HTTPException(422, "A matrícula é obrigatória para o perfil de aluno.")
        if resulting_category not in DISABILITY_CATEGORIES:
            raise HTTPException(422, "Selecione a deficiência do aluno no cadastro.")
        if any(
            row.get("nivel_usuario") == "ALUNO"
            and str(row.get("matricula", "")).strip() == str(resulting_matricula).strip()
            and str(row.get("id_usuario")) != str(id_usuario)
            for row in db.all_rows("usuarios")
        ):
            raise HTTPException(409, "Já existe um aluno cadastrado com essa matrícula.")
        changes["categoria_deficiencia"] = resulting_category
    elif resulting_role != "ALUNO":
        changes["categoria_deficiencia"] = None
    if "tel_num" in payload or "telefone" in payload:
        changes["tel_num"] = str(
            payload.get("tel_num", payload.get("telefone", ""))
        ).strip()
    if payload.get("senha"):
        senha = str(payload["senha"])
        if len(senha) < 12 or len(senha.encode("utf-8")) > 72:
            raise HTTPException(422, "A senha deve ter entre 12 e 72 bytes.")
        changes["senha_hash"] = gerar_hash(senha)
    if not changes:
        raise HTTPException(422, "Informe ao menos um campo para atualizar.")
    if (
        alvo.get("ativo", True)
        and alvo.get("nivel_usuario") == "COORDENADOR"
        and changes.get("nivel_usuario", "COORDENADOR") != "COORDENADOR"
        and not any(
            user.get("nivel_usuario") == "COORDENADOR"
            and user.get("ativo", True)
            and str(user.get("id_usuario")) != str(id_usuario)
            for user in db.all_rows("usuarios")
        )
    ):
        raise HTTPException(409, "Não é permitido remover o último coordenador ativo.")
    updated = db.update("usuarios", "id_usuario", id_usuario, changes)
    registrar_auditoria(
        ator,
        "PERFIL_ALTERADO" if "nivel_usuario" in changes else "USUARIO_EDITADO",
        id_usuario,
    )
    return usuario_publico(updated)


def atualizar_ativacao(id_usuario, ativo, ator):
    alvo = db.get("usuarios", "id_usuario", id_usuario)
    if not alvo:
        raise HTTPException(404, "Usuário não encontrado.")
    if not ativo and alvo.get("nivel_usuario") == "COORDENADOR" and alvo.get("ativo", True):
        other_active = [
            user for user in db.all_rows("usuarios")
            if user.get("nivel_usuario") == "COORDENADOR"
            and user.get("ativo", True)
            and str(user.get("id_usuario")) != str(id_usuario)
        ]
        if not other_active:
            raise HTTPException(409, "Não é permitido desativar o último coordenador ativo.")
    updated = db.update("usuarios", "id_usuario", id_usuario, {"ativo": ativo})
    registrar_auditoria(
        ator,
        "USUARIO_REATIVADO" if ativo else "USUARIO_DESATIVADO",
        id_usuario,
    )
    return usuario_publico(updated)


@app.post("/api/usuarios/{id_usuario}/desativar")
def desativar_usuario(id_usuario: int, ator=Depends(coordenador)):
    return atualizar_ativacao(id_usuario, False, ator)


@app.post("/api/usuarios/{id_usuario}/reativar")
def reativar_usuario(id_usuario: int, ator=Depends(coordenador)):
    return atualizar_ativacao(id_usuario, True, ator)


@app.get("/api/auditoria")
def listar_auditoria(usuario=Depends(coordenador)):
    return sorted(
        db.all_rows("auditoria"),
        key=lambda row: row.get("id_auditoria", 0),
        reverse=True,
    )


@app.get("/api/alunos")
def listar_alunos(usuario=Depends(coordenador)):
    return [
        usuario_publico(row) for row in db.all_rows("usuarios")
        if row.get("nivel_usuario") == "ALUNO"
    ]


@app.get("/api/alunos/{matricula}/estatisticas")
def estatisticas_aluno(matricula: str, materia: str = "", usuario=Depends(coordenador)):
    student = next(
        (
            row for row in db.all_rows("usuarios")
            if row.get("nivel_usuario") == "ALUNO"
            and str(row.get("matricula", "")).casefold() == matricula.strip().casefold()
        ),
        None,
    )
    if not student:
        raise HTTPException(404, "Aluno não encontrado.")
    reports = [
        row for row in db.all_rows("relatorios")
        if str(row.get("id_aluno", "")).casefold() == matricula.strip().casefold()
        and (not materia or str(row.get("materia", "")).casefold() == materia.strip().casefold())
    ]
    return {
        "aluno": {
            "matricula": student.get("matricula"),
            "nome": student.get("nome"),
            "categoria_deficiencia": student.get("categoria_deficiencia"),
        },
        "materias": sorted({str(row["materia"]).strip() for row in reports if row.get("materia")}),
        "aspectos": [
            {"chave": key, "nome": label}
            for key, label in REPORT_FIELDS.get(student.get("categoria_deficiencia"), {}).items()
        ],
        "estatisticas_mensais": monthly_report_statistics(reports),
    }


@app.get("/api/alunos-designados")
def listar_alunos_designados(usuario=Depends(autenticar_papel("ASSISTENTE"))):
    matriculas = {
        str(row.get("matricula"))
        for row in db.all_rows("designacoes")
        if str(row.get("id_assistente")) == str(usuario["id_usuario"])
        and designacao_ativa(row.get("matricula"), usuario["id_usuario"])
    }
    return [
        usuario_publico(row) for row in db.all_rows("usuarios")
        if row.get("nivel_usuario") == "ALUNO"
        and row.get("ativo", True)
        and str(row.get("matricula")) in matriculas
    ]


@app.get("/api/professores")
def listar_professores(usuario=Depends(coordenador)):
    return [
        usuario_publico(row) for row in db.all_rows("usuarios")
        if row.get("nivel_usuario") == "PROFESSOR"
    ]


@app.get("/api/assistentes")
def listar_assistentes(usuario=Depends(coordenador)):
    return [
        usuario_publico(row) for row in db.all_rows("usuarios")
        if row.get("nivel_usuario") == "ASSISTENTE"
    ]


@app.get("/api/coordenadores")
def listar_coordenadores(usuario=Depends(coordenador)):
    return [
        usuario_publico(row) for row in db.all_rows("usuarios")
        if row.get("nivel_usuario") == "COORDENADOR"
    ]


@app.post("/api/solicitacoes", status_code=201)
def criar_solicitacao(payload: dict, usuario=Depends(autenticar_papel("ALUNO"))):
    required(payload, "motivo")
    matricula = usuario.get("matricula")
    if not matricula:
        raise HTTPException(409, "Seu perfil ainda não possui matrícula cadastrada.")
    category = usuario.get("categoria_deficiencia")
    if category not in DISABILITY_CATEGORIES:
        raise HTTPException(409, "Solicite à coordenação o cadastro da deficiência no seu perfil.")
    criado_em = now()
    row, form = db.create_many([
        ("solicitacoes", {
            "matricula": str(matricula),
            "criado_por": usuario["id_usuario"],
            "motivo": str(payload["motivo"]).strip(),
            "categoria_deficiencia": category,
            "status": "ABERTA",
            "criado_em": criado_em,
            "atualizado_em": criado_em,
        }, "id_solicitacao"),
        ("formularios", lambda created: {
            "id_solicitacao": created[0]["id_solicitacao"],
            "status": "RASCUNHO",
            "secoes": {},
            "criado_em": criado_em,
            "assinaturas": [],
        }, "id_formulario"),
    ])
    row["id_formulario"] = form["id_formulario"]
    registrar_auditoria(usuario, "SOLICITACAO_CRIADA", row["id_solicitacao"], "solicitacao")
    return row


@app.get("/api/solicitacoes")
def listar_solicitacoes(usuario=Depends(autenticar_papel("ALUNO", "COORDENADOR"))):
    rows = db.all_rows("solicitacoes")
    if usuario["nivel_usuario"] != "COORDENADOR":
        rows = [
            row for row in rows
            if str(row.get("criado_por")) == str(usuario["id_usuario"])
        ]
    return sorted(rows, key=lambda row: row.get("id_solicitacao", 0), reverse=True)


@app.get("/api/solicitacoes/{id_solicitacao}")
def obter_solicitacao(
    id_solicitacao: int,
    usuario=Depends(autenticar_papel("ALUNO", "COORDENADOR")),
):
    row = encontrar_solicitacao(id_solicitacao)
    autorizar_solicitacao(row, usuario)
    form = next(
        (item for item in db.all_rows("formularios")
         if item.get("id_solicitacao") == id_solicitacao),
        None,
    )
    return {**row, "formulario": formulario_publico(form) if form else None}


@app.patch("/api/solicitacoes/{id_solicitacao}/status")
def atualizar_status(id_solicitacao: int, payload: dict, usuario=Depends(coordenador)):
    row = encontrar_solicitacao(id_solicitacao)
    novo = str(payload.get("status", "")).upper()
    try:
        validar_transicao_status(row["status"], novo)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    updated = db.update(
        "solicitacoes",
        "id_solicitacao",
        id_solicitacao,
        {"status": novo, "atualizado_em": now()},
    )
    registrar_auditoria(usuario, "STATUS_ALTERADO", id_solicitacao, "solicitacao")
    return updated


@app.get("/api/historico/{matricula}")
def historico(matricula: str, usuario=Depends(coordenador)):
    rows = [
        row for row in db.all_rows("solicitacoes")
        if str(row.get("matricula")) == str(matricula)
    ]
    return sorted(rows, key=lambda row: row.get("id_solicitacao", 0), reverse=True)


@app.get("/api/formularios")
def listar_formularios(usuario=Depends(autenticar_papel("COORDENADOR", "ASSISTENTE"))):
    rows = []
    for form in db.all_rows("formularios"):
        solicitacao = db.get("solicitacoes", "id_solicitacao", form.get("id_solicitacao"))
        if not solicitacao:
            continue
        try:
            autorizar_formulario(form, solicitacao, usuario)
            rows.append(formulario_publico(form))
        except HTTPException:
            continue
    return sorted(rows, key=lambda row: row.get("id_formulario", 0), reverse=True)


@app.get("/api/formularios/{id_formulario}")
def obter_formulario(
    id_formulario: int,
    usuario=Depends(autenticar_papel("COORDENADOR", "ASSISTENTE")),
):
    form, solicitacao = encontrar_formulario(id_formulario)
    autorizar_formulario(form, solicitacao, usuario)
    return formulario_publico(form)


@app.get("/api/formularios/{id_formulario}/secoes")
def listar_secoes(
    id_formulario: int,
    usuario=Depends(autenticar_papel("COORDENADOR", "ASSISTENTE")),
):
    form, solicitacao = encontrar_formulario(id_formulario)
    autorizar_formulario(form, solicitacao, usuario)
    return [{"nome_secao": key, "conteudo": value} for key, value in form.get("secoes", {}).items()]


@app.put("/api/formularios/{id_formulario}/secoes/{secao}")
def salvar_secao(
    id_formulario: int,
    secao: str,
    payload: dict,
    usuario=Depends(autenticar_papel("ASSISTENTE")),
):
    try:
        validar_secao(secao, payload.get("conteudo"))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    form, solicitacao = encontrar_formulario(id_formulario)
    if not designacao_ativa(solicitacao["matricula"], usuario["id_usuario"]):
        raise HTTPException(403, "É necessária uma designação ativa para preencher este formulário.")
    if form.get("status") == "APROVADO" or form.get("assinaturas"):
        raise HTTPException(409, "O formulário não pode ser alterado após uma assinatura.")
    author = form.get("id_assistente_autor")
    if author is not None and str(author) != str(usuario["id_usuario"]):
        raise HTTPException(403, "Somente o assistente autor pode alterar este formulário.")
    sections = {**form.get("secoes", {}), secao: payload["conteudo"]}
    updated = db.update("formularios", "id_formulario", id_formulario, {
        "secoes": sections,
        "id_assistente_autor": usuario["id_usuario"],
        "status": "EM_PREENCHIMENTO",
        "atualizado_em": now(),
    })
    registrar_auditoria(usuario, "FORMULARIO_PREENCHIDO", id_formulario, "formulario")
    return formulario_publico(updated)


@app.post("/api/formularios/{id_formulario}/assinar", status_code=201)
def assinar(
    id_formulario: int,
    usuario=Depends(autenticar_papel("COORDENADOR", "ASSISTENTE")),
):
    papel = usuario["nivel_usuario"]
    def registrar(data):
        form = next(
            (row for row in data["formularios"]
             if str(row.get("id_formulario")) == str(id_formulario)),
            None,
        )
        if not form:
            raise HTTPException(404, "Formulário não encontrado.")
        solicitacao = next(
            (row for row in data["solicitacoes"]
             if str(row.get("id_solicitacao")) == str(form.get("id_solicitacao"))),
            None,
        )
        if not solicitacao:
            raise HTTPException(404, "Solicitação não encontrada.")
        assinaturas = form.get("assinaturas", [])
        if form.get("status") == "APROVADO":
            raise HTTPException(409, "Formulário já aprovado.")
        if any(str(item.get("id_usuario")) == str(usuario["id_usuario"]) for item in assinaturas):
            raise HTTPException(409, "Este usuário já assinou o formulário.")
        if papel == "COORDENADOR":
            if any(item.get("papel") == "ASSISTENTE" for item in assinaturas):
                raise HTTPException(409, "A assinatura da coordenação deve ocorrer primeiro.")
            author = form.get("id_assistente_autor")
            if not author or not designacao_ativa(solicitacao["matricula"], author):
                raise HTTPException(
                    409,
                    "O assistente designado deve preencher o formulário antes da assinatura da coordenação.",
                )
        else:
            if not any(item.get("papel") == "COORDENADOR" for item in assinaturas):
                raise HTTPException(409, "A coordenação deve assinar antes do assistente.")
            if str(form.get("id_assistente_autor")) != str(usuario["id_usuario"]):
                raise HTTPException(403, "Somente o assistente autor designado pode assinar.")
            if not designacao_ativa(solicitacao["matricula"], usuario["id_usuario"]):
                raise HTTPException(403, "É necessária designação ativa para assinar.")
        signature = {
            "id_usuario": usuario["id_usuario"],
            "papel": papel,
            "assinado_em": now(),
        }
        assinaturas.append(signature)
        form.update({
            "assinaturas": assinaturas,
            "status": (
                "AGUARDANDO_APROVACAO"
                if papel == "ASSISTENTE"
                else "AGUARDANDO_ASSINATURA_ASSISTENTE"
            ),
            "atualizado_em": now(),
        })
        return {"assinatura": signature, "formulario": formulario_publico(form)}

    resultado = db.mutate(registrar)
    registrar_auditoria(usuario, "FORMULARIO_ASSINADO", id_formulario, "formulario")
    return resultado


@app.get("/api/formularios/{id_formulario}/assinaturas")
def listar_assinaturas(
    id_formulario: int,
    usuario=Depends(autenticar_papel("COORDENADOR", "ASSISTENTE")),
):
    form, solicitacao = encontrar_formulario(id_formulario)
    autorizar_formulario(form, solicitacao, usuario)
    return form.get("assinaturas", [])


@app.post("/api/formularios/{id_formulario}/aprovar")
def aprovar_formulario(id_formulario: int, usuario=Depends(coordenador)):
    form, solicitacao = encontrar_formulario(id_formulario)
    roles = {item.get("papel") for item in form.get("assinaturas", [])}
    if not {"COORDENADOR", "ASSISTENTE"}.issubset(roles):
        raise HTTPException(409, "A coordenação e o assistente autor devem assinar, nesta ordem.")
    if form.get("status") == "APROVADO":
        return formulario_publico(form)
    assistant_signature = next(
        item for item in form["assinaturas"] if item.get("papel") == "ASSISTENTE"
    )
    if str(assistant_signature.get("id_usuario")) != str(form.get("id_assistente_autor")):
        raise HTTPException(409, "A assinatura deve pertencer ao assistente autor.")
    updated = db.update("formularios", "id_formulario", id_formulario, {
        "status": "APROVADO",
        "aprovado_por": usuario["id_usuario"],
        "aprovado_em": now(),
        "atualizado_em": now(),
    })
    db.update("solicitacoes", "id_solicitacao", solicitacao["id_solicitacao"], {
        "status": "APROVADA",
        "atualizado_em": now(),
    })
    registrar_auditoria(usuario, "FORMULARIO_APROVADO", id_formulario, "formulario")
    return formulario_publico(updated)


@app.post("/api/formularios/{id_formulario}/anexo")
async def substituir_anexo(
    id_formulario: int,
    arquivo: UploadFile = File(...),
    usuario=Depends(autenticar_papel("COORDENADOR", "ASSISTENTE")),
):
    form, solicitacao = encontrar_formulario(id_formulario)
    autorizar_formulario(form, solicitacao, usuario)
    if form.get("assinaturas"):
        raise HTTPException(409, "O anexo não pode ser substituído após uma assinatura.")
    if usuario["nivel_usuario"] == "ASSISTENTE":
        if form.get("id_assistente_autor") not in (None, usuario["id_usuario"]):
            raise HTTPException(403, "Somente o assistente autor pode anexar arquivo.")
        if not designacao_ativa(solicitacao["matricula"], usuario["id_usuario"]):
            raise HTTPException(403, "É necessária uma designação ativa para anexar arquivo.")
    if arquivo.content_type != "application/pdf":
        raise HTTPException(415, "Envie um arquivo PDF.")
    if PRIVATE_STORAGE == FRONTEND_DIR.resolve() or PRIVATE_STORAGE.is_relative_to(FRONTEND_DIR.resolve()):
        raise HTTPException(500, "O armazenamento privado não pode ficar sob a pasta estática.")
    content = await arquivo.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(413, "O arquivo deve ter no máximo 10 MB.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(422, "O arquivo não possui uma assinatura PDF válida.")
    PRIVATE_STORAGE.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid4().hex}.pdf"
    destination = (PRIVATE_STORAGE / storage_key).resolve()
    if destination.parent != PRIVATE_STORAGE:
        raise HTTPException(400, "Nome de arquivo inválido.")
    destination.write_bytes(content)
    previous_key = form.get("storage_key")
    metadata = {
        "nome_original": Path(arquivo.filename or "documento.pdf").name[:180],
        "content_type": "application/pdf",
        "tamanho_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
        "enviado_por": usuario["id_usuario"],
        "enviado_em": now(),
    }
    updated = db.update("formularios", "id_formulario", id_formulario, {
        "storage_key": storage_key,
        "anexo": metadata,
        **(
            {"id_assistente_autor": usuario["id_usuario"]}
            if usuario["nivel_usuario"] == "ASSISTENTE"
            else {}
        ),
        "atualizado_em": now(),
    })
    if previous_key:
        old_path = (PRIVATE_STORAGE / Path(previous_key).name).resolve()
        if old_path.parent == PRIVATE_STORAGE and old_path.exists():
            old_path.unlink()
    registrar_auditoria(usuario, "ANEXO_SUBSTITUIDO", id_formulario, "formulario")
    return {"anexo": metadata, "formulario": formulario_publico(updated)}


@app.get("/api/formularios/{id_formulario}/anexo")
def baixar_anexo(
    id_formulario: int,
    usuario=Depends(autenticar_papel("COORDENADOR", "ASSISTENTE")),
):
    form, solicitacao = encontrar_formulario(id_formulario)
    autorizar_formulario(form, solicitacao, usuario)
    key = form.get("storage_key")
    if not key:
        raise HTTPException(404, "Este formulário não possui anexo.")
    path = (PRIVATE_STORAGE / Path(key).name).resolve()
    if path.parent != PRIVATE_STORAGE or not path.is_file():
        raise HTTPException(404, "Anexo não encontrado.")
    filename = (form.get("anexo") or {}).get("nome_original", "documento.pdf")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.post("/api/designacoes", status_code=201)
def criar_designacao(payload: dict, usuario=Depends(coordenador)):
    required(payload, "matricula", "id_assistente", "data_inicio")
    try:
        validar_designacao(payload["data_inicio"], payload.get("data_fim"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    matricula = str(payload["matricula"]).strip()
    assistente_id = as_int(payload["id_assistente"], "ID do assistente")
    assistant = db.get("usuarios", "id_usuario", assistente_id)
    if not assistant or assistant.get("nivel_usuario") != "ASSISTENTE" or not assistant.get("ativo", True):
        raise HTTPException(422, "Selecione um usuário assistente ativo.")
    if not any(
        row.get("nivel_usuario") == "ALUNO"
        and row.get("ativo", True)
        and str(row.get("matricula", "")) == matricula
        for row in db.all_rows("usuarios")
    ):
        raise HTTPException(422, "A matrícula não corresponde a um aluno ativo.")
    try:
        inicio = date.fromisoformat(str(payload["data_inicio"]))
        fim = date.fromisoformat(str(payload["data_fim"])) if payload.get("data_fim") else None
    except ValueError:
        raise HTTPException(422, "Período de designação inválido.")
    for current in db.all_rows("designacoes"):
        if str(current.get("matricula")) != matricula:
            continue
        try:
            current_start = date.fromisoformat(str(current["data_inicio"]))
            current_end = date.fromisoformat(str(current["data_fim"])) if current.get("data_fim") else None
        except (KeyError, ValueError, TypeError):
            continue
        if (current_end is None or inicio <= current_end) and (fim is None or fim >= current_start):
            raise HTTPException(409, "Já existe designação conflitante para esta matrícula.")
    row = db.create("designacoes", {
        "matricula": matricula,
        "id_assistente": assistente_id,
        "data_inicio": inicio.isoformat(),
        "data_fim": fim.isoformat() if fim else None,
        "criado_por": usuario["id_usuario"],
        "criado_em": now(),
    }, "id_designacao")
    registrar_auditoria(usuario, "DESIGNACAO_CRIADA", row["id_designacao"], "designacao")
    return row


@app.get("/api/designacoes")
def listar_designacoes(usuario=Depends(coordenador)):
    return sorted(
        db.all_rows("designacoes"),
        key=lambda row: row.get("id_designacao", 0),
        reverse=True,
    )


@app.post("/api/relatorios", status_code=201)
@app.post("/relatorio", status_code=201, include_in_schema=False)
def criar_relatorio(payload: dict, usuario=Depends(autenticar_papel("ASSISTENTE"))):
    required(payload, "id_aluno", "data_relatorio", "materia", "descricao")
    matricula = str(payload["id_aluno"]).strip()
    if not designacao_ativa(matricula, usuario["id_usuario"]):
        raise HTTPException(403, "Relatórios só podem ser criados para alunos designados ao assistente.")
    student = next(
        (
            row for row in db.all_rows("usuarios")
            if row.get("nivel_usuario") == "ALUNO"
            and row.get("ativo", True)
            and str(row.get("matricula", "")).strip() == matricula
        ),
        None,
    )
    if not student:
        raise HTTPException(422, "A matrícula não corresponde a um aluno ativo cadastrado.")
    category = student.get("categoria_deficiencia")
    if category not in DISABILITY_CATEGORIES:
        raise HTTPException(409, "Cadastre a deficiência do aluno antes de criar o relatório.")
    try:
        report_date = date.fromisoformat(str(payload["data_relatorio"]))
        start = date.fromisoformat(str(payload.get("data_inicio", payload["data_relatorio"])))
        end = date.fromisoformat(str(payload.get("data_fim", payload["data_relatorio"])))
    except (ValueError, TypeError):
        raise HTTPException(422, "Data do relatório inválida.")
    if end < start:
        raise HTTPException(422, "A data final não pode ser anterior à inicial.")
    evaluations = payload.get("avaliacoes", {})
    if not isinstance(evaluations, dict) or set(evaluations) != set(REPORT_FIELDS[category]):
        raise HTTPException(
            422,
            "Informe uma avaliação para cada aspecto da categoria do aluno.",
        )
    clean_evaluations = {}
    for aspect, value in evaluations.items():
        if not isinstance(value, dict) or set(value) - {"nota", "comentario"}:
            raise HTTPException(422, "Formato de avaliação inválido.")
        score = value.get("nota")
        comment = value.get("comentario", "")
        if not isinstance(score, int) or isinstance(score, bool) or score not in range(1, 6):
            raise HTTPException(422, f"A nota de {REPORT_FIELDS[category][aspect]} deve ser de 1 a 5.")
        if not isinstance(comment, str) or len(comment) > 2000:
            raise HTTPException(422, "Os comentários devem ter até 2000 caracteres.")
        clean_evaluations[aspect] = {"nota": score, "comentario": comment.strip()}
    materia = str(payload["materia"]).strip()
    if len(materia) > 120:
        raise HTTPException(422, "A matéria deve ter até 120 caracteres.")
    row = db.create("relatorios", {
        "id_aluno": matricula,
        "data_relatorio": report_date.isoformat(),
        "materia": materia,
        "data_inicio": start.isoformat(),
        "data_fim": end.isoformat(),
        "descricao": str(payload["descricao"]).strip(),
        "observacao": str(payload.get("observacao", "")).strip(),
        "titulo": str(payload.get("titulo", "Relatório PAEE")).strip(),
        "tipo": str(payload.get("tipo", "Acompanhamento")).strip(),
        "categoria_deficiencia": category,
        "avaliacoes": clean_evaluations,
        "responsavel": usuario.get("nome", ""),
        "situacao": str(payload.get("situacao", "Em andamento")).strip(),
        "criado_por": usuario["id_usuario"],
        "criado_em": now(),
    }, "id_relatorio")
    registrar_auditoria(usuario, "RELATORIO_CRIADO", row["id_relatorio"], "relatorio")
    return row


@app.get("/api/relatorios")
def listar_relatorios(usuario=Depends(autenticar_papel("ASSISTENTE"))):
    rows = db.all_rows("relatorios")
    rows = [row for row in rows if str(row.get("criado_por")) == str(usuario["id_usuario"])]
    return sorted(rows, key=lambda row: row.get("id_relatorio", 0), reverse=True)


@app.get("/api/relatorios/estatisticas")
def estatisticas_relatorios(materia: str = "", usuario=Depends(coordenador)):
    reports = db.all_rows("relatorios")
    subjects = sorted({str(row["materia"]).strip() for row in reports if row.get("materia")})
    filtered = [
        row for row in reports
        if not materia or str(row.get("materia", "")).casefold() == materia.strip().casefold()
    ]
    return {
        "materias": subjects,
        "estatisticas_mensais": monthly_report_statistics(filtered),
    }


@app.get("/api/relatorios/resumo")
def resumo(usuario=Depends(coordenador)):
    counts = {}
    for row in db.all_rows("solicitacoes"):
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return [{"status": key, "quantidade": value} for key, value in sorted(counts.items())]


@app.post("/api/feedback", status_code=201)
def feedback(
    payload: dict,
    usuario=Depends(autenticar_papel("ALUNO", "ASSISTENTE", "PROFESSOR")),
):
    required(payload, "assunto", "avaliacao", "comentario")
    try:
        rating = int(str(payload["avaliacao"]).split(" ")[0])
    except ValueError:
        raise HTTPException(422, "A avaliação deve ser de 1 a 5")
    if rating not in range(1, 6):
        raise HTTPException(422, "A avaliação deve ser de 1 a 5")
    return db.create("feedbacks", {
        "id_usuario": usuario["id_usuario"],
        "nome": usuario.get("nome", ""),
        "email": usuario["email"],
        "assunto": str(payload["assunto"]).strip(),
        "avaliacao": rating,
        "comentario": str(payload["comentario"]).strip(),
        "criado_em": now(),
    }, "id_feedback")


@app.get("/api/feedback")
def listar_feedback(usuario=Depends(coordenador)):
    return sorted(db.all_rows("feedbacks"), key=lambda row: row.get("id_feedback", 0), reverse=True)


if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
