import { describe, expect, it } from 'vitest'
import { canCancelReservation, findActiveReservation } from './reservation-ui'

describe('reservation-ui helpers', () => {
  it('finds only active reservations for a session', () => {
    const reservation = findActiveReservation([
      { id: 1, session_id: 3, status: 'cancelled' },
      { id: 2, session_id: 3, status: 'waitlist' },
    ], 3)

    expect(reservation.id).toBe(2)
  })

  it('allows waitlist reservations to be cancelled before session start', () => {
    const now = new Date('2030-08-10T10:00:00Z')
    const reservation = { id: 1, session_id: 2, status: 'waitlist' }
    const session = { id: 2, start_time: '2030-08-12T10:00:00Z' }

    expect(canCancelReservation(reservation, session, now)).toBe(true)
  })

  it('hides cancel action for cancelled reservations', () => {
    const now = new Date('2030-08-10T10:00:00Z')
    const reservation = { id: 1, session_id: 2, status: 'cancelled' }
    const session = { id: 2, start_time: '2030-08-12T10:00:00Z' }

    expect(canCancelReservation(reservation, session, now)).toBe(false)
  })
})