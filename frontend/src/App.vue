<template>
  <div class="app">
    <h1>工作坊預約系統</h1>
    <p>這裡提供兩個入口：管理員建立課程，使用者加入既有課程。</p>

    <nav class="nav">
      <button :class="{ active: route === '/admin' }" @click="navigate('/admin')">管理員 /admin</button>
      <button :class="{ active: route === '/user' }" @click="navigate('/user')">使用者 /user</button>
    </nav>

    <section v-if="route === '/admin'" class="panel">
      <h2>管理員：建立課程</h2>
      <p class="hint">課程建立者固定為 admin。</p>
      <form @submit.prevent="createSession">
        <input v-model="form.title" placeholder="課程標題" required />
        <input v-model="form.start_time" type="datetime-local" required />
        <input v-model="form.duration_minutes" type="number" min="30" placeholder="時長(分鐘)" required />
        <input v-model="form.capacity" type="number" min="1" placeholder="人數上限" required />
        <input v-model="form.price" type="number" min="0" step="0.01" placeholder="價格" required />
        <button type="submit">建立課程</button>
      </form>
    </section>

    <section v-if="route === '/user'" class="panel">
      <h2>使用者 UUID</h2>
      <div class="user-tools">
        <select v-model="currentUserId" data-testid="user-switcher" @change="switchUserId">
          <option v-for="userId in knownUserIds" :key="userId" :value="userId">{{ userId }}</option>
        </select>
        <button data-testid="create-user" @click="createUser">建立新使用者</button>
      </div>
      <p class="hint">所有預約都以目前選取的 UUID 識別，且會透過 X-User-Id 標頭送到後端。</p>
    </section>

    <section class="panel">
      <h2>課程列表</h2>
      <div v-for="session in sessions" :key="session.id" class="card">
        <h3>{{ session.title }}</h3>
        <p>開始時間: {{ session.start_time }}</p>
        <p>時長: {{ session.duration_minutes }} 分鐘</p>
        <p>人數上限: {{ session.capacity }}</p>
        <p>價格: {{ session.price }}</p>
        <p>已預約: {{ session.confirmed_count }}，候補: {{ session.waitlist_count }}</p>
        <p v-if="session.created_by">建立者: {{ session.created_by }}</p>

        <div v-if="route === '/user' && canReserveSession(session.id)" class="actions">
          <button :data-testid="`reserve-${session.id}`" @click="reserve(session.id)">加入課程 / 候補</button>
        </div>
        <p v-else-if="route === '/user'" class="hint">{{ reservationStatusText(session.id) }}</p>
      </div>
    </section>

    <section v-if="route === '/user'" class="panel">
      <h2>我的預約</h2>
      <div v-if="userReservations.length === 0" class="empty">目前沒有任何預約。</div>
      <ul class="reservation-list">
        <li v-for="reservation in userReservations" :key="reservation.id" class="reservation-item">
          <div>
            <strong>{{ reservationSessionTitle(reservation) }}</strong>
            <p>課程 #{{ reservation.session_id }}，狀態: {{ reservation.status }}</p>
          </div>
          <button
            v-if="canShowCancelButton(reservation)"
            :data-testid="`cancel-${reservation.id}`"
            @click="cancelReservation(reservation.id)"
          >
            取消我的預約
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { canCancelReservation, findActiveReservation } from './reservation-ui'

const sessions = ref([])
const userReservations = ref([])
const form = ref({ title: '', start_time: '', duration_minutes: 60, capacity: 10, price: 1000 })
const knownUserIds = ref(loadStoredUserIds())
const currentUserId = ref(loadCurrentUserId(knownUserIds.value))
const route = ref(getRoute())
const sessionsById = computed(() => Object.fromEntries(sessions.value.map((session) => [session.id, session])))

const api = 'http://127.0.0.1:5000'

function fallbackUuid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return '00000000-0000-0000-0000-000000000000'
}

function loadStoredUserIds() {
  const saved = localStorage.getItem('workshop-user-ids')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed
      }
    } catch {
      // Ignore invalid local storage payloads.
    }
  }

  const legacyUserId = localStorage.getItem('workshop-user-id')
  return [legacyUserId || fallbackUuid()]
}

function loadCurrentUserId(userIds) {
  const saved = localStorage.getItem('workshop-user-id')
  if (saved && userIds.includes(saved)) {
    return saved
  }
  return userIds[0]
}

function getRoute() {
  const path = window.location.pathname || '/'
  return path.startsWith('/user') ? '/user' : '/admin'
}

function navigate(target) {
  const normalized = target === '/user' ? '/user' : '/admin'
  history.pushState({}, '', normalized)
  route.value = normalized
}

function buildHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-User-Id': currentUserId.value,
  }
}

function persistUserIds() {
  localStorage.setItem('workshop-user-ids', JSON.stringify(knownUserIds.value))
  localStorage.setItem('workshop-user-id', currentUserId.value)
}

async function switchUserId() {
  persistUserIds()
  await loadReservations()
}

async function createUser() {
  const response = await fetch(`${api}/users/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  const result = await response.json()
  const userId = result.user_id
  if (!userId) {
    alert('建立新使用者失敗')
    return
  }
  if (!knownUserIds.value.includes(userId)) {
    knownUserIds.value = [...knownUserIds.value, userId]
  }
  currentUserId.value = userId
  persistUserIds()
  await loadReservations()
}

async function loadSessions() {
  const res = await fetch(`${api}/sessions`)
  sessions.value = await res.json()
}

async function loadReservations() {
  const res = await fetch(`${api}/reservations`, { headers: buildHeaders() })
  if (res.ok) {
    userReservations.value = await res.json()
  }
}

async function createSession() {
  const payload = {
    ...form.value,
    start_time: new Date(form.value.start_time).toISOString(),
  }
  const res = await fetch(`${api}/sessions`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  })
  if (res.ok) {
    form.value = { title: '', start_time: '', duration_minutes: 60, capacity: 10, price: 1000 }
    await loadSessions()
  }
}

async function reserve(sessionId) {
  const res = await fetch(`${api}/sessions/${sessionId}/reservations`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ user_id: currentUserId.value }),
  })
  const result = await res.json()
  alert(result.status === 'confirmed' ? '已確認預約' : '已加入候補')
  await loadSessions()
  await loadReservations()
}

async function cancelReservation(reservationId) {
  const target = userReservations.value.find((reservation) => reservation.id === reservationId)
  if (!target) {
    alert('找不到你的預約')
    return
  }
  const res = await fetch(`${api}/reservations/${target.id}`, { method: 'DELETE', headers: buildHeaders() })
  const result = await res.json()
  if (res.ok) {
    alert('取消成功')
  } else {
    alert(result.error || '取消失敗')
  }
  await loadSessions()
  await loadReservations()
}

function reservationForSession(sessionId) {
  return findActiveReservation(userReservations.value, sessionId)
}

function canReserveSession(sessionId) {
  return !reservationForSession(sessionId)
}

function reservationStatusText(sessionId) {
  const reservation = reservationForSession(sessionId)
  if (!reservation) {
    return ''
  }
  return reservation.status === 'confirmed' ? '你已預約成功' : '你已在候補名單中'
}

function reservationSessionTitle(reservation) {
  const session = sessionsById.value[reservation.session_id]
  return session ? session.title : `課程 #${reservation.session_id}`
}

function canShowCancelButton(reservation) {
  const session = sessionsById.value[reservation.session_id]
  return canCancelReservation(reservation, session)
}

function handlePopState() {
  route.value = getRoute()
}

onMounted(async () => {
  window.addEventListener('popstate', handlePopState)
  await loadSessions()
  await loadReservations()
})

onBeforeUnmount(() => {
  window.removeEventListener('popstate', handlePopState)
})
</script>

<style scoped>
body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f7fb; }
.app { max-width: 900px; margin: 0 auto; padding: 24px; }
.nav { display: flex; gap: 8px; margin-bottom: 16px; }
button { padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: white; cursor: pointer; }
button.active { background: #2563eb; color: white; border-color: #2563eb; }
.panel { background: white; padding: 16px; border-radius: 12px; margin-bottom: 16px; }
.card { border: 1px solid #ddd; padding: 12px; border-radius: 8px; margin-top: 10px; }
input { margin-right: 8px; margin-bottom: 8px; padding: 8px; }
.user-tools { display: flex; gap: 8px; flex-wrap: wrap; }
.user-tools select { min-width: 320px; padding: 8px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.reservation-list { list-style: none; padding: 0; margin: 0; }
.reservation-item { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #eee; }
.reservation-item p { margin: 4px 0 0; }
.hint { color: #666; font-size: 0.9rem; }
.empty { color: #777; }
</style>
