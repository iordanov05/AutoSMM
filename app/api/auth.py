from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.user import User
from jose import JWTError, jwt
from app.core.config import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
       
        user_email = payload.get("sub")  
   
        if user_email is None:
            raise HTTPException(status_code=401, detail="Ошибка проверки токена (неверный формат email)")

        user = db.query(User).filter(User.email == user_email).first()  
        if user is None:
            raise HTTPException(status_code=401, detail="Пользователь не найден")

        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Некорректный токен")
