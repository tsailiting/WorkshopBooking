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

### 1. docker compose 啟動
```bash
docker compose up -d --build
```

啟動後可直接使用：
- 前端: http://localhost:5173
- 後端: http://localhost:5000
- PostgreSQL: localhost:5432

#### 1. 啟用postgreSQL

資料表 schema 如下：

```mermaid
erDiagram
	WORKSHOP_SESSIONS {
		int id PK
		string title
		datetime start_time
		int duration_minutes
		int capacity
		decimal price
		string created_by
		datetime created_at
		datetime updated_at
	}

	RESERVATIONS {
		int id PK
		int session_id FK
		string student_name
		string user_id
		string status
		datetime created_at
		datetime cancelled_at
	}

	WORKSHOP_SESSIONS ||--o{ RESERVATIONS : has
```

欄位與約束重點：
- `reservations.session_id` 對應 `workshop_sessions.id`。
- `reservations` 上有 `user_id + session_id` 的唯一約束，同一個使用者不能重複預約同一堂課。
- `reservations.status` 目前使用 `confirmed`、`waitlist`、`cancelled` 三種狀態。

#### 2. 使用 Poetry 安裝 Python 依賴
```bash
cd backend
poetry install
```

#### 3. 啟動 Flask API
```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workshop
poetry run python app.py
```

#### 4. 啟動 Vue 前端
```bash
cd frontend
npm install
npm run dev
```

## 測試

### 自動化測試
後端測試使用 `pytest`，前端測試使用 `Vitest`。

後端測試：
```bash
cd backend
PYTHONPATH=. poetry run pytest -q tests/test_business_rules.py
```

前端測試：
```bash
cd frontend
npm run test
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

### 手動 E2E 測試案例
1. 開啟 `http://localhost:5173/admin`，建立一個新的課程，確認課程會出現在列表中，且建立者顯示為 `admin`。
2. 切換到 `http://localhost:5173/user`，建立一個新的 UUID，確認頁面會切換到新使用者，且 UUID 會保留在下拉選單中。
3. 使用同一個 UUID 預約一門課，確認成功後不再顯示「加入課程 / 候補」按鈕。
4. 對已滿額的課程以不同 UUID 進行預約，確認後者會進入候補名單。
5. 對一筆已確認的預約，在課程開始前超過 24 小時時執行取消，確認按鈕會顯示且取消後狀態更新。
6. 取消一筆已確認的預約後，確認候補名單中的第一位會自動遞補成已確認。
7. 開啟瀏覽器後檢查所有時間顯示都符合瀏覽器本地時區，而不是固定 UTC。