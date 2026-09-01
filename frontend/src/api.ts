import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('fs_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem('fs_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export async function login(username: string, password: string): Promise<string> {
  const form = new URLSearchParams()
  form.set('username', username)
  form.set('password', password)
  const { data } = await api.post('/auth/login', form)
  return data.access_token
}
