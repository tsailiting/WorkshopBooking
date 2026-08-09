import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import App from './App.vue'

function mockResponse(data, ok = true) {
  return {
    ok,
    json: async () => data,
  }
}

describe('App user reservations UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
    window.localStorage.setItem('workshop-user-id', '123e4567-e89b-12d3-a456-426614174000')
    window.localStorage.setItem('workshop-user-ids', JSON.stringify(['123e4567-e89b-12d3-a456-426614174000']))
    window.history.replaceState({}, '', '/user')
    window.alert = vi.fn()
  })

  it('does not show user UUID tools on /admin', async () => {
    window.history.replaceState({}, '', '/admin')
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/api/sessions') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([]))
      }

      if (url.endsWith('/api/reservations') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([]))
      }

      return Promise.resolve(mockResponse({}))
    }))

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('[data-testid="user-switcher"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="create-user"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('課程建立者固定為 admin')
  })

  it('shows cancel in 我的預約 and hides reserve for already reserved sessions', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/api/sessions') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 1,
            title: '已報名課程',
            start_time: '2030-08-12T10:00:00Z',
            duration_minutes: 60,
            capacity: 10,
            price: 1000,
            confirmed_count: 1,
            waitlist_count: 0,
            created_by: 'admin',
          },
          {
            id: 2,
            title: '可加入課程',
            start_time: '2030-08-13T10:00:00Z',
            duration_minutes: 60,
            capacity: 10,
            price: 1000,
            confirmed_count: 0,
            waitlist_count: 0,
            created_by: 'admin',
          },
        ]))
      }

      if (url.endsWith('/api/reservations') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 10,
            session_id: 1,
            status: 'confirmed',
            user_id: '123e4567-e89b-12d3-a456-426614174000',
          },
        ]))
      }

      return Promise.resolve(mockResponse({}))
    }))

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('[data-testid="reserve-1"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="reserve-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cancel-10"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('你已預約成功')
  })

  it('renders session time in browser local time format', async () => {
    const localFormatter = new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
    const localTime = localFormatter.format(new Date('2030-08-12T10:00:00Z'))

    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/api/sessions') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 1,
            title: '本地時間課程',
            start_time: '2030-08-12T10:00:00Z',
            duration_minutes: 60,
            capacity: 10,
            price: 1000,
            confirmed_count: 0,
            waitlist_count: 0,
            created_by: 'admin',
          },
        ]))
      }

      if (url.endsWith('/api/reservations') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([]))
      }

      return Promise.resolve(mockResponse({}))
    }))

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain(`開始時間: ${localTime}`)
  })

  it('hides cancel button for confirmed reservations within 24 hours', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/api/sessions') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 1,
            title: '即將開始課程',
            start_time: '2030-08-12T10:00:00Z',
            duration_minutes: 60,
            capacity: 10,
            price: 1000,
            confirmed_count: 1,
            waitlist_count: 0,
            created_by: 'admin',
          },
        ]))
      }

      if (url.endsWith('/api/reservations') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 11,
            session_id: 1,
            status: 'confirmed',
            user_id: '123e4567-e89b-12d3-a456-426614174000',
          },
        ]))
      }

      return Promise.resolve(mockResponse({}))
    }))

    vi.useFakeTimers()
    vi.setSystemTime(new Date('2030-08-11T12:00:00Z'))

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('[data-testid="cancel-11"]').exists()).toBe(false)

    vi.useRealTimers()
  })

  it('shows cancel button for waitlisted reservations', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/api/sessions') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 3,
            title: '熱門課程',
            start_time: '2030-08-15T10:00:00Z',
            duration_minutes: 60,
            capacity: 1,
            price: 1200,
            confirmed_count: 1,
            waitlist_count: 1,
            created_by: 'admin',
          },
        ]))
      }

      if (url.endsWith('/api/reservations') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 12,
            session_id: 3,
            status: 'waitlist',
            user_id: '123e4567-e89b-12d3-a456-426614174000',
          },
        ]))
      }

      return Promise.resolve(mockResponse({}))
    }))

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('[data-testid="reserve-3"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="cancel-12"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('你已在候補名單中')
  })

  it('hides cancel button for cancelled reservations', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/api/sessions') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 4,
            title: '已取消課程預約',
            start_time: '2030-08-15T10:00:00Z',
            duration_minutes: 60,
            capacity: 10,
            price: 1200,
            confirmed_count: 0,
            waitlist_count: 0,
            created_by: 'admin',
          },
        ]))
      }

      if (url.endsWith('/api/reservations') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([
          {
            id: 13,
            session_id: 4,
            status: 'cancelled',
            user_id: '123e4567-e89b-12d3-a456-426614174000',
          },
        ]))
      }

      return Promise.resolve(mockResponse({}))
    }))

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('[data-testid="cancel-13"]').exists()).toBe(false)
  })

  it('creates a new user from the online generator endpoint and switches uuid', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/api/users/generate') && options.method === 'POST') {
        return Promise.resolve(mockResponse({
          user_id: '99999999-9999-4999-8999-999999999999',
        }))
      }

      if (url.endsWith('/api/sessions') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([]))
      }

      if (url.endsWith('/api/reservations') && (!options.method || options.method === 'GET')) {
        return Promise.resolve(mockResponse([]))
      }

      return Promise.resolve(mockResponse({}))
    }))

    const wrapper = mount(App)
    await flushPromises()

    await wrapper.find('[data-testid="create-user"]').trigger('click')
    await flushPromises()

    const select = wrapper.find('[data-testid="user-switcher"]')
    const options = select.findAll('option').map((option) => option.text())

    expect(options).toContain('99999999-9999-4999-8999-999999999999')
    expect(select.element.value).toBe('99999999-9999-4999-8999-999999999999')
    expect(JSON.parse(window.localStorage.getItem('workshop-user-ids'))).toContain('99999999-9999-4999-8999-999999999999')
    expect(window.localStorage.getItem('workshop-user-id')).toBe('99999999-9999-4999-8999-999999999999')
  })
})