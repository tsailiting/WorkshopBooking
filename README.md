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
- docker-compose.yml: 前端、後端與 PostgreSQL 服務

## 啟動方式

### 1. 啟動 PostgreSQL
```bash
docker compose up -d --build
```

啟動後可直接使用：
- 前端: http://localhost:5173
- 後端: http://localhost:5000
- PostgreSQL: localhost:5432

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

後端測試目前涵蓋：
- 人數上限不會被破壞
- 並行預約情境
- 取消預約的時間限制
- 候補名單自動遞補

前端測試目前涵蓋：
- `/admin` 不顯示使用者 UUID 工具
- `/user` 可建立與切換 UUID
- 已預約成功的課程不顯示加入課程 / 候補
- 已取消的預約不顯示取消按鈕

### 6. 進入 Poetry 虛擬環境（可選）
```bash
cd backend
poetry shell
```

### 7. 前端測試
```bash
cd frontend
npm run test
```