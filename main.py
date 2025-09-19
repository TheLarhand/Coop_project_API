from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import secrets

app = FastAPI(title="Task Management API", version="1.0.0")
security = HTTPBasic()

# Фиксированные пользователи
USERS = {
    1: {"name": "Нурбай", "login": "UserNyrbai", "password": "111", "ava": "https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_640.png"},
    2: {"name": "Роман", "login": "UserRoman", "password": "222", "ava": "https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_640.png"},
    3: {"name": "Влад", "login": "UserVlad", "password": "333", "ava": "https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_640.png"},
    4: {"name": "Михаил", "login": "UserMikhail", "password": "444", "ava": "https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_640.png"},
    5: {"name": "Аскербек", "login": "UserAskerbek", "password": "555", "ava": "https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_640.png"}
}

# Хранилище задач (в реальном приложении это была бы БД)
tasks_storage = []
task_counter = 1

# Pydantic модели
class TaskCreate(BaseModel):
    title: str
    description: str
    deadline: date
    performer: int

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[date] = None

class TaskResult(BaseModel):
    result: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    ava: Optional[str] = None

class Task(BaseModel):
    taskId: int
    title: str
    author: int
    performer: int
    deadline: date
    status: str
    description: str
    result: Optional[str] = None

class UserStatistic(BaseModel):
    id: int
    name: str
    ava: str
    completedTasks: int
    inWorkTasks: int
    failedTasks: int

class MyStatistic(BaseModel):
    completedTasks: int
    inWorkTasks: int
    failedTasks: int

class UserProfile(BaseModel):
    name: str
    ava: str

# Функция аутентификации
def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    for user_id, user_data in USERS.items():
        if (user_data["login"] == credentials.username and 
            secrets.compare_digest(user_data["password"], credentials.password)):
            return user_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Basic"},
    )

# Функции для подсчета статистики
def get_user_stats(user_id: int):
    today = date.today()
    completed = 0
    in_work = 0
    failed = 0
    
    for task in tasks_storage:
        if task["performer"] == user_id:
            if task["status"] == "completed":
                completed += 1
            elif task["deadline"] < today:
                failed += 1
            else:
                in_work += 1
    
    return {"completedTasks": completed, "inWorkTasks": in_work, "failedTasks": failed}

# API эндпоинты

@app.get("/task-api/globalStatistic", response_model=List[UserStatistic])
async def get_global_statistic():
    """Получить глобальную статистику по всем пользователям"""
    result = []
    for user_id, user_data in USERS.items():
        stats = get_user_stats(user_id)
        result.append(UserStatistic(
            id=user_id,
            name=user_data["name"],
            ava=user_data["ava"],
            completedTasks=stats["completedTasks"],
            inWorkTasks=stats["inWorkTasks"],
            failedTasks=stats["failedTasks"]
        ))
    return result

@app.get("/task-api/myProfile", response_model=UserProfile)
async def get_my_profile(current_user: int = Depends(get_current_user)):
    """Получить профиль текущего пользователя"""
    user_data = USERS[current_user]
    return UserProfile(name=user_data["name"], ava=user_data["ava"])

@app.put("/task-api/updateUser", response_model=UserProfile)
async def update_user(
    user_update: UserUpdate, 
    current_user: int = Depends(get_current_user)
):
    """Обновить информацию о текущем пользователе"""
    user_data = USERS[current_user]
    
    # Обновляем только переданные поля
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field in user_data:
            user_data[field] = value
    
    return UserProfile(name=user_data["name"], ava=user_data["ava"])

@app.get("/task-api/myStatistic", response_model=MyStatistic)
async def get_my_statistic(current_user: int = Depends(get_current_user)):
    """Получить статистику текущего пользователя"""
    stats = get_user_stats(current_user)
    return MyStatistic(**stats)

@app.post("/task-api/createTask", response_model=Task)
async def create_task(task_data: TaskCreate, current_user: int = Depends(get_current_user)):
    """Создать новую задачу"""
    global task_counter
    
    # Проверяем, существует ли исполнитель
    if task_data.performer not in USERS:
        raise HTTPException(status_code=400, detail="Исполнитель не найден")
    
    new_task = {
        "taskId": task_counter,
        "title": task_data.title,
        "author": current_user,
        "performer": task_data.performer,
        "deadline": task_data.deadline,
        "status": "in work",
        "description": task_data.description,
        "result": None
    }
    
    tasks_storage.append(new_task)
    task_counter += 1
    
    return Task(**new_task)

@app.get("/task-api/delegatedTasks", response_model=List[Task])
async def get_delegated_tasks(
    current_user: int = Depends(get_current_user),
    start: int = Query(0, ge=0, description="Начальный индекс для пагинации"),
    limit: int = Query(10, ge=1, le=100, description="Количество задач для возврата")
):
    """Получить задачи, которые я назначил другим"""
    user_tasks = [task for task in tasks_storage if task["author"] == current_user]
    
    # Применяем пагинацию
    paginated_tasks = user_tasks[start:start + limit]
    
    return [Task(**task) for task in paginated_tasks]

@app.delete("/task-api/delegatedTasks/{taskId}")
async def delete_delegated_task(taskId: int, current_user: int = Depends(get_current_user)):
    """Удалить задачу (только автор может удалить)"""
    task_index = None
    for i, task in enumerate(tasks_storage):
        if task["taskId"] == taskId:
            if task["author"] != current_user:
                raise HTTPException(status_code=403, detail="Вы не можете удалить эту задачу")
            task_index = i
            break
    
    if task_index is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    del tasks_storage[task_index]
    return {"message": "Задача успешно удалена"}

@app.put("/task-api/delegatedTasks/{taskId}", response_model=Task)
async def update_delegated_task(
    taskId: int, 
    task_update: TaskUpdate, 
    current_user: int = Depends(get_current_user)
):
    """Обновить задачу (только автор может обновить)"""
    task = None
    for t in tasks_storage:
        if t["taskId"] == taskId:
            if t["author"] != current_user:
                raise HTTPException(status_code=403, detail="Вы не можете обновить эту задачу")
            task = t
            break
    
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Обновляем только переданные поля
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field in task:
            task[field] = value
    
    return Task(**task)

@app.get("/task-api/myTasks", response_model=List[Task])
async def get_my_tasks(
    current_user: int = Depends(get_current_user),
    start: int = Query(0, ge=0, description="Начальный индекс для пагинации"),
    limit: int = Query(10, ge=1, le=100, description="Количество задач для возврата")
):
    """Получить задачи, которые мне назначили"""
    user_tasks = [task for task in tasks_storage if task["performer"] == current_user]
    
    # Применяем пагинацию
    paginated_tasks = user_tasks[start:start + limit]
    
    return [Task(**task) for task in paginated_tasks]

@app.put("/task-api/myTasks/{taskId}", response_model=Task)
async def complete_my_task(
    taskId: int, 
    task_result: TaskResult, 
    current_user: int = Depends(get_current_user)
):
    """Завершить задачу (добавить результат и изменить статус)"""
    task = None
    for t in tasks_storage:
        if t["taskId"] == taskId:
            if t["performer"] != current_user:
                raise HTTPException(status_code=403, detail="Вы не можете обновить эту задачу")
            task = t
            break
    
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task["result"] = task_result.result
    task["status"] = "completed"
    
    return Task(**task)

@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"message": "Task Management API", "version": "1.0.0"}