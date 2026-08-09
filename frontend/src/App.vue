<template>
  <div class="app">
    <h1>工作坊預約系統</h1>

    <section class="panel">
      <h2>建立場次</h2>
      <form @submit.prevent="createSession">
        <input v-model="form.title" placeholder="標題" required />
        <input v-model="form.start_time" type="datetime-local" required />
        <input v-model="form.duration_minutes" type="number" min="30" placeholder="時長(分鐘)" required />
        <input v-model="form.capacity" type="number" min="1" placeholder="人數上限" required />
        <input v-model="form.price" type="number" min="0" step="0.01" placeholder="價格" required />
        <button type="submit">建立</button>
      </form>
    </section>

    <section class="panel">
      <h2>即將開課的場次</h2>
      <div v-for="session in sessions" :key="session.id" class="card">
        <h3>{{ session.title }}</h3>
        <p>開始時間: {{ session.start_time }}</p>
        <p>時長: {{ session.duration_minutes }} 分鐘</p>
        <p>人數上限: {{ session.capacity }}</p>
        <p>價格: {{ session.price }}</p>
        <p>已預約: {{ session.confirmed_count }}，候補: {{ session.waitlist_count }}</p>
        <div class="actions">
          <input v-model="studentNames[session.id]" placeholder="您的姓名" />
          <button @click="reserve(session.id)">預約 / 候補</button>
          <button @click="cancel(session.id)">取消</button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const sessions = ref([])
const form = ref({ title: '', start_time: '', duration_minutes: 60, capacity: 10, price: 1000 })
const studentNames = ref({})

const api = 'http://127.0.0.1:5000'

async function loadSessions() {
  const res = await fetch(`${api}/sessions`)
  sessions.value = await res.json()
}

async function createSession() {
  const payload = {
    ...form.value,
    start_time: new Date(form.value.start_time).toISOString(),
  }
  const res = await fetch(`${api}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (res.ok) {
    form.value = { title: '', start_time: '', duration_minutes: 60, capacity: 10, price: 1000 }
    await loadSessions()
  }
}

async function reserve(sessionId) {
  const studentName = (studentNames.value[sessionId] || '').trim()
  if (!studentName) return
  const res = await fetch(`${api}/sessions/${sessionId}/reservations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_name: studentName }),
  })
  const result = await res.json()
  alert(result.status === 'confirmed' ? '已確認預約' : '已加入候補')
  await loadSessions()
}

async function cancel(sessionId) {
  const studentName = (studentNames.value[sessionId] || '').trim()
  if (!studentName) return
  const reservations = await (await fetch(`${api}/reservations`)).json()
  const target = reservations.find(r => r.session_id === sessionId && r.student_name === studentName)
  if (!target) {
    alert('找不到你的預約')
    return
  }
  const res = await fetch(`${api}/reservations/${target.id}`, { method: 'DELETE' })
  const result = await res.json()
  if (res.ok) {
    alert('取消成功')
  } else {
    alert(result.error || '取消失敗')
  }
  await loadSessions()
}

onMounted(loadSessions)
</script>

<style scoped>
body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f7fb; }
.app { max-width: 900px; margin: 0 auto; padding: 24px; }
.panel { background: white; padding: 16px; border-radius: 12px; margin-bottom: 16px; }
.card { border: 1px solid #ddd; padding: 12px; border-radius: 8px; margin-top: 10px; }
input { margin-right: 8px; margin-bottom: 8px; padding: 8px; }
button { padding: 8px 12px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
