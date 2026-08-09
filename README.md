# Workshop Booking System

這是一個以 Flask + PostgreSQL + Vue 建立的簡化版工作坊預約系統。

## 功能
- 講師可建立場次
- 學員可瀏覽即將開課場次
- 預約座位，額滿時加入候補
- 取消預約，超過 24 小時可取消
- 候補名單自動遞補
- 已結束場次不可再預約或取消

## 目錄結構
- backend/: Flask API 與資料模型
- frontend/: Vue 3 前端介面
- docker-compose.yml: PostgreSQL 服務

## 啟動方式

### 1. 啟動 PostgreSQL
```bash
docker compose up -d
```

### 2. 使用 Poetry 安裝 Python 依賴
```bash
cd backend
poetry install
```

### 3. 啟動 Flask API
```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workshop
poetry run python app.py
```

### 4. 啟動 Vue 前端
```bash
cd frontend
npm install
npm run dev
```

### 5. 驗證
```bash
cd backend
PYTHONPATH=. poetry run pytest -q tests/test_business_rules.py
```

### 6. 進入 Poetry 虛擬環境（可選）
```bash
cd backend
poetry shell
```

> 如果你沒有使用 Poetry，也可以繼續使用 requirements.txt；但在這個專案中，Poetry 已是主要的依賴管理方式。
