from backend.database import conectar
from backend.models import RelatorioCreate

def criar_relatorio(relatorio: RelatorioCreate):
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute("INSERT INTO relatorio_paee (matricula, data_relatorio, descricao, observacao) VALUES (%s,%s,%s,%s) RETURNING id_relatorio", (relatorio.id_aluno, relatorio.data_relatorio, relatorio.descricao, relatorio.observacao))
                row = cursor.fetchone()
            conexao.commit()
        return {"success":True,"message":"Relatório criado com sucesso","relatorio":{"id_relatorio":row[0],"id_aluno":relatorio.id_aluno,"data_relatorio":relatorio.data_relatorio,"descricao":relatorio.descricao,"observacao":relatorio.observacao}}
    except Exception as error:
        return {"success":False,"message":f"Erro ao cadastrar relatório: {error}","type":type(error).__name__}
