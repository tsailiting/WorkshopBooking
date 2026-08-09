const ACTIVE_STATUSES = new Set(['confirmed', 'waitlist'])
const CANCELLATION_WINDOW_MS = 24 * 60 * 60 * 1000

export function findActiveReservation(reservations, sessionId) {
  return reservations.find(
    (reservation) => reservation.session_id === sessionId && ACTIVE_STATUSES.has(reservation.status),
  )
}

export function canCancelReservation(reservation, session, now = new Date()) {
  if (!reservation || !session) {
    return false
  }

  const startTime = new Date(session.start_time)
  if (Number.isNaN(startTime.getTime()) || startTime <= now) {
    return false
  }

  if (reservation.status === 'waitlist') {
    return true
  }

  if (reservation.status !== 'confirmed') {
    return false
  }

  return startTime.getTime() - now.getTime() > CANCELLATION_WINDOW_MS
}