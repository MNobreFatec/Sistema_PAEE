from aluno import criar_aluno
from fastapi import FastAPI, HTTPException
from models import AlunoCreate

app = FastAPI()

@app.post("/aluno")
def criar_aluno_endpoint(aluno: AlunoCreate):
    resultado = criar_aluno(aluno)
    if resultado["success"]:
        return resultado
    else:
        raise HTTPException(status_code=400, detail=resultado["message"])

