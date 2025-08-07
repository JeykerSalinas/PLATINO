import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNotificationStore = defineStore('notification', () => {
  const show = ref(false)
  const message = ref('')
  const color = ref<'success' | 'info' | 'error' | 'warning'>('error')

  function notify(msg: string, col: 'success' | 'info' | 'error' | 'warning' = 'error') {
    message.value = msg
    color.value = col
    show.value = true
  }

  return { show, message, color, notify }
})
