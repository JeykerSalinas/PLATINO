import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ChatMessage {
  from: 'user' | 'ai'
  text: string
}

export const useOllamaStore = defineStore('ollama', () => {
  const messages = ref<ChatMessage[]>([])
  const connected = ref(false)
  let socket: WebSocket | null = null

  function connect () {
    if (socket || connected.value) return

    socket = new WebSocket('ws://localhost:11434/api/chat')

    socket.addEventListener('open', () => {
      connected.value = true
    })

    socket.addEventListener('message', (e) => {
      messages.value.push({ from: 'ai', text: e.data })
    })

    socket.addEventListener('close', () => {
      connected.value = false
      socket = null
    })
  }

  function disconnect () {
    if (socket) {
      socket.close()
    }
  }

  function sendMessage (text: string) {
    if (!socket || socket.readyState !== WebSocket.OPEN) connect()
    socket?.send(text)
    messages.value.push({ from: 'user', text })
  }

  return { messages, connected, connect, disconnect, sendMessage }
})
