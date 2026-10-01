import bcrypt

def gerar_hash(senha: str) -> str: #Type hint para comunicar que tipo de dados a função receve e devolve (->)
    senha_bytes = senha.encode("utf-8") # Converte a senha de string para bytes, formato exigido pela biblioteca bcrypt.

    senha_hash = bcrypt.hashpw( #Gera o hash da senha usando a função hashpw do bcrypt, que recebe a senha em bytes e um salt gerado pela função gensalt.
        senha_bytes,
        bcrypt.gensalt()
    )

    return senha_hash.decode("utf-8") # Decodifica o hash gerado de bytes para string antes de retornar, para facilitar o armazenamento e a manipulação do hash.

def verificar_senha(senha_digitada: str, senha_hash: str) -> bool: #Type hint para comunicar que tipo de dados a função receve e devolve (->)
    senha_bytes = senha_digitada.encode("utf-8") # Converte a senha digitada de string para bytes.
    hash_bytes = senha_hash.encode("utf-8") # Converte o hash armazenado de string para bytes.
    return bcrypt.checkpw(senha_bytes, hash_bytes) # Verifica se a senha digitada corresponde ao hash armazenado usando a função checkpw do bcrypt, que retorna True se as senhas corresponderem e False caso contrário.
